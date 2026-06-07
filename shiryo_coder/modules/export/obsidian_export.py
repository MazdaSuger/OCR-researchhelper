"""Obsidian Vault としての再構築（仕様書 3.8）。

コード=タグ、セグメント=callout、コード間関係=リンクで各文書を `.md` 出力する。
"""

from __future__ import annotations

import re
from pathlib import Path

from shiryo_coder.modules.ocr.markdown_writer import build_front_matter

_SAFE = re.compile(r'[\\/:*?"<>|]+')


def _safe_name(name: str) -> str:
    return _SAFE.sub("_", name).strip() or "untitled"


def _tag(name: str) -> str:
    # Obsidian タグは空白不可
    return "#" + re.sub(r"\s+", "_", name)


def export_vault(db, project_id: int, folder: Path | str) -> list[Path]:
    """各文書を Obsidian ノートとして書き出し、作成パスのリストを返す。"""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for d in db.conn.execute(
        "SELECT id, title, body, author, year, era, language FROM document "
        "WHERE project_id = ? ORDER BY id",
        (project_id,),
    ).fetchall():
        codings = db.conn.execute(
            "SELECT c.name AS code, cr.name AS coder, s.char_start AS a, s.char_end AS b, "
            "       SUBSTR(d.body, s.char_start + 1, s.char_end - s.char_start) AS text "
            "FROM segment s JOIN code c ON c.id = s.code_id "
            "LEFT JOIN coder cr ON cr.id = s.coder_id JOIN document d ON d.id = s.document_id "
            "WHERE s.document_id = ? ORDER BY s.char_start",
            (d["id"],),
        ).fetchall()

        tags = sorted({_tag(c["code"]) for c in codings})
        meta = {
            "title": d["title"], "author": d["author"], "year": d["year"],
            "era": d["era"], "language": d["language"],
            "tags": [t.lstrip("#") for t in tags] or None,
        }
        content = build_front_matter(meta)
        content += f"# {d['title']}\n\n{d['body']}\n"
        if codings:
            content += "\n## コーディング\n"
            for c in codings:
                content += (
                    f"\n> [!note] [[{c['code']}]]"
                    f"{'（' + c['coder'] + '）' if c['coder'] else ''} "
                    f"[{c['a']}–{c['b']}]\n> {c['text']}\n"
                )

        path = folder / f"{_safe_name(d['title'])}.md"
        path.write_text(content, encoding="utf-8")
        written.append(path)

    # コード関係を 1 ノートにまとめ、wikilink で表現
    relations = db.conn.execute(
        "SELECT ca.name AS a, cb.name AS b, r.relation_type AS rel FROM code_relation r "
        "JOIN code ca ON ca.id = r.code_a_id JOIN code cb ON cb.id = r.code_b_id "
        "WHERE r.project_id = ?",
        (project_id,),
    ).fetchall()
    if relations:
        lines = ["# コード関係\n"]
        for r in relations:
            lines.append(f"- [[{r['a']}]] —{r['rel']}→ [[{r['b']}]]")
        rel_path = folder / "コード関係.md"
        rel_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(rel_path)

    return written
