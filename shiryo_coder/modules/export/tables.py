"""表形式エクスポート（CSV / Excel）。仕様書 3.8。

コード集計表・セグメント一覧・メタデータ表・感情極性スコアを CSV 文字列で出力。
openpyxl が導入されていれば複数シートの Excel ブックも生成する。
"""

from __future__ import annotations

import csv
import io
from pathlib import Path


def _csv(rows: list[list], header: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def code_summary(db, project_id: int) -> tuple[list[str], list[list]]:
    rows = db.conn.execute(
        "SELECT c.id, c.name, "
        "       (SELECT COUNT(*) FROM segment s WHERE s.code_id = c.id) AS freq, "
        "       (SELECT COUNT(DISTINCT s.document_id) FROM segment s WHERE s.code_id = c.id) AS docs "
        "FROM code c WHERE c.project_id = ? ORDER BY c.sort_order, c.id",
        (project_id,),
    ).fetchall()
    return ["code_id", "name", "frequency", "documents"], [
        [r["id"], r["name"], r["freq"], r["docs"]] for r in rows
    ]


def segments(db, project_id: int) -> tuple[list[str], list[list]]:
    rows = db.conn.execute(
        "SELECT d.title AS doc, c.name AS code, cr.name AS coder, "
        "       s.char_start AS a, s.char_end AS b, s.status AS status, "
        "       SUBSTR(d.body, s.char_start + 1, s.char_end - s.char_start) AS text "
        "FROM segment s JOIN document d ON d.id = s.document_id "
        "JOIN code c ON c.id = s.code_id LEFT JOIN coder cr ON cr.id = s.coder_id "
        "WHERE d.project_id = ? ORDER BY d.title, s.char_start",
        (project_id,),
    ).fetchall()
    return (
        ["document", "code", "coder", "start", "end", "status", "text"],
        [[r["doc"], r["code"], r["coder"], r["a"], r["b"], r["status"], r["text"]] for r in rows],
    )


def metadata(db, project_id: int) -> tuple[list[str], list[list]]:
    rows = db.conn.execute(
        "SELECT id, title, author, year, era, language, script, ocr_engine, confidence "
        "FROM document WHERE project_id = ? ORDER BY id",
        (project_id,),
    ).fetchall()
    header = ["id", "title", "author", "year", "era", "language", "script", "ocr_engine", "confidence"]
    return header, [[r[h] for h in header] for r in rows]


def sentiment(db, project_id: int) -> tuple[list[str], list[list]]:
    rows = db.conn.execute(
        "SELECT d.title AS doc, s.unit AS unit, s.char_start AS a, s.char_end AS b, "
        "       s.polarity AS polarity, s.dictionary AS dictionary "
        "FROM sentiment s JOIN document d ON d.id = s.document_id "
        "WHERE d.project_id = ? ORDER BY d.title, s.char_start",
        (project_id,),
    ).fetchall()
    return (
        ["document", "unit", "start", "end", "polarity", "dictionary"],
        [[r["doc"], r["unit"], r["a"], r["b"], r["polarity"], r["dictionary"]] for r in rows],
    )


_TABLES = {
    "codes": code_summary,
    "segments": segments,
    "metadata": metadata,
    "sentiment": sentiment,
}


def to_csv(db, project_id: int, table: str) -> str:
    """指定テーブルを CSV 文字列で返す。"""
    if table not in _TABLES:
        raise ValueError(f"未知のテーブル: {table}")
    header, rows = _TABLES[table](db, project_id)
    return _csv(rows, header)


def excel_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("openpyxl") is not None


def to_excel(db, project_id: int, path: Path | str) -> Path:
    """全テーブルを複数シートの Excel ブックに書き出す（openpyxl 必須）。"""
    import openpyxl

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, fn in _TABLES.items():
        header, rows = fn(db, project_id)
        ws = wb.create_sheet(name)
        ws.append(header)
        for row in rows:
            ws.append(list(row))
    path = Path(path)
    wb.save(path)
    return path
