"""Obsidian 互換モード（仕様書 3.2）。

プロジェクトフォルダを Obsidian Vault として扱い、`[[wikilink]]` を保持したまま
`.md`（YAML Front Matter 付き）を走査・取り込みする。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shiryo_coder.modules.ocr.markdown_writer import read_markdown

# [[リンク]] / [[リンク|表示名]] / [[ノート#見出し]]
_WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|[^\]]+)?\]\]")


def extract_wikilinks(text: str) -> list[str]:
    """本文中の wikilink のターゲット名を出現順（重複除去）で返す。"""
    seen: dict[str, None] = {}
    for match in _WIKILINK_RE.findall(text):
        target = match.strip()
        if target:
            seen.setdefault(target, None)
    return list(seen)


@dataclass
class VaultNote:
    """Vault 内の 1 ノート。"""

    path: Path
    title: str
    metadata: dict[str, Any]
    body: str
    wikilinks: list[str] = field(default_factory=list)


def is_vault(folder: Path | str) -> bool:
    """フォルダが Vault とみなせるか（.obsidian があるか .md を含む）。"""
    folder = Path(folder)
    if not folder.is_dir():
        return False
    if (folder / ".obsidian").exists():
        return True
    return any(folder.rglob("*.md"))


def scan_vault(folder: Path | str) -> list[VaultNote]:
    """Vault 内の `.md` を走査して VaultNote のリストを返す。"""
    folder = Path(folder)
    notes: list[VaultNote] = []
    for path in sorted(folder.rglob("*.md")):
        metadata, body = read_markdown(path)
        title = metadata.get("title") or path.stem
        notes.append(
            VaultNote(
                path=path,
                title=title,
                metadata=metadata,
                body=body,
                wikilinks=extract_wikilinks(body),
            )
        )
    return notes


def import_vault(db, project_id: int, folder: Path | str) -> list[int]:
    """Vault の各ノートを document として取り込み、作成した id を返す。"""
    ids: list[int] = []
    for note in scan_vault(folder):
        meta = note.metadata
        row = db.conn.execute(
            """
            INSERT INTO document(project_id, title, body, file_path,
                                 author, year, era, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                project_id,
                note.title,
                note.body,
                str(note.path),
                meta.get("author"),
                meta.get("year"),
                meta.get("era"),
                meta.get("language"),
            ),
        ).fetchone()
        ids.append(int(row["id"]))
    db.conn.commit()
    return ids
