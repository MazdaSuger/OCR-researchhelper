"""手動校正画面（3.1）のテスト。

`CorrectionModel` は Qt 非依存で常にテストする。ウィジェットは PySide6 が
あるときのみ offscreen プラットフォームで検証する。
"""

from __future__ import annotations

import os

import pytest

from shiryo_coder.modules.ocr.result import BoundingBox, OcrLine, OcrResult
from shiryo_coder.ui.correction.model import CorrectionModel


def _sample_result() -> OcrResult:
    lines = [
        OcrLine("第一行", BoundingBox(10, 10, 100, 20)),
        OcrLine("第二行", BoundingBox(10, 40, 100, 20)),
        OcrLine("小箱", BoundingBox(20, 42, 10, 10)),     # 第二行に重なる小ボックス
    ]
    return OcrResult(text="第一行\n第二行\n小箱", engine="test", lines=lines)


# -- 純モデル -------------------------------------------------------------------
def test_model_initial_state():
    model = CorrectionModel(_sample_result())
    assert len(model.lines) == 3
    assert not model.is_dirty()
    assert model.corrected_text() == "第一行\n第二行\n小箱"


def test_model_hit_test_returns_smallest_box():
    model = CorrectionModel(_sample_result())
    assert model.line_at_point(50, 15) == 0          # 第一行のみ
    # (25, 46) は第二行(index1)と小箱(index2)に重なる → 面積最小の小箱
    assert model.line_at_point(25, 46) == 2
    assert model.line_at_point(500, 500) is None     # どこにもない


def test_model_edit_and_export():
    model = CorrectionModel(_sample_result())
    model.set_corrected(1, "第二行（校正）")
    assert model.is_dirty()
    assert model.lines[1].edited
    assert model.corrected_text() == "第一行\n第二行（校正）\n小箱"

    result = model.to_result()
    assert result.text == model.corrected_text()
    assert result.lines[1].text == "第二行（校正）"
    assert result.lines[1].bbox == BoundingBox(10, 40, 100, 20)


def test_model_select_validates_index():
    model = CorrectionModel(_sample_result())
    model.select(2)
    assert model.selected_index == 2
    model.select(None)
    assert model.selected_index is None
    with pytest.raises(IndexError):
        model.select(99)


# -- ウィジェット（offscreen） ---------------------------------------------------
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def widget(qapp):
    import numpy as np

    from shiryo_coder.ui.correction import CorrectionWidget

    image = np.full((80, 140, 3), 255, dtype=np.uint8)   # 白画像
    w = CorrectionWidget(image, _sample_result(), metadata={"title": "テスト"})
    yield w
    w.deleteLater()


def test_widget_builds_rows(widget):
    assert widget.text_view.rowCount() == 3
    assert widget.text_view.item(0, 1).text() == "第一行"


def test_image_click_syncs_text_selection(widget):
    # 画像クリック相当: line_clicked を発火
    widget.image_view.line_clicked.emit(1)
    assert widget.model.selected_index == 1
    assert widget.text_view.currentRow() == 1


def test_text_selection_syncs_image_highlight(widget):
    widget.text_view.line_selected.emit(2)
    assert widget.model.selected_index == 2
    # 強調されたボックスのみ太線ペン
    from shiryo_coder.ui.correction.image_view import _SELECTED_PEN

    rect = widget.image_view._rects[2]
    assert rect.pen().width() == _SELECTED_PEN.width()


def test_editing_cell_updates_model_and_export(widget, tmp_path):
    item = widget.text_view.item(0, 1)
    item.setText("第一行（修正）")
    assert widget.model.lines[0].corrected == "第一行（修正）"
    assert widget.model.is_dirty()

    out = widget.save_markdown(tmp_path / "c.md")
    from shiryo_coder.modules.ocr.markdown_writer import read_markdown

    meta, body = read_markdown(out)
    assert meta["title"] == "テスト"
    assert body.startswith("第一行（修正）")


def test_no_signal_loop_on_programmatic_select(widget):
    # 相互ジャンプで無限ループや多重選択が起きないこと
    widget.image_view.line_clicked.emit(0)
    widget.text_view.line_selected.emit(1)
    widget.image_view.line_clicked.emit(2)
    assert widget.model.selected_index == 2
    assert widget.text_view.currentRow() == 2


# -- 実 OCR 結果からの校正画面 ---------------------------------------------------
import shutil  # noqa: E402


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract バイナリが必要")
def test_correction_widget_from_real_ocr(qapp):
    pytest.importorskip("cv2")
    from PIL import Image, ImageDraw, ImageFont

    from shiryo_coder.modules.ocr import get_engine
    from shiryo_coder.modules.ocr.engines.tesseract import _to_pil  # noqa: F401
    from shiryo_coder.ui.correction import CorrectionWidget

    img = Image.new("RGB", (640, 200), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("DejaVuSans.ttf", 40)
    draw.text((20, 20), "FIRST LINE", fill="black", font=font)
    draw.text((20, 110), "SECOND LINE", fill="black", font=font)

    import numpy as np

    arr = np.asarray(img)[:, :, ::-1]  # RGB->BGR
    result = get_engine("tesseract").recognize(arr, language="en")
    assert len(result.lines) >= 2

    w = CorrectionWidget(arr, result, metadata={"source_image": "x.png"})
    assert w.text_view.rowCount() == len(result.lines)
    # 1 行目を編集 → エクスポートに反映
    w.text_view.item(0, 1).setText("CORRECTED LINE")
    assert "CORRECTED LINE" in w.corrected_text()
    w.deleteLater()
