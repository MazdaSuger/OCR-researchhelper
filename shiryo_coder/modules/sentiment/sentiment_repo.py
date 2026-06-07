"""センチメント解析の高水準 API（仕様書 3.4）。

分析単位（文・段落・コードセグメント・文書全体）ごとに極性を計算して sentiment
テーブルへ保存し、可視化用の集計（年代別時系列、コード別の極性分布）を提供する。
"""

from __future__ import annotations

from dataclasses import dataclass

from shiryo_coder.modules.reliability import units as unit_mod
from shiryo_coder.modules.sentiment.analyzer import SentimentAnalyzer

UNITS = ("sentence", "paragraph", "segment", "document")


@dataclass
class UnitSentiment:
    """1 単位分の極性スコア。"""

    char_start: int | None
    char_end: int | None
    segment_id: int | None
    polarity: float
    text: str
    word_count: int


class SentimentRepository:
    """sentiment テーブルへの計算・保存と集計。"""

    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn

    def _body(self, document_id: int) -> str:
        row = self.conn.execute(
            "SELECT body FROM document WHERE id = ?", (document_id,)
        ).fetchone()
        return row["body"] if row else ""

    def _segments(self, document_id: int):
        return self.conn.execute(
            "SELECT id, char_start, char_end FROM segment WHERE document_id = ? "
            "ORDER BY char_start",
            (document_id,),
        ).fetchall()

    # -- 解析 + 保存 -----------------------------------------------------------
    def analyze_document(
        self,
        document_id: int,
        analyzer: SentimentAnalyzer,
        *,
        unit: str = "sentence",
        persist: bool = True,
    ) -> list[UnitSentiment]:
        if unit not in UNITS:
            raise ValueError(f"未知の分析単位: {unit}")
        body = self._body(document_id)
        results: list[UnitSentiment] = []

        if unit == "document":
            score = analyzer.score_text(body)
            results.append(UnitSentiment(0, len(body), None, score.polarity, body, score.word_count))
        elif unit == "segment":
            for seg in self._segments(document_id):
                text = body[seg["char_start"]:seg["char_end"]]
                score = analyzer.score_text(text)
                results.append(
                    UnitSentiment(seg["char_start"], seg["char_end"], seg["id"],
                                  score.polarity, text, score.word_count)
                )
        else:
            spans = (
                unit_mod.sentence_spans(body)
                if unit == "sentence"
                else unit_mod.paragraph_spans(body)
            )
            for start, end in spans:
                text = body[start:end]
                score = analyzer.score_text(text)
                results.append(UnitSentiment(start, end, None, score.polarity, text, score.word_count))

        if persist:
            self._persist(document_id, unit, analyzer.dictionary.name, results)
        return results

    def _persist(self, document_id: int, unit: str, dictionary: str, results) -> None:
        self.conn.execute(
            "DELETE FROM sentiment WHERE document_id = ? AND unit = ?", (document_id, unit)
        )
        self.conn.executemany(
            "INSERT INTO sentiment(document_id, segment_id, unit, char_start, char_end, "
            "polarity, dictionary) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (document_id, r.segment_id, unit, r.char_start, r.char_end, r.polarity, dictionary)
                for r in results
            ],
        )
        self.conn.commit()

    # -- 集計（可視化用） ------------------------------------------------------
    def timeseries(self, project_id: int, *, unit: str = "document") -> dict[int, float]:
        """年代 → 平均極性（年代メタデータのある文書）。"""
        rows = self.conn.execute(
            "SELECT d.year AS year, AVG(s.polarity) AS p "
            "FROM sentiment s JOIN document d ON d.id = s.document_id "
            "WHERE d.project_id = ? AND d.year IS NOT NULL AND s.unit = ? "
            "GROUP BY d.year ORDER BY d.year",
            (project_id, unit),
        ).fetchall()
        return {r["year"]: r["p"] for r in rows}

    def by_code(self, project_id: int) -> dict[int, list[float]]:
        """コード → そのコードセグメントの極性値リスト（ボックスプロット用）。"""
        rows = self.conn.execute(
            "SELECT seg.code_id AS cid, s.polarity AS p "
            "FROM sentiment s "
            "JOIN segment seg ON seg.id = s.segment_id "
            "JOIN code c ON c.id = seg.code_id "
            "WHERE c.project_id = ? AND s.unit = 'segment'",
            (project_id,),
        ).fetchall()
        out: dict[int, list[float]] = {}
        for r in rows:
            out.setdefault(r["cid"], []).append(r["p"])
        return out
