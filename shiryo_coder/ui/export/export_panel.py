"""エクスポートパネル（仕様書 3.8）。

各種出力（CSV/Excel、REFI-QDA .qdpx、Obsidian Vault、HTML レポート、SVG 可視化）
をボタンから実行する。書き出し本体は path を取るメソッドに分離し、GUI ハンドラは
ファイルダイアログを挟むだけにしてテスト可能にしている。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shiryo_coder.modules.cooccurrence import HeatmapRepository
from shiryo_coder.modules.export import (
    build_report,
    excel_available,
    export_qdpx,
    export_vault,
    heatmap_svg,
    tables,
    timeseries_svg,
)
from shiryo_coder.modules.sentiment import SentimentRepository

_CSV_TABLES = [("コード集計", "codes"), ("セグメント一覧", "segments"),
               ("メタデータ", "metadata"), ("感情極性", "sentiment")]


class ExportPanel(QWidget):
    """プロジェクトの各種エクスポート。"""

    def __init__(self, db, project_id: int, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.project_id = project_id

        self.status = QLabel("出力形式を選択してください。")
        self.csv_combo = QComboBox()
        for label, value in _CSV_TABLES:
            self.csv_combo.addItem(label, value)
        self.heatmap_dim = QComboBox()
        for label, value in [("年代", "year"), ("著者", "author"), ("言語", "language")]:
            self.heatmap_dim.addItem(label, value)

        grid = QGridLayout()
        self._add_button(grid, 0, "CSV を出力", self._on_csv, self.csv_combo)
        self._add_button(grid, 1, "Excel を出力（全表）", self._on_excel)
        self._add_button(grid, 2, "REFI-QDA (.qdpx) を出力", self._on_qdpx)
        self._add_button(grid, 3, "Obsidian Vault を出力", self._on_vault)
        self._add_button(grid, 4, "HTML レポートを出力", self._on_html)
        self._add_button(grid, 5, "ヒートマップ SVG を出力", self._on_heatmap, self.heatmap_dim)
        self._add_button(grid, 6, "時系列（感情）SVG を出力", self._on_timeseries)

        layout = QVBoxLayout(self)
        layout.addLayout(grid)
        layout.addWidget(self.status)
        layout.addStretch(1)

    def _add_button(self, grid, row, label, handler, extra=None) -> None:
        btn = QPushButton(label)
        btn.clicked.connect(handler)
        grid.addWidget(btn, row, 0)
        if extra is not None:
            grid.addWidget(extra, row, 1)

    # -- 書き出し本体（テスト用に path を受ける） ------------------------------
    def write_csv(self, table: str, path: Path | str) -> Path:
        path = Path(path)
        path.write_text(tables.to_csv(self.db, self.project_id, table), encoding="utf-8-sig")
        return path

    def write_excel(self, path: Path | str) -> Path:
        return tables.to_excel(self.db, self.project_id, path)

    def write_qdpx(self, path: Path | str) -> Path:
        return export_qdpx(self.db, self.project_id, path)

    def write_vault(self, folder: Path | str) -> list[Path]:
        return export_vault(self.db, self.project_id, folder)

    def write_html(self, path: Path | str) -> Path:
        path = Path(path)
        path.write_text(build_report(self.db, self.project_id), encoding="utf-8")
        return path

    def write_heatmap_svg(self, path: Path | str, dimension: str) -> Path:
        ct = HeatmapRepository(self.db).crosstab(self.project_id, dimension)
        path = Path(path)
        path.write_text(heatmap_svg(ct), encoding="utf-8")
        return path

    def write_timeseries_svg(self, path: Path | str) -> Path:
        series = SentimentRepository(self.db).timeseries(self.project_id, unit="document")
        path = Path(path)
        path.write_text(timeseries_svg(series), encoding="utf-8")
        return path

    # -- GUI ハンドラ -----------------------------------------------------------
    def _save(self, caption: str, default: str, filt: str) -> str | None:
        path, _ = QFileDialog.getSaveFileName(self, caption, default, filt)
        return path or None

    def _done(self, target) -> None:
        self.status.setText(f"出力しました: {target}")

    def _on_csv(self) -> None:
        table = self.csv_combo.currentData()
        path = self._save("CSV 出力", f"{table}.csv", "CSV (*.csv)")
        if path:
            self._done(self.write_csv(table, path))

    def _on_excel(self) -> None:
        if not excel_available():
            self.status.setText("openpyxl が未導入です（pip install openpyxl）。")
            return
        path = self._save("Excel 出力", "export.xlsx", "Excel (*.xlsx)")
        if path:
            self._done(self.write_excel(path))

    def _on_qdpx(self) -> None:
        path = self._save("REFI-QDA 出力", "project.qdpx", "QDPX (*.qdpx)")
        if path:
            self._done(self.write_qdpx(path))

    def _on_vault(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Vault の出力先")
        if folder:
            self._done(f"{len(self.write_vault(folder))} ファイル")

    def _on_html(self) -> None:
        path = self._save("HTML レポート", "report.html", "HTML (*.html)")
        if path:
            self._done(self.write_html(path))

    def _on_heatmap(self) -> None:
        path = self._save("ヒートマップ SVG", "heatmap.svg", "SVG (*.svg)")
        if path:
            self._done(self.write_heatmap_svg(path, self.heatmap_dim.currentData()))

    def _on_timeseries(self) -> None:
        path = self._save("時系列 SVG", "timeseries.svg", "SVG (*.svg)")
        if path:
            self._done(self.write_timeseries_svg(path))
