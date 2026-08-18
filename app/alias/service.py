"""Gemini-powered alias generation service."""

import json
import logging

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "You are an alias generator. Given any input text, you MUST respond "
    "ONLY with a JSON array of strings containing possible aliases, synonyms, "
    "abbreviations, alternative names, or common variations for that text. "
    "Do not include any explanation, commentary, or additional text. "
    "Alias for Taiwanese Mandarin should be in Traditional Chinese. "
    'Example input: "AI" → '
    'Example output: ["Artificial Intelligence", "machine intelligence", '
    '"computational intelligence"]'
)

RESPONSE_SCHEMA = {
    "type": "array",
    "items": {"type": "string"},
}


class AliasServiceError(Exception):
    """Raised when the alias service fails."""


def _get_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise AliasServiceError("GEMINI_API_KEY is not configured")
    return genai.Client(api_key=settings.gemini_api_key)


async def get_aliases(text: str) -> list[str]:
    """Return a list of possible aliases for the given text using Gemini."""
    client = _get_client()
    try:
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
            ),
        )
    except AliasServiceError:
        raise
    except Exception as exc:
        logger.error("Gemini API call failed: %s", exc)
        raise AliasServiceError(f"Gemini API error: {exc}") from exc

    raw = response.text
    if not raw:
        logger.warning("Gemini returned empty response for text=%r", text)
        return []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned invalid JSON: %s", raw)
        raise AliasServiceError("Gemini returned invalid JSON") from exc

    if not isinstance(parsed, list):
        logger.error("Gemini returned non-list JSON: %s", raw)
        raise AliasServiceError("Gemini returned unexpected JSON structure")

    return [item for item in parsed if isinstance(item, str)]
