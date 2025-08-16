# humanizer_app/humanizer_service/passes.py
import logging
from collections import defaultdict
from openai import OpenAI

logger = logging.getLogger(__name__)

def convert_dialect_spellings_only(text: str, dialect: str = "us") -> str:
    """
    Uses an AI model to correct spellings to a specific English dialect
    without changing wording, sentence structure, or punctuation.
    """
    from .api_clients import call_api_with_fallback
    dialect_map = {
        "us": "United States", "uk": "United Kingdom",
        "ca": "Canadian", "au": "Australian"
    }
    dialect_full_name = dialect_map.get(dialect.lower(), "United States")
    
    prompt = (
        f"You are a proofreading assistant. Your only task is to correct the spelling in the following text to conform to {dialect_full_name} English standards. "
        "DO NOT change any wording, sentence structure, or punctuation. Only correct spelling errors. "
        "If there are no spelling errors, return the original text."
    )
    
    try:
        corrected_text = call_api_with_fallback(
            model_list=["gpt-4o"],
            system_message=prompt,
            user_prompt=text,
            temperature=0.0,
            top_p=1.0,
            presence_penalty=0.0,
            frequency_penalty=0.0,
            max_tokens=2048
        )
        return corrected_text
    except Exception as e:
        logger.error(f"Could not convert dialect due to an API error: {e}")
        return text

def generate_title_openai(text: str) -> str:
    """
    Generates a suitable academic title for a given text using an AI model.
    """
    from .api_clients import call_api_with_fallback
    prompt = "Generate a suitable academic title for the following paper. The title should be concise and relevant."
    try:
        title = call_api_with_fallback(
            model_list=["gpt-4o"],
            system_message=prompt,
            user_prompt=text,
            temperature=0.7,
            top_p=1.0,
            presence_penalty=0.0,
            frequency_penalty=0.0,
            max_tokens=100
        )
        return title.strip().strip('"')
    except Exception as e:
        logger.error(f"Could not generate title due to an API error: {e}")
        return "Formatted Document"

def format_references_with_openai(references_text: str, style: str) -> list:
    """
    Uses OpenAI to parse a string of references (any format) and format them
    into the specified academic style.
    """
    from .api_clients import call_api_with_fallback
    style_guide = {
        "apa_7": "APA 7th Edition",
        "mla_9": "MLA 9th Edition",
        "harvard": "Harvard"
    }
    full_style_name = style_guide.get(style, "APA 7th Edition")

    prompt = (
        f"You are an expert academic librarian. Your task is to parse the following text, which contains one or more references, and format each one according to the {full_style_name} citation style. "
        "Follow these rules:\n"
        "1. Identify each individual reference in the provided text.\n"
        "2. Format each reference exactly according to the official guidelines for its type (e.g., book, journal article, website).\n"
        "3. Return the formatted references as a Python list of strings, where each string is a single, complete reference.\n"
        "4. Ensure the output is ONLY a valid Python list. Do not include any introductory text, explanation, or code block formatting."
        "For example: ['Reference 1...', 'Reference 2...']"
    )

    try:
        response_str = call_api_with_fallback(
            model_list=["gpt-4o"],
            system_message=prompt,
            user_prompt=references_text,
            temperature=0.0,
            top_p=1.0,
            presence_penalty=0.0,
            frequency_penalty=0.0,
            max_tokens=2048
        )
        
        import ast
        formatted_list = ast.literal_eval(response_str)
        
        if isinstance(formatted_list, list):
            return formatted_list
        else:
            logger.error(f"OpenAI did not return a valid list for references. Fallback.")
            return [references_text]

    except (ValueError, SyntaxError) as e:
        logger.error(f"Could not parse OpenAI response for references: {e}. Fallback.")
        return [references_text]
    except Exception as e:
        logger.error(f"Could not format references due to an API error: {e}")
        return [references_text]
