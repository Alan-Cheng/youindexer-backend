"""Gemini-powered alias generation service."""

import json
import logging

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = (
    "You are a search keyword normalizer and expansion engine. Given any input "
    "text, return a JSON array of search terms. The FIRST item MUST be the single "
    "core noun or noun phrase that best represents the topic. Remove first-person "
    "wording, filler words, sentence fragments, and intent words. After the first "
    "item, include useful synonyms, common names, abbreviations, brand names, "
    "place names, and current web-search terms strongly related to the topic. "
    "Use web search grounding to find current or popular related results when "
    "available. Return 2-10 concise terms, with no explanations or duplicates. "
    "Do not include any explanation, commentary, or additional text. "
    "Alias for Taiwanese Mandarin should be in Traditional Chinese. "
    'Example input: "我一個大陸人" → Example output: ["大陸人", "中國人"] '
    'Example input: "曼谷臘腸狗咖啡廳" → '
    'Example output: ["臘腸狗咖啡廳", "曼谷狗狗咖啡廳", "BENKOFF"]'
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
                tools=[types.Tool(google_search=types.GoogleSearch())],
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

    values: list[str] = []
    seen: set[str] = set()
    for item in parsed:
        if not isinstance(item, str):
            continue
        value = item.strip()
        key = value.casefold()
        if value and key not in seen:
            values.append(value)
            seen.add(key)
    return values[:10]


async def get_search_terms(text: str) -> list[str]:
    """Return LLM aliases, falling back to the original search text."""
    try:
        aliases = await get_aliases(text)
    except AliasServiceError:
        logger.warning("Alias generation failed; using the original search text")
        return [text]
    return aliases or [text]
