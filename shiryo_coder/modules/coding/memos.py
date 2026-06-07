"""メモ・注釈（3 階層）とジャーナル。仕様書 3.3。

階層: プロジェクトメモ / ドキュメントメモ / セグメントメモ。
ジャーナルは日付付きの分析ログ（is_journal=1）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Memo:
    id: int
    content: str
    project_id: int | None
    document_id: int | None
    segment_id: int | None
    coder_id: int | None
    is_journal: bool
    created_at: str
    updated_at: str


class MemoRepository:
    """memo テーブルへの読み書き。"""

    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn

    def add(
        self,
        content: str,
        *,
        project_id: int | None = None,
        document_id: int | None = None,
        segment_id: int | None = None,
        coder_id: int | None = None,
        is_journal: bool = False,
    ) -> int:
        row = self.conn.execute(
            "INSERT INTO memo(project_id, document_id, segment_id, coder_id, content, is_journal) "
            "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
            (project_id, document_id, segment_id, coder_id, content, int(is_journal)),
        ).fetchone()
        self.conn.commit()
        return int(row["id"])

    def update(self, memo_id: int, content: str) -> None:
        self.conn.execute(
            "UPDATE memo SET content = ?, updated_at = datetime('now') WHERE id = ?",
            (content, memo_id),
        )
        self.conn.commit()

    def delete(self, memo_id: int) -> None:
        self.conn.execute("DELETE FROM memo WHERE id = ?", (memo_id,))
        self.conn.commit()

    def _query(self, where: str, params: list) -> list[Memo]:
        rows = self.conn.execute(
            "SELECT id, content, project_id, document_id, segment_id, coder_id, "
            "       is_journal, created_at, updated_at "
            f"FROM memo WHERE {where} ORDER BY created_at, id",
            params,
        ).fetchall()
        return [
            Memo(
                id=r["id"], content=r["content"], project_id=r["project_id"],
                document_id=r["document_id"], segment_id=r["segment_id"],
                coder_id=r["coder_id"], is_journal=bool(r["is_journal"]),
                created_at=r["created_at"], updated_at=r["updated_at"],
            )
            for r in rows
        ]

    def for_document(self, document_id: int) -> list[Memo]:
        return self._query("document_id = ? AND is_journal = 0", [document_id])

    def for_segment(self, segment_id: int) -> list[Memo]:
        return self._query("segment_id = ? AND is_journal = 0", [segment_id])

    def for_project(self, project_id: int) -> list[Memo]:
        return self._query(
            "project_id = ? AND document_id IS NULL AND segment_id IS NULL AND is_journal = 0",
            [project_id],
        )

    def journal(self, project_id: int) -> list[Memo]:
        return self._query("project_id = ? AND is_journal = 1", [project_id])
