"""変更履歴（誰がいつどのセグメントに何をしたか）。仕様書 3.7。"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class AuditEntry:
    id: int
    coder_id: int | None
    entity: str
    entity_id: int | None
    action: str
    detail: dict
    created_at: str


class AuditRepository:
    """audit_log への記録と参照。"""

    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn

    def record(
        self,
        coder_id: int | None,
        entity: str,
        entity_id: int | None,
        action: str,
        detail: dict | None = None,
    ) -> int:
        row = self.conn.execute(
            "INSERT INTO audit_log(coder_id, entity, entity_id, action, detail_json) "
            "VALUES (?, ?, ?, ?, ?) RETURNING id",
            (coder_id, entity, entity_id, action,
             json.dumps(detail, ensure_ascii=False) if detail else None),
        ).fetchone()
        self.conn.commit()
        return int(row["id"])

    def history(
        self,
        *,
        coder_ids: list[int] | None = None,
        entity: str | None = None,
        entity_id: int | None = None,
        limit: int = 500,
    ) -> list[AuditEntry]:
        where: list[str] = []
        params: list = []
        if coder_ids:
            where.append(f"coder_id IN ({','.join('?' for _ in coder_ids)})")
            params.extend(coder_ids)
        if entity is not None:
            where.append("entity = ?")
            params.append(entity)
        if entity_id is not None:
            where.append("entity_id = ?")
            params.append(entity_id)
        sql = "SELECT id, coder_id, entity, entity_id, action, detail_json, created_at FROM audit_log"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return [
            AuditEntry(
                id=r["id"], coder_id=r["coder_id"], entity=r["entity"],
                entity_id=r["entity_id"], action=r["action"],
                detail=json.loads(r["detail_json"]) if r["detail_json"] else {},
                created_at=r["created_at"],
            )
            for r in self.conn.execute(sql, params).fetchall()
        ]

    def for_project(self, project_id: int, *, limit: int = 500) -> list[AuditEntry]:
        coders = [
            r["id"]
            for r in self.conn.execute(
                "SELECT id FROM coder WHERE project_id = ?", (project_id,)
            ).fetchall()
        ]
        return self.history(coder_ids=coders, limit=limit) if coders else []
