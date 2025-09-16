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
HUMANIZE_AI_TOOLS_API_KEY = os.getenv("HUMANIZE_AI_TOOLS_API_KEY")

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

def call_humanize_ai_tools_api(paragraph: str) -> tuple[str, bool]:
    """
    IMPORTANT! Wrapper for the AI Text Humanizer Multilingual Undetectable API.
    Kept the same function name so existing code does not break.
    """
    if not paragraph or not paragraph.strip():
        return paragraph, True

    sanitized_paragraph = (
        paragraph.replace('’', "'")
        .replace('‘', "'")
        .replace('”', '"')
        .replace('“', '"')
        .replace('\u00a0', ' ')
    )

    url = "https://ai-text-humanizer-multilingual-undetectable.p.rapidapi.com/humanize"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-key": HUMANIZE_AI_TOOLS_API_KEY,
        "x-rapidapi-host": "ai-text-humanizer-multilingual-undetectable.p.rapidapi.com",
    }
    payload = {"text": sanitized_paragraph}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        data = response.json()

        # Adjusted key to match new API
        humanized_text = data.get("humanized_text")
        if not humanized_text:
            raise CustomApiError(debug_info="AI Text Humanizer API returned an empty result.")

        # ✅ Keep the same return signature as before
        return humanized_text, True

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            logger.warning(
                f"Humanizer API rejected a paragraph with 400. Returning original. Response: {e.response.text}"
            )
            return paragraph, False
        raise CustomApiError(debug_info=f"API Error: {e.response.status_code} - {e.response.text}") from e
    except requests.exceptions.RequestException as e:
        raise CustomApiError(debug_info=f"Request failed: {e}") from e


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
