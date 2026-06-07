"""コードの自動配色（HSL）。仕様書 3.3「HSL 自動配色＋手動上書き」。"""

from __future__ import annotations

import colorsys

# 視認しやすい色相を巡回させる既定パレットサイズ
_DEFAULT_WHEEL = 12


def auto_color(
    index: int,
    *,
    wheel: int = _DEFAULT_WHEEL,
    saturation: float = 0.55,
    lightness: float = 0.62,
) -> str:
    """インデックスに応じて色相環上で等間隔の色を `#RRGGBB` で返す。"""
    hue = (index % wheel) / wheel
    r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
    return "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))


def text_color_for(background: str) -> str:
    """背景色に対して読みやすい文字色（黒 or 白）を返す。"""
    bg = background.lstrip("#")
    if len(bg) != 6:
        return "#000000"
    r, g, b = (int(bg[i : i + 2], 16) for i in (0, 2, 4))
    # 相対輝度（簡易）
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#000000" if luminance > 0.55 else "#FFFFFF"
