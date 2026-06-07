"""3.8 エクスポート・連携モジュール。

責務:
- CSV / Excel（コード集計・セグメント・メタデータ・感情極性）
- REFI-QDA .qdpx（MAXQDA / NVivo / ATLAS.ti / QualCoder 互換）
- 可視化（ヒートマップ・時系列の SVG、ネットワークは vis-network HTML）
- 学術引用形式（APA / Chicago / SIST02）
- Obsidian Vault 再構築（コード=タグ、セグメント=callout、関係=リンク）
- HTML 静的レポート

公開 API:
- `tables`（to_csv / to_excel）, `citation`（format_citation / format_segment_citation）
- `export_qdpx`, `export_vault`, `build_report` / `write_report`
- `heatmap_svg`, `timeseries_svg`
"""

from shiryo_coder.modules.export import citation, tables
from shiryo_coder.modules.export.citation import (
    STYLES,
    format_citation,
    format_segment_citation,
)
from shiryo_coder.modules.export.html_report import build_report, write_report
from shiryo_coder.modules.export.obsidian_export import export_vault
from shiryo_coder.modules.export.qdpx import export_qdpx
from shiryo_coder.modules.export.tables import excel_available, to_csv, to_excel
from shiryo_coder.modules.export.viz import heatmap_svg, timeseries_svg

__all__ = [
    "tables",
    "citation",
    "to_csv",
    "to_excel",
    "excel_available",
    "format_citation",
    "format_segment_citation",
    "STYLES",
    "export_qdpx",
    "export_vault",
    "build_report",
    "write_report",
    "heatmap_svg",
    "timeseries_svg",
]
