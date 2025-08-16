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


def _call_openai_api(instructions: str, user_input: str, model: str, temperature: float, top_p: float, presence_penalty: float, frequency_penalty: float) -> tuple[str, bool]:
    if not openai_client:
        raise ValueError("OpenAI client is not initialized.")
    
    logger.info(f"Sending request to OpenAI Responses API with model: {model}.")
    try:
        response = openai_client.responses.create(
            model=model,
            instructions=instructions,
            input=user_input,
            temperature=temperature,
            top_p=top_p,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            timeout=120.0
        )
        if response.output_text:
            logger.info("OpenAI Responses API call successful.")
            return response.output_text, True
        return "", False
    except OpenAIError as e:
        logger.error(f"OpenAI Responses API call failed for model {model}: {e}")
        return "", False

def call_api_with_fallback(model_list: list, system_message: str, user_prompt: str, **kwargs) -> str:
    # This function is now a wrapper for the new API call structure
    for model in model_list:
        content, success = _call_openai_api(instructions=system_message, user_input=user_prompt, model=model, **kwargs)
        if success and content.strip():
            return content
    raise AllModelsFailedError(
        message="We're sorry, but a key component of our service is currently unavailable. Please try again later.",
        debug_info="All OpenAI models failed to generate a response."
    )

def call_humanize_ai_tools_api(paragraph: str) -> tuple[str, bool]:
    # ... (This function remains unchanged as it calls a different service)
    if not paragraph or not paragraph.strip():
        return paragraph, True
    sanitized_paragraph = paragraph.replace('’', "'").replace('‘', "'").replace('”', '"').replace('“', '"').replace('\u00a0', ' ')
    url = "https://humanize-ai-tools.p.rapidapi.com/humanize"
    headers = {"content-type": "application/json", "X-RapidAPI-Key": HUMANIZE_AI_TOOLS_API_KEY, "X-RapidAPI-Host": "humanize-ai-tools.p.rapidapi.com"}
    payload = {"language": "english", "paragraph": sanitized_paragraph}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        data = response.json()
        humanized_text = data.get("paragraph")
        if not humanized_text:
            raise CustomApiError(debug_info="Humanize AI Tools API returned an empty result.")
        return humanized_text, True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            logger.warning(f"HAT API rejected a paragraph with a 400 error. Returning original paragraph. Response: {e.response.text}")
            return paragraph, False
        raise CustomApiError(debug_info=f"API Error: {e.response.status_code} - {e.response.text}") from e
    except requests.exceptions.RequestException as e:
        raise CustomApiError(debug_info=f"Request failed: {e}") from e

def call_single_openai_model(user_prompt: str, model: str) -> str:
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
