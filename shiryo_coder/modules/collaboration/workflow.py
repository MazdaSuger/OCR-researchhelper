"""承認ワークフロー（仕様書 3.7）。

「下書きコード」(draft) → 「主任承認」(reviewed) → 「確定」(confirmed) の三段階。
承認・確定は管理者（admin）のみ。変更は監査ログへ記録する。
"""

from __future__ import annotations

from shiryo_coder.modules.collaboration.accounts import AccountRepository
from shiryo_coder.modules.collaboration.audit import AuditRepository

_NEXT = {"draft": "reviewed", "reviewed": "confirmed"}


class WorkflowError(Exception):
    """不正な状態遷移。"""


class ApprovalWorkflow:
    """segment.status の遷移を役割と履歴つきで管理する。"""

    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn
        self.accounts = AccountRepository(db)
        self.audit = AuditRepository(db)

    def _status(self, segment_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT status FROM segment WHERE id = ?", (segment_id,)
        ).fetchone()
        return row["status"] if row else None

    def _set(self, segment_id: int, status: str, approver_id: int, action: str) -> None:
        self.accounts.require(approver_id, "approve")
        self.conn.execute("UPDATE segment SET status = ? WHERE id = ?", (status, segment_id))
        self.conn.commit()
        self.audit.record(approver_id, "segment", segment_id, action, {"status": status})

    def approve(self, segment_id: int, approver_id: int) -> None:
        """主任承認: draft → reviewed。"""
        if self._status(segment_id) != "draft":
            raise WorkflowError("draft のセグメントのみ承認できます。")
        self._set(segment_id, "reviewed", approver_id, "approve")

    def confirm(self, segment_id: int, approver_id: int) -> None:
        """確定: reviewed → confirmed。"""
        if self._status(segment_id) != "reviewed":
            raise WorkflowError("reviewed のセグメントのみ確定できます。")
        self._set(segment_id, "confirmed", approver_id, "confirm")

    def reject(self, segment_id: int, approver_id: int) -> None:
        """差し戻し: → draft。"""
        self._set(segment_id, "draft", approver_id, "reject")

    def advance(self, segment_id: int, approver_id: int) -> str:
        """現在状態から 1 段階進める。新しい状態を返す。"""
        current = self._status(segment_id)
        if current not in _NEXT:
            raise WorkflowError(f"これ以上進められません（現在: {current}）。")
        target = _NEXT[current]
        action = "approve" if target == "reviewed" else "confirm"
        self._set(segment_id, target, approver_id, action)
        return target

    # -- 待ち行列 ---------------------------------------------------------------
    def pending(self, project_id: int, status: str) -> list[int]:
        rows = self.conn.execute(
            "SELECT s.id FROM segment s "
            "JOIN document d ON d.id = s.document_id "
            "WHERE d.project_id = ? AND s.status = ? ORDER BY s.id",
            (project_id, status),
        ).fetchall()
        return [r["id"] for r in rows]
