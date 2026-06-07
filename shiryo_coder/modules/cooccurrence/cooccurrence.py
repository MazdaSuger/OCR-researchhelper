"""コード共起の集計（仕様書 3.6）。

スコープ（同一セグメント=重なり／同一段落／距離 N 文字以内）でコード対の共起回数を
数える。共起の 1 件は「条件を満たす、異なるコードのセグメント対」で数える。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")

Span = tuple[int, int]


@dataclass
class CooccurrenceResult:
    """コード共起の集計結果。"""

    code_ids: list[int]
    code_names: dict[int, str]
    frequencies: dict[int, int]                       # code_id → セグメント数
    matrix: dict[tuple[int, int], int] = field(default_factory=dict)  # (min,max)→共起数

    def pair_count(self, a: int, b: int) -> int:
        if a == b:
            return 0
        return self.matrix.get((min(a, b), max(a, b)), 0)


def _paragraph_index(body: str, pos: int) -> int:
    """文字位置が属する段落番号（空行区切り）。"""
    idx = 0
    last = 0
    for m in _PARAGRAPH_SPLIT.finditer(body):
        if pos < m.start():
            return idx
        idx += 1
        last = m.end()
    _ = last
    return idx


def _gap(a: Span, b: Span) -> int:
    """2 区間の間隔（重なりは 0）。"""
    return max(0, max(a[0], b[0]) - min(a[1], b[1]))


class CooccurrenceRepository:
    """segment からコード共起を集計する。"""

    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn

    def _segments(self, project_id: int, document_id: int | None):
        sql = (
            "SELECT s.id, s.document_id, s.code_id, s.char_start, s.char_end, c.name "
            "FROM segment s JOIN code c ON c.id = s.code_id "
            "WHERE c.project_id = ?"
        )
        params: list = [project_id]
        if document_id is not None:
            sql += " AND s.document_id = ?"
            params.append(document_id)
        return self.conn.execute(sql, params).fetchall()

    def matrix(
        self,
        project_id: int,
        *,
        scope: str = "overlap",
        distance: int = 20,
        document_id: int | None = None,
    ) -> CooccurrenceResult:
        rows = self._segments(project_id, document_id)
        code_names: dict[int, str] = {}
        frequencies: dict[int, int] = {}
        by_doc: dict[int, list] = {}
        for r in rows:
            code_names[r["code_id"]] = r["name"]
            frequencies[r["code_id"]] = frequencies.get(r["code_id"], 0) + 1
            by_doc.setdefault(r["document_id"], []).append(r)

        bodies = self._bodies(set(by_doc)) if scope == "paragraph" else {}
        matrix: dict[tuple[int, int], int] = {}

        for doc_id, segs in by_doc.items():
            body = bodies.get(doc_id, "")
            for i in range(len(segs)):
                for j in range(i + 1, len(segs)):
                    s1, s2 = segs[i], segs[j]
                    if s1["code_id"] == s2["code_id"]:
                        continue
                    if not self._co(s1, s2, scope, distance, body):
                        continue
                    key = (min(s1["code_id"], s2["code_id"]), max(s1["code_id"], s2["code_id"]))
                    matrix[key] = matrix.get(key, 0) + 1

        return CooccurrenceResult(
            code_ids=sorted(code_names),
            code_names=code_names,
            frequencies=frequencies,
            matrix=matrix,
        )

    def _bodies(self, doc_ids: set[int]) -> dict[int, str]:
        if not doc_ids:
            return {}
        placeholders = ",".join("?" for _ in doc_ids)
        rows = self.conn.execute(
            f"SELECT id, body FROM document WHERE id IN ({placeholders})", list(doc_ids)
        ).fetchall()
        return {r["id"]: r["body"] for r in rows}

    @staticmethod
    def _co(s1, s2, scope: str, distance: int, body: str) -> bool:
        a = (s1["char_start"], s1["char_end"])
        b = (s2["char_start"], s2["char_end"])
        if scope == "overlap":
            return a[0] < b[1] and b[0] < a[1]
        if scope == "distance":
            return _gap(a, b) <= distance
        if scope == "paragraph":
            return _paragraph_index(body, a[0]) == _paragraph_index(body, b[0])
        raise ValueError(f"未知のスコープ: {scope}")
