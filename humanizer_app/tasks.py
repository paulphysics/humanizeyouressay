# humanizer_app/tasks.py
import logging
import json
from celery import shared_task
from flask import current_app

# DO NOT import create_app here to avoid circular imports

from .extensions import db
from .models import Task, User, Transaction, Conversation, ChatMessage
from .humanizer_service.workflows import perform_humanization_task
from .humanizer_service.exceptions import AllModelsFailedError, CustomApiError
from .humanizer_service.utils import count_words
from .humanizer_service.api_clients import openai_client
from .payment_service import WORDS_PER_UNIT, PRICE_PER_UNIT, ESSAY_PRICE_PER_UNIT

# Set up logging for the Celery worker
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DO NOT create the app instance here. The worker handles the context.


@shared_task(ignore_result=True)
def process_humanization_task(task_id: int):
    """
    The main Celery task for humanization. It runs on a separate worker process.
    """
    # The app context is automatically handled by the worker setup.
    task = Task.query.get(task_id)
    if not task:
        logger.error(f"[Task ID: {task_id}] Task not found in background job.")
        return

    try:
        # (Your existing, correct humanization logic remains here)
        logger.info(f"[Task ID: {task.id}] Processing task: {task.external_reference}")
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
        task.status = 'humanization_complete'

        # (Your refund logic remains here)
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

        db.session.commit()

    except Exception as e:
        logger.error(f"Humanization task {task_id} failed: {e}", exc_info=True)
        db.session.rollback()
        task = Task.query.get(task_id)
        if task:
            task.status = 'humanization_failed'
            task.error_message = "An unexpected error occurred."
            db.session.commit()
    finally:
        db.session.remove()


@shared_task(bind=True)
def process_playground_chat_task(self, task_id: int):
    """
    Celery task to process a playground chat message in the background.
    """
    # The app context is automatically handled by the worker setup.
    task = Task.query.get(task_id)
    if not task:
        logger.error(f"[Playground Task ID: {task_id}] Task not found.")
        return

    try:
        task.status = 'processing'
        db.session.commit()

        task_data = task.diff_data or {}
        conversation_id = task_data.get('conversation_id')
        
        if not conversation_id:
            raise ValueError("conversation_id is missing from the task data.")

        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found.")

        # --- Simplified Logic: The conversation and user message already exist ---
        message_history = []
        past_messages = ChatMessage.query.filter_by(conversation_id=conversation.id).order_by(ChatMessage.created_at.asc()).all()
        
        for msg in past_messages:
            # Reconstruct simple text content for the AI model
            if msg.role == 'user':
                try:
                    # User message content is now stored as full JSON from routes.py
                    content_parts = json.loads(msg.content)
                    simple_content = " ".join(part.get("text", "") for part in content_parts if part.get("type") == "input_text")
                    message_history.append({"role": "user", "content": simple_content})
                except (json.JSONDecodeError, TypeError):
                     # Fallback for older, plain text messages if any exist
                    message_history.append({"role": "user", "content": msg.content})
            elif msg.role == 'assistant':
                message_history.append({"role": "assistant", "content": msg.content})

        # --- Call OpenAI ---
        model_key = task_data.get('model_key')
        models_config = current_app.config.get('MODELS', {})
        model_info = models_config.get(model_key)
        if not model_info:
            raise Exception(f"Unknown model key: {model_key}")

        response = openai_client.chat.completions.create(
            model=model_info['api_id'],
            messages=message_history,
        )
        output_text = response.choices[0].message.content or ""

        # --- Billing Logic ---
        user = task.user
        price_per_word = model_info['price_per_word']
        # We only bill for the AI's output words now
        output_word_count = count_words(output_text)
        total_cost = output_word_count * price_per_word

        if user.wallet.balance < total_cost:
            raise Exception("Insufficient funds detected during task execution.")

        user.wallet.balance -= total_cost
        db.session.add(Transaction(
            wallet_id=user.wallet.id,
            amount=-total_cost,
            transaction_type='playground_fee',
            description=f"CONV-{conversation.id}: {output_word_count} words"
        ))

        # --- Save ONLY the assistant's response ---
        db.session.add(ChatMessage(conversation_id=conversation.id, role='assistant', content=output_text))

        # --- Finalize task ---
        task.humanized_output = output_text
        task.status = 'humanization_complete'
        dd = dict(task.diff_data or {})
        dd["final_conversation_id"] = conversation_id
        task.diff_data = dd
        db.session.commit()

    except Exception as e:
        logger.error(f"Playground chat task {task_id} failed: {e}", exc_info=True)
        # IMPORTANT: reset the failed transaction before updating the Task
        try:
            db.session.rollback()
        except Exception:
            pass
        # Re-fetch a clean instance before updating
        task = Task.query.get(task_id)
        if task:
            task.status = 'humanization_failed'
            task.error_message = "An error occurred while communicating with the AI model."
            try:
                db.session.commit()
            except Exception:
                logger.exception("Failed to commit failure status for task %s", task_id)
    finally:
        db.session.remove()
