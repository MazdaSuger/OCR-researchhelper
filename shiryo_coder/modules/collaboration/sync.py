"""コーディングの差分共有（共同作業 B. ファイル共有方式: 仕様書 3.7）。

各コーダーのコーディングを名前ベースの可搬レコードへ書き出し（export）、別 DB へ
取り込んで統合する（import）。同一箇所・同一コード・同一コーダーで状態が食い違う
場合はコンフリクトとして報告する（既定では既存を保持）。Git/Nextcloud 共有を想定。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImportReport:
    added: int = 0
    skipped: int = 0
    conflicts: list[dict] = field(default_factory=list)
    missing_documents: list[str] = field(default_factory=list)


def export_codings(db, project_id: int) -> list[dict]:
    """プロジェクトのコーディングを可搬レコード（名前ベース）へ。"""
    rows = db.conn.execute(
        "SELECT d.title AS doc, c.name AS code, cr.name AS coder, "
        "       s.char_start AS start, s.char_end AS end, s.status AS status "
        "FROM segment s "
        "JOIN document d ON d.id = s.document_id "
        "JOIN code c ON c.id = s.code_id "
        "JOIN coder cr ON cr.id = s.coder_id "
        "WHERE d.project_id = ? ORDER BY d.title, s.char_start",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def export_to_file(db, project_id: int, path: Path | str) -> Path:
    path = Path(path)
    path.write_text(
        json.dumps(export_codings(db, project_id), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def import_codings(
    db, project_id: int, records: list[dict], *, prefer: str = "existing"
) -> ImportReport:
    """可搬レコードを取り込む。

    - document は title で解決（存在しなければ missing として報告）。
    - code / coder は名前で解決し、無ければ作成する。
    - 同一(doc,code,coder,範囲)が異なる status を持つ場合はコンフリクト。
      `prefer='incoming'` なら取り込み側で上書き、既定 'existing' は保持。
    """
    report = ImportReport()
    conn = db.conn
    for rec in records:
        doc = conn.execute(
            "SELECT id FROM document WHERE project_id = ? AND title = ?",
            (project_id, rec["doc"]),
        ).fetchone()
        if doc is None:
            report.missing_documents.append(rec["doc"])
            continue
        code_id = _resolve_code(conn, project_id, rec["code"])
        coder_id = _resolve_coder(conn, project_id, rec["coder"])

        existing = conn.execute(
            "SELECT id, status FROM segment WHERE document_id=? AND code_id=? AND coder_id=? "
            "AND char_start=? AND char_end=?",
            (doc["id"], code_id, coder_id, rec["start"], rec["end"]),
        ).fetchone()

        if existing is None:
            conn.execute(
                "INSERT INTO segment(document_id, code_id, coder_id, char_start, char_end, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (doc["id"], code_id, coder_id, rec["start"], rec["end"], rec.get("status", "draft")),
            )
            report.added += 1
        elif existing["status"] != rec.get("status", "draft"):
            report.conflicts.append(
                {**rec, "existing_status": existing["status"], "incoming_status": rec.get("status")}
            )
            if prefer == "incoming":
                conn.execute(
                    "UPDATE segment SET status = ? WHERE id = ?",
                    (rec.get("status", "draft"), existing["id"]),
                )
        else:
            report.skipped += 1
    conn.commit()
    return report


def _resolve_code(conn, project_id: int, name: str) -> int:
    row = conn.execute(
        "SELECT id FROM code WHERE project_id = ? AND name = ?", (project_id, name)
    ).fetchone()
    if row is not None:
        return row["id"]
    return conn.execute(
        "INSERT INTO code(project_id, name) VALUES (?, ?) RETURNING id", (project_id, name)
    ).fetchone()["id"]


def _resolve_coder(conn, project_id: int, name: str) -> int:
    row = conn.execute(
        "SELECT id FROM coder WHERE project_id = ? AND name = ?", (project_id, name)
    ).fetchone()
    if row is not None:
        return row["id"]
    return conn.execute(
        "INSERT INTO coder(project_id, name) VALUES (?, ?) RETURNING id", (project_id, name)
    ).fetchone()["id"]
