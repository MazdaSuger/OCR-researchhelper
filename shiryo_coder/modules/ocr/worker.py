"""バックグラウンド OCR 実行（QThreadPool / QRunnable）。

仕様書 3.1「OCR 実行: バックグラウンドキュー（QThreadPool）でバッチ処理、進捗バー」。
PySide6 は遅延 import し、GUI 非依存のパイプライン本体（pipeline.py）と分離する。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from shiryo_coder.modules.ocr.pipeline import IngestedDocument, OcrPipeline


class OcrSignals(QObject):
    """OCR ジョブのシグナル束。"""

    progress = Signal(str, int, int)        # source, current, total
    finished = Signal(str, object)          # source, IngestedDocument
    failed = Signal(str, str)               # source, error message


class OcrRunnable(QRunnable):
    """1 入力分の OCR ジョブ。"""

    def __init__(
        self,
        pipeline: OcrPipeline,
        path: Path | str,
        *,
        signals: OcrSignals,
        **ingest_kwargs: Any,
    ) -> None:
        super().__init__()
        self.pipeline = pipeline
        self.path = str(path)
        self.signals = signals
        self.ingest_kwargs = ingest_kwargs

    @Slot()
    def run(self) -> None:
        def on_progress(current: int, total: int) -> None:
            self.signals.progress.emit(self.path, current, total)

        try:
            doc: IngestedDocument = self.pipeline.ingest(
                self.path, progress=on_progress, **self.ingest_kwargs
            )
            self.signals.finished.emit(self.path, doc)
        except Exception as exc:  # noqa: BLE001 - GUI へ転送するため広く捕捉
            self.signals.failed.emit(self.path, f"{type(exc).__name__}: {exc}")


class OcrQueue:
    """複数入力をスレッドプールで処理するキュー。"""

    def __init__(self, pipeline: OcrPipeline, *, max_threads: int | None = None) -> None:
        self.pipeline = pipeline
        self.signals = OcrSignals()
        self.pool = QThreadPool.globalInstance()
        if max_threads is not None:
            self.pool.setMaxThreadCount(max_threads)

    def submit(self, path: Path | str, **ingest_kwargs: Any) -> None:
        """1 入力をキューに投入する。"""
        runnable = OcrRunnable(
            self.pipeline, path, signals=self.signals, **ingest_kwargs
        )
        self.pool.start(runnable)

    def submit_many(self, paths: list[Path | str], **ingest_kwargs: Any) -> None:
        for path in paths:
            self.submit(path, **ingest_kwargs)

    def wait_for_done(self, timeout_ms: int = -1) -> bool:
        """全ジョブの完了を待つ（テスト・CLI 用）。"""
        return self.pool.waitForDone(timeout_ms)
