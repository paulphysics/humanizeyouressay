# humanizer_app/humanizer_service/parsers.py
import re
import difflib
from .utils import count_words

def _split_text_and_headings(text: str) -> list:
    normalized_text = text.replace('\r\n', '\n')
    lines = normalized_text.split('\n')
    structured_content = []
    current_paragraph = []

    for i, line in enumerate(lines):
        stripped_line = line.strip()
        if not stripped_line:
            if current_paragraph:
                structured_content.append(('paragraph', '\n'.join(current_paragraph)))
                current_paragraph = []
            continue

        # Enhanced heading detection logic
        # 1. Check for Markdown
        is_markdown_heading = stripped_line.startswith(('#', '##', '###'))
        
        # 2. Check for punctuation at the end
        ends_with_punctuation = bool(re.search(r'[.!?]$', stripped_line))
        
        # 3. Check if the line is in Title Case (and doesn't end with punctuation)
        is_title_case_heading = stripped_line.istitle() and not ends_with_punctuation
        
        # 4. Fallback for short lines (now consistent at 7 words)
        is_short_line_heading = (count_words(stripped_line) < 7 and not ends_with_punctuation)

        is_heading = is_markdown_heading or is_title_case_heading or is_short_line_heading

        if is_heading:
            if current_paragraph:
                structured_content.append(('paragraph', '\n'.join(current_paragraph)))
                current_paragraph = []
            
            if not structured_content:
                 structured_content.append(('title', stripped_line))
            else:
                 structured_content.append(('heading', stripped_line))
        else:
            current_paragraph.append(stripped_line)
            
    if current_paragraph:
        structured_content.append(('paragraph', '\n'.join(current_paragraph)))
            
    return structured_content

def generate_word_diff(text1: str, text2: str) -> list[dict]:
    placeholder = "[[PARAGRAPH_BREAK]]"
    text1_p = text1.replace('\n\n', f' {placeholder} ')
    text2_p = text2.replace('\n\n', f' {placeholder} ')
    words1 = text1_p.split()
    words2 = text2_p.split()

    matcher = difflib.SequenceMatcher(None, words1, words2, autojunk=False)
    diff_elements = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        segment = ' '.join(words2[j1:j2])
        if tag == 'equal':
            diff_elements.append({'type': 'equal', 'text': segment})
        elif tag in ('insert', 'replace'):
            diff_elements.append({'type': 'added', 'text': segment})
    return diff_elements

def split_text_into_chunks(text: str, max_words: int) -> list[str]:
    """Splits text into chunks of a maximum word count without breaking sentences."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk_words = []
    
    for sentence in sentences:
        sentence_words = sentence.split()
        if len(current_chunk_words) + len(sentence_words) > max_words and current_chunk_words:
            chunks.append(" ".join(current_chunk_words))
            current_chunk_words = []
        
        current_chunk_words.extend(sentence_words)
        
    if current_chunk_words:
        chunks.append(" ".join(current_chunk_words))
        
    return chunks
