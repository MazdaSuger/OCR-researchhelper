"""OCR 取り込みパイプライン: 入力 → 前処理 → OCR → `.md` / DB。

仕様書 3.1 の取り込みワークフローを 1 本のオーケストレーションにまとめる。
GUI からはこの `OcrPipeline` を `worker` 経由でバックグラウンド実行する。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from shiryo_coder.modules.ocr.detect import (
    OcrProposal,
    detect_language,
    propose_settings,
)
from shiryo_coder.modules.ocr.engines.base import OcrEngine
from shiryo_coder.modules.ocr.inputs import enumerate_pages
from shiryo_coder.modules.ocr.markdown_writer import write_markdown
from shiryo_coder.modules.ocr.preprocess import PreprocessConfig, preprocess
from shiryo_coder.modules.ocr.result import OcrResult

# (current_page, total_pages) を受け取る進捗コールバック
ProgressCallback = Callable[[int, int], None]

# DB の document テーブルに直接対応する列
_DOCUMENT_COLUMNS = (
    "title", "author", "year", "era", "language",
    "script", "source_image", "ocr_engine", "confidence",
)


@dataclass
class IngestedDocument:
    """1 入力（複数ページ可）の取り込み結果。"""

    title: str
    body: str
    metadata: dict[str, Any]
    pages: list[OcrResult] = field(default_factory=list)
    source: str | None = None
    proposal: OcrProposal | None = None

    @property
    def confidence(self) -> float | None:
        confs = [p.confidence for p in self.pages if p.confidence is not None]
        return sum(confs) / len(confs) if confs else None

    @property
    def page_count(self) -> int:
        return len(self.pages)


@dataclass
class OcrPipeline:
    """OCR 取り込みのオーケストレータ。"""

    engine: OcrEngine
    preprocess_config: PreprocessConfig = field(default_factory=PreprocessConfig)
    pdf_dpi: int = 200
    page_separator: str = "\n\n"
    #: この信頼度を下回るページは「要校正」として metadata に印を付ける
    review_threshold: float = 0.6

    def ingest(
        self,
        path: Path | str,
        *,
        title: str | None = None,
        language: str | None = None,
        vertical: bool | None = None,
        era: str | None = None,
        author: str | None = None,
        year: int | None = None,
        metadata: dict[str, Any] | None = None,
        progress: ProgressCallback | None = None,
    ) -> IngestedDocument:
        """入力を OCR し、メタデータ付きの取り込み結果を返す。"""
        path = Path(path)
        pages = enumerate_pages(path, pdf_dpi=self.pdf_dpi)
        if not pages:
            raise ValueError(f"OCR 対象のページがありません: {path}")

        total = len(pages)
        results: list[OcrResult] = []
        resolved_lang = language
        resolved_vertical = vertical
        proposal: OcrProposal | None = None

        for i, page in enumerate(pages):
            image = page.load()
            processed = preprocess(image, self.preprocess_config)

            # 先頭ページを縮小推論し、言語/方向を提案（明示指定がない項目のみ採用）
            if i == 0 and (resolved_lang is None or resolved_vertical is None):
                proposal = propose_settings(processed, self.engine)
                if resolved_lang is None and proposal.language != "und":
                    resolved_lang = proposal.language
                if resolved_vertical is None:
                    resolved_vertical = proposal.vertical

            result = self.engine.recognize(
                processed,
                vertical=bool(resolved_vertical),
                language=resolved_lang,
            )
            results.append(result)
            if progress is not None:
                progress(i + 1, total)

        body = self.page_separator.join(r.text for r in results).strip()
        if resolved_lang is None:
            resolved_lang = detect_language(body)

        doc = IngestedDocument(
            title=title or path.stem,
            body=body,
            metadata={},
            pages=results,
            source=str(path),
            proposal=proposal,
        )
        conf = doc.confidence
        needs_review = conf is not None and conf < self.review_threshold
        doc.metadata = {
            "title": doc.title,
            "author": author,
            "year": year,
            "era": era,
            "language": resolved_lang,
            "script": "vertical" if resolved_vertical else "horizontal",
            "source_image": str(path),
            "ocr_engine": self.engine.name,
            "confidence": round(conf, 4) if conf is not None else None,
            "pages": total,
            "needs_review": needs_review or None,
            **(metadata or {}),
        }
        return doc

    def save_markdown(
        self, doc: IngestedDocument, out_path: Path | str, *, heading: str = "本文"
    ) -> Path:
        """取り込み結果を `.md`（YAML Front Matter 付き）として書き出す。"""
        return write_markdown(out_path, doc.metadata, doc.body, heading=heading)

    def persist(self, db, project_id: int, doc: IngestedDocument) -> int:
        """取り込み結果を document テーブルに 1 行として保存し、その id を返す。"""
        meta = dict(doc.metadata)
        columns = {k: meta.pop(k, None) for k in _DOCUMENT_COLUMNS}
        extras = {k: v for k, v in meta.items() if v is not None}
        row = db.conn.execute(
            """
            INSERT INTO document(
                project_id, title, body, file_path,
                author, year, era, language, script,
                source_image, ocr_engine, confidence, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                project_id,
                columns["title"] or doc.title,
                doc.body,
                doc.source,
                columns["author"],
                columns["year"],
                columns["era"],
                columns["language"],
                columns["script"],
                columns["source_image"],
                columns["ocr_engine"],
                columns["confidence"],
                json.dumps(extras, ensure_ascii=False) if extras else None,
            ),
        ).fetchone()
        db.conn.commit()
        return int(row["id"])
