"""メインウィンドウシェル。

QualCoder 風の三カラムレイアウト（フォルダツリー / ドキュメント一覧 / プレビュー）。
「取り込み」メニューから OCR 取り込みワークフロー（仕様書 3.1）を起動できる。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
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

_IMPORT_FILTER = "史料 (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.pdf *.zip);;すべて (*)"


class MainWindow(QMainWindow):
    """アプリのメインウィンドウ。"""

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self._queues: list = []          # 実行中の OcrQueue を保持（GC 防止）
        self.setWindowTitle(f"{__app_name__}  v{__version__}")
        self.resize(1200, 760)
        self._build_menu()
        self._build_central()
        self._build_status_bar()
        self._refresh_documents()

    # -- 構築 ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = self.menuBar()
        import_menu = menubar.addMenu("取り込み(&I)")
        action = QAction("OCR 取り込み…", self)
        action.triggered.connect(self.import_documents)
        import_menu.addAction(action)
        for label in ("コーディング(&C)", "分析(&A)", "エクスポート(&E)", "ヘルプ(&H)"):
            menubar.addMenu(label)

    def _build_central(self) -> None:
        tree = QTreeWidget()
        tree.setHeaderLabel("プロジェクト")
        root = QTreeWidgetItem(tree, ["既定プロジェクト"])
        for name in ("ドキュメント", "コードブック", "コーダー", "メモ"):
            QTreeWidgetItem(root, [name])
        tree.expandAll()

        self.doc_list = QListWidget()
        self.doc_list.currentItemChanged.connect(self._on_document_selected)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("ここに選択した史料のプレビューが表示されます。")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(tree)
        splitter.addWidget(self.doc_list)
        splitter.addWidget(self.preview)
        splitter.setSizes([240, 360, 600])

        container = QWidget()
        outer = QHBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(splitter)
        self.setCentralWidget(container)

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        version = self.db.schema_version()
        status.showMessage(f"DB: {self.db.db_path}  /  スキーマ v{version}")
        self.setStatusBar(status)

    # -- プロジェクト/ドキュメント ---------------------------------------------
    def _ensure_project(self) -> int:
        row = self.db.conn.execute("SELECT id FROM project ORDER BY id LIMIT 1").fetchone()
        if row is not None:
            return int(row["id"])
        row = self.db.conn.execute(
            "INSERT INTO project(name) VALUES ('既定プロジェクト') RETURNING id"
        ).fetchone()
        self.db.conn.commit()
        return int(row["id"])

    def _refresh_documents(self) -> None:
        self.doc_list.clear()
        rows = self.db.conn.execute(
            "SELECT id, title, language, confidence FROM document ORDER BY id"
        ).fetchall()
        for row in rows:
            conf = f"{row['confidence']:.2f}" if row["confidence"] is not None else "—"
            item = QListWidgetItem(f"{row['title']}  [{row['language'] or '?'} / {conf}]")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.doc_list.addItem(item)

    def _on_document_selected(self, current, _previous) -> None:
        if current is None:
            self.preview.clear()
            return
        doc_id = current.data(Qt.ItemDataRole.UserRole)
        row = self.db.conn.execute(
            "SELECT body FROM document WHERE id = ?", (doc_id,)
        ).fetchone()
        self.preview.setPlainText(row["body"] if row else "")

    # -- 取り込みワークフロー ---------------------------------------------------
    def import_documents(self) -> None:
        """ファイル選択 → 自動判定の提示 → 設定確認 → バッチ OCR を起動する。"""
        from shiryo_coder.modules.ocr.engines import get_engine
        from shiryo_coder.modules.ocr.inputs import enumerate_pages
        from shiryo_coder.modules.ocr.preprocess import PreprocessConfig, preprocess
        from shiryo_coder.ui.ocr_import import ImportSettingsDialog

        paths, _ = QFileDialog.getOpenFileNames(self, "史料を選択", "", _IMPORT_FILTER)
        if not paths:
            return

        try:
            first = enumerate_pages(paths[0])[0].load()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "取り込み", f"先頭ページを読めません: {exc}")
            return

        engine = get_engine("tesseract")
        proposal = None
        if engine.is_available():
            from shiryo_coder.modules.ocr.detect import propose_settings

            proposal = propose_settings(preprocess(first, PreprocessConfig()), engine)

        dialog = ImportSettingsDialog(first, proposal=proposal, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.start_batch(paths, dialog.settings())

    def start_batch(self, paths: list[str], settings) -> "object":
        """設定に従いバッチ OCR を開始する。進捗ダイアログを表示し、queue を返す。"""
        from shiryo_coder.modules.ocr import OcrPipeline
        from shiryo_coder.modules.ocr.engines import get_engine
        from shiryo_coder.modules.ocr.worker import OcrQueue
        from shiryo_coder.ui.ocr_import import BatchProgressWidget

        project_id = self._ensure_project()
        pipeline = OcrPipeline(
            engine=get_engine(settings.engine),
            preprocess_config=settings.preprocess,
        )
        queue = OcrQueue(pipeline)
        self._queues.append(queue)

        progress = BatchProgressWidget()
        progress.set_total(len(paths))
        progress.bind(queue)

        def on_finished(_source: str, doc) -> None:
            pipeline.persist(self.db, project_id, doc)
            self._refresh_documents()

        queue.signals.finished.connect(on_finished)

        dialog = QDialog(self)
        dialog.setWindowTitle("OCR 取り込みの進捗")
        dialog.resize(520, 360)
        layout = QVBoxLayout(dialog)
        layout.addWidget(progress)
        dialog.show()
        self._progress_dialog = dialog

        queue.submit_many(
            paths,
            language=settings.language,
            vertical=settings.vertical or None,
        )
        return queue
