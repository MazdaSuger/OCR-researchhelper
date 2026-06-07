"""Tesseract 5 エンジン（ローカル）。

仕様書 3.1: 英語史料・現代横書き日本語、PSM 5 で縦書き対応。
`image_to_string` で整形済み本文を、`image_to_data` で座標付きトークンを取得する。
"""

from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path

from shiryo_coder.modules.ocr.engines.base import EngineUnavailable, OcrEngine
from shiryo_coder.modules.ocr.result import BoundingBox, OcrResult, OcrWord

# tesseract は既定で OpenMP により全コアを使うため、QThreadPool で並列実行すると
# スレッド過剰割り当てで激しく遅くなる。各プロセスを単一スレッド化して健全に並列化する。
# （tesseract 公式が推奨する並列化時の設定）
os.environ.setdefault("OMP_THREAD_LIMIT", "1")


@lru_cache(maxsize=1)
def _configure_bundled() -> str | None:
    """凍結 .app に同梱された tesseract を pytesseract に設定する。

    PyInstaller でビルドした macOS アプリでは、bundle_tesseract.sh が
    `Contents/MacOS/tesseract` と `Contents/Resources/tessdata` を配置する。
    非凍結環境ではすぐに None を返す（システムの tesseract を使う）。
    """
    if not getattr(sys, "frozen", False):
        return None
    exe_dir = Path(sys.executable).resolve().parent      # .../Contents/MacOS
    contents = exe_dir.parent
    for candidate in (exe_dir / "tesseract", contents / "Resources" / "tesseract"):
        if candidate.exists():
            try:
                import pytesseract

                pytesseract.pytesseract.tesseract_cmd = str(candidate)
            except Exception:
                pass
            resources = contents / "Resources"
            if (resources / "tessdata").is_dir():
                os.environ.setdefault("TESSDATA_PREFIX", str(resources))
            return str(candidate)
    return None


def _to_pil(image):
    """numpy 配列・パスを PIL Image に正規化する。"""
    from PIL import Image

    if isinstance(image, (str, bytes)) or hasattr(image, "__fspath__"):
        return Image.open(image)
    # numpy 配列
    import numpy as np

    if isinstance(image, np.ndarray):
        if image.ndim == 2:
            return Image.fromarray(image)
        # OpenCV は BGR、PIL は RGB
        return Image.fromarray(image[:, :, ::-1])
    return image  # 既に PIL.Image とみなす


class Tesseract5Engine(OcrEngine):
    """Tesseract 5 ラッパ。"""

    name = "tesseract"
    vertical_supported = True

    def __init__(self, *, default_language: str = "en", oem: int = 3) -> None:
        self.default_language = default_language
        self.oem = oem

    # -- 可用性 ----------------------------------------------------------------
    def is_available(self) -> bool:
        try:
            import pytesseract  # noqa: F401
        except ImportError:
            return False
        # 同梱 tesseract（凍結アプリ）があればそれを使う。無ければシステムを探す。
        if _configure_bundled() is None and shutil.which("tesseract") is None:
            return False
        return True

    # -- 言語・PSM の解決 ------------------------------------------------------
    def _lang_code(self, language: str | None, vertical: bool) -> str:
        lang = language or self.default_language
        if lang in ("ja", "jpn", "jp"):
            return "jpn_vert" if vertical else "jpn"
        if lang in ("en", "eng"):
            return "eng"
        return lang  # 'jpn+eng' などはそのまま渡す

    @staticmethod
    def _psm(vertical: bool) -> int:
        # 5 = 縦書き 1 ブロック / 3 = 自動（横書き）
        return 5 if vertical else 3

    # -- 認識 ------------------------------------------------------------------
    def recognize(
        self,
        image,
        *,
        vertical: bool = False,
        language: str | None = None,
    ) -> OcrResult:
        self.ensure_available()
        _configure_bundled()
        import pytesseract

        pil = _to_pil(image)
        lang = self._lang_code(language, vertical)
        config = f"--oem {self.oem} --psm {self._psm(vertical)}"

        try:
            text = pytesseract.image_to_string(pil, lang=lang, config=config).strip()
            data = pytesseract.image_to_data(
                pil, lang=lang, config=config, output_type=pytesseract.Output.DICT
            )
        except pytesseract.TesseractError as exc:  # pragma: no cover - 環境依存
            raise EngineUnavailable(f"Tesseract 実行エラー: {exc}") from exc

        words = self._words_from_data(data)
        result = OcrResult.from_words(words, engine=self.name, text=text)
        return result

    @staticmethod
    def _words_from_data(data: dict) -> list[OcrWord]:
        words: list[OcrWord] = []
        n = len(data.get("text", []))
        line_key_to_index: dict[tuple, int] = {}
        for i in range(n):
            token = data["text"][i].strip()
            conf_raw = data["conf"][i]
            try:
                conf = float(conf_raw)
            except (TypeError, ValueError):
                conf = -1.0
            if not token or conf < 0:
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            line_index = line_key_to_index.setdefault(key, len(line_key_to_index))
            words.append(
                OcrWord(
                    text=token,
                    bbox=BoundingBox(
                        x=int(data["left"][i]),
                        y=int(data["top"][i]),
                        w=int(data["width"][i]),
                        h=int(data["height"][i]),
                    ),
                    confidence=conf / 100.0,
                    line_index=line_index,
                )
            )
        return words
