# humanizer_app/tasks.py
"""
This module contains the Celery background task for processing humanization requests.
"""
import logging
from celery import shared_task
from .extensions import db
from .models import Task, User, Transaction
from .humanizer_service.workflows import perform_humanization_task
from .humanizer_service.exceptions import AllModelsFailedError, CustomApiError
from .payment_service import WORDS_PER_UNIT, PRICE_PER_UNIT, ESSAY_PRICE_PER_UNIT

# Set up logging for the Celery worker
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@shared_task(ignore_result=True)
def process_humanization_task(task_id: int):
    """
    The main Celery task for humanization. It runs on a separate worker process.
    """
    task = Task.query.get(task_id)
    if not task:
        logger.error(f"[Task ID: {task_id}] Task not found in background job.")
        return

    try:
        logger.info(f"[Task ID: {task.id}] Processing task: {task.external_reference}")
        
        # Set status to 'humanizing' so the user sees progress
        task.status = 'humanizing'
        db.session.commit()
        
        humanized_output, word_count, updated_diff_data, failed_word_count, total_paragraph_word_count = perform_humanization_task(
            task.input_text,
            diff_data=task.diff_data,
            dialect=task.diff_data.get("english_dialect", "us"),
            mode=task.diff_data.get("humanizer_mode", "standard")
        )

        task.humanized_output = humanized_output
        task.output_word_count = word_count
        task.diff_data = updated_diff_data
        task.status = 'humanization_complete' # Set final status

        # Handle partial refunds for failed words
        if failed_word_count > 0:
            user = task.user
            if user and user.wallet:
                price = ESSAY_PRICE_PER_UNIT if task.diff_data.get("humanizer_mode") == 'essay' else PRICE_PER_UNIT
                refund_amount = round((failed_word_count / WORDS_PER_UNIT) * price, 2)
                
                if refund_amount > 0:
                    user.wallet.balance += refund_amount
                    db.session.add(Transaction(
                        wallet_id=user.wallet.id,
                        amount=refund_amount,
                        transaction_type='refund',
                        description=f'Partial refund for task {task.external_reference}'
                    ))
                    
                    humanized_word_count = total_paragraph_word_count - failed_word_count
                    task.diff_data['refund_info'] = f"{humanized_word_count}/{total_paragraph_word_count} words were humanized. KSh {refund_amount:.2f} has been refunded to your wallet."
                    logger.info(f"Refunded KSh {refund_amount} to user {user.id} for {failed_word_count} failed words.")

        logger.info(f"Task {task.external_reference} completed successfully.")

    except (AllModelsFailedError, CustomApiError) as e:
        logger.error(f"Critical failure for task {task.id}. Issuing full refund. Error: {e.message}", exc_info=True)
        task.status = 'humanization_failed'
        
        user = task.user
        if user and user.wallet:
            refund_amount = task.amount_charged
            user.wallet.balance += refund_amount
            db.session.add(Transaction(
                wallet_id=user.wallet.id,
                amount=refund_amount,
                transaction_type='full_refund',
                description=f'Full refund for failed task {task.external_reference}'
            ))
            task.error_message = "This task failed due to a critical error. A full refund has been issued to your wallet."
            logger.info(f"Issued full refund of KSh {refund_amount} to user {user.id} for failed task.")

    except Exception as e:
        logger.error(f"Background processing for task {task.id} failed with an unexpected error: {e}", exc_info=True)
        task.status = 'humanization_failed'
        task.error_message = "An unexpected error occurred. Our team has been notified."
    
    finally:
        # Commit all changes (status updates, refunds, etc.) at the very end
        db.session.commit()
