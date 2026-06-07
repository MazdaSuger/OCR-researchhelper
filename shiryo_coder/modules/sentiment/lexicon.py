"""プロジェクト同梱のカスタム史料辞書（仕様書 3.4 辞書編集 UI のデータ層）。"""

from __future__ import annotations

from shiryo_coder.modules.sentiment.dictionary import SentimentDictionary


class LexiconRepository:
    """sentiment_lexicon への読み書きと辞書への合成。"""

    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn

    def set_word(self, project_id: int, word: str, polarity: float, *, language: str = "ja") -> int:
        """語に独自極性を割り当てる（既存なら更新）。"""
        row = self.conn.execute(
            "INSERT INTO sentiment_lexicon(project_id, word, polarity, language) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(project_id, word, language) DO UPDATE SET polarity = excluded.polarity "
            "RETURNING id",
            (project_id, word, polarity, language),
        ).fetchone()
        self.conn.commit()
        return int(row["id"])

    def remove_word(self, project_id: int, word: str, *, language: str = "ja") -> None:
        self.conn.execute(
            "DELETE FROM sentiment_lexicon WHERE project_id = ? AND word = ? AND language IS ?",
            (project_id, word, language),
        )
        self.conn.commit()

    def words(self, project_id: int, *, language: str | None = None) -> dict[str, float]:
        sql = "SELECT word, polarity FROM sentiment_lexicon WHERE project_id = ?"
        params: list = [project_id]
        if language is not None:
            sql += " AND language = ?"
            params.append(language)
        return {r["word"]: r["polarity"] for r in self.conn.execute(sql, params).fetchall()}

    def to_dictionary(self, project_id: int, language: str = "ja") -> SentimentDictionary:
        """カスタム辞書を SentimentDictionary として返す。"""
        return SentimentDictionary(
            language=language,
            words=self.words(project_id, language=language),
            negations=set(),
            name="project-lexicon",
        )

    def merged_with_builtin(self, project_id: int, language: str = "ja") -> SentimentDictionary:
        """内蔵辞書にカスタム辞書を上書き合成した辞書を返す。"""
        builtin = SentimentDictionary.builtin(language)
        return builtin.merge(self.to_dictionary(project_id, language))
