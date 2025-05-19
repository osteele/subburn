"""Translation utilities for subtitle generation."""

import openai
from pydantic import BaseModel

from .types import Segment


class Translation(BaseModel):
    """Single translation with its index."""

    index: int
    translation: str


class TranslationResponse(BaseModel):
    """Response containing all translations."""

    translations: list[Translation]


def contains_chinese(text: str) -> bool:
    """Check if text contains Chinese characters."""
    return any("\u4e00" <= c <= "\u9fff" for c in text)


def translate_segments(segments: list[Segment], client: openai.OpenAI) -> None:
    """Translate all Chinese segments in a single batch API call using structured output."""
    # Filter segments that need translation
    chinese_segments = [(i, seg) for i, seg in enumerate(segments) if contains_chinese(seg.text)]

    if not chinese_segments:
        return

    # Prepare numbered texts for batch translation
    numbered_texts = [f"{i + 1}. {seg.text}" for i, (_, seg) in enumerate(chinese_segments)]
    texts_prompt = "\n".join(numbered_texts)

    # Create a structured prompt for batch translation
    system_prompt = """You are a professional translator. Translate the following numbered Chinese texts to English.
    Provide accurate, natural-sounding translations that preserve the meaning and tone of the original.
    Return translations with their corresponding numbers."""

    user_prompt = f"Translate these numbered Chinese texts to English:\n{texts_prompt}"

    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",  # Using a cost-effective model for translation
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        response_format=TranslationResponse,
        temperature=0.3,  # Lower temperature for more consistent translations
    )

    # Get the parsed response
    parsed_response = response.choices[0].message.parsed

    if parsed_response:
        # Create a mapping from index to translation
        translation_map = {t.index: t.translation for t in parsed_response.translations}

        # Map translations back to original segments
        for i, (original_idx, _segment) in enumerate(chinese_segments):
            expected_index = i + 1
            assert expected_index in translation_map, f"Missing translation for segment {expected_index}"
            segments[original_idx].translation = translation_map[expected_index]
