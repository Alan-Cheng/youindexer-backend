import asyncio

from app.api.v1.alias import AliasRequest, generate_aliases
from app.alias.service import AliasServiceError


def test_alias_api_reports_llm_aliases(monkeypatch) -> None:
    async def fake_get_aliases(text: str) -> list[str]:
        return ["AI", "artificial intelligence"]

    monkeypatch.setattr("app.api.v1.alias.get_aliases", fake_get_aliases)

    response = asyncio.run(generate_aliases(AliasRequest(text="人工智慧")))

    assert response.data.aliases == ["AI", "artificial intelligence"]
    assert response.data.llm_aliases_available is True


def test_alias_api_falls_back_when_llm_fails(monkeypatch) -> None:
    async def fake_get_aliases(text: str) -> list[str]:
        raise AliasServiceError("LLM unavailable")

    monkeypatch.setattr("app.api.v1.alias.get_aliases", fake_get_aliases)

    response = asyncio.run(generate_aliases(AliasRequest(text="人工智慧")))

    assert response.data.aliases == ["人工智慧"]
    assert response.data.llm_aliases_available is False


def test_alias_api_falls_back_when_llm_returns_empty(monkeypatch) -> None:
    async def fake_get_aliases(text: str) -> list[str]:
        return []

    monkeypatch.setattr("app.api.v1.alias.get_aliases", fake_get_aliases)

    response = asyncio.run(generate_aliases(AliasRequest(text="人工智慧")))

    assert response.data.aliases == ["人工智慧"]
    assert response.data.llm_aliases_available is False
