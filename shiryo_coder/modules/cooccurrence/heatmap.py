"""クロス集計（ヒートマップ）と時系列（仕様書 3.6）。

- crosstab: コード × メタデータ（年代/著者/時代/言語）のセグメント数。
- timeseries: 年代メタデータに基づくコード出現頻度の推移。
"""

from __future__ import annotations

from dataclasses import dataclass

_DIMENSIONS = {
    "year": "d.year",
    "author": "d.author",
    "era": "d.era",
    "language": "d.language",
}


@dataclass
class CrossTab:
    """コード（行）× ディメンション値（列）の計数表。"""

    dimension: str
    row_codes: list[int]
    code_names: dict[int, str]
    columns: list                       # ディメンション値（昇順）
    cells: dict[tuple[int, object], int]  # (code_id, column) → 件数

    def value(self, code_id: int, column) -> int:
        return self.cells.get((code_id, column), 0)


class HeatmapRepository:
    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn

    def crosstab(self, project_id: int, dimension: str) -> CrossTab:
        if dimension not in _DIMENSIONS:
            raise ValueError(f"未知のディメンション: {dimension}")
        col_expr = _DIMENSIONS[dimension]
        rows = self.conn.execute(
            f"""
            SELECT s.code_id AS cid, c.name AS cname, {col_expr} AS dim, COUNT(*) AS n
            FROM segment s
            JOIN code c ON c.id = s.code_id
            JOIN document d ON d.id = s.document_id
            WHERE c.project_id = ? AND {col_expr} IS NOT NULL
            GROUP BY s.code_id, dim
            """,
            (project_id,),
        ).fetchall()

        code_names: dict[int, str] = {}
        columns: set = set()
        cells: dict[tuple[int, object], int] = {}
        for r in rows:
            code_names[r["cid"]] = r["cname"]
            columns.add(r["dim"])
            cells[(r["cid"], r["dim"])] = r["n"]

        return CrossTab(
            dimension=dimension,
            row_codes=sorted(code_names),
            code_names=code_names,
            columns=sorted(columns, key=lambda v: (v is None, v)),
            cells=cells,
        )

    def timeseries(
        self, project_id: int, code_ids: list[int] | None = None
    ) -> dict[int, dict[int, int]]:
        """code_id → {year: 件数}。年代メタデータのある文書のみ。"""
        sql = (
            "SELECT s.code_id AS cid, d.year AS year, COUNT(*) AS n "
            "FROM segment s JOIN code c ON c.id = s.code_id "
            "JOIN document d ON d.id = s.document_id "
            "WHERE c.project_id = ? AND d.year IS NOT NULL"
        )
        params: list = [project_id]
        if code_ids:
            placeholders = ",".join("?" for _ in code_ids)
            sql += f" AND s.code_id IN ({placeholders})"
            params.extend(code_ids)
        sql += " GROUP BY s.code_id, d.year ORDER BY d.year"
        out: dict[int, dict[int, int]] = {}
        for r in self.conn.execute(sql, params).fetchall():
            out.setdefault(r["cid"], {})[r["year"]] = r["n"]
        return out
