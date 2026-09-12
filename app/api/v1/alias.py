"""Alias generation API route."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.alias.service import AliasServiceError, get_aliases
from app.core.response import APIResponse

router = APIRouter()


class AliasRequest(BaseModel):
    text: str = Field(
        min_length=1, max_length=500, description="Text to generate aliases for"
    )


class AliasResponse(BaseModel):
    text: str
    aliases: list[str]
    llm_aliases_available: bool


@router.post("/aliases", response_model=APIResponse[AliasResponse])
async def generate_aliases(payload: AliasRequest) -> APIResponse[AliasResponse]:
    """Generate possible aliases for the given text using Gemini."""
    normalized = payload.text.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="text must not be blank",
        )
    try:
        aliases = await get_aliases(normalized)
    except AliasServiceError:
        return APIResponse.ok(
            AliasResponse(
                text=normalized,
                aliases=[normalized],
                llm_aliases_available=False,
            )
        )
    if not aliases:
        return APIResponse.ok(
            AliasResponse(
                text=normalized,
                aliases=[normalized],
                llm_aliases_available=False,
            )
        )
    return APIResponse.ok(
        AliasResponse(
            text=normalized,
            aliases=aliases,
            llm_aliases_available=True,
        )
    )
