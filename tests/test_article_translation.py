"""Tests for faithful Chinese article translation validation."""

from pathlib import Path

import pytest

from src.articles.translation import (
    TranslationError,
    load_translated_body,
    validate_article_translation,
)


SOURCE = """# Research update

This source paragraph is long enough to represent captured English prose.

[Read more](https://example.com/more)

![Product image](https://images.example.com/product.png)

<video controls="" src="https://media.example.com/demo.mp4"></video>

## Example

- First item
- Second item

```python
print("keep me")
```
"""

TRANSLATED = """# 研究更新

这是对应英文原文的完整中文译文，用于验证文章在进入 Horizon 之前已经转换为中文，同时保留原有结构、链接、图片、视频以及代码内容。

[阅读更多](https://example.com/more)

![产品图片](https://images.example.com/product.png)

<video controls="" src="https://media.example.com/demo.mp4"></video>

## 示例

- 第一项内容
- 第二项内容

```python
print("keep me")
```
"""


def _manifest() -> dict[str, str]:
    return {
        "title": "研究功能更新",
        "summary": "这是一篇经过结构保真校验的中文译文。",
    }


def test_valid_translation_preserves_structure_and_references():
    assert (
        validate_article_translation(_manifest(), SOURCE, TRANSLATED)
        == TRANSLATED.strip()
    )


def test_translation_rejects_english_body():
    with pytest.raises(TranslationError, match="predominantly Chinese"):
        validate_article_translation(_manifest(), SOURCE, SOURCE)


def test_translation_rejects_dropped_media():
    without_video = TRANSLATED.replace(
        '<video controls="" src="https://media.example.com/demo.mp4"></video>\n\n',
        "",
    )
    with pytest.raises(TranslationError, match="raw HTML references"):
        validate_article_translation(_manifest(), SOURCE, without_video)


def test_translation_rejects_modified_code():
    with pytest.raises(TranslationError, match="fenced code blocks"):
        validate_article_translation(
            _manifest(), SOURCE, TRANSLATED.replace('print("keep me")', 'print("改动")')
        )


def test_translation_rejects_dropped_plain_paragraph():
    source = """# Research update

The first source paragraph explains the context in detail.

The second source paragraph contains a distinct conclusion.
"""
    translated = """# 研究更新

这是第一段完整中文译文，包含足够多的中文内容以通过语言校验。
"""

    with pytest.raises(TranslationError, match="Markdown blocks"):
        validate_article_translation(_manifest(), source, translated)


@pytest.mark.parametrize("field", ["title", "summary"])
def test_translation_requires_chinese_metadata(field):
    manifest = _manifest()
    manifest[field] = "English only"
    with pytest.raises(TranslationError, match=f"{field} must be written in Chinese"):
        validate_article_translation(manifest, SOURCE, TRANSLATED)


def test_load_translated_body_rejects_frontmatter(tmp_path: Path):
    path = tmp_path / "translated.md"
    path.write_text("---\ntitle: nested\n---\n\n中文正文内容\n", encoding="utf-8")
    with pytest.raises(TranslationError, match="must not contain frontmatter"):
        load_translated_body(path)
