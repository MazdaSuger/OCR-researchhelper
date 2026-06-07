"""史料語彙の正規化（旧字旧仮名 → 新字新仮名）。仕様書 3.4。

旧字体・旧仮名づかいを新字体・現代仮名へ写像してから辞書照合する。内蔵マップは
代表的な対応のみで、プロジェクトごとにユーザー追加できる（extend）。
"""

from __future__ import annotations

# 旧字体 → 新字体（1 文字対応の代表例）
_OLD_KANJI = {
    "國": "国", "學": "学", "體": "体", "廣": "広", "觀": "観", "假": "仮",
    "聲": "声", "會": "会", "豐": "豊", "鐵": "鉄", "號": "号", "圓": "円",
    "藝": "芸", "缺": "欠", "辭": "辞", "舊": "旧", "寶": "宝", "獨": "独",
    "當": "当", "經": "経", "惠": "恵", "醫": "医", "齋": "斎", "櫻": "桜",
    "氣": "気", "澤": "沢", "驛": "駅", "萬": "万", "與": "与", "亂": "乱",
    "佛": "仏", "戰": "戦", "禮": "礼", "勳": "勲", "獻": "献", "歸": "帰",
}

# 旧仮名 → 現代仮名（字母レベル）
_OLD_KANA = {
    "ゐ": "い", "ゑ": "え", "ヰ": "イ", "ヱ": "エ",
    "ゝ": "", "ゞ": "", "ヽ": "", "ヾ": "",   # 繰り返し記号は素朴に除去
}


class OldToNewNormalizer:
    """旧字旧仮名を新字新仮名へ正規化する（ユーザー拡張可能）。"""

    def __init__(self, extra: dict[str, str] | None = None) -> None:
        self._map: dict[str, str] = {**_OLD_KANJI, **_OLD_KANA}
        if extra:
            self._map.update(extra)

    def extend(self, mapping: dict[str, str]) -> None:
        """対応を追加する（史料特有の異体字など）。"""
        self._map.update(mapping)

    def normalize(self, text: str) -> str:
        return "".join(self._map.get(ch, ch) for ch in text)
