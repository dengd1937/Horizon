"""Tests for stage-specific AI configuration and routing."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from src.ai.enricher import ContentEnricher
from src.models import (
    AIConfig,
    AIProvider,
    Config,
    ContentItem,
    FilteringConfig,
    SourceType,
    SourcesConfig,
    ThinkingMode,
)
from src.orchestrator import HorizonOrchestrator


def _item() -> ContentItem:
    return ContentItem(
        id="rss:test:stage-routing",
        source_type=SourceType.RSS,
        title="Stage routing test",
        url="https://example.com/stage-routing",
        content="A short test article.",
        published_at=datetime.now(timezone.utc),
        ai_score=8.0,
        ai_summary="A test summary.",
    )


def test_stage_override_inherits_global_deepseek_settings() -> None:
    config = AIConfig(
        provider=AIProvider.DEEPSEEK,
        model="deepseek-v4-flash",
        api_key_env="DEEPSEEK_API_KEY",
        thinking=ThinkingMode.DISABLED,
        enrichment_concurrency=2,
        stages={
            "enrichment": {
                "model": "deepseek-v4-pro",
            }
        },
    )

    screening = config.for_stage("screening")
    enrichment = config.for_stage("enrichment")

    assert screening is config
    assert screening.model == "deepseek-v4-flash"
    assert enrichment.model == "deepseek-v4-pro"
    assert enrichment.provider == AIProvider.DEEPSEEK
    assert enrichment.api_key_env == "DEEPSEEK_API_KEY"
    assert enrichment.thinking == ThinkingMode.DISABLED
    assert enrichment.enrichment_concurrency == 2


class _RecordingClient:
    def __init__(self, response: str, concurrency: int = 1):
        self.response = response
        self.config = SimpleNamespace(enrichment_concurrency=concurrency)
        self.calls: list[dict[str, str]] = []

    async def complete(self, *, system: str, user: str, **kwargs: object) -> str:
        self.calls.append({"system": system, "user": user})
        return self.response


def test_enricher_routes_concepts_and_final_writeup_to_different_clients() -> None:
    concept_client = _RecordingClient('{"queries": []}')
    enrichment_client = _RecordingClient("{}", concurrency=2)
    enricher = ContentEnricher(concept_client, enrichment_client)

    asyncio.run(enricher._enrich_item(_item()))

    assert len(concept_client.calls) == 1
    assert len(enrichment_client.calls) == 1
    assert enricher._get_concurrency() == 2


def test_orchestrator_creates_flash_and_pro_clients_for_enrichment(monkeypatch) -> None:
    config = Config(
        ai=AIConfig(
            provider=AIProvider.DEEPSEEK,
            model="deepseek-v4-flash",
            api_key_env="DEEPSEEK_API_KEY",
            thinking=ThinkingMode.DISABLED,
            stages={"enrichment": {"model": "deepseek-v4-pro"}},
        ),
        sources=SourcesConfig(),
        filtering=FilteringConfig(),
    )
    orchestrator = HorizonOrchestrator(config, SimpleNamespace())
    client_configs: list[AIConfig] = []
    enricher_clients: list[object] = []

    def fake_create_client(client_config: AIConfig) -> object:
        client_configs.append(client_config)
        return object()

    class _FakeEnricher:
        def __init__(self, concept_client: object, enrichment_client: object):
            enricher_clients.extend([concept_client, enrichment_client])

        async def enrich_batch(self, items: list[ContentItem]) -> None:
            return None

    monkeypatch.setattr("src.orchestrator.create_ai_client", fake_create_client)
    monkeypatch.setattr("src.orchestrator.ContentEnricher", _FakeEnricher)

    asyncio.run(orchestrator._enrich_important_items([_item()]))

    assert [cfg.model for cfg in client_configs] == [
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    ]
    assert len(enricher_clients) == 2
