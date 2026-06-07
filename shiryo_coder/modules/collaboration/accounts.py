"""コーダーアカウントと役割ベースの権限（仕様書 3.7）。

役割: 管理者(admin) / コーダー(coder) / 閲覧者(viewer)。
"""

from __future__ import annotations

from dataclasses import dataclass

ROLES = ("admin", "coder", "viewer")

# 操作 → 許可される役割
_PERMISSIONS: dict[str, set[str]] = {
    "view": {"admin", "coder", "viewer"},
    "code": {"admin", "coder"},            # コーディング・メモ
    "manage_codebook": {"admin", "coder"},
    "lock": {"admin", "coder"},
    "approve": {"admin"},                  # 承認・確定
    "manage_accounts": {"admin"},
}


class PermissionError(Exception):
    """役割に許可されていない操作。"""


def can(role: str, action: str) -> bool:
    return role in _PERMISSIONS.get(action, set())


@dataclass
class Account:
    id: int
    name: str
    role: str
    color: str | None


class AccountRepository:
    """coder テーブルをアカウントとして管理する。"""

    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn

    def create(self, project_id: int, name: str, *, role: str = "coder", color: str | None = None) -> int:
        if role not in ROLES:
            raise ValueError(f"未知の役割: {role}")
        row = self.conn.execute(
            "INSERT INTO coder(project_id, name, role, color) VALUES (?, ?, ?, ?) RETURNING id",
            (project_id, name, role, color),
        ).fetchone()
        self.conn.commit()
        return int(row["id"])

    def set_role(self, coder_id: int, role: str) -> None:
        if role not in ROLES:
            raise ValueError(f"未知の役割: {role}")
        self.conn.execute("UPDATE coder SET role = ? WHERE id = ?", (role, coder_id))
        self.conn.commit()

    def set_color(self, coder_id: int, color: str) -> None:
        self.conn.execute("UPDATE coder SET color = ? WHERE id = ?", (color, coder_id))
        self.conn.commit()

    def delete(self, coder_id: int) -> None:
        self.conn.execute("DELETE FROM coder WHERE id = ?", (coder_id,))
        self.conn.commit()

    def role_of(self, coder_id: int) -> str | None:
        row = self.conn.execute("SELECT role FROM coder WHERE id = ?", (coder_id,)).fetchone()
        return row["role"] if row else None

    def list(self, project_id: int) -> list[Account]:
        rows = self.conn.execute(
            "SELECT id, name, role, color FROM coder WHERE project_id = ? ORDER BY id",
            (project_id,),
        ).fetchall()
        return [Account(r["id"], r["name"], r["role"], r["color"]) for r in rows]

    # -- 権限チェック -----------------------------------------------------------
    def can(self, coder_id: int, action: str) -> bool:
        role = self.role_of(coder_id)
        return role is not None and can(role, action)

    def require(self, coder_id: int, action: str) -> None:
        if not self.can(coder_id, action):
            role = self.role_of(coder_id)
            raise PermissionError(f"役割 '{role}' は操作 '{action}' を許可されていません。")
