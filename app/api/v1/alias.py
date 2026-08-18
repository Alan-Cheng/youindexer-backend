"""Alias generation API route."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.alias.service import AliasServiceError, get_aliases

router = APIRouter()


class AliasRequest(BaseModel):
    text: str = Field(
        min_length=1, max_length=500, description="Text to generate aliases for"
    )


class AliasResponse(BaseModel):
    text: str
    aliases: list[str]


@router.post("/aliases", response_model=AliasResponse)
async def generate_aliases(payload: AliasRequest) -> AliasResponse:
    """Generate possible aliases for the given text using Gemini."""
    normalized = payload.text.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="text must not be blank",
        )
    try:
        aliases = await get_aliases(normalized)
    except AliasServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return AliasResponse(text=normalized, aliases=aliases)
