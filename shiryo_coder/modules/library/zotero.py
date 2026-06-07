"""Zotero（Better BibTeX / CSL-JSON）連携（仕様書 3.2）。

Better BibTeX の JSON 出力（`{"items": [...]}` 形式）または CSL-JSON（配列）を
読み込み、ドキュメントのメタデータ（著者・年・言語・出典）を補完する。
ネットワークは使わず、エクスポート済み JSON のみを扱う。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_YEAR_RE = re.compile(r"(\d{4})")


@dataclass
class ZoteroEntry:
    """Zotero の 1 文献。"""

    key: str
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    language: str | None = None
    source: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        """このアプリのメタデータ列にマップする（None は除く）。"""
        meta = {
            "title": self.title,
            "author": "; ".join(self.authors) if self.authors else None,
            "year": self.year,
            "language": self.language,
            "source": self.source,
            "citation_key": self.key,
        }
        return {k: v for k, v in meta.items() if v}


def _year_from(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, dict):  # CSL-JSON: {"date-parts": [[1867]]}
        parts = value.get("date-parts")
        if parts and parts[0]:
            return _year_from(parts[0][0])
    if isinstance(value, str):
        m = _YEAR_RE.search(value)
        if m:
            return int(m.group(1))
    return None


def _authors_from(item: dict[str, Any]) -> list[str]:
    authors: list[str] = []
    for creator in item.get("creators") or item.get("author") or []:
        if isinstance(creator, str):
            authors.append(creator)
            continue
        last = creator.get("lastName") or creator.get("family") or ""
        first = creator.get("firstName") or creator.get("given") or ""
        name = (last + ("　" + first if first else "")).strip() or creator.get("name", "")
        if name:
            authors.append(name)
    return authors


def _entry_from_item(item: dict[str, Any]) -> ZoteroEntry:
    key = (
        item.get("citationKey")
        or item.get("citation-key")
        or item.get("id")
        or item.get("key")
        or ""
    )
    return ZoteroEntry(
        key=str(key),
        title=item.get("title"),
        authors=_authors_from(item),
        year=_year_from(item.get("date") or item.get("issued") or item.get("year")),
        language=item.get("language"),
        source=item.get("publicationTitle") or item.get("container-title"),
        raw=item,
    )


def load_zotero_json(source: str | Path) -> list[ZoteroEntry]:
    """JSON ファイルパスまたは JSON 文字列から文献リストを読み込む。"""
    text = source
    if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source and Path(source).exists()):
        text = Path(source).read_text(encoding="utf-8")
    data = json.loads(text)
    items = data.get("items", data) if isinstance(data, dict) else data
    return [_entry_from_item(it) for it in items if isinstance(it, dict)]


def apply_to_document(db, document_id: int, entry: ZoteroEntry) -> None:
    """文献メタデータでドキュメントの空き列を補完する（既存値は上書きしない）。"""
    meta = entry.to_metadata()
    sets: list[str] = []
    params: list[Any] = []
    for column in ("title", "author", "year", "language"):
        if column in meta:
            # 既存値が NULL/空のときのみ補完
            sets.append(f"{column} = COALESCE(NULLIF({column}, ''), ?)")
            params.append(meta[column])
    if not sets:
        return
    params.append(document_id)
    db.conn.execute(f"UPDATE document SET {', '.join(sets)} WHERE id = ?", params)
    db.conn.commit()
