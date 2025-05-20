"""Translation utilities for subtitle generation."""

import json
import os
from typing import Any

import openai
from pydantic import BaseModel

from .cache import cached
from .types import OpenAIKeyException, Segment


class Translation(BaseModel):
    """Single translation with its index."""

    index: int
    translation: str


class TranslationResponse(BaseModel):
    """Response containing all translations."""

    translations: list[Translation]


class TranslationModelParams(BaseModel):
    """Model parameters for translation."""

    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    system_prompt: str = """You are a professional translator. Translate the following numbered
    Chinese texts to English. Provide accurate, natural-sounding translations that preserve
    the meaning and tone of the original. Return translations with their corresponding numbers."""


# Default translation model parameters
DEFAULT_MODEL_PARAMS = TranslationModelParams()


def contains_chinese(text: str) -> bool:
    """Check if text contains Chinese characters."""
    return any("\u4e00" <= c <= "\u9fff" for c in text)


def get_translation_key_params(**kwargs: Any) -> dict[str, Any]:
    """Generate key parameters for translation cache."""
    return {
        "model": DEFAULT_MODEL_PARAMS.model,
        "temperature": DEFAULT_MODEL_PARAMS.temperature,
        "system_prompt": DEFAULT_MODEL_PARAMS.system_prompt,
    }


def serialize_segments(segments: list[Segment]) -> str:
    """Serialize segments to a string for cache key generation."""
    # Create a serializable representation of segments
    # We only care about the start, end, and text content for cache keys
    serialized = [
        {
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
        }
        for seg in segments
    ]

    # Convert to JSON string for hashing
    return json.dumps(serialized, sort_keys=True)


@cached(
    cache_type="translation",
    key_generator=get_translation_key_params,
)
def translate_segments(
    segments: list[Segment],
    cached: bool = True,
) -> list[Segment]:
    """Translate all Chinese segments in a single batch API call using structured output.

    Args:
        segments: List of segments to translate
        cached: Whether to use caching (default: True)

    Returns:
        List of segments with translations applied
    """
    # Initialize the OpenAI client
    if "OPENAI_API_KEY" not in os.environ:
        raise OpenAIKeyException("translation")

    client = openai.OpenAI()

    # Create a copy of the segments to avoid modifying the original
    segments_copy = [
        Segment(start=seg.start, end=seg.end, text=seg.text, translation=seg.translation) for seg in segments
    ]

    # Filter segments that need translation
    chinese_segments = [
        (i, seg) for i, seg in enumerate(segments_copy) if contains_chinese(seg.text) and seg.translation is None
    ]

    if not chinese_segments:
        return segments_copy

    # Prepare numbered texts for batch translation
    numbered_texts = [f"{i + 1}. {seg.text}" for i, (_, seg) in enumerate(chinese_segments)]
    texts_prompt = "\n".join(numbered_texts)

    # Use the default parameters
    system_prompt = DEFAULT_MODEL_PARAMS.system_prompt
    user_prompt = f"Translate these numbered Chinese texts to English:\n{texts_prompt}"

    response = client.beta.chat.completions.parse(
        model=DEFAULT_MODEL_PARAMS.model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        response_format=TranslationResponse,
        temperature=DEFAULT_MODEL_PARAMS.temperature,
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
            segments_copy[original_idx].translation = translation_map[expected_index]

    return segments_copy
