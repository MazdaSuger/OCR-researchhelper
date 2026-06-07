"""ライブラリ管理のデータアクセス層（仕様書 3.2）。

言語別 FTS5（trigram / unicode61）を横断する全文検索、メタデータフィルタ
（年代・著者・言語・コード付与状況）、コレクション/タグの管理を提供する。
"""

from __future__ import annotations

from dataclasses import dataclass

# ORDER BY に許可する列（SQL インジェクション防止のホワイトリスト）
_SORT_COLUMNS = {
    "id": "d.id",
    "title": "d.title",
    "author": "d.author",
    "year": "d.year",
    "era": "d.era",
    "language": "d.language",
    "confidence": "d.confidence",
    "code_count": "code_count",
}


@dataclass
class DocumentSummary:
    """ドキュメント一覧の 1 行分。"""

    id: int
    title: str
    author: str | None
    year: int | None
    era: str | None
    language: str | None
    confidence: float | None
    code_count: int


def _fts_query(text: str) -> str:
    """任意の検索語を FTS5 の文字列リテラル（フレーズ）に安全に変換する。"""
    escaped = text.replace('"', '""')
    return f'"{escaped}"'


class LibraryRepository:
    """document・collection に対する検索/集計/グルーピング。"""

    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn

    # -- 全文検索 + フィルタ ----------------------------------------------------
    def search(
        self,
        query: str | None = None,
        *,
        project_id: int | None = None,
        language: str | None = None,
        author: str | None = None,
        year_min: int | None = None,
        year_max: int | None = None,
        collection_id: int | None = None,
        coded: bool | None = None,
        order_by: str = "id",
        descending: bool = False,
    ) -> list[DocumentSummary]:
        """条件に合致するドキュメント要約を返す。

        - `query`: 全文検索語（言語別 FTS を横断）。空なら全件。
        - `coded`: True=コード付与済みのみ / False=未付与のみ / None=不問。
        - `order_by`: _SORT_COLUMNS のキー。
        """
        where: list[str] = []
        params: list = []

        if project_id is not None:
            where.append("d.project_id = ?")
            params.append(project_id)

        if query:
            stripped = query.strip()
            if len(stripped) < 3:
                # trigram は 3 文字未満を索引できないため、短い語（2 文字の漢語など）は
                # LIKE による部分一致でフォールバックする。
                like = f"%{stripped}%"
                where.append("(d.title LIKE ? OR d.body LIKE ?)")
                params.extend([like, like])
            else:
                fts = _fts_query(stripped)
                where.append(
                    "d.id IN ("
                    " SELECT rowid FROM document_fts_tri WHERE document_fts_tri MATCH ?"
                    " UNION SELECT rowid FROM document_fts_uni WHERE document_fts_uni MATCH ?"
                    ")"
                )
                params.extend([fts, fts])

        if language:
            where.append("d.language = ?")
            params.append(language)
        if author:
            where.append("d.author LIKE ?")
            params.append(f"%{author}%")
        if year_min is not None:
            where.append("d.year >= ?")
            params.append(year_min)
        if year_max is not None:
            where.append("d.year <= ?")
            params.append(year_max)
        if collection_id is not None:
            where.append(
                "d.id IN (SELECT document_id FROM document_collection WHERE collection_id = ?)"
            )
            params.append(collection_id)

        sort_col = _SORT_COLUMNS.get(order_by, "d.id")
        direction = "DESC" if descending else "ASC"
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        having = ""
        if coded is True:
            having = "HAVING code_count > 0"
        elif coded is False:
            having = "HAVING code_count = 0"

        sql = f"""
            SELECT d.id, d.title, d.author, d.year, d.era, d.language, d.confidence,
                   COUNT(DISTINCT s.id) AS code_count
            FROM document d
            LEFT JOIN segment s ON s.document_id = d.id
            {where_sql}
            GROUP BY d.id
            {having}
            ORDER BY {sort_col} {direction}, d.id ASC
        """
        rows = self.conn.execute(sql, params).fetchall()
        return [
            DocumentSummary(
                id=r["id"], title=r["title"], author=r["author"], year=r["year"],
                era=r["era"], language=r["language"], confidence=r["confidence"],
                code_count=r["code_count"],
            )
            for r in rows
        ]

    def document_body(self, document_id: int) -> str:
        row = self.conn.execute(
            "SELECT body FROM document WHERE id = ?", (document_id,)
        ).fetchone()
        return row["body"] if row else ""

    def distinct_languages(self, project_id: int | None = None) -> list[str]:
        sql = "SELECT DISTINCT language FROM document WHERE language IS NOT NULL"
        params: list = []
        if project_id is not None:
            sql += " AND project_id = ?"
            params.append(project_id)
        sql += " ORDER BY language"
        return [r["language"] for r in self.conn.execute(sql, params).fetchall()]

    def year_range(self, project_id: int | None = None) -> tuple[int | None, int | None]:
        sql = "SELECT MIN(year) AS lo, MAX(year) AS hi FROM document WHERE year IS NOT NULL"
        params: list = []
        if project_id is not None:
            sql += " AND project_id = ?"
            params.append(project_id)
        row = self.conn.execute(sql, params).fetchone()
        return (row["lo"], row["hi"]) if row else (None, None)

    # -- コレクション / タグ ----------------------------------------------------
    def create_collection(self, project_id: int, name: str, *, kind: str = "collection") -> int:
        row = self.conn.execute(
            "INSERT INTO collection(project_id, name, kind) VALUES (?, ?, ?) RETURNING id",
            (project_id, name, kind),
        ).fetchone()
        self.conn.commit()
        return int(row["id"])

    def collections(self, project_id: int, *, kind: str | None = None):
        sql = (
            "SELECT c.id, c.name, c.kind, COUNT(dc.document_id) AS doc_count "
            "FROM collection c "
            "LEFT JOIN document_collection dc ON dc.collection_id = c.id "
            "WHERE c.project_id = ?"
        )
        params: list = [project_id]
        if kind is not None:
            sql += " AND c.kind = ?"
            params.append(kind)
        sql += " GROUP BY c.id ORDER BY c.kind, c.name"
        return self.conn.execute(sql, params).fetchall()

    def add_to_collection(self, document_id: int, collection_id: int) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO document_collection(document_id, collection_id) "
            "VALUES (?, ?)",
            (document_id, collection_id),
        )
        self.conn.commit()

    def remove_from_collection(self, document_id: int, collection_id: int) -> None:
        self.conn.execute(
            "DELETE FROM document_collection WHERE document_id = ? AND collection_id = ?",
            (document_id, collection_id),
        )
        self.conn.commit()

    def document_collections(self, document_id: int):
        return self.conn.execute(
            "SELECT c.id, c.name, c.kind FROM collection c "
            "JOIN document_collection dc ON dc.collection_id = c.id "
            "WHERE dc.document_id = ? ORDER BY c.kind, c.name",
            (document_id,),
        ).fetchall()
