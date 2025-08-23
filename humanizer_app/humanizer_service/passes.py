# FILE: humanizer_app/humanizer_service/passes.py
import logging
from .api_clients import call_api_with_fallback
from .parsers import count_words

logger = logging.getLogger(__name__)

def generate_title_openai(text_content: str) -> str:
    """
    Uses an AI model to generate a concise, academic title for a given text.
    """
    prompt = (
        "You are an academic editor. Your task is to create a concise, formal, and descriptive title for the following essay. "
        "The title should accurately reflect the main argument or topic of the text. Do not use quotation marks in the output. "
        "Return only the title and nothing else."
    )
    try:
        new_title = call_api_with_fallback(
            model_list=["gpt-4o"],
            system_message=prompt,
            user_prompt=text_content,
            temperature=0.3
            # FIX: Removed invalid 'max_tokens=20' argument
        )
        return new_title.strip().strip('"')
    except Exception as e:
        logger.error(f"Could not generate title due to an API error: {e}")
        return "Formatted Document" # Fallback title

def format_references_with_openai(bibtex_str: str, style: str) -> list:
    """
    Uses an AI model to format a BibTeX string into a specified citation style.
    """
    style_guide = {"apa_7": "APA 7th Edition", "mla_9": "MLA 9th Edition", "harvard": "Harvard"}
    prompt = (
        "You are a citation formatting expert. Convert the following BibTeX entries into a properly formatted reference list according to the "
        f"{style_guide.get(style, 'APA 7th Edition')} style. Each reference should be on a new line. Do not include a title like 'References'. "
        "Return only the formatted reference list."
    )
    try:
        formatted_text = call_api_with_fallback(
            model_list=["gpt-4o"],
            system_message=prompt,
            user_prompt=bibtex_str,
            temperature=0.0
            # FIX: Removed invalid 'max_tokens=2048' argument
        )
        return [ref.strip() for ref in formatted_text.split('\n') if ref.strip()]
    except Exception as e:
        logger.error(f"Could not format references due to an API error: {e}")
        return []

def convert_dialect_spellings_only(text: str, target_dialect: str) -> str:
    """
    Uses an AI model to convert the spelling of a text between US and UK English.
    """
    if target_dialect not in ["us", "uk"]:
        return text
    
    prompt = (
        f"You are a language expert specializing in English dialects. Your task is to correct the spelling in the provided text to conform strictly to {target_dialect.upper()} English. "
        "Follow these rules precisely:\n"
        "1. Only change spellings (e.g., 'colour' to 'color' or vice-versa).\n"
        "2. Do not change any vocabulary, grammar, punctuation, or sentence structure.\n"
        "3. Preserve all original formatting, including markdown and line breaks.\n"
        "4. If the text is already in the correct dialect, return it unchanged.\n"
        "5. Return only the corrected text and nothing else."
    )
    try:
        converted_text = call_api_with_fallback(
            model_list=["gpt-4o"],
            system_message=prompt,
            user_prompt=text,
            temperature=0.0
            # FIX: Removed invalid 'max_tokens=2048' argument
        )
        return converted_text
    except Exception as e:
        logger.error(f"Could not convert dialect due to an API error: {e}")
        return text # Return original text on failure
