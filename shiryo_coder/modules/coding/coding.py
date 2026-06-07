"""コーディング（コード付与セグメント）の管理と重なりレイアウト。仕様書 3.3。

セグメントは「文字オフセット start/end + コーダー ID + コード ID」。重複・部分重なり・
複数コーダーによる同一箇所のコーディングを許容する。
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass


@dataclass
class CodedSegment:
    """コード付与された 1 セグメント（表示用の付帯情報込み）。"""

    id: int
    document_id: int
    code_id: int
    coder_id: int
    char_start: int
    char_end: int
    status: str
    code_name: str
    color: str | None
    coder_name: str | None = None

    def overlaps(self, start: int, end: int) -> bool:
        return self.char_start < end and start < self.char_end


def assign_layers(segments: list[CodedSegment]) -> dict[int, int]:
    """重なるセグメントを別レイヤーへ割り当てる（積層下線表示用）。

    同一レイヤー内のセグメントは重ならない。区間分割の貪欲法で最小レイヤー数を狙う。
    返り値は segment.id → レイヤー番号（0 始まり）。
    """
    ordered = sorted(segments, key=lambda s: (s.char_start, s.char_end, s.id))
    layers: dict[int, int] = {}
    # ヒープ: (空きになる位置=その層の現在 end, 層番号)
    free: list[tuple[int, int]] = []
    next_layer = 0
    for seg in ordered:
        if free and free[0][0] <= seg.char_start:
            _end, layer = heapq.heappop(free)
        else:
            layer = next_layer
            next_layer += 1
        layers[seg.id] = layer
        heapq.heappush(free, (seg.char_end, layer))
    return layers


class CodingRepository:
    """segment テーブルに対するコーディング操作。"""

    def __init__(self, db) -> None:
        self.db = db
        self.conn = db.conn

    # -- 付与 / 解除 / 状態 -----------------------------------------------------
    def add_coding(
        self,
        document_id: int,
        code_id: int,
        coder_id: int,
        char_start: int,
        char_end: int,
        *,
        status: str = "draft",
    ) -> int:
        """コードを付与する。同一(doc,code,coder,範囲)が既にあればそれを返す。"""
        if char_end <= char_start:
            raise ValueError("char_end は char_start より大きい必要があります。")
        existing = self.conn.execute(
            "SELECT id FROM segment WHERE document_id=? AND code_id=? AND coder_id=? "
            "AND char_start=? AND char_end=?",
            (document_id, code_id, coder_id, char_start, char_end),
        ).fetchone()
        if existing is not None:
            return int(existing["id"])
        row = self.conn.execute(
            "INSERT INTO segment(document_id, code_id, coder_id, char_start, char_end, status) "
            "VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
            (document_id, code_id, coder_id, char_start, char_end, status),
        ).fetchone()
        self.conn.commit()
        return int(row["id"])

    def remove_coding(self, segment_id: int) -> None:
        self.conn.execute("DELETE FROM segment WHERE id = ?", (segment_id,))
        self.conn.commit()

    def set_status(self, segment_id: int, status: str) -> None:
        """承認ワークフロー: draft → reviewed → confirmed。"""
        self.conn.execute(
            "UPDATE segment SET status = ? WHERE id = ?", (status, segment_id)
        )
        self.conn.commit()

    # -- 参照 ------------------------------------------------------------------
    def segments_for_document(
        self, document_id: int, *, coder_id: int | None = None
    ) -> list[CodedSegment]:
        sql = (
            "SELECT s.id, s.document_id, s.code_id, s.coder_id, s.char_start, s.char_end, "
            "       s.status, c.name AS code_name, c.color, cr.name AS coder_name "
            "FROM segment s "
            "JOIN code c ON c.id = s.code_id "
            "LEFT JOIN coder cr ON cr.id = s.coder_id "
            "WHERE s.document_id = ?"
        )
        params: list = [document_id]
        if coder_id is not None:
            sql += " AND s.coder_id = ?"
            params.append(coder_id)
        sql += " ORDER BY s.char_start, s.char_end, s.id"
        return [self._segment(r) for r in self.conn.execute(sql, params).fetchall()]

    def codings_at(self, document_id: int, offset: int) -> list[CodedSegment]:
        """指定文字オフセットを含む全コーディング（1 文字に複数コード）。"""
        return [
            s
            for s in self.segments_for_document(document_id)
            if s.char_start <= offset < s.char_end
        ]

    def code_frequencies(self, project_id: int) -> dict[int, int]:
        rows = self.conn.execute(
            "SELECT s.code_id AS cid, COUNT(*) AS n FROM segment s "
            "JOIN code c ON c.id = s.code_id WHERE c.project_id = ? GROUP BY s.code_id",
            (project_id,),
        ).fetchall()
        return {r["cid"]: r["n"] for r in rows}

    def representative_texts(self, project_id: int) -> dict[int, list[str]]:
        """コードごとの代表セグメントの実テキスト（AI 支援コーディングの素材）。"""
        rows = self.conn.execute(
            "SELECT s.code_id AS cid, "
            "       SUBSTR(d.body, s.char_start + 1, s.char_end - s.char_start) AS text "
            "FROM segment s "
            "JOIN code c ON c.id = s.code_id "
            "JOIN document d ON d.id = s.document_id "
            "WHERE c.project_id = ?",
            (project_id,),
        ).fetchall()
        out: dict[int, list[str]] = {}
        for r in rows:
            if r["text"]:
                out.setdefault(r["cid"], []).append(r["text"])
        return out

    @staticmethod
    def _segment(r) -> CodedSegment:
        return CodedSegment(
            id=r["id"], document_id=r["document_id"], code_id=r["code_id"],
            coder_id=r["coder_id"], char_start=r["char_start"], char_end=r["char_end"],
            status=r["status"], code_name=r["code_name"], color=r["color"],
            coder_name=r["coder_name"],
        )
