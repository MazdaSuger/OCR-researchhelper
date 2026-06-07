"""手動校正ウィジェット: 左＝画像＋行ボックス／右＝編集可能テキスト。

両ペインを双方向に同期し、校正後テキストの取得・`.md` 保存を提供する。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from shiryo_coder.modules.ocr.markdown_writer import write_markdown
from shiryo_coder.modules.ocr.result import OcrResult
from shiryo_coder.ui.correction.image_view import ImageBoxView
from shiryo_coder.ui.correction.model import CorrectionModel
from shiryo_coder.ui.correction.text_view import LineTextView


class CorrectionWidget(QWidget):
    """1 ページ分の OCR 結果を校正するウィジェット。"""

    saved = Signal(str)   # 保存先パス

    def __init__(
        self,
        image,
        result: OcrResult,
        *,
        metadata: dict[str, Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.model = CorrectionModel(result)
        self._metadata = dict(metadata or {})
        self._syncing = False

        self.image_view = ImageBoxView(self.model, image)
        self.text_view = LineTextView(self.model)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.image_view)
        splitter.addWidget(self.text_view)
        splitter.setSizes([600, 600])

        self.status = QLabel(self._status_text())
        save_button = QPushButton("校正を保存")
        save_button.clicked.connect(self._on_save_clicked)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.status)
        toolbar.addStretch(1)
        toolbar.addWidget(save_button)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter, 1)
        layout.addLayout(toolbar)

        # 双方向ワイヤリング
        self.image_view.line_clicked.connect(self._select_from_image)
        self.text_view.line_selected.connect(self._select_from_text)
        self.text_view.text_edited.connect(self._on_text_edited)

    # -- 同期 ------------------------------------------------------------------
    def _select(self, index: int) -> None:
        """両ペインの選択を index に合わせる（ループ防止つき）。"""
        if self._syncing:
            return
        self._syncing = True
        self.model.select(index)
        self.image_view.highlight(index)
        self.text_view.select_row(index)
        self._syncing = False

    def _select_from_image(self, index: int) -> None:
        self._select(index)

    def _select_from_text(self, index: int) -> None:
        self._select(index)

    def _on_text_edited(self, _index: int, _text: str) -> None:
        self.status.setText(self._status_text())

    # -- 保存 ------------------------------------------------------------------
    def corrected_text(self) -> str:
        return self.model.corrected_text()

    def corrected_result(self) -> OcrResult:
        return self.model.to_result()

    def save_markdown(self, out_path: Path | str, *, heading: str = "本文") -> Path:
        return write_markdown(out_path, self._metadata, self.corrected_text(), heading=heading)

    def _on_save_clicked(self) -> None:
        out = self._metadata.get("source_image")
        target = Path(out).with_suffix(".md") if out else Path("corrected.md")
        self.save_markdown(target)
        self.saved.emit(str(target))
        self.status.setText(f"保存しました: {target}")

    def _status_text(self) -> str:
        edited = sum(1 for line in self.model.lines if line.edited)
        return f"{len(self.model.lines)} 行 / 編集済み {edited} 行"
