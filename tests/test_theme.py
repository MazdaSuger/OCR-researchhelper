"""テーマ適用（白・オレンジ・黒）のテスト（offscreen）。"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from shiryo_coder.ui.theme import PALETTE, apply_theme, stylesheet


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_stylesheet_contains_palette_colors():
    css = stylesheet()
    assert PALETTE["accent"] in css            # オレンジ
    assert PALETTE["text"] in css              # 黒
    assert PALETTE["bg"] in css                # 白
    # 主要セレクタが含まれる
    for selector in ("QPushButton", "QTabBar::tab", "QHeaderView::section", "QProgressBar::chunk"):
        assert selector in css


def test_apply_theme_sets_app_stylesheet(qapp):
    apply_theme(qapp)
    assert PALETTE["accent"] in qapp.styleSheet()

    # ウィジェットにカスケードして適用される
    from PySide6.QtWidgets import QPushButton

    btn = QPushButton("テスト")
    btn.ensurePolished()
    assert qapp.styleSheet() != ""
    btn.deleteLater()
