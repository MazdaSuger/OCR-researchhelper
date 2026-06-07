"""バッチ取り込みの進捗表示（仕様書 3.1: 進捗バー）。

`OcrQueue` のシグナルに接続し、完了/失敗の件数と進捗バー・ログを更新する。
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class BatchProgressWidget(QWidget):
    """OCR バッチの進捗バー＋ログ。"""

    all_done = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._total = 0
        self._done = 0

        self._status = QLabel("待機中")
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._log = QListWidget()

        layout = QVBoxLayout(self)
        layout.addWidget(self._status)
        layout.addWidget(self._bar)
        layout.addWidget(self._log, 1)

    def set_total(self, total: int) -> None:
        self._total = total
        self._done = 0
        self._update_status()

    def bind(self, queue) -> None:
        """OcrQueue のシグナルを購読する。"""
        queue.signals.progress.connect(self._on_progress)
        queue.signals.finished.connect(self._on_finished)
        queue.signals.failed.connect(self._on_failed)

    # -- スロット ---------------------------------------------------------------
    def _on_progress(self, source: str, current: int, total: int) -> None:
        if total > 0 and self._total > 0:
            # 全体進捗 = (完了ページ + 現在ファイルの途中) / おおよその総量
            self._bar.setValue(int(100 * (self._done + current / total) / self._total))

    def _on_finished(self, source: str, doc) -> None:
        self._done += 1
        title = getattr(doc, "title", source)
        conf = getattr(doc, "confidence", None)
        conf_s = f"{conf:.2f}" if conf is not None else "N/A"
        flag = " ⚠要校正" if getattr(doc, "metadata", {}).get("needs_review") else ""
        self._log.addItem(f"✓ {title}（信頼度 {conf_s}）{flag}")
        self._after_item()

    def _on_failed(self, source: str, message: str) -> None:
        self._done += 1
        self._log.addItem(f"✗ {source}: {message}")
        self._after_item()

    def _after_item(self) -> None:
        self._update_status()
        if self._total and self._done >= self._total:
            self._bar.setValue(100)
            self.all_done.emit()

    def _update_status(self) -> None:
        self._status.setText(f"取り込み {self._done} / {self._total} 件")

    # -- テスト/参照用 ----------------------------------------------------------
    @property
    def done_count(self) -> int:
        return self._done

    @property
    def log_count(self) -> int:
        return self._log.count()
