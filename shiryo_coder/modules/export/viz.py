"""可視化エクスポート（SVG）。仕様書 3.8。

ヒートマップ・時系列プロットを外部依存なしの SVG 文字列として生成する
（共起ネットワークは modules.cooccurrence.to_html の vis-network HTML を利用）。
matplotlib が導入されていれば PNG/SVG レンダリングにも拡張可能。
"""

from __future__ import annotations

import html


def _color_scale(value: float, peak: float) -> str:
    """0..peak を白→赤のグラデーションにする。"""
    if peak <= 0:
        return "#ffffff"
    t = max(0.0, min(1.0, value / peak))
    r = 255
    g = int(255 * (1 - t))
    b = int(220 * (1 - t))
    return f"#{r:02x}{g:02x}{b:02x}"


def heatmap_svg(crosstab, *, cell: int = 44, label_w: int = 120, label_h: int = 40) -> str:
    """CrossTab（コード×ディメンション）をヒートマップ SVG にする。"""
    codes = crosstab.row_codes
    cols = crosstab.columns
    width = label_w + cell * len(cols)
    height = label_h + cell * len(codes)
    peak = max(
        [crosstab.value(rc, c) for rc in codes for c in cols] + [1]
    )
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'font-family="sans-serif" font-size="11">']
    # 列見出し
    for j, c in enumerate(cols):
        x = label_w + j * cell + cell / 2
        parts.append(f'<text x="{x:.0f}" y="{label_h - 8}" text-anchor="middle">{html.escape(str(c))}</text>')
    # 行
    for i, code in enumerate(codes):
        y = label_h + i * cell
        parts.append(f'<text x="4" y="{y + cell / 2 + 4:.0f}">{html.escape(crosstab.code_names[code])}</text>')
        for j, c in enumerate(cols):
            v = crosstab.value(code, c)
            x = label_w + j * cell
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'fill="{_color_scale(v, peak)}" stroke="#ccc"/>'
                f'<text x="{x + cell / 2:.0f}" y="{y + cell / 2 + 4:.0f}" '
                f'text-anchor="middle">{v if v else ""}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def timeseries_svg(
    series: dict[int, float], *, width: int = 480, height: int = 240, pad: int = 40
) -> str:
    """年代→値の系列を折れ線 SVG にする（極性 -1..1 等を想定）。"""
    if not series:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"/>'
    years = sorted(series)
    values = [series[y] for y in years]
    lo, hi = min(values + [0.0]), max(values + [0.0])
    span = (hi - lo) or 1.0
    n = len(years)

    def px(i):
        return pad + (i * (width - 2 * pad) / max(n - 1, 1))

    def py(v):
        return height - pad - ((v - lo) / span) * (height - 2 * pad)

    points = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(values))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'font-family="sans-serif" font-size="11">']
    # 軸（0 線）
    if lo < 0 < hi:
        zero = py(0.0)
        parts.append(f'<line x1="{pad}" y1="{zero:.1f}" x2="{width - pad}" y2="{zero:.1f}" stroke="#bbb"/>')
    parts.append(f'<polyline fill="none" stroke="#2b7" stroke-width="2" points="{points}"/>')
    for i, (y, v) in enumerate(zip(years, values)):
        parts.append(f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="3" fill="#176"/>')
        parts.append(f'<text x="{px(i):.1f}" y="{height - pad + 14:.0f}" text-anchor="middle">{y}</text>')
    parts.append("</svg>")
    return "".join(parts)
