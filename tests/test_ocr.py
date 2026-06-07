"""OCR 取り込みモジュール（3.1）のテスト。

重い依存（cv2/pytesseract/pypdfium2）と tesseract バイナリが必要なテストは、
未導入の環境では自動的にスキップされる。
"""

from __future__ import annotations

import os
import shutil
import zipfile

import pytest

from shiryo_coder.modules.ocr.detect import detect_language
from shiryo_coder.modules.ocr.engines import available_engines, engine_names, get_engine
from shiryo_coder.modules.ocr.markdown_writer import read_markdown, write_markdown
from shiryo_coder.modules.ocr.result import BoundingBox, OcrResult, OcrWord

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
Image = pytest.importorskip("PIL.Image")
ImageDraw = pytest.importorskip("PIL.ImageDraw")
ImageFont = pytest.importorskip("PIL.ImageFont")

_HAS_TESSERACT = shutil.which("tesseract") is not None
_needs_tesseract = pytest.mark.skipif(not _HAS_TESSERACT, reason="tesseract バイナリが必要")

_CJK_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
_HAS_CJK = os.path.exists(_CJK_FONT)
_needs_japanese = pytest.mark.skipif(
    not (_HAS_TESSERACT and _HAS_CJK), reason="tesseract + CJK フォントが必要"
)


# -- フィクスチャ ----------------------------------------------------------------
def _text_image(text: str, *, size=(640, 160), font_size=56) -> "Image.Image":
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    draw.text((20, 40), text, fill="black", font=font)
    return img


def _jp_horizontal(text: str) -> "np.ndarray":
    img = Image.new("RGB", (900, 110), "white")
    ImageDraw.Draw(img).text((15, 28), text, fill="black", font=ImageFont.truetype(_CJK_FONT, 44))
    return np.ascontiguousarray(np.asarray(img)[:, :, ::-1])


def _jp_vertical(chars: str, *, step: int = 95) -> "np.ndarray":
    height = 40 + len(chars) * step
    img = Image.new("RGB", (120, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_CJK_FONT, 56)
    for i, ch in enumerate(chars):
        draw.text((30, 20 + i * step), ch, fill="black", font=font)
    return np.ascontiguousarray(np.asarray(img)[:, :, ::-1])


@pytest.fixture
def english_png(tmp_path):
    path = tmp_path / "hello.png"
    _text_image("HELLO WORLD").save(path)
    return path


# -- 純データ型 -----------------------------------------------------------------
def test_bounding_box_union():
    a = BoundingBox(0, 0, 10, 10)
    b = BoundingBox(20, 5, 10, 10)
    u = a.union(b)
    assert u.as_tuple() == (0, 0, 30, 15)


def test_ocr_result_from_words_groups_lines_and_confidence():
    words = [
        OcrWord("Hello", BoundingBox(0, 0, 50, 20), 0.9, line_index=0),
        OcrWord("World", BoundingBox(60, 0, 50, 20), 0.8, line_index=0),
        OcrWord("Next", BoundingBox(0, 30, 40, 20), 1.0, line_index=1),
    ]
    result = OcrResult.from_words(words, engine="test")
    assert len(result.lines) == 2
    assert result.lines[0].text == "Hello World"
    assert result.lines[0].bbox.as_tuple() == (0, 0, 110, 20)
    assert result.confidence == pytest.approx((0.9 + 0.8 + 1.0) / 3)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("これは日本語の史料です", "ja"),
        ("This is an English source", "en"),
        ("1867 年 大政奉還", "ja"),
        ("12345 !!!", "und"),
    ],
)
def test_detect_language(text, expected):
    assert detect_language(text) == expected


# -- Markdown 入出力 ------------------------------------------------------------
def test_markdown_roundtrip(tmp_path):
    meta = {
        "title": "大政奉還上表文",
        "author": "徳川慶喜",
        "year": 1867,
        "era": "江戸後期",
        "language": "ja",
        "script": "vertical",
        "confidence": 0.94,
        "custom_field": "値",
    }
    body = "朕惟フニ我皇祖皇宗國ヲ肇ムルコト宏遠ニ"
    path = write_markdown(tmp_path / "doc.md", meta, body)

    text = path.read_text(encoding="utf-8")
    # 標準キーが定義順に並ぶ
    assert text.index("title:") < text.index("author:") < text.index("year:")

    parsed_meta, parsed_body = read_markdown(path)
    assert parsed_meta == meta
    assert parsed_body == body


# -- エンジンレジストリ ----------------------------------------------------------
def test_engine_registry_lists_all_engines():
    names = engine_names()
    assert {"tesseract", "ndlocr_lite", "google_vision", "vision_llm"} <= set(names)


def test_unconfigured_api_engines_report_unavailable():
    status = available_engines()
    # 認証情報なしの環境では API/未導入エンジンは利用不可
    assert status["vision_llm"] is False
    assert status["ndlocr_lite"] is False


@_needs_tesseract
def test_tesseract_reports_available():
    assert available_engines()["tesseract"] is True


def test_tesseract_engine_limits_openmp_for_parallelism():
    # 並列 OCR でのスレッド過剰割り当てを防ぐ設定（engine import の副作用）
    import shiryo_coder.modules.ocr.engines.tesseract  # noqa: F401

    assert os.environ.get("OMP_THREAD_LIMIT") == "1"


def test_bundled_tesseract_config_noop_when_not_frozen():
    # 非凍結環境（通常実行）では同梱 tesseract 設定は何もしない
    from shiryo_coder.modules.ocr.engines import tesseract as tess

    tess._configure_bundled.cache_clear()
    assert tess._configure_bundled() is None


# -- 入力の列挙 -----------------------------------------------------------------
def test_enumerate_single_image(english_png):
    from shiryo_coder.modules.ocr.inputs import enumerate_pages

    pages = enumerate_pages(english_png)
    assert len(pages) == 1
    array = pages[0].load()
    assert array.ndim == 3 and array.shape[2] == 3


def test_enumerate_multipage_pdf(tmp_path):
    from shiryo_coder.modules.ocr.inputs import enumerate_pages

    pdf_path = tmp_path / "scan.pdf"
    # この Pillow ビルドは JPEG 非対応のため、PDF はビットマップ(mode "1")で保存する
    p1 = _text_image("PAGE ONE").convert("1")
    p2 = _text_image("PAGE TWO").convert("1")
    p1.save(pdf_path, save_all=True, append_images=[p2])

    pages = enumerate_pages(pdf_path, pdf_dpi=120)
    assert len(pages) == 2
    assert pages[1].label == "scan.pdf#p2"


def test_enumerate_zip(tmp_path):
    from shiryo_coder.modules.ocr.inputs import enumerate_pages

    zip_path = tmp_path / "batch.zip"
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    _text_image("A").save(a)
    _text_image("B").save(b)
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(a, "a.png")
        zf.write(b, "b.png")

    pages = enumerate_pages(zip_path)
    assert len(pages) == 2


# -- 前処理 ---------------------------------------------------------------------
def test_preprocess_outputs_binary(english_png):
    from shiryo_coder.modules.ocr.inputs import enumerate_pages
    from shiryo_coder.modules.ocr.preprocess import PreprocessConfig, preprocess

    image = enumerate_pages(english_png)[0].load()
    out = preprocess(image, PreprocessConfig())
    assert out.ndim == 2                       # グレースケール/二値
    assert set(np.unique(out)).issubset({0, 255})


# -- Tesseract 実認識 -----------------------------------------------------------
@_needs_tesseract
def test_tesseract_recognizes_english(english_png):
    from shiryo_coder.modules.ocr.inputs import enumerate_pages

    engine = get_engine("tesseract")
    image = enumerate_pages(english_png)[0].load()
    result = engine.recognize(image, language="en")
    assert "HELLO" in result.text.upper()
    assert result.words and result.confidence is not None
    assert all(isinstance(w.bbox, BoundingBox) for w in result.words)


# -- パイプライン + DB 永続化 ----------------------------------------------------
@_needs_tesseract
def test_pipeline_ingest_and_persist(tmp_path, english_png):
    from shiryo_coder.db import Database
    from shiryo_coder.modules.ocr import OcrPipeline

    pipeline = OcrPipeline(engine=get_engine("tesseract"))
    doc = pipeline.ingest(english_png, language="en", title="テスト史料")

    assert "HELLO" in doc.body.upper()
    assert doc.metadata["ocr_engine"] == "tesseract"
    assert doc.metadata["language"] == "en"
    assert doc.metadata["script"] == "horizontal"
    assert doc.confidence is not None

    # .md 保存の往復
    md_path = pipeline.save_markdown(doc, tmp_path / "out.md")
    saved_meta, saved_body = read_markdown(md_path)
    assert saved_meta["title"] == "テスト史料"
    assert "HELLO" in saved_body.upper()

    # DB 永続化 + FTS 検索
    db = Database(tmp_path / "p.db")
    db.initialize()
    pid = db.conn.execute(
        "INSERT INTO project(name) VALUES ('p') RETURNING id"
    ).fetchone()["id"]
    doc_id = pipeline.persist(db, pid, doc)
    row = db.conn.execute(
        "SELECT title, language, ocr_engine FROM document WHERE id = ?", (doc_id,)
    ).fetchone()
    assert row["title"] == "テスト史料"
    assert row["ocr_engine"] == "tesseract"
    # 英語ドキュメントは unicode61 索引へルーティングされ、横断検索でヒットする
    from shiryo_coder.modules.library import LibraryRepository

    results = LibraryRepository(db).search("HELLO")
    assert [r.id for r in results] == [doc_id]
    db.close()


# -- 言語/方向の自動判定（縮小推論） ---------------------------------------------
@_needs_japanese
@pytest.mark.parametrize(
    "factory,exp_lang,exp_vertical",
    [
        (lambda: _jp_horizontal("我皇祖皇宗國ヲ肇ムルコト宏遠ニ"), "ja", False),
        (lambda: _jp_vertical("朕惟フニ我皇祖"), "ja", True),
    ],
)
def test_propose_settings_japanese(factory, exp_lang, exp_vertical):
    from shiryo_coder.modules.ocr.detect import propose_settings

    proposal = propose_settings(factory(), get_engine("tesseract"))
    assert proposal.language == exp_lang
    assert proposal.vertical is exp_vertical


@_needs_tesseract
def test_propose_settings_english():
    from shiryo_coder.modules.ocr.detect import propose_settings

    img = np.ascontiguousarray(np.asarray(_text_image("MEIJI RESTORATION 1868"))[:, :, ::-1])
    proposal = propose_settings(img, get_engine("tesseract"))
    assert proposal.language == "en"
    assert proposal.vertical is False


@_needs_japanese
def test_pipeline_auto_detects_vertical_japanese(tmp_path):
    from shiryo_coder.modules.ocr import OcrPipeline

    png = tmp_path / "tate.png"
    Image.fromarray(_jp_vertical("朕惟フニ我皇祖")[:, :, ::-1]).save(png)

    # language も vertical も指定しない → 先頭ページ推論で決定
    doc = OcrPipeline(engine=get_engine("tesseract")).ingest(png)
    assert doc.metadata["language"] == "ja"
    assert doc.metadata["script"] == "vertical"
    assert doc.proposal is not None and doc.proposal.vertical is True


# -- マルチページ TIFF ----------------------------------------------------------
def test_enumerate_multipage_tiff(tmp_path):
    from shiryo_coder.modules.ocr.inputs import enumerate_pages

    tiff_path = tmp_path / "scan.tiff"
    p1 = _text_image("PAGE ONE")
    p2 = _text_image("PAGE TWO")
    p1.save(tiff_path, save_all=True, append_images=[p2])

    pages = enumerate_pages(tiff_path)
    assert len(pages) == 2
    assert pages[0].load().shape[2] == 3


# -- 低信頼度の要校正フラグ・空ページ -------------------------------------------
@_needs_tesseract
def test_low_confidence_flagged_for_review(tmp_path):
    from shiryo_coder.modules.ocr import OcrPipeline

    # 文字のない白紙 → 信頼度なし、本文空でもクラッシュしない
    blank = tmp_path / "blank.png"
    Image.new("RGB", (400, 200), "white").save(blank)
    doc = OcrPipeline(engine=get_engine("tesseract")).ingest(blank, language="en")
    assert doc.body == ""
    assert doc.confidence is None
    assert doc.metadata["needs_review"] is None      # 信頼度不明はフラグ立てない

    # 高い閾値を課せば、読めたページでも要校正になる
    pipeline = OcrPipeline(engine=get_engine("tesseract"), review_threshold=1.1)
    png = tmp_path / "h.png"
    _text_image("HELLO WORLD").save(png)
    doc2 = pipeline.ingest(png, language="en")
    assert doc2.metadata["needs_review"] is True
