# humanizer_app/tasks.py
"""
This module contains the Celery background tasks for processing humanization
requests and playground chats.
"""
import logging
import json
from celery import shared_task
from flask import current_app
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
        db.session.commit()


@shared_task(bind=True)
def process_playground_chat_task(self, task_id: int):
    """
    Celery task to process a playground chat message in the background.
    """
    task = Task.query.get(task_id)
    if not task:
        logger.error(f"[Playground Task ID: {task_id}] Task not found.")
        return

    try:
        logger.info(f"[Playground Task ID: {task.id}] Processing playground task.")
        task.status = 'processing'
        db.session.commit()

        user_input_parts = task.diff_data.get('user_input_parts', [])
        model_key = task.diff_data.get('model_key')
        conversation_id = task.diff_data.get('conversation_id')
        
        user = task.user
        models_config = current_app.config.get('MODELS', {})
        model_info = models_config.get(model_key)

        model_name = model_info.get('label', "AI Assistant")
        system_instructions = (
            "You are a helpful assistant. All code you provide must be enclosed in triple backticks. "
            f"If a user asks for your name, you must respond that you are based on '{model_name}'."
        )

        simple_user_input = " ".join(part.get("text", "") for part in user_input_parts)

        messages = [{"role": "system", "content": system_instructions}]
        
        conversation = None
        if conversation_id:
            conversation = Conversation.query.get(conversation_id)

        # If a conversation was found, load its history
        if conversation:
            past_messages = ChatMessage.query.filter_by(conversation_id=conversation.id).order_by(ChatMessage.timestamp.asc()).all()
            for msg in past_messages:
                if msg.role == 'user':
                    try:
                        content_parts = json.loads(msg.content)
                        simple_content = " ".join(part.get("text", "") for part in content_parts)
                        messages.append({"role": "user", "content": simple_content})
                    except (json.JSONDecodeError, TypeError):
                        messages.append({"role": "user", "content": msg.content})
                else:
                    messages.append({"role": "assistant", "content": msg.content})
        
        # If no conversation exists yet, create one now and save it immediately
        else:
            title = "New Chat"
            try:
                title_prompt = f"Create a short title (4-5 words max) for this chat:\n\nUser: {simple_user_input}"
                title_model = models_config.get('gpt-4o') or model_info
                title_resp = openai_client.chat.completions.create(
                    model=title_model['api_id'],
                    messages=[{"role": "user", "content": title_prompt}],
                )
                title_text = (title_resp.choices[0].message.content or "").strip().strip('"')
                if title_text: title = title_text
            except Exception as te:
                logger.warning(f"Title generation failed: {te}")
            
            conversation = Conversation(user_id=user.id, title=title, model_key=model_key)
            db.session.add(conversation)
            
            # ✅ THE FIX: Commit the new conversation immediately to prevent race conditions
            db.session.commit()

        messages.append({"role": "user", "content": simple_user_input})
        
        response = openai_client.chat.completions.create(
            model=model_info['api_id'],
            messages=messages,
        )
        output_text = response.choices[0].message.content or ""

        # Correct billing logic: Only charge for the new words
        price_per_word = model_info['price_per_word']
        input_word_count = count_words(simple_user_input)
        output_word_count = count_words(output_text)
        total_word_count = input_word_count + output_word_count
        total_cost = total_word_count * price_per_word

        if not user.wallet or user.wallet.balance < total_cost:
            raise Exception("Insufficient funds detected during task execution.")

        user.wallet.balance -= total_cost
        db.session.add(Transaction(
            wallet_id=user.wallet.id, amount=-total_cost,
            transaction_type='playground_fee',
            description=f"CONV-{conversation.id}: {total_word_count} words"
        ))
        db.session.add(ChatMessage(conversation_id=conversation.id, role='user', content=json.dumps(user_input_parts)))
        db.session.add(ChatMessage(conversation_id=conversation.id, role='assistant', content=output_text))

        task.humanized_output = output_text
        task.status = 'humanization_complete'
        task.diff_data['final_conversation_id'] = conversation.id

        db.session.commit()
        return {'status': 'SUCCESS', 'result': output_text, 'conversation_id': conversation.id}

    except Exception as e:
        logger.error(f"Playground task {task.id} failed: {e}", exc_info=True)
        task.status = 'humanization_failed'
        task.error_message = "An error occurred while communicating with the AI model."
        db.session.commit()
        self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
        return {"status": "FAILURE", "error": "An unexpected error occurred. Please try again later."}
