"""コード間の意味的関係（対立・包含・因果など）の手動定義。仕様書 3.6。

code_relation テーブルを用いる（cooccurrence ログとは relation_type で区別）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CodeRelation:
    id: int
    code_a_id: int
    code_b_id: int
    relation_type: str
    weight: float


class RelationRepository:
    """code_relation への読み書き。"""

    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn

    def add_relation(
        self,
        project_id: int,
        code_a_id: int,
        code_b_id: int,
        relation_type: str,
        *,
        weight: float = 1.0,
    ) -> int:
        row = self.conn.execute(
            "INSERT INTO code_relation(project_id, code_a_id, code_b_id, relation_type, weight) "
            "VALUES (?, ?, ?, ?, ?) RETURNING id",
            (project_id, code_a_id, code_b_id, relation_type, weight),
        ).fetchone()
        self.conn.commit()
        return int(row["id"])

    def remove_relation(self, relation_id: int) -> None:
        self.conn.execute("DELETE FROM code_relation WHERE id = ?", (relation_id,))
        self.conn.commit()

    def relations(
        self, project_id: int, *, relation_type: str | None = None
    ) -> list[CodeRelation]:
        sql = "SELECT id, code_a_id, code_b_id, relation_type, weight FROM code_relation WHERE project_id = ?"
        params: list = [project_id]
        if relation_type is not None:
            sql += " AND relation_type = ?"
            params.append(relation_type)
        sql += " ORDER BY id"
        return [
            CodeRelation(
                id=r["id"], code_a_id=r["code_a_id"], code_b_id=r["code_b_id"],
                relation_type=r["relation_type"], weight=r["weight"],
            )
            for r in self.conn.execute(sql, params).fetchall()
        ]
