"""取り込み設定ダイアログ（仕様書 3.1: 自動判定の提示→ユーザー確認）。

エンジン・言語・書字方向・前処理を確認/上書きし、`ImportSettings` を返す。
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)

from shiryo_coder.modules.ocr.detect import OcrProposal
from shiryo_coder.modules.ocr.engines import available_engines
from shiryo_coder.modules.ocr.preprocess import PreprocessConfig
from shiryo_coder.ui.ocr_import.preprocess_preview import PreprocessPreviewWidget

_LANGUAGES = [("自動判定", None), ("日本語 (ja)", "ja"), ("英語 (en)", "en")]


@dataclass
class ImportSettings:
    """取り込み実行に必要な確定設定。"""

    engine: str
    language: str | None      # None = 自動判定
    vertical: bool
    preprocess: PreprocessConfig


class ImportSettingsDialog(QDialog):
    """先頭ページのプレビューつき取り込み設定ダイアログ。"""

    def __init__(
        self,
        first_image=None,
        *,
        proposal: OcrProposal | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("OCR 取り込み設定")

        # エンジン選択（可用性を併記）
        self._engine = QComboBox()
        first_available = None
        for name, ok in available_engines().items():
            self._engine.addItem(f"{name}　{'✓ 利用可' if ok else '✗ 未設定'}", name)
            if ok and first_available is None:
                first_available = self._engine.count() - 1
        if first_available is not None:
            self._engine.setCurrentIndex(first_available)

        # 言語
        self._language = QComboBox()
        for label, code in _LANGUAGES:
            self._language.addItem(label, code)

        # 方向
        self._vertical = QCheckBox("縦書き（PSM 5）")

        # 自動判定の提示
        self._proposal_label = QLabel("自動判定: —")
        if proposal is not None:
            self._proposal_label.setText(
                f"自動判定: {proposal.label}（信頼度 {proposal.confidence:.2f}）"
            )
            self._select_language(proposal.language)
            self._vertical.setChecked(proposal.vertical)

        form = QFormLayout()
        form.addRow("エンジン", self._engine)
        form.addRow("言語", self._language)
        form.addRow("方向", self._vertical)

        settings_box = QGroupBox("認識設定")
        settings_box.setLayout(form)

        self._preview = PreprocessPreviewWidget(first_image)
        preview_box = QGroupBox("前処理（プレビュー）")
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.addWidget(self._preview)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._proposal_label)
        layout.addWidget(settings_box)
        layout.addWidget(preview_box, 1)
        layout.addWidget(buttons)

    def _select_language(self, code: str | None) -> None:
        for i in range(self._language.count()):
            if self._language.itemData(i) == code:
                self._language.setCurrentIndex(i)
                return

    # -- 公開 API ---------------------------------------------------------------
    def settings(self) -> ImportSettings:
        return ImportSettings(
            engine=self._engine.currentData(),
            language=self._language.currentData(),
            vertical=self._vertical.isChecked(),
            preprocess=self._preview.config(),
        )
