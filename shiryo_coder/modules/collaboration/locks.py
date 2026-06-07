"""ドキュメントの排他ロック（共同作業 C. ロック方式: 仕様書 3.7）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Lock:
    document_id: int
    coder_id: int
    acquired_at: str


class LockRepository:
    """document_lock による同時編集の排他制御。"""

    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn

    def holder(self, document_id: int) -> int | None:
        row = self.conn.execute(
            "SELECT coder_id FROM document_lock WHERE document_id = ?", (document_id,)
        ).fetchone()
        return row["coder_id"] if row else None

    def acquire(self, document_id: int, coder_id: int) -> bool:
        """ロックを取得する。他者が保持中なら False（自分が保持中なら True）。"""
        current = self.holder(document_id)
        if current is not None:
            return current == coder_id
        self.conn.execute(
            "INSERT INTO document_lock(document_id, coder_id) VALUES (?, ?)",
            (document_id, coder_id),
        )
        self.conn.commit()
        return True

    def release(self, document_id: int, coder_id: int, *, force: bool = False) -> bool:
        """ロックを解放する。保持者本人または force のときのみ。"""
        current = self.holder(document_id)
        if current is None:
            return True
        if not force and current != coder_id:
            return False
        self.conn.execute("DELETE FROM document_lock WHERE document_id = ?", (document_id,))
        self.conn.commit()
        return True

    def locks(self, project_id: int) -> list[Lock]:
        rows = self.conn.execute(
            "SELECT l.document_id, l.coder_id, l.acquired_at FROM document_lock l "
            "JOIN document d ON d.id = l.document_id WHERE d.project_id = ? "
            "ORDER BY l.acquired_at",
            (project_id,),
        ).fetchall()
        return [Lock(r["document_id"], r["coder_id"], r["acquired_at"]) for r in rows]
