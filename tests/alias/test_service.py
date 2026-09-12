import asyncio

from app.alias.service import AliasServiceError, get_search_terms


def test_search_terms_use_aliases(monkeypatch) -> None:
    async def fake_get_aliases(text: str) -> list[str]:
        return ["AI", "artificial intelligence"]

    monkeypatch.setattr("app.alias.service.get_aliases", fake_get_aliases)

    assert asyncio.run(get_search_terms("人工智慧")) == [
        "AI",
        "artificial intelligence",
    ]


def test_search_terms_fall_back_to_original_text_on_alias_failure(monkeypatch) -> None:
    async def fake_get_aliases(text: str) -> list[str]:
        raise AliasServiceError("LLM unavailable")

    monkeypatch.setattr("app.alias.service.get_aliases", fake_get_aliases)

    assert asyncio.run(get_search_terms("人工智慧")) == ["人工智慧"]


def test_search_terms_fall_back_to_original_text_on_empty_aliases(monkeypatch) -> None:
    async def fake_get_aliases(text: str) -> list[str]:
        return []

    monkeypatch.setattr("app.alias.service.get_aliases", fake_get_aliases)

    assert asyncio.run(get_search_terms("人工智慧")) == ["人工智慧"]
