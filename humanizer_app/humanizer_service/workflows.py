# humanizer_app/humanizer_service/workflows.py
import logging
import re
from collections import defaultdict
from .exceptions import AllModelsFailedError, CustomApiError
from .passes import (convert_dialect_spellings_only, generate_title_openai, 
                     format_references_with_openai)
from .parsers import (_split_text_and_headings, generate_word_diff, count_words)
from .api_clients import call_humanize_ai_tools_api, call_api_with_fallback

logger = logging.getLogger(__name__)

def rewrite_paragraph_with_citations_openai(paragraph: str, references: list, citation_style: str, citation_counter: defaultdict) -> tuple[str, defaultdict]:
    """
    Uses an AI model to rewrite a paragraph, intelligently inserting in-text citations.
    """
    available_references = [ref for ref in references if citation_counter[ref] < 4]
    if not available_references:
        return paragraph, citation_counter

    style_guide = {"apa_7": "APA 7th Edition (Author, Year)", "mla_9": "MLA 9th Edition (Author Page)", "harvard": "Harvard (Author, Year)"}
    prompt = (
        "You are an academic writing assistant. Your task is to rewrite the given paragraph to naturally integrate in-text citations "
        f"based on the provided list of references. Follow these strict rules:\n"
        "1. Analyze the paragraph's content and the list of available references.\n"
        "2. Identify the most contextually relevant references for the paragraph's claims.\n"
        "3. Rewrite the paragraph to seamlessly include citations for the relevant references.\n"
        f"4. Format all in-text citations according to the {style_guide.get(citation_style, 'APA 7th Edition')} style.\n"
        "5. DO NOT add more than 3 citations to this single paragraph.\n"
        "6. If no references are relevant, return the original paragraph without any changes.\n"
        "7. Do not add any commentary or explanation, only return the rewritten paragraph text."
    )
    context = f"PARAGRAPH TO REWRITE:\n\"\"\"\n{paragraph}\n\"\"\"\n\nAVAILABLE REFERENCES:\n"
    for i, ref in enumerate(available_references, 1):
        context += f"{i}. {ref}\n"

    try:
        new_paragraph = call_api_with_fallback(
            model_list=["gpt-4o"],
            system_message=prompt,
            user_prompt=context,
            temperature=0.5,
            top_p=1.0,
            presence_penalty=0.0,
            frequency_penalty=0.0,
            max_tokens=1024
        )
        for ref in available_references:
            if ref.split(',')[0].split(' ')[-1] in new_paragraph:
                citation_counter[ref] += 1
        return new_paragraph, citation_counter
    except Exception as e:
        logger.error(f"Could not rewrite paragraph with citations due to an API error: {e}")
        return paragraph, citation_counter


def perform_humanization_task(input_text: str, diff_data: dict, dialect: str = "us", mode: str = "standard") -> tuple[str, int, dict, int, int]:
    current_diff_data = dict(diff_data or {})
    original_text = input_text.strip()
    
    output_format = current_diff_data.get("output_format")
    if output_format != 'plain_text' and not original_text.lstrip().startswith('#'):
        current_diff_data['generated_title'] = generate_title_openai(original_text)

    if mode == "document_formatter":
        final_text = convert_dialect_spellings_only(original_text, dialect)
        failed_word_count = 0
        total_paragraph_word_count = 0
    else:
        structured_content = _split_text_and_headings(original_text)
        final_text_parts = []
        failed_word_count = 0
        total_paragraph_word_count = sum(count_words(content) for content_type, content in structured_content if content_type == 'paragraph')
        
        formatted_references = []
        citation_counter = defaultdict(int)
        
        if mode == 'essay' and current_diff_data.get('bibtex_input'):
            citation_style = current_diff_data.get('output_format', 'apa_7')
            formatted_references = format_references_with_openai(
                current_diff_data['bibtex_input'], citation_style
            )
            current_diff_data['formatted_references'] = formatted_references

        paragraphs = [(i, content) for i, (ctype, content) in enumerate(structured_content) if ctype == 'paragraph']
        num_paragraphs = len(paragraphs)
        processed_content = list(structured_content)

        for para_idx, (original_struct_idx, para_content) in enumerate(paragraphs):
            is_intro_or_conclusion = (num_paragraphs > 2 and (para_idx == 0 or para_idx == num_paragraphs - 1))
            
            paragraph_to_humanize = para_content
            
            if mode == 'essay' and formatted_references and not is_intro_or_conclusion:
                sentences = re.split(r'(?<=[.!?])\s+', para_content.strip())
                
                if len(sentences) >= 3:
                    topic_sentence = sentences[0]
                    concluding_sentence = sentences[-1]
                    middle_block = " ".join(sentences[1:-1])

                    citation_style = current_diff_data.get('output_format', 'apa_7')
                    cited_middle_block, citation_counter = rewrite_paragraph_with_citations_openai(
                        paragraph=middle_block,
                        references=formatted_references,
                        citation_style=citation_style,
                        citation_counter=citation_counter
                    )
                    
                    paragraph_to_humanize = f"{topic_sentence} {cited_middle_block} {concluding_sentence}"
            
            humanized_paragraph, was_successful = call_humanize_ai_tools_api(paragraph_to_humanize)
            if not was_successful:
                failed_word_count += count_words(para_content)
            
            processed_content[original_struct_idx] = (processed_content[original_struct_idx][0], humanized_paragraph)

        final_text_parts = [content for ctype, content in processed_content]
        custom_humanized_text = "\n\n".join(final_text_parts)
        final_text = convert_dialect_spellings_only(custom_humanized_text, dialect)

    current_diff_data['word_diff'] = generate_word_diff(original_text, final_text)
    final_word_count = count_words(final_text)

    return final_text, final_word_count, current_diff_data, failed_word_count, total_paragraph_word_count
