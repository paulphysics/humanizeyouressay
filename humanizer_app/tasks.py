# FILE: humanizer_app/tasks.py
import logging
import json
from celery import shared_task
from flask import current_app
import google.generativeai as genai
import os

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

# Configure Google Generative AI
google_api_key = os.getenv("GOOGLE_API_KEY")
if google_api_key:
    genai.configure(api_key=google_api_key)
else:
    logger.warning("GOOGLE_API_KEY is not set. Gemini models will not be available.")


@shared_task(ignore_result=True)
def process_humanization_task(task_id: int):
    """
    The main Celery task for humanization. It runs on a separate worker process.
    """
    # ... (This function remains unchanged)
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

        db.session.commit()

    except Exception as e:
        logger.error(f"Humanization task {task_id} failed: {e}", exc_info=True)
        db.session.rollback()

        task = Task.query.get(task_id)
        if task:
            task.status = 'humanization_failed'
            task.error_message = "An unexpected error occurred. A full refund has been issued."

            user = task.user
            original_charge = task.amount_charged

            if user and user.wallet and original_charge > 0:
                user.wallet.balance += original_charge

                db.session.add(Transaction(
                    wallet_id=user.wallet.id,
                    amount=original_charge,
                    transaction_type='refund',
                    description=f'Full refund for failed task {task.external_reference}'
                ))
                logger.info(f"Full refund of KSh {original_charge:.2f} processed for user {user.id} for failed task {task.id}.")

            db.session.commit()

    finally:
        db.session.remove()


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
        task.status = 'processing'
        db.session.commit()

        task_data = task.diff_data or {}
        conversation_id = task_data.get('conversation_id')

        if not conversation_id:
            raise ValueError("conversation_id is missing from the task data.")

        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found.")

        message_history = []
        past_messages = ChatMessage.query.filter_by(conversation_id=conversation.id).order_by(ChatMessage.created_at.asc()).all()

        for msg in past_messages:
            if msg.role == 'user':
                try:
                    content_parts = json.loads(msg.content)
                    vision_message_content = []
                    for part in content_parts:
                        if part.get("type") == "input_text" and part.get("text"):
                            vision_message_content.append({
                                "type": "text",
                                "text": part["text"]
                            })
                        elif part.get("type") == "input_image" and part.get("image_url"):
                            vision_message_content.append({
                                "type": "image_url",
                                "image_url": part["image_url"]
                            })

                    if vision_message_content:
                        message_history.append({"role": "user", "content": vision_message_content})

                except (json.JSONDecodeError, TypeError):
                    message_history.append({"role": "user", "content": msg.content})
            elif msg.role == 'assistant':
                message_history.append({"role": "assistant", "content": msg.content})

        model_key = task_data.get('model_key')
        models_config = current_app.config.get('MODELS', {})
        model_info = models_config.get(model_key)
        if not model_info:
            raise Exception(f"Unknown model key: {model_key}")

        system_prompt = {
            "role": "system",
            "content": "You are a helpful assistant. Format all of your responses using Github Flavored Markdown. For all code snippets, you must use markdown code blocks (e.g., ```python ... ```)."
        }
        final_messages = [system_prompt] + message_history

        output_text = ""
        # --- Logic to switch between OpenAI and Gemini ---
        if "gemini" in model_key:
            if not os.getenv("GOOGLE_API_KEY"):
                raise Exception("Google API key is not configured.")
            
            gemini_model = genai.GenerativeModel(model_info['api_id'])
            
            # --- START: CORRECTED Gemini Message Formatting ---
            gemini_messages = []
            for message in final_messages:
                # Gemini uses 'user' and 'model' roles, and doesn't have a 'system' role.
                role = "user" if message["role"] in ["user", "system"] else "model"
                
                content = message["content"]
                parts = []

                if isinstance(content, list):
                    # Handle complex content (e.g., with images)
                    for part in content:
                        if part.get("type") == "text":
                            parts.append(part["text"])
                elif isinstance(content, str):
                    # Handle simple string content
                    parts.append(content)
                
                if parts:
                     gemini_messages.append({'role': role, 'parts': parts})
            # --- END: CORRECTED Gemini Message Formatting ---

            response = gemini_model.generate_content(gemini_messages)
            output_text = response.text

        elif "gpt" in model_key:
            response = openai_client.chat.completions.create(
                model=model_info['api_id'],
                messages=final_messages,
            )
            output_text = response.choices[0].message.content or ""
        else:
            raise Exception(f"Model key '{model_key}' does not specify a known provider (gpt or gemini).")
        # --- END ---

        if len(past_messages) == 1 and past_messages[0].role == 'user':
            try:
                try:
                    user_content_parts = json.loads(past_messages[0].content)
                    user_prompt_for_title = " ".join(part.get("text", "") for part in user_content_parts if part.get("type") == "input_text")
                except (json.JSONDecodeError, TypeError):
                    user_prompt_for_title = past_messages[0].content

                title_prompt = f"Create a short title (4-5 words max) for this chat:\n\nUser: {user_prompt_for_title}\nAssistant: {output_text}"

                title_model = models_config.get('gpt-4o') or model_info

                title_resp = openai_client.chat.completions.create(
                    model=title_model['api_id'],
                    messages=[
                        {"role": "system", "content": "You write concise chat titles. Return the title only, with no quotes."},
                        {"role": "user", "content": title_prompt}
                    ],
                    temperature=0.2,
                    max_tokens=20
                )

                title_text = (title_resp.choices[0].message.content or "").strip()

                if title_text and conversation:
                    conversation.title = title_text.strip('"')
                    db.session.add(conversation)
                    db.session.commit()

            except Exception as te:
                logger.warning(f"Title generation failed for CONV-{conversation.id}, using default. Error: {te}")
                db.session.rollback()

        user = task.user
        price_per_word = model_info['price_per_word']
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

        db.session.add(ChatMessage(conversation_id=conversation.id, role='assistant', content=output_text))

        task.humanized_output = output_text
        task.status = 'humanization_complete'
        dd = dict(task.diff_data or {})
        dd["final_conversation_id"] = conversation_id
        task.diff_data = dd
        db.session.commit()

    except Exception as e:
        logger.error(f"Playground chat task {task_id} failed: {e}", exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
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
