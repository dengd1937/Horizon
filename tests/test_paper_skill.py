"""Static contracts for the project-local paper ingestion skill."""

from pathlib import Path

import yaml


SKILL_ROOT = Path("skills/horizon-add-paper")


def test_paper_skill_has_discoverable_metadata_and_no_placeholders():
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(skill.split("---", 2)[1])

    assert frontmatter["name"] == "horizon-add-paper"
    assert "arXiv" in frontmatter["description"]
    assert "TODO" not in skill
    assert "uv run horizon-paper validate" in skill
    assert "uv run horizon-paper preview" in skill
    assert "uv run horizon-paper create" in skill
    assert "Never stage, commit, push, deploy" in skill


def test_paper_skill_interface_mentions_explicit_invocation():
    metadata = yaml.safe_load(
        (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )

    assert metadata["interface"]["display_name"] == "Horizon Add Papers"
    assert "$horizon-add-paper" in metadata["interface"]["default_prompt"]
    assert (SKILL_ROOT / "references" / "close-read-template.md").is_file()
