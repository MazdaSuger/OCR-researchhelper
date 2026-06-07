"""前処理プレビュー: 各ステップを個別に切り替えて結果を確認する（仕様書 3.1）。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from shiryo_coder.modules.ocr.preprocess import PreprocessConfig, preprocess
from shiryo_coder.ui.correction.image_view import to_qpixmap

_PREVIEW_MAX = 480


class PreprocessPreviewWidget(QWidget):
    """前処理の ON/OFF をトグルし、結果画像をプレビューするウィジェット。"""

    config_changed = Signal()

    def __init__(self, image=None, parent=None) -> None:
        super().__init__(parent)
        self._source = image

        self._cb_grayscale = QCheckBox("グレースケール")
        self._cb_deskew = QCheckBox("傾き補正")
        self._cb_denoise = QCheckBox("ノイズ除去")
        self._cb_binarize = QCheckBox("二値化")
        for cb in self._checkboxes():
            cb.setChecked(True)
            cb.toggled.connect(self._on_toggled)

        self._preview = QLabel("（プレビューなし）")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumSize(240, 200)
        self._preview.setStyleSheet("border: 1px solid #ccc; background: #fafafa;")

        controls = QHBoxLayout()
        for cb in self._checkboxes():
            controls.addWidget(cb)
        controls.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self._preview, 1)

        self._refresh()

    def _checkboxes(self) -> tuple[QCheckBox, ...]:
        return (self._cb_grayscale, self._cb_deskew, self._cb_denoise, self._cb_binarize)

    # -- 公開 API ---------------------------------------------------------------
    def config(self) -> PreprocessConfig:
        return PreprocessConfig(
            grayscale=self._cb_grayscale.isChecked(),
            deskew=self._cb_deskew.isChecked(),
            denoise=self._cb_denoise.isChecked(),
            binarize=self._cb_binarize.isChecked(),
        )

    def set_image(self, image) -> None:
        self._source = image
        self._refresh()

    def processed_image(self):
        """現在の設定で前処理した画像（プレビュー用に縮小済み）を返す。"""
        if self._source is None:
            return None
        return preprocess(self._downscaled(), self.config())

    # -- 内部 ------------------------------------------------------------------
    def _downscaled(self):
        import cv2

        img = self._source
        h, w = img.shape[:2]
        longest = max(h, w)
        if longest <= _PREVIEW_MAX:
            return img
        scale = _PREVIEW_MAX / longest
        return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    def _on_toggled(self, _checked: bool) -> None:
        self._refresh()
        self.config_changed.emit()

    def _refresh(self) -> None:
        processed = self.processed_image()
        if processed is None:
            self._preview.setText("（プレビューなし）")
            return
        self._preview.setPixmap(to_qpixmap(processed))
