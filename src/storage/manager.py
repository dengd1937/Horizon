"""Storage manager for configuration and state persistence."""

import json
import os
import re
import shutil
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from ..models import Config, ContentItem


# Matches ${VAR_NAME} in string config values. Names follow env-var rules
# (ASCII letters, digits, underscore; must not start with a digit).
_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RUN_SCHEMA_VERSION = 1


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand ``${VAR}`` references inside any string leaves.

    Containers (dicts, lists, tuples) are walked; non-string leaves are
    returned unchanged. Strings with no ``${...}`` tokens are returned
    unchanged. References to unset variables are **left as-is**, so
    ``${MISSING}`` round-trips to ``${MISSING}`` and surfaces as a clear
    downstream error rather than a silent empty string.

    This is intentionally identical to the behaviour ``RSSScraper`` uses
    for RSS feed URLs, so a single ``${VAR}`` convention works everywhere
    in the config (AI ``base_url``, feed URLs, webhook URLs, ...).
    """
    if isinstance(value, str):
        return _ENV_VAR_PATTERN.sub(
            lambda m: os.environ.get(m.group(1), m.group(0)),
            value,
        )
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_expand_env_vars(v) for v in value)
    return value


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""

    pass


class StorageManager:
    """Manages file-based storage for configuration and state."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.config_path = self.data_dir / "config.json"
        self.summaries_dir = self.data_dir / "summaries"
        self.runs_dir = self.data_dir / "runs"
        self.email_delivery_state_path = self.data_dir / "email_delivery_state.json"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def load_config(self) -> Config:
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please create it based on the template in README.md"
            )

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(
                f"Invalid JSON in configuration file: {self.config_path}\n" f"Error: {e}"
            ) from e

        # Expand ${VAR} references in every string value before pydantic
        # validation. Keeps credentials / private endpoints / tenant IDs
        # out of the JSON file so it is safe to commit to a public repo.
        data = _expand_env_vars(data)

        try:
            return Config.model_validate(data)
        except ValidationError as e:
            raise ConfigError(
                f"Configuration validation failed for {self.config_path}\n"
                f"Details: {e}"
            ) from e

    def save_config(self, config: Config, backup: bool = True) -> Path:
        """Save configuration to config.json, optionally backing up the existing file.

        Args:
            config: The Config object to save.
            backup: If True and config.json exists, copy it to config.json.bak first.

        Returns:
            Path to the saved config file.
        """
        if backup and self.config_path.exists():
            shutil.copy2(self.config_path, self.config_path.with_suffix(".json.bak"))

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
            f.write("\n")

        return self.config_path

    def save_daily_summary(self, date: str, markdown: str, language: str = "en") -> Path:
        filename = f"horizon-{date}-{language}.md"
        filepath = self.summaries_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown)

        return filepath

    def load_last_successful_email_date(self, language: str) -> Optional[str]:
        """Return the last successfully delivered UTC report date for ``language``.

        The state is intentionally separate from generated summaries: rendering a
        summary does not mean a subscriber received it.  Invalid or absent state
        is treated as no watermark so callers can use their first-send fallback.
        """
        if not self.email_delivery_state_path.exists():
            return None
        try:
            with open(self.email_delivery_state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            if not isinstance(state, dict):
                return None
            value = (state.get("last_successful_email_dates") or {}).get(language)
            if not isinstance(value, str) or not _ISO_DATE_RE.fullmatch(value):
                return None
            date.fromisoformat(value)
            return value
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def load_delivered_article_slugs(self, language: str) -> set[str]:
        """Return article slugs already included in a fully delivered email."""
        if not self.email_delivery_state_path.exists():
            return set()
        try:
            with open(self.email_delivery_state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            if not isinstance(state, dict):
                return set()
            values = (state.get("delivered_article_slugs") or {}).get(language, [])
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value for value in values
            ):
                return set()
            return set(values)
        except (OSError, json.JSONDecodeError):
            return set()

    def save_last_successful_email_date(
        self,
        report_date: str,
        language: str,
        *,
        article_slugs: list[str] | tuple[str, ...] = (),
    ) -> Path:
        """Atomically persist a successful delivery date and included articles."""
        if not _ISO_DATE_RE.fullmatch(report_date):
            raise ValueError("report_date must be ISO YYYY-MM-DD")
        date.fromisoformat(report_date)
        if any(not isinstance(slug, str) or not slug for slug in article_slugs):
            raise ValueError("article_slugs must contain non-empty strings")
        state: dict[str, Any] = {}
        if self.email_delivery_state_path.exists():
            try:
                with open(self.email_delivery_state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except (OSError, json.JSONDecodeError):
                state = {}
        if not isinstance(state, dict):
            state = {}
        dates = state.get("last_successful_email_dates")
        if not isinstance(dates, dict):
            dates = {}
        dates[language] = report_date
        state["last_successful_email_dates"] = dates

        delivered = state.get("delivered_article_slugs")
        if not isinstance(delivered, dict):
            delivered = {}
        existing = delivered.get(language, [])
        if not isinstance(existing, list):
            existing = []
        delivered[language] = sorted(
            {
                value
                for value in [*existing, *article_slugs]
                if isinstance(value, str) and value
            }
        )
        state["delivered_article_slugs"] = delivered

        fd, temporary_name = tempfile.mkstemp(
            prefix=".email-delivery-state.", suffix=".tmp", dir=self.data_dir
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, self.email_delivery_state_path)
        finally:
            temporary.unlink(missing_ok=True)
        return self.email_delivery_state_path

    def save_run_items(
        self, date: str, items: list[ContentItem], total_fetched: int
    ) -> Path:
        """Persist one run's selected items (post analysis + enrichment).

        Structured source for site rendering, historical re-rendering, and
        any future consumer. Re-running the same date overwrites the file.
        """
        filepath = self.runs_dir / f"{date}.json"
        payload = {
            "schema_version": RUN_SCHEMA_VERSION,
            "date": date,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_fetched": total_fetched,
            "items": [item.model_dump(mode="json") for item in items],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write("\n")
        return filepath

    def load_run_items(
        self, date: str
    ) -> Optional[tuple[list[ContentItem], dict]]:
        """Load a persisted run. Returns (items, meta) or None if absent."""
        filepath = self.runs_dir / f"{date}.json"
        if not filepath.exists():
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)
        schema_version = payload.get("schema_version", 0)
        if schema_version not in {0, RUN_SCHEMA_VERSION}:
            raise ValueError(f"unsupported run schema version: {schema_version}")
        items = [ContentItem.model_validate(raw) for raw in payload.get("items", [])]
        meta = {k: v for k, v in payload.items() if k != "items"}
        return items, meta

    def load_subscribers(self) -> list:
        """Loads the list of email subscribers."""
        subscribers_path = self.data_dir / "subscribers.json"
        if not subscribers_path.exists():
            return []

        try:
            with open(subscribers_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def add_subscriber(self, email_addr: str):
        """Adds a new subscriber email."""
        subscribers = self.load_subscribers()
        if email_addr not in subscribers:
            subscribers.append(email_addr)
            self._save_subscribers(subscribers)

    def remove_subscriber(self, email_addr: str):
        """Removes a subscriber email."""
        subscribers = self.load_subscribers()
        if email_addr in subscribers:
            subscribers.remove(email_addr)
            self._save_subscribers(subscribers)

    def _save_subscribers(self, subscribers: list):
        """Helper to save subscribers list."""
        subscribers_path = self.data_dir / "subscribers.json"
        with open(subscribers_path, "w", encoding="utf-8") as f:
            json.dump(subscribers, f, indent=2)
