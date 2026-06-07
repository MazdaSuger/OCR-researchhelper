"""言語・方向の自動判定（仕様書 3.1「言語/方向自動判定」）。

- `detect_language`: 認識済みテキストの文字種比率からの軽量判定
- `detect_orientation`: Tesseract OSD による向き・字種推定（画像から）

縦書き／横書きの確定判定はモデル依存のため、ここでは OSD の字種と
テキスト比率による示唆に留め、最終確認はユーザーに委ねる設計とする。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# CJK 統合漢字・ひらがな・カタカナ
_CJK_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def detect_language(text: str) -> str:
    """テキストの文字種比率から 'ja' / 'en' を推定する。"""
    cjk = len(_CJK_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    if cjk == 0 and latin == 0:
        return "und"          # 判定不能
    return "ja" if cjk >= latin else "en"


@dataclass
class Orientation:
    """Tesseract OSD の判定結果。"""

    rotate: int          # 画像を正立させるための回転角（度）
    script: str          # 例: 'Han', 'Japanese', 'Latin'
    language: str        # detect_language 互換の 'ja'/'en'/'und'
    confidence: float    # OSD の orientation 信頼度


_SCRIPT_TO_LANG = {
    "Han": "ja",
    "Japanese": "ja",
    "Hiragana": "ja",
    "Katakana": "ja",
    "Latin": "en",
}


def detect_orientation(image) -> Orientation:
    """Tesseract OSD で画像の向きと字種を判定する。

    Tesseract バイナリが必要。失敗時は中立値（rotate=0, script='', lang='und'）。
    """
    import pytesseract

    try:
        osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
    except Exception:
        return Orientation(rotate=0, script="", language="und", confidence=0.0)

    script = str(osd.get("script", ""))
    return Orientation(
        rotate=int(osd.get("rotate", 0)),
        script=script,
        language=_SCRIPT_TO_LANG.get(script, "und"),
        confidence=float(osd.get("orientation_conf", 0.0)),
    )
