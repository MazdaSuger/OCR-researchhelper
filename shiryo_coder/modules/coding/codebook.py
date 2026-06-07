"""コードブック（無制限階層ツリー）の管理。仕様書 3.3。"""

from __future__ import annotations

from dataclasses import dataclass, field

from shiryo_coder.modules.coding.colors import auto_color


@dataclass
class CodeNode:
    """コードツリーの 1 ノード。"""

    id: int
    name: str
    parent_id: int | None
    definition: str | None
    color: str | None
    sort_order: int
    children: list["CodeNode"] = field(default_factory=list)

    def walk(self):
        """自身と子孫を前順で列挙する。"""
        yield self
        for child in self.children:
            yield from child.walk()


class CycleError(ValueError):
    """コードを自身の子孫の下へ移動しようとした。"""


class CodebookRepository:
    """code テーブルに対する階層操作。"""

    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn

    # -- 生成 / 更新 / 削除 -----------------------------------------------------
    def create_code(
        self,
        project_id: int,
        name: str,
        *,
        parent_id: int | None = None,
        definition: str | None = None,
        color: str | None = None,
    ) -> int:
        if color is None:
            count = self.conn.execute(
                "SELECT COUNT(*) AS c FROM code WHERE project_id = ?", (project_id,)
            ).fetchone()["c"]
            color = auto_color(count)
        sort_order = self.conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM code "
            "WHERE project_id = ? AND parent_id IS ?",
            (project_id, parent_id),
        ).fetchone()["n"]
        row = self.conn.execute(
            "INSERT INTO code(project_id, parent_id, name, definition, color, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
            (project_id, parent_id, name, definition, color, sort_order),
        ).fetchone()
        self.conn.commit()
        return int(row["id"])

    def update_code(
        self,
        code_id: int,
        *,
        name: str | None = None,
        definition: str | None = None,
        color: str | None = None,
    ) -> None:
        sets, params = [], []
        for column, value in (("name", name), ("definition", definition), ("color", color)):
            if value is not None:
                sets.append(f"{column} = ?")
                params.append(value)
        if not sets:
            return
        params.append(code_id)
        self.conn.execute(f"UPDATE code SET {', '.join(sets)} WHERE id = ?", params)
        self.conn.commit()

    def delete_code(self, code_id: int) -> None:
        """コードを削除する（子孫は FK の ON DELETE CASCADE で消える）。"""
        self.conn.execute("DELETE FROM code WHERE id = ?", (code_id,))
        self.conn.commit()

    # -- 移動（ドラッグ&ドロップによる親子変更） -------------------------------
    def descendants(self, code_id: int) -> set[int]:
        """code_id の全子孫 id を返す。"""
        result: set[int] = set()
        frontier = [code_id]
        while frontier:
            current = frontier.pop()
            children = self.conn.execute(
                "SELECT id FROM code WHERE parent_id = ?", (current,)
            ).fetchall()
            for row in children:
                if row["id"] not in result:
                    result.add(row["id"])
                    frontier.append(row["id"])
        return result

    def move_code(self, code_id: int, new_parent_id: int | None) -> None:
        """コードを別の親の下へ移動する（循環は拒否）。"""
        if new_parent_id is not None:
            if new_parent_id == code_id or new_parent_id in self.descendants(code_id):
                raise CycleError("コードを自身の子孫の下へは移動できません。")
        project_id = self.conn.execute(
            "SELECT project_id FROM code WHERE id = ?", (code_id,)
        ).fetchone()["project_id"]
        sort_order = self.conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM code "
            "WHERE project_id = ? AND parent_id IS ?",
            (project_id, new_parent_id),
        ).fetchone()["n"]
        self.conn.execute(
            "UPDATE code SET parent_id = ?, sort_order = ? WHERE id = ?",
            (new_parent_id, sort_order, code_id),
        )
        self.conn.commit()

    # -- 参照 ------------------------------------------------------------------
    def list_codes(self, project_id: int) -> list[CodeNode]:
        rows = self.conn.execute(
            "SELECT id, name, parent_id, definition, color, sort_order FROM code "
            "WHERE project_id = ? ORDER BY parent_id IS NOT NULL, sort_order, id",
            (project_id,),
        ).fetchall()
        return [
            CodeNode(
                id=r["id"], name=r["name"], parent_id=r["parent_id"],
                definition=r["definition"], color=r["color"], sort_order=r["sort_order"],
            )
            for r in rows
        ]

    def tree(self, project_id: int) -> list[CodeNode]:
        """最上位コードのリストを返す（children を再帰的に組み立て済み）。"""
        nodes = {n.id: n for n in self.list_codes(project_id)}
        roots: list[CodeNode] = []
        for node in nodes.values():
            if node.parent_id is None:
                roots.append(node)
            else:
                parent = nodes.get(node.parent_id)
                (parent.children if parent else roots).append(node)
        # 兄弟を sort_order で安定化
        def sort_children(items: list[CodeNode]) -> None:
            items.sort(key=lambda n: (n.sort_order, n.id))
            for it in items:
                sort_children(it.children)

        sort_children(roots)
        return roots
