"""信頼性検証の高水準 API（仕様書 3.5）。

コーディング結果を算出単位へ変換し、コーダー数に応じた一致係数を計算する。
不一致単位の抽出（協議用）とコーダー研修モードのフィードバックも提供する。
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from shiryo_coder.modules.coding.coding import CodingRepository
from shiryo_coder.modules.reliability import units as unit_mod
from shiryo_coder.modules.reliability.agreement import (
    cohens_kappa,
    fleiss_kappa,
    krippendorff_alpha,
)

GRANULARITIES = ("character", "sentence", "segment")


@dataclass
class ReliabilityResult:
    """一致係数の計算結果。"""

    method: str               # 'cohen' / 'fleiss' / 'krippendorff'
    value: float
    n_units: int
    coder_ids: list[int]
    granularity: str
    extra: dict = field(default_factory=dict)   # 例: krippendorff α 併記


@dataclass
class Disagreement:
    """不一致のあった単位。"""

    char_start: int
    char_end: int
    text: str
    labels: dict[int, int]    # coder_id → 0/1


@dataclass
class TrainingFeedback:
    """研修モード: マスターとの突き合わせ結果。"""

    kappa: float
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int
    missed: list[Disagreement]    # マスターは付与、研修者は未付与
    extra: list[Disagreement]     # 研修者は付与、マスターは未付与


class ReliabilityRepository:
    """document・segment からの一致率計算。"""

    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn
        self._coding = CodingRepository(db)

    # -- 準備 ------------------------------------------------------------------
    def _body(self, document_id: int) -> str:
        row = self.conn.execute(
            "SELECT body FROM document WHERE id = ?", (document_id,)
        ).fetchone()
        return row["body"] if row else ""

    def segments_by_coder(self, document_id: int, coder_ids: list[int]) -> dict[int, list]:
        all_segs = self._coding.segments_for_document(document_id)
        return {cid: [s for s in all_segs if s.coder_id == cid] for cid in coder_ids}

    def _units(self, document_id: int, granularity: str, body: str, all_segments) -> list:
        if granularity == "character":
            return unit_mod.character_spans(len(body))
        if granularity == "sentence":
            return unit_mod.sentence_spans(body)
        if granularity == "segment":
            return unit_mod.segment_atomic_spans(all_segments, len(body))
        raise ValueError(f"未知の粒度: {granularity}")

    def labels(
        self,
        document_id: int,
        code_id: int,
        coder_ids: list[int],
        granularity: str,
        *,
        min_overlap_ratio: float = 0.0,
    ) -> tuple[dict[int, list[int]], list]:
        body = self._body(document_id)
        by_coder = self.segments_by_coder(document_id, coder_ids)
        all_segs = [s for segs in by_coder.values() for s in segs]
        units = self._units(document_id, granularity, body, all_segs)
        return (
            unit_mod.coder_binary_labels(
                by_coder, code_id, units, min_overlap_ratio=min_overlap_ratio
            ),
            units,
        )

    # -- 係数 ------------------------------------------------------------------
    def compute(
        self,
        document_id: int,
        code_id: int,
        coder_ids: list[int],
        granularity: str = "character",
        *,
        min_overlap_ratio: float = 0.0,
    ) -> ReliabilityResult:
        """コーダー数に応じた係数を計算する（2 名=Cohen、3 名以上=Fleiss+α）。"""
        if len(coder_ids) < 2:
            raise ValueError("一致率の計算には 2 名以上のコーダーが必要です。")
        labels, units = self.labels(
            document_id, code_id, coder_ids, granularity, min_overlap_ratio=min_overlap_ratio
        )
        sequences = [labels[c] for c in coder_ids]

        if len(coder_ids) == 2:
            value = cohens_kappa(sequences[0], sequences[1])
            return ReliabilityResult("cohen", value, len(units), coder_ids, granularity)

        items = [[labels[c][u] for c in coder_ids] for u in range(len(units))]
        kappa = fleiss_kappa(items) if items else float("nan")
        alpha = krippendorff_alpha(sequences)
        return ReliabilityResult(
            "fleiss", kappa, len(units), coder_ids, granularity,
            extra={"krippendorff_alpha": alpha},
        )

    def pairwise_matrix(
        self,
        document_id: int,
        code_id: int,
        coder_ids: list[int],
        granularity: str = "character",
    ) -> dict[tuple[int, int], float]:
        """全コーダー対の Cohen's κ を返す。"""
        labels, _units = self.labels(document_id, code_id, coder_ids, granularity)
        result: dict[tuple[int, int], float] = {}
        for i, a in enumerate(coder_ids):
            for b in coder_ids[i + 1 :]:
                result[(a, b)] = cohens_kappa(labels[a], labels[b])
        return result

    # -- 不一致抽出 -------------------------------------------------------------
    def disagreements(
        self,
        document_id: int,
        code_id: int,
        coder_ids: list[int],
        granularity: str = "segment",
    ) -> list[Disagreement]:
        body = self._body(document_id)
        labels, units = self.labels(document_id, code_id, coder_ids, granularity)
        out: list[Disagreement] = []
        for u, (start, end) in enumerate(units):
            row = {c: labels[c][u] for c in coder_ids}
            if len(set(row.values())) > 1:        # 全員一致でない
                out.append(Disagreement(start, end, body[start:end], row))
        return out

    # -- 研修モード -------------------------------------------------------------
    def training_feedback(
        self,
        document_id: int,
        code_id: int,
        master_coder: int,
        trainee_coder: int,
        granularity: str = "segment",
    ) -> TrainingFeedback:
        body = self._body(document_id)
        labels, units = self.labels(
            document_id, code_id, [master_coder, trainee_coder], granularity
        )
        master, trainee = labels[master_coder], labels[trainee_coder]
        tp = fp = fn = tn = 0
        missed: list[Disagreement] = []
        extra: list[Disagreement] = []
        for u, (start, end) in enumerate(units):
            m, t = master[u], trainee[u]
            if m and t:
                tp += 1
            elif m and not t:
                fn += 1
                missed.append(Disagreement(start, end, body[start:end],
                                           {master_coder: 1, trainee_coder: 0}))
            elif t and not m:
                fp += 1
                extra.append(Disagreement(start, end, body[start:end],
                                          {master_coder: 0, trainee_coder: 1}))
            else:
                tn += 1
        return TrainingFeedback(
            kappa=cohens_kappa(master, trainee),
            true_positive=tp, false_positive=fp, false_negative=fn, true_negative=tn,
            missed=missed, extra=extra,
        )


def disagreements_to_csv(rows: list[Disagreement], coder_names: dict[int, str]) -> str:
    """不一致一覧を協議用 CSV 文字列に変換する。"""
    buffer = io.StringIO()
    coder_ids = list(coder_names)
    writer = csv.writer(buffer)
    writer.writerow(["start", "end", "text", *[coder_names[c] for c in coder_ids]])
    for d in rows:
        writer.writerow(
            [d.char_start, d.char_end, d.text, *[d.labels.get(c, "") for c in coder_ids]]
        )
    return buffer.getvalue()
