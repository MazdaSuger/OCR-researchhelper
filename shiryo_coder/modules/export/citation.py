"""学術引用形式の生成（APA / Chicago / SIST02）。仕様書 3.8。

文書メタデータ（著者・標題・年・出典）と引用文から書誌・引用文字列を組み立てる。
SIST02 は人文系日本の標準。
"""

from __future__ import annotations

from typing import Any

STYLES = ("apa", "chicago", "sist02")


def _meta(document: dict[str, Any]) -> tuple[str, str, str, str]:
    author = (document.get("author") or "").strip()
    title = (document.get("title") or "").strip()
    year = document.get("year")
    year_s = str(year) if year else "n.d."
    source = (document.get("source") or document.get("era") or "").strip()
    return author, title, year_s, source


def format_citation(
    document: dict[str, Any],
    style: str = "sist02",
    *,
    quote: str | None = None,
    locator: str | None = None,
) -> str:
    """書誌＋（任意で）引用文を 1 行の引用形式にする。"""
    author, title, year, source = _meta(document)
    loc = f", {locator}" if locator else ""

    if style == "apa":
        # Author (Year). Title. Source.
        parts = [p for p in [f"{author} ({year}).", f"{title}.", f"{source}." if source else ""] if p]
        citation = " ".join(parts).strip()
    elif style == "chicago":
        # Author. "Title." Source, Year.
        src = f"{source}, " if source else ""
        citation = f'{author}. "{title}." {src}{year}{loc}.'.strip()
    elif style == "sist02":
        # 著者. 標題. 出典, 出版年.
        src = f"{source}, " if source else ""
        citation = f"{author}. {title}. {src}{year}{loc}.".strip(" ")
    else:
        raise ValueError(f"未知の引用形式: {style}")

    if quote:
        citation = f"「{quote}」（{citation}）"
    return citation


def format_segment_citation(
    db, segment_id: int, style: str = "sist02"
) -> str:
    """セグメントの引用文と出典書誌を結合した引用を返す。"""
    row = db.conn.execute(
        "SELECT d.title, d.author, d.year, d.era, "
        "       SUBSTR(d.body, s.char_start + 1, s.char_end - s.char_start) AS quote, "
        "       d.metadata_json "
        "FROM segment s JOIN document d ON d.id = s.document_id WHERE s.id = ?",
        (segment_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"セグメントが見つかりません: {segment_id}")
    import json

    extras = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
    document = {
        "title": row["title"], "author": row["author"], "year": row["year"],
        "era": row["era"], "source": extras.get("source"),
    }
    return format_citation(document, style, quote=row["quote"])
