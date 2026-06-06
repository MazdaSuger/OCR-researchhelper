"""メインウィンドウシェル。

QualCoder 風の三カラムレイアウト（フォルダツリー / ドキュメント一覧 / プレビュー）
の足場のみを提供する。各ペインの中身は対応モジュールの実装で差し替える。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from shiryo_coder import __app_name__, __version__
from shiryo_coder.db import Database


def _placeholder(title: str, body: str) -> QWidget:
    """見出し付きのプレースホルダーペインを作る。"""
    panel = QWidget()
    layout = QVBoxLayout(panel)
    heading = QLabel(f"<b>{title}</b>")
    heading.setTextFormat(Qt.TextFormat.RichText)
    note = QLabel(body)
    note.setWordWrap(True)
    note.setStyleSheet("color: gray;")
    layout.addWidget(heading)
    layout.addWidget(note)
    layout.addStretch(1)
    return panel


class MainWindow(QMainWindow):
    """アプリのメインウィンドウ。"""

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.setWindowTitle(f"{__app_name__}  v{__version__}")
        self.resize(1200, 760)
        self._build_menu()
        self._build_central()
        self._build_status_bar()

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        for label in ("プロジェクト(&P)", "取り込み(&I)", "コーディング(&C)",
                      "分析(&A)", "エクスポート(&E)", "ヘルプ(&H)"):
            menubar.addMenu(label)

    def _build_central(self) -> None:
        # 左: フォルダツリー（史料カタログの足場）
        tree = QTreeWidget()
        tree.setHeaderLabel("プロジェクト")
        root = QTreeWidgetItem(tree, ["（プロジェクト未作成）"])
        for name in ("ドキュメント", "コードブック", "コーダー", "メモ"):
            QTreeWidgetItem(root, [name])
        tree.expandAll()

        # 中央: ドキュメント一覧 / プレビューの足場
        middle = _placeholder(
            "ドキュメント一覧",
            "OCR 取り込み済みの .md がここに並びます（メタデータ列ソート対応予定）。",
        )

        # 右: プレビュー
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setPlaceholderText(
            "ここに選択した史料のプレビュー／コーディングビューが表示されます。"
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(tree)
        splitter.addWidget(middle)
        splitter.addWidget(preview)
        splitter.setSizes([240, 360, 600])

        container = QWidget()
        outer = QHBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(splitter)
        self.setCentralWidget(container)

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        version = self.db.schema_version()
        status.showMessage(
            f"DB: {self.db.db_path}  /  スキーマ v{version}  ・  雛形（モジュール未実装）"
        )
        self.setStatusBar(status)
