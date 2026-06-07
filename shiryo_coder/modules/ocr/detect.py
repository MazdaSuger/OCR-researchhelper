"""言語・方向の自動判定（仕様書 3.1「言語/方向自動判定」）。

- `detect_language`: 認識済みテキストの文字種比率からの軽量判定
- `detect_orientation`: Tesseract OSD による向き・字種推定（画像から）

縦書き／横書きの確定判定はモデル依存のため、ここでは OSD の字種と
テキスト比率による示唆に留め、最終確認はユーザーに委ねる設計とする。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shiryo_coder.modules.ocr.engines.base import OcrEngine

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


def _label(language: str, vertical: bool) -> str:
    base = {"ja": "日本語", "en": "英語"}.get(language, "判定不能")
    if language == "und":
        return base
    return f"{base}{'縦書き' if vertical else '横書き'}"


@dataclass
class OcrProposal:
    """先頭ページの縮小推論による取り込み設定の提案（仕様書 3.1）。"""

    language: str          # 'ja' / 'en' / 'und'
    vertical: bool
    confidence: float      # 採用試行の平均信頼度（0.0–1.0）
    script: str            # OSD の字種（参考）
    label: str             # 人間可読ラベル（例: 「日本語縦書き」）


def _downscale(image, max_dim: int):
    """長辺が max_dim を超える場合のみ縮小する（縮小推論の高速化）。"""
    import cv2

    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return image
    scale = max_dim / longest
    return cv2.resize(
        image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
    )


@dataclass
class _Trial:
    language: str
    vertical: bool
    confidence: float
    chars: int       # 空白を除く文字数
    cjk: int         # CJK 文字数


def propose_settings(
    image,
    engine: "OcrEngine",
    *,
    languages: tuple[str, ...] = ("ja", "en"),
    max_dim: int = 1200,
    min_cjk: int = 2,
    cjk_conf: float = 0.4,
    cjk_ratio: float = 0.5,
) -> OcrProposal:
    """先頭ページを縮小推論し、言語×方向の候補を試して最良設定を提案する。

    判定方針（Tesseract の信頼度がスクリプト間で比較不能なことへの対処）:
    - **言語**: 日本語候補が信頼度 `cjk_conf` 以上で CJK を `min_cjk` 文字以上
      読めたら日本語とみなす（ラテン文字の画像から確信度の高い CJK は出ないため）。
      そうでなければ非日本語候補のうち信頼度×文字数が最大の言語を採用。
    - **方向**: 日本語のとき、`信頼度 × CJK 文字数` が最大の試行の向きを採る。

    エンジンが使えない場合は OSD/中立値にフォールバックする。
    """
    small = _downscale(image, max_dim)
    osd = detect_orientation(small)

    trials: list[_Trial] = []
    for lang in languages:
        orientations = (False, True) if lang == "ja" else (False,)
        for vertical in orientations:
            try:
                result = engine.recognize(small, language=lang, vertical=vertical)
            except Exception:
                continue
            stripped = re.sub(r"\s", "", result.text)
            trials.append(
                _Trial(
                    language=lang,
                    vertical=vertical,
                    confidence=result.confidence or 0.0,
                    chars=len(stripped),
                    cjk=len(_CJK_RE.findall(stripped)),
                )
            )

    if not trials:
        return OcrProposal(osd.language, False, 0.0, osd.script, _label(osd.language, False))

    ja_trials = [t for t in trials if t.language == "ja"]
    best_ja = max(ja_trials, key=lambda t: t.confidence * t.cjk, default=None)
    # ラテン文字画像でも jpn_vert は少数の CJK を幻覚するため、CJK 比率も併用する
    is_japanese = (
        best_ja is not None
        and best_ja.cjk >= min_cjk
        and best_ja.confidence >= cjk_conf
        and best_ja.cjk / max(best_ja.chars, 1) >= cjk_ratio
    )

    if is_japanese:
        return OcrProposal(
            language="ja",
            vertical=best_ja.vertical,
            confidence=best_ja.confidence,
            script=osd.script,
            label=_label("ja", best_ja.vertical),
        )

    # 非日本語: ラテン候補のうち信頼度×文字数が最大の言語を採用
    non_ja = [t for t in trials if t.language != "ja"]
    best = max(non_ja, key=lambda t: t.confidence * t.chars, default=None)
    if best is None:
        return OcrProposal(osd.language, False, 0.0, osd.script, _label(osd.language, False))
    return OcrProposal(
        language=best.language,
        vertical=False,
        confidence=best.confidence,
        script=osd.script,
        label=_label(best.language, False),
    )
