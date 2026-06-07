"""`.md`（YAML Front Matter 付き）の読み書き（仕様書 3.1 末尾の保存形式）。

```markdown
---
title: 大政奉還上表文
author: 徳川慶喜
year: 1867
era: 江戸後期
language: ja
script: vertical
source_image: ./images/taisei_001.jpg
ocr_engine: NDLOCR-Lite-1.2
confidence: 0.94
---
# 本文
…
```
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Front Matter の標準キー順（これ以外のキーは後ろに続けて出力）
FRONT_MATTER_ORDER = [
    "title", "author", "year", "era",
    "language", "script", "source_image", "ocr_engine", "confidence",
]

_DELIMITER = "---"


def _ordered(metadata: dict[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in FRONT_MATTER_ORDER:
        if key in metadata and metadata[key] is not None:
            ordered[key] = metadata[key]
    for key, value in metadata.items():
        if key not in ordered and value is not None:
            ordered[key] = value
    return ordered


def build_front_matter(metadata: dict[str, Any]) -> str:
    """メタデータを YAML Front Matter ブロック（区切り線込み）に整形する。"""
    body = yaml.safe_dump(
        _ordered(metadata),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).rstrip()
    return f"{_DELIMITER}\n{body}\n{_DELIMITER}\n"


def write_markdown(
    path: Path | str,
    metadata: dict[str, Any],
    body: str,
    *,
    heading: str = "本文",
) -> Path:
    """Front Matter + 本文の `.md` を書き出す。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = build_front_matter(metadata)
    if heading:
        content += f"# {heading}\n"
    content += body if body.endswith("\n") else body + "\n"
    path.write_text(content, encoding="utf-8")
    return path


def read_markdown(path: Path | str) -> tuple[dict[str, Any], str]:
    """`.md` を Front Matter（dict）と本文（見出し以降）に分解する。"""
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != _DELIMITER:
        return {}, text

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _DELIMITER:
            end = i
            break
    if end is None:
        return {}, text

    metadata = yaml.safe_load("\n".join(lines[1:end])) or {}
    rest = lines[end + 1:]
    # 先頭の見出し行（# …）と空行をスキップして本文を取り出す
    while rest and (rest[0].startswith("#") or rest[0].strip() == ""):
        rest.pop(0)
    return metadata, "\n".join(rest)
