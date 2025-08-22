import logging
from celery import shared_task
from flask import current_app
from .extensions import db
from .models import Task, User, Conversation, ChatMessage
from .humanizer_service.humanizer import Humanizer
from .humanizer_service.utils import count_words
from .humanizer_service.exceptions import AllModelsFailedError, ContentGenerationError
from .humanizer_service.api_clients import GroqClient, OpenAIClient, AnthropicClient
from .humanizer_service.billing_logic import calculate_and_charge_playground_fee

logger = logging.getLogger(__name__)

# --- MODIFICATION START: Updated function signature ---
@shared_task(ignore_result=True)
def process_humanization_task(task_id: int):
    """
    Celery task to process a humanization request.
    This task is now simplified to only need the task_id, as all
    necessary info is retrieved from the database.
    """
    with current_app.app_context():
        task = db.session.get(Task, task_id)
        if not task:
            logger.error(f"Task with ID {task_id} not found.")
            return

        try:
            task.status = 'humanizing'
            db.session.commit()

            diff_data = task.diff_data or {}
            
            # Use the data stored in the task object
            humanized_output, word_count, updated_diff_data, failed_word_count, total_paragraph_word_count = perform_humanization_task(
                task.input_text,
                diff_data=diff_data,
                dialect=diff_data.get("english_dialect", "us"),
                mode=diff_data.get("humanizer_mode", "standard")
            )

            task.humanized_output = humanized_output
            task.output_word_count = word_count
            task.status = 'humanization_complete'
            task.diff_data = updated_diff_data
            
            # Refund logic for failed paragraphs
            if failed_word_count > 0 and task.user_id:
                user = db.session.get(User, task.user_id)
                if user and user.wallet:
                    total_cost_per_word = task.amount_charged / total_paragraph_word_count if total_paragraph_word_count > 0 else 0
                    refund_amount = round(failed_word_count * total_cost_per_word, 2)
                    if refund_amount > 0:
                        user.wallet.balance += refund_amount
                        # Update refund info in diff_data
                        refund_info = f"Partial refund of KSh {refund_amount:.2f} issued for unhumanized content."
                        task.diff_data['refund_info'] = refund_info
                        logger.info(f"Refunded {refund_amount} to user {user.id} for task {task.id}")

        except (AllModelsFailedError, ContentGenerationError) as e:
            task.status = 'humanization_failed'
            task.error_message = str(e)
            logger.error(f"Humanization failed for task {task.id}: {e}", exc_info=True)
            # Full refund logic for complete failure
            if task.user_id:
                user = db.session.get(User, task.user_id)
                if user and user.wallet and task.amount_charged:
                    user.wallet.balance += task.amount_charged
                    task.diff_data['refund_info'] = f"Full refund of KSh {task.amount_charged:.2f} issued due to processing failure."
                    logger.info(f"Full refund of {task.amount_charged} issued to user {user.id} for failed task {task.id}")

        except Exception as e:
            task.status = 'humanization_failed'
            task.error_message = "An unexpected server error occurred."
            logger.error(f"Unexpected error in process_humanization_task for task {task.id}: {e}", exc_info=True)
            if task.user_id and task.amount_charged:
                user = db.session.get(User, task.user_id)
                if user and user.wallet:
                    user.wallet.balance += task.amount_charged
                    task.diff_data['refund_info'] = f"Full refund of KSh {task.amount_charged:.2f} issued due to a server error."
                    logger.info(f"Full refund of {task.amount_charged} issued to user {user.id} for failed task {task.id} due to server error.")

        finally:
            db.session.commit()
# --- MODIFICATION END ---

def perform_humanization_task(text_to_humanize, diff_data, dialect, mode):
    # This function remains the same as it was, no changes needed here
    # It contains the core logic for the Humanizer service
    humanizer = Humanizer(
        output_format=diff_data.get("output_format", "plain_text"),
        bibtex_input=diff_data.get("bibtex_input"),
        dialect=dialect,
        mode=mode
    )
    result = humanizer.humanize_text_and_handle_output(text_to_humanize)
    return (
        result.get("humanized_text", ""),
        result.get("word_count", 0),
        result.get("diff_data", {}),
        result.get("failed_word_count", 0),
        result.get("total_word_count", 0)
    )

@shared_task(ignore_result=True)
def process_playground_chat_task(task_id: int):
    with current_app.app_context():
        task = db.session.get(Task, task_id)
        if not task:
            logger.error(f"Playground task with ID {task_id} not found.")
            return
            
        try:
            task.status = 'processing'
            db.session.commit()
            
            task_data = task.diff_data or {}
            user_input_parts = task_data.get("user_input_parts", [])
            model_key = task_data.get("model_key")
            conversation_id = task_data.get("conversation_id")

            if not all([user_input_parts, model_key, conversation_id]):
                raise ValueError("Missing required data for playground chat task.")

            models_config = current_app.config.get('MODELS', {})
            model_config = models_config.get(model_key)
            if not model_config:
                raise ValueError(f"Model '{model_key}' not found in configuration.")

            provider = model_config.get('provider')
            model_name = model_config.get('model_name')
            api_key = os.getenv(model_config.get('api_key_env'))

            if provider == 'groq':
                client = GroqClient(api_key=api_key, model=model_name)
            elif provider == 'openai':
                client = OpenAIClient(api_key=api_key, model=model_name)
            elif provider == 'anthropic':
                client = AnthropicClient(api_key=api_key, model=model_name)
            else:
                raise ValueError(f"Unsupported provider: {provider}")

            conversation = db.session.get(Conversation, conversation_id)
            if not conversation:
                 raise ValueError(f"Conversation with ID {conversation_id} not found.")

            history = [{"role": msg.role, "content": msg.content} for msg in conversation.chat_messages]
            
            response_text = client.generate_content(history, user_input_parts)

            db.session.add(ChatMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=response_text
            ))

            if conversation.title == "New chat":
                try:
                    title_prompt = f"Based on the following conversation, create a short, concise title (under 8 words):\n\nUser: {user_input_parts[0].get('text', '')}\nAssistant: {response_text}"
                    title_client = GroqClient(api_key=os.getenv("GROQ_API_KEY"), model="llama3-8b-8192")
                    generated_title = title_client.generate_content_simple(title_prompt)
                    conversation.title = generated_title.strip().strip('"')
                except Exception as title_e:
                    logger.error(f"Failed to generate title for conversation {conversation_id}: {title_e}")
                    
            task.humanized_output = response_text
            task.status = 'humanization_complete'
            task.diff_data['final_conversation_id'] = conversation_id
            
            # --- Billing Logic ---
            user_prompt_text = "".join([p.get("text", "") for p in user_input_parts if p.get("type") == "input_text"])
            input_word_count = count_words(user_prompt_text)
            output_word_count = count_words(response_text)
            price_per_word = model_config.get('price_per_word', 0.001)

            user = db.session.get(User, task.user_id)
            if user:
                calculate_and_charge_playground_fee(
                    user=user,
                    conversation=conversation,
                    input_word_count=input_word_count,
                    output_word_count=output_word_count,
                    price_per_word=price_per_word
                )

        except Exception as e:
            task.status = 'humanization_failed'
            task.error_message = "An error occurred while processing your chat."
            logger.error(f"Error in process_playground_chat_task for task {task_id}: {e}", exc_info=True)
        finally:
            db.session.commit()
