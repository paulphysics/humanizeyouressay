# humanizer_app/humanizer_service/utils.py
import re

def count_words(text: str) -> int:
    """
    Counts the number of words in a given text string.
    """
    if not text:
        return 0
    return len(re.findall(r'\b\w+\b', text))
