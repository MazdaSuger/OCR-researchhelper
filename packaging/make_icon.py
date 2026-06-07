"""アプリアイコン（1024px PNG）を生成する。白・オレンジ・黒のテーマ。

生成物 `packaging/icon.png` をリポジトリに同梱し、macOS ビルド時に
`make_icon.sh` が `.icns` へ変換する。実行: `python packaging/make_icon.py`
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ORANGE = (249, 115, 22, 255)        # #F97316
ORANGE_DARK = (234, 88, 12, 255)    # #EA580C
BLACK = (26, 26, 26, 255)           # #1A1A1A
WHITE = (255, 255, 255, 255)

_CJK_FONTS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W7.ttc",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in _CJK_FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def build(size: int = 1024) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = int(size * 0.08)
    radius = int(size * 0.225)
    box = (margin, margin, size - margin, size - margin)

    # オレンジの角丸（squircle 風）＋黒の細い縁取り
    draw.rounded_rectangle(box, radius=radius, fill=ORANGE)
    draw.rounded_rectangle(box, radius=radius, outline=BLACK, width=max(2, size // 256))
    # 下部に黒のアクセントバー（「白・オレンジ・黒」を均す）
    bar_h = int(size * 0.07)
    bar_y = size - margin - bar_h - int(size * 0.02)
    draw.rounded_rectangle(
        (margin + radius // 2, bar_y, size - margin - radius // 2, bar_y + bar_h),
        radius=bar_h // 2, fill=BLACK,
    )

    # 中央に白の「史」
    glyph = "史"
    font = _font(int(size * 0.6))
    bbox = draw.textbbox((0, 0), glyph, font=font)
    gw, gh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - gw) / 2 - bbox[0]
    y = (size - gh) / 2 - bbox[1] - int(size * 0.03)
    draw.text((x, y), glyph, font=font, fill=WHITE)
    return img


def main() -> None:
    out = Path(__file__).with_name("icon.png")
    build().save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
