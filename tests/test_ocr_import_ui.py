"""OCR 取り込み GUI（3.1）のテスト（offscreen）。

前処理プレビュー・設定ダイアログ・バッチ進捗・QThreadPool キュー・
MainWindow の取り込みフローを検証する。
"""

from __future__ import annotations

import os
import shutil

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
np = pytest.importorskip("numpy")
pytest.importorskip("cv2")
Image = pytest.importorskip("PIL.Image")
ImageDraw = pytest.importorskip("PIL.ImageDraw")
ImageFont = pytest.importorskip("PIL.ImageFont")

_HAS_TESSERACT = shutil.which("tesseract") is not None
_needs_tesseract = pytest.mark.skipif(not _HAS_TESSERACT, reason="tesseract バイナリが必要")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _white(w=200, h=120):
    return np.full((h, w, 3), 255, dtype=np.uint8)


def _hello_png(path):
    img = Image.new("RGB", (560, 140), "white")
    ImageDraw.Draw(img).text(
        (20, 40), "HELLO WORLD", fill="black", font=ImageFont.truetype("DejaVuSans.ttf", 48)
    )
    img.save(path)
    return str(path)


# -- 前処理プレビュー ------------------------------------------------------------
def test_preprocess_preview_config_toggles(qapp):
    from shiryo_coder.ui.ocr_import import PreprocessPreviewWidget

    w = PreprocessPreviewWidget(_white())
    assert w.config().binarize is True
    w._cb_binarize.setChecked(False)
    assert w.config().binarize is False
    # プレビューが生成される（二値化 OFF なら出力はグレースケール 2 次元）
    out = w.processed_image()
    assert out is not None
    w.deleteLater()


# -- 設定ダイアログ --------------------------------------------------------------
def test_import_dialog_presets_from_proposal(qapp):
    from shiryo_coder.modules.ocr.detect import OcrProposal
    from shiryo_coder.ui.ocr_import import ImportSettingsDialog

    proposal = OcrProposal(
        language="ja", vertical=True, confidence=0.8, script="Japanese", label="日本語縦書き"
    )
    dlg = ImportSettingsDialog(_white(), proposal=proposal)
    settings = dlg.settings()
    assert settings.language == "ja"
    assert settings.vertical is True
    assert settings.engine == "tesseract"          # 既定で利用可能なエンジン
    assert settings.preprocess.binarize is True
    dlg.deleteLater()


# -- QThreadPool キュー + 進捗 ---------------------------------------------------
@_needs_tesseract
def test_ocr_queue_runs_batch_and_updates_progress(qapp, tmp_path):
    from shiryo_coder.modules.ocr import OcrPipeline
    from shiryo_coder.modules.ocr.engines import get_engine
    from shiryo_coder.modules.ocr.worker import OcrQueue
    from shiryo_coder.ui.ocr_import import BatchProgressWidget

    paths = [_hello_png(tmp_path / f"p{i}.png") for i in range(2)]
    queue = OcrQueue(OcrPipeline(engine=get_engine("tesseract")))
    progress = BatchProgressWidget()
    progress.set_total(len(paths))
    progress.bind(queue)

    results = []
    queue.signals.finished.connect(lambda src, doc: results.append(doc))

    queue.submit_many(paths, language="en")
    assert queue.wait_for_done(30_000)
    qapp.processEvents()                            # キュー済みシグナルを配送

    assert len(results) == 2
    assert progress.log_count == 2
    assert all("HELLO" in d.body.upper() for d in results)


# -- MainWindow バッチフロー -----------------------------------------------------
@_needs_tesseract
def test_main_window_start_batch_persists_documents(qapp, tmp_path):
    from shiryo_coder.db import Database
    from shiryo_coder.ui.main_window import MainWindow
    from shiryo_coder.ui.ocr_import import ImportSettings
    from shiryo_coder.modules.ocr.preprocess import PreprocessConfig

    db = Database(tmp_path / "app.db")
    db.initialize()
    window = MainWindow(db)

    paths = [_hello_png(tmp_path / f"d{i}.png") for i in range(2)]
    settings = ImportSettings(
        engine="tesseract", language="en", vertical=False, preprocess=PreprocessConfig()
    )
    queue = window.start_batch(paths, settings)
    assert queue.wait_for_done(30_000)
    qapp.processEvents()

    rows = db.conn.execute("SELECT title, body FROM document").fetchall()
    assert len(rows) == 2
    assert window.doc_list.count() == 2
    db.close()
    window.deleteLater()
