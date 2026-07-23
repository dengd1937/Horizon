import json
import pytest
from pathlib import Path
from src.storage.manager import StorageManager, ConfigError, _expand_env_vars

def test_load_config_missing_file(tmp_path):
    storage = StorageManager(data_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        storage.load_config()

def test_load_config_invalid_json(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("invalid json", encoding="utf-8")
    
    storage = StorageManager(data_dir=str(tmp_path))
    with pytest.raises(ConfigError) as excinfo:
        storage.load_config()
    assert "Invalid JSON in configuration file" in str(excinfo.value)
    assert str(config_path) in str(excinfo.value)

def test_load_config_validation_failure(tmp_path):
    config_path = tmp_path / "config.json"
    # Missing required 'ai' and 'sources' fields
    config_path.write_text(json.dumps({"version": "1.0"}), encoding="utf-8")
    
    storage = StorageManager(data_dir=str(tmp_path))
    with pytest.raises(ConfigError) as excinfo:
        storage.load_config()
    assert "Configuration validation failed" in str(excinfo.value)
    assert str(config_path) in str(excinfo.value)

def test_load_config_success(tmp_path):
    config_path = tmp_path / "config.json"
    config_data = {
        "version": "1.0",
        "ai": {
            "provider": "anthropic",
            "model": "claude-3-sonnet",
            "api_key_env": "ANTHROPIC_API_KEY"
        },
        "sources": {
            "hackernews": {"enabled": True}
        },
        "filtering": {
            "ai_score_threshold": 7.0,
            "time_window_hours": 24
        }
    }
    config_path.write_text(json.dumps(config_data), encoding="utf-8")
    
    storage = StorageManager(data_dir=str(tmp_path))
    config = storage.load_config()
    assert config.version == "1.0"
    assert config.ai.provider == "anthropic"


class TestExpandEnvVars:
    """Recursive ${VAR} expansion on config dicts/lists/strings."""

    def test_expands_simple_reference(self, monkeypatch):
        monkeypatch.setenv("FOO", "bar")
        assert _expand_env_vars("prefix-${FOO}-suffix") == "prefix-bar-suffix"

    def test_expands_multiple_references_in_one_string(self, monkeypatch):
        monkeypatch.setenv("A", "1")
        monkeypatch.setenv("B", "2")
        assert _expand_env_vars("${A}/${B}") == "1/2"

    def test_leaves_unset_var_as_placeholder(self, monkeypatch):
        monkeypatch.delenv("MISSING", raising=False)
        assert _expand_env_vars("${MISSING}") == "${MISSING}"

    def test_ignores_non_matching_patterns(self):
        assert _expand_env_vars("no braces here") == "no braces here"
        assert _expand_env_vars("$FOO without braces") == "$FOO without braces"
        assert _expand_env_vars("${123INVALID}") == "${123INVALID}"

    def test_recurses_into_dict(self, monkeypatch):
        monkeypatch.setenv("HOST", "api.example.com")
        result = _expand_env_vars({"url": "https://${HOST}/v1", "port": 443})
        assert result == {"url": "https://api.example.com/v1", "port": 443}

    def test_recurses_into_list(self, monkeypatch):
        monkeypatch.setenv("X", "hi")
        assert _expand_env_vars(["${X}", "plain", 7]) == ["hi", "plain", 7]

    def test_preserves_non_string_leaves(self):
        assert _expand_env_vars(42) == 42
        assert _expand_env_vars(3.14) == 3.14
        assert _expand_env_vars(True) is True
        assert _expand_env_vars(None) is None

    def test_deeply_nested(self, monkeypatch):
        monkeypatch.setenv("TOKEN", "secret")
        value = {
            "a": [
                {"b": "Bearer ${TOKEN}"},
                {"b": ["${TOKEN}", 1]},
            ],
        }
        out = _expand_env_vars(value)
        assert out["a"][0]["b"] == "Bearer secret"
        assert out["a"][1]["b"] == ["secret", 1]


def test_load_config_expands_env_vars_in_ai_base_url(tmp_path, monkeypatch):
    """Integration: proves base_url is env-expandable end-to-end.

    This is exactly the use case that keeps private/tenant endpoint
    URLs out of version control.
    """
    monkeypatch.setenv("HORIZON_AI_BASE_URL", "https://private-proxy.example/v1")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "version": "1.0",
        "ai": {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key_env": "OPENAI_API_KEY",
            "base_url": "${HORIZON_AI_BASE_URL}",
        },
        "sources": {"hackernews": {"enabled": True}},
        "filtering": {"ai_score_threshold": 6.0, "time_window_hours": 24},
    }), encoding="utf-8")

    storage = StorageManager(data_dir=str(tmp_path))
    config = storage.load_config()
    assert config.ai.base_url == "https://private-proxy.example/v1"


# ---------- run items persistence ----------


def _make_item(tweet_id: str = "100", **meta_overrides) -> "ContentItem":
    from datetime import datetime, timezone

    from src.models import ContentItem, SourceType

    metadata = {
        "tweet_id": tweet_id,
        "is_retweet": False,
        "is_quote": True,
        "conversation_id": tweet_id,
        "media": [
            {
                "type": "video",
                "thumbnail_url": "https://pbs.twimg.com/t.jpg",
                "mp4_url": "https://video.twimg.com/v.mp4",
                "duration_ms": 15402,
                "width": 1280,
                "height": 720,
            }
        ],
        "links": [
            {
                "short_url": "https://t.co/x",
                "expanded_url": "https://example.com/post",
                "display_url": "example.com/post",
            }
        ],
        "thread_parts": [
            {"tweet_id": tweet_id, "text": "第一段", "media": [], "links": []},
            {"tweet_id": "101", "text": "第二段", "media": [], "links": []},
        ],
        "category": "ai-news",
    }
    metadata.update(meta_overrides)
    return ContentItem(
        id=f"twitter:tweet:{tweet_id}",
        source_type=SourceType.TWITTER,
        title="@dotey: 测试推文",
        url=f"https://x.com/dotey/status/{tweet_id}",
        content="第一段\n\n第二段",
        author="dotey",
        published_at=datetime(2026, 7, 5, 8, 30, tzinfo=timezone.utc),
        metadata=metadata,
        ai_score=8.5,
        ai_summary="一条测试摘要",
        ai_tags=["AI", "测试"],
    )


def test_save_and_load_run_items_round_trip(tmp_path):
    storage = StorageManager(data_dir=str(tmp_path))
    items = [_make_item("100"), _make_item("200", media=[], thread_parts=[])]

    path = storage.save_run_items("2026-07-05", items, total_fetched=18)
    assert path == tmp_path / "runs" / "2026-07-05.json"
    assert path.exists()

    loaded, meta = storage.load_run_items("2026-07-05")
    assert meta["date"] == "2026-07-05"
    assert meta["schema_version"] == 1
    assert meta["total_fetched"] == 18
    assert meta["generated_at"]
    assert len(loaded) == 2

    original, restored = items[0], loaded[0]
    assert restored.id == original.id
    assert str(restored.url) == str(original.url)
    assert restored.published_at == original.published_at
    assert restored.ai_score == original.ai_score
    assert restored.metadata["media"] == original.metadata["media"]
    assert restored.metadata["thread_parts"] == original.metadata["thread_parts"]
    assert restored.metadata["links"][0]["expanded_url"] == "https://example.com/post"


def test_load_run_items_missing_returns_none(tmp_path):
    storage = StorageManager(data_dir=str(tmp_path))
    assert storage.load_run_items("1999-01-01") is None


def test_save_run_items_same_date_overwrites(tmp_path):
    storage = StorageManager(data_dir=str(tmp_path))
    storage.save_run_items("2026-07-05", [_make_item("100")], total_fetched=10)
    storage.save_run_items("2026-07-05", [_make_item("300")], total_fetched=5)

    loaded, meta = storage.load_run_items("2026-07-05")
    assert len(loaded) == 1
    assert loaded[0].metadata["tweet_id"] == "300"
    assert meta["total_fetched"] == 5
