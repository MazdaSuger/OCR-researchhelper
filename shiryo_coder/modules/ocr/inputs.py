"""入力の列挙: 画像 / PDF（複数頁分割）/ ZIP 一括 / ディレクトリ。

仕様書 3.1「入力: 画像（jpg/png/tiff）、PDF（複数頁自動分割）、ZIP フォルダ一括」。
各入力を 1 ページ = 1 `PageImage` に展開する。
"""

from __future__ import annotations

import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
TIFF_SUFFIXES = {".tif", ".tiff"}      # マルチページの可能性あり
PDF_SUFFIXES = {".pdf"}
ZIP_SUFFIXES = {".zip"}


def _pil_to_bgr(frame) -> np.ndarray:
    rgb = np.asarray(frame.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _imread(path: Path) -> np.ndarray:
    """非 ASCII パスにも耐える画像読み込み（BGR）。cv2 失敗時は PIL にフォールバック。"""
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is not None:
        return image
    try:
        from PIL import Image

        with Image.open(path) as im:
            return _pil_to_bgr(im)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"画像を読み込めません: {path}") from exc


def _load_tiff(path: Path, *, source: str | None = None) -> list["PageImage"]:
    """TIFF を 1 フレーム = 1 ページに展開する（マルチページ対応）。"""
    from PIL import Image, ImageSequence

    src = source or str(path)
    pages: list[PageImage] = []
    with Image.open(path) as im:
        for i, frame in enumerate(ImageSequence.Iterator(im)):
            pages.append(PageImage(source=src, page_index=i, _array=_pil_to_bgr(frame)))
    return pages


def _imdecode(buffer: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(buffer, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("ZIP 内の画像をデコードできません")
    return image


@dataclass
class PageImage:
    """OCR 対象の 1 ページ。実体は遅延ロードまたは展開済み配列。"""

    source: str            # 由来（ファイルパスや ZIP メンバ名）
    page_index: int        # source 内での 0 始まりのページ番号
    path: Path | None = None
    _array: np.ndarray | None = None

    def load(self) -> np.ndarray:
        """BGR の numpy 配列として画像を取得する。"""
        if self._array is not None:
            return self._array
        if self.path is not None:
            return _imread(self.path)
        raise ValueError("PageImage に画像の実体がありません")

    @property
    def label(self) -> str:
        """`scan.pdf#p2` のような表示用ラベル。"""
        name = Path(self.source).name
        return f"{name}#p{self.page_index + 1}"


def _render_pdf(path: Path, *, dpi: int) -> list[PageImage]:
    """PDF を 1 頁ずつ画像化する（pypdfium2）。"""
    import pypdfium2 as pdfium

    scale = dpi / 72.0
    pages: list[PageImage] = []
    pdf = pdfium.PdfDocument(str(path))
    try:
        for i in range(len(pdf)):
            bitmap = pdf[i].render(scale=scale)
            rgb = np.asarray(bitmap.to_pil().convert("RGB"))
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            pages.append(PageImage(source=str(path), page_index=i, _array=bgr))
    finally:
        pdf.close()
    return pages


def _expand_zip(path: Path, *, dpi: int) -> list[PageImage]:
    """ZIP 内の画像・PDF を展開する。"""
    pages: list[PageImage] = []
    with zipfile.ZipFile(path) as zf:
        for name in sorted(zf.namelist()):
            member = Path(name)
            suffix = member.suffix.lower()
            if name.endswith("/"):
                continue
            if suffix in TIFF_SUFFIXES:
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
                    tmp.write(zf.read(name))
                    tmp.flush()
                    pages.extend(_load_tiff(Path(tmp.name), source=f"{path}!{name}"))
            elif suffix in IMAGE_SUFFIXES:
                array = _imdecode(zf.read(name))
                pages.append(PageImage(source=f"{path}!{name}", page_index=0, _array=array))
            elif suffix in PDF_SUFFIXES:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
                    tmp.write(zf.read(name))
                    tmp.flush()
                    for j, pg in enumerate(_render_pdf(Path(tmp.name), dpi=dpi)):
                        pages.append(
                            PageImage(source=f"{path}!{name}", page_index=j, _array=pg.load())
                        )
    return pages


def enumerate_pages(path: Path | str, *, pdf_dpi: int = 200) -> list[PageImage]:
    """入力パスを `PageImage` のリストに展開する。

    対応: 単一画像 / PDF / ZIP / ディレクトリ（再帰）。
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    if path.is_dir():
        pages: list[PageImage] = []
        for child in sorted(path.iterdir()):
            if child.is_dir() or child.suffix.lower() in (
                IMAGE_SUFFIXES | PDF_SUFFIXES | ZIP_SUFFIXES
            ):
                pages.extend(enumerate_pages(child, pdf_dpi=pdf_dpi))
        return pages

    suffix = path.suffix.lower()
    if suffix in TIFF_SUFFIXES:
        return _load_tiff(path)
    if suffix in IMAGE_SUFFIXES:
        return [PageImage(source=str(path), page_index=0, path=path)]
    if suffix in PDF_SUFFIXES:
        return _render_pdf(path, dpi=pdf_dpi)
    if suffix in ZIP_SUFFIXES:
        return _expand_zip(path, dpi=pdf_dpi)
    raise ValueError(f"未対応の入力形式です: {path}")
