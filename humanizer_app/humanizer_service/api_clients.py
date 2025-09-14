# humanizer_app/humanizer_service/api_clients.py
import os
import logging
import requests
import json
import time
from openai import OpenAI, OpenAIError

# --- Local Imports ---
from .exceptions import AllModelsFailedError, CustomApiError
from .utils import count_words

# --- Configuration ---
# It's best practice to configure logging at the application's entry point.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- API Keys & App-Specific Config ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HUMANIZE_AI_PRO_API_KEY = os.getenv("HUMANIZE_AI_PRO_API_KEY")
# Use an environment variable for your app's domain for flexibility.
# This allows you to use different domains for development, staging, and production.
APP_ORIGIN = os.getenv("APP_ORIGIN", "https://www.humanizeyouressay.online")

# --- Constants ---
HUMANIZE_AI_PRO_URL = "https://api.humanizeai.pro/v1/"
HUMANIZE_AI_POLL_INTERVAL = 2  # seconds
HUMANIZE_AI_MAX_RETRIES = 30
REQUEST_TIMEOUT = 120.0

# --- Client Initialization ---
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
else:
    logger.warning("OPENAI_API_KEY not set. OpenAI features will be disabled.")

# Create a persistent session for Humanize AI Pro API calls
humanize_session = requests.Session()
if HUMANIZE_AI_PRO_API_KEY:
    humanize_session.headers.update({
        "x-api-key": HUMANIZE_AI_PRO_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
        # These headers are for the API's security, tying your key to your domain.
        "Origin": APP_ORIGIN,
        "Referer": f"{APP_ORIGIN}/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    })

def _call_openai_api(instructions: str, user_input: str, model: str, **kwargs) -> tuple[str, bool]:
    if not openai_client:
        raise ValueError("OpenAI client is not initialized.")

    logger.info(f"Sending request to OpenAI Chat Completions API with model: {model}.")

    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_input}
            ],
            temperature=kwargs.get("temperature", 0.7),
            top_p=kwargs.get("top_p", 1.0),
            timeout=REQUEST_TIMEOUT
        )
        
        output_text = response.choices[0].message.content
        if output_text:
            logger.info("OpenAI API call successful.")
            return output_text, True
        return "", False
    except OpenAIError as e:
        logger.error(f"OpenAI API call failed for model {model}: {e}")
        return "", False
    except (TypeError, KeyError) as e:
        logger.error(f"Error during OpenAI API call, likely bad params or response format. Error: {e}")
        return "", False

def call_api_with_fallback(model_list: list, system_message: str, user_prompt: str, **kwargs) -> str:
    for model in model_list:
        content, success = _call_openai_api(instructions=system_message, user_input=user_prompt, model=model, **kwargs)
        if success and content.strip():
            return content
            
    raise AllModelsFailedError(
        message="We're sorry, but a key component of our service is currently unavailable. Please try again later.",
        debug_info="All configured OpenAI models failed to generate a response."
    )

def call_humanize_ai_pro(text: str) -> str:
    """
    Submits text to Humanize AI Pro and polls until the humanized text is returned.
    """
    if not HUMANIZE_AI_PRO_API_KEY:
        raise ValueError("HUMANIZE_AI_PRO_API_KEY not set in environment")

    # --- 1. Submit task ---
    logger.info("Submitting Humanize AI Pro task...")
    try:
        submit_res = humanize_session.post(HUMANIZE_AI_PRO_URL, json={"text": text}, timeout=REQUEST_TIMEOUT)
        submit_res.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
    except requests.RequestException as e:
        raise CustomApiError(f"Failed to submit task to Humanize AI Pro: {e}")

    submit_data = submit_res.json()
    task_id = submit_data.get("id")
    if not task_id:
        raise CustomApiError("No task ID returned from Humanize AI Pro.", debug_info=str(submit_data))

    logger.info(f"Submitted Humanize AI Pro task: {task_id}")

    # --- 2. Poll until done ---
    for attempt in range(HUMANIZE_AI_MAX_RETRIES):
        logger.info(f"Polling task {task_id} (attempt {attempt+1}/{HUMANIZE_AI_MAX_RETRIES})...")
        try:
            poll_res = humanize_session.get(HUMANIZE_AI_PRO_URL, params={"id": task_id}, timeout=REQUEST_TIMEOUT)
            poll_res.raise_for_status()
        except requests.RequestException as e:
            raise CustomApiError(f"Polling failed for task {task_id}: {e}")

        poll_data = poll_res.json()
        status = poll_data.get("status")

        if status == "processing":
            time.sleep(HUMANIZE_AI_POLL_INTERVAL)
            continue
        elif status == "success":
            logger.info(f"Task {task_id} completed successfully.")
            humanized_text = poll_data.get("humanized_text")
            if humanized_text is not None:
                return humanized_text
            raise CustomApiError("Task succeeded but API response was missing 'humanized_text'.", debug_info=str(poll_data))
        else:
            raise CustomApiError(f"Task {task_id} failed with status '{status}'.", debug_info=str(poll_data))

    raise TimeoutError(f"Task {task_id} did not complete after {HUMANIZE_AI_MAX_RETRIES * HUMANIZE_AI_POLL_INTERVAL} seconds.")

# --- Legacy Wrapper for Backwards Compatibility ---
def call_humanize_ai_tools_api(text: str, **kwargs):
    return call_humanize_ai_pro(text)
