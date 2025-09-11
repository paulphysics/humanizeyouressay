# humanizer_app/humanizer_service/api_clients.py
import os
import logging
import requests
import json
from openai import OpenAI, OpenAIError

# --- Local Imports ---
from .exceptions import AllModelsFailedError, CustomApiError
from .utils import count_words

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HUMANIZE_AI_PRO_API_KEY = os.getenv("HUMANIZE_AI_PRO_API_KEY")

# --- Config ---
HUMANIZE_AI_PRO_URL = "https://api.humanizeai.pro/v1/"

# --- Client Initialization ---
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
else:
    logger.warning("OPENAI_API_KEY not set. Advanced features will be disabled.")

def _call_openai_api(instructions: str, user_input: str, model: str, **kwargs) -> tuple[str, bool]:
    if not openai_client:
        raise ValueError("OpenAI client is not initialized.")
    
    logger.info(f"Sending request to OpenAI Responses API with model: {model}.")
    
    # **FIX:** Removed 'presence_penalty' and 'frequency_penalty' as they are not supported.
    valid_params = {
        "model": model,
        "instructions": instructions,
        "input": user_input,
        "temperature": kwargs.get("temperature", 0.7),
        "top_p": kwargs.get("top_p", 1.0),
        "timeout": 120.0
    }

    try:
        response = openai_client.responses.create(**valid_params)
        
        if response.output_text:
            logger.info("OpenAI Responses API call successful.")
            return response.output_text, True
        return "", False
    except OpenAIError as e:
        logger.error(f"OpenAI Responses API call failed for model {model}: {e}")
        return "", False
    except TypeError as e:
        logger.error(f"TypeError during OpenAI API call. Likely an unsupported parameter. Error: {e}")
        return "", False

def call_api_with_fallback(model_list: list, system_message: str, user_prompt: str, **kwargs) -> str:
    for model in model_list:
        content, success = _call_openai_api(instructions=system_message, user_input=user_prompt, model=model, **kwargs)
        if success and content.strip():
            return content
            
    raise AllModelsFailedError(
        message="We're sorry, but a key component of our service is currently unavailable. Please try again later.",
        debug_info="All OpenAI models failed to generate a response."
    )

def call_humanize_ai_pro(text: str, max_retries: int = 30, poll_interval: int = 2) -> str:
    """
    Submit text to Humanize AI Pro and poll until humanized text is returned.

    Args:
        text (str): Input text (must be at least 30 words).
        max_retries (int): How many times to poll before giving up.
        poll_interval (int): Seconds to wait between polls.

    Returns:
        str: The humanized text.

    Raises:
        Exception: If the task fails or times out.
    """
    if not HUMANIZE_AI_PRO_API_KEY:
        raise ValueError("HUMANIZE_AI_PRO_API_KEY not set in environment")

    headers = {
        "x-api-key": HUMANIZE_AI_PRO_API_KEY,
        "Content-Type": "application/json",
    }

    # 1. Submit task
    submit_res = requests.post(HUMANIZE_AI_PRO_URL, json={"text": text}, headers=headers)
    if submit_res.status_code != 200:
        raise Exception(f"Failed to submit task: {submit_res.text}")

    submit_data = submit_res.json()
    task_id = submit_data.get("id")
    if not task_id:
        raise Exception(f"No task ID returned: {submit_data}")

    logger.info(f"Submitted Humanize AI Pro task: {task_id}")

    # 2. Poll until done
    for attempt in range(max_retries):
        poll_res = requests.get(HUMANIZE_AI_PRO_URL, params={"id": task_id}, headers=headers)
        if poll_res.status_code != 200:
            raise Exception(f"Polling failed: {poll_res.text}")

        poll_data = poll_res.json()
        status = poll_data.get("status")

        if status == "processing":
            logger.info(f"Task {task_id} still processing... ({attempt+1}/{max_retries})")
            time.sleep(poll_interval)
            continue
        elif status == "success":
            return poll_data.get("humanized_text") or poll_data
        else:
            raise Exception(f"Task failed: {poll_data}")

    raise TimeoutError(f"Task {task_id} did not finish after {max_retries} retries")

def call_single_openai_model(user_prompt: str, model: str) -> str:
    # This function remains unchanged
    if not openai_client:
        raise ValueError("OpenAI client is not initialized.")
    
    try:
        response = openai_client.responses.create(
            model=model,
            instructions="You are a helpful and creative assistant.",
            input=user_prompt,
            temperature=0.7,
            timeout=120.0
        )
        if response.output_text:
            return response.output_text
        raise AllModelsFailedError(debug_info=f"No response from model {model}.")
    except OpenAIError as e:
        logger.error(f"OpenAI API call failed for model {model}: {e}")
        raise AllModelsFailedError(debug_info=str(e))

# --- Legacy Wrapper for Backwards Compatibility ---
def call_humanize_ai_tools_api(text: str, **kwargs):
    """
    Legacy alias: use call_humanize_ai_pro internally.
    Prevents ImportError in workflows.py and routes old calls.
    """
    return call_humanize_ai_pro(text, **kwargs)
