"""Tests for successful-email watermarks and their orchestrator integration."""

import json

import pytest

from src.orchestrator import HorizonOrchestrator
from src.storage.manager import StorageManager


class FakeEmailManager:
    def __init__(self, delivered: bool):
        self.delivered = delivered
        self.calls = []

    def send_daily_summary(self, summary, subject, subscribers, *, site_url=None):
        self.calls.append((summary, subject, subscribers, site_url))
        return self.delivered


def _orchestrator(storage, delivered: bool):
    orchestrator = HorizonOrchestrator.__new__(HorizonOrchestrator)
    orchestrator.storage = storage
    orchestrator.email_manager = FakeEmailManager(delivered)
    return orchestrator


def test_storage_email_watermark_is_per_language_and_tolerates_absence(tmp_path):
    storage = StorageManager(str(tmp_path))

    assert storage.load_last_successful_email_date("zh") is None
    assert storage.load_delivered_article_slugs("zh") == set()
    storage.save_last_successful_email_date(
        "2026-07-08", "zh", article_slugs=("article-a",)
    )
    storage.save_last_successful_email_date(
        "2026-07-09", "zh", article_slugs=("article-b", "article-a")
    )
    storage.save_last_successful_email_date(
        "2026-07-07", "en", article_slugs=("article-en",)
    )

    assert storage.load_last_successful_email_date("zh") == "2026-07-09"
    assert storage.load_last_successful_email_date("en") == "2026-07-07"
    assert storage.load_delivered_article_slugs("zh") == {"article-a", "article-b"}
    assert storage.load_delivered_article_slugs("en") == {"article-en"}


def test_email_watermark_advances_only_after_successful_delivery(tmp_path):
    storage = StorageManager(str(tmp_path))
    storage.save_last_successful_email_date("2026-07-01", "zh")

    successful = _orchestrator(storage, delivered=True)
    assert successful._deliver_email_summary(
        "summary",
        "subject",
        ["reader@example.com"],
        site_url="https://h.example",
        language="zh",
        report_date="2026-07-09",
        article_slugs=("article-a",),
    )
    assert storage.load_last_successful_email_date("zh") == "2026-07-09"
    assert storage.load_delivered_article_slugs("zh") == {"article-a"}

    for delivery_name in ("all_failed", "disabled", "dry_run"):
        unsuccessful = _orchestrator(storage, delivered=False)
        assert not unsuccessful._deliver_email_summary(
            delivery_name,
            "subject",
            ["reader@example.com"],
            site_url="https://h.example",
            language="zh",
            report_date="2026-07-10",
            article_slugs=("article-b",),
        )
        assert storage.load_last_successful_email_date("zh") == "2026-07-09"
        assert storage.load_delivered_article_slugs("zh") == {"article-a"}


def test_first_email_fallback_and_existing_watermark_define_article_window(tmp_path):
    storage = StorageManager(str(tmp_path))
    orchestrator = _orchestrator(storage, delivered=False)

    assert orchestrator._email_articles_since("zh", "2026-07-09") == "2026-07-08"
    storage.save_last_successful_email_date("2026-07-05", "zh")
    assert orchestrator._email_articles_since("zh", "2026-07-09") == "2026-07-05"


def test_email_watermark_treats_malformed_state_as_absent(tmp_path):
    storage = StorageManager(str(tmp_path))
    storage.email_delivery_state_path.write_text("[]", encoding="utf-8")

    assert storage.load_last_successful_email_date("zh") is None
    assert storage.load_delivered_article_slugs("zh") == set()
    storage.save_last_successful_email_date(
        "2026-07-09", "zh", article_slugs=("article-a",)
    )
    assert json.loads(storage.email_delivery_state_path.read_text(encoding="utf-8"))[
        "delivered_article_slugs"
    ]["zh"] == ["article-a"]


@pytest.mark.parametrize("value", ["20260709", "2026-W28-4"])
def test_email_watermark_rejects_non_canonical_report_dates(tmp_path, value):
    storage = StorageManager(str(tmp_path))
    with pytest.raises(ValueError, match="ISO YYYY-MM-DD"):
        storage.save_last_successful_email_date(value, "zh")
