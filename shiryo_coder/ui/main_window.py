"""メインウィンドウ。

三カラムの史料カタログ（左＝コレクション/タグツリー、中央＝検索可能な
ドキュメント一覧、右＝プレビュー）と、OCR 取り込みワークフロー（仕様書 3.1/3.2）。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from shiryo_coder import __app_name__, __version__
from shiryo_coder.db import Database
from shiryo_coder.modules.library import LibraryRepository
from shiryo_coder.ui.library import LibraryPanel

_IMPORT_FILTER = "史料 (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.pdf *.zip);;すべて (*)"
_COLLECTION_ROLE = Qt.ItemDataRole.UserRole


class MainWindow(QMainWindow):
    """アプリのメインウィンドウ。"""

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.repo = LibraryRepository(db)
        self.project_id = self._ensure_project()
        self._queues: list = []          # 実行中の OcrQueue を保持（GC 防止）
        self.setWindowTitle(f"{__app_name__}  v{__version__}")
        self.resize(1280, 780)
        self._build_menu()
        self._build_central()
        self._build_status_bar()
        self._refresh_collections()

    # -- 構築 ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = self.menuBar()
        import_menu = menubar.addMenu("取り込み(&I)")
        action = QAction("OCR 取り込み…", self)
        action.triggered.connect(self.import_documents)
        import_menu.addAction(action)

        vault_action = QAction("Obsidian Vault を取り込み…", self)
        vault_action.triggered.connect(self.import_vault)
        import_menu.addAction(vault_action)

        coding_menu = menubar.addMenu("コーディング(&C)")
        code_action = QAction("選択した史料をコーディング…", self)
        code_action.triggered.connect(self.open_coding)
        coding_menu.addAction(code_action)

        analysis_menu = menubar.addMenu("分析(&A)")
        reliability_action = QAction("信頼性検証（コーダー間一致率）…", self)
        reliability_action.triggered.connect(self.open_reliability)
        analysis_menu.addAction(reliability_action)

        for label in ("エクスポート(&E)", "ヘルプ(&H)"):
            menubar.addMenu(label)

    def _build_central(self) -> None:
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("コレクション")
        self.tree.currentItemChanged.connect(self._on_collection_selected)

        self.panel = LibraryPanel(self.repo, self.project_id)
        self.panel.document_activated.connect(self._open_coding_for)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.panel)
        splitter.setSizes([220, 1040])

        container = QWidget()
        outer = QHBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(splitter)
        self.setCentralWidget(container)

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        status.showMessage(f"DB: {self.db.db_path}  /  スキーマ v{self.db.schema_version()}")
        self.setStatusBar(status)

    # -- コレクションツリー -----------------------------------------------------
    def _refresh_collections(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        root = QTreeWidgetItem(self.tree, ["すべての史料"])
        root.setData(0, _COLLECTION_ROLE, None)
        for row in self.repo.collections(self.project_id):
            label = f"{row['name']}（{row['doc_count']}）"
            item = QTreeWidgetItem(root, [label])
            item.setData(0, _COLLECTION_ROLE, row["id"])
        self.tree.expandAll()
        self.tree.setCurrentItem(root)
        self.tree.blockSignals(False)

    def _on_collection_selected(self, current, _previous) -> None:
        if current is None:
            return
        self.panel.set_collection(current.data(0, _COLLECTION_ROLE))

    def _reload_library(self) -> None:
        self.panel.reload_filters()
        self.panel.refresh()
        self._refresh_collections()

    # -- プロジェクト -----------------------------------------------------------
    def _ensure_project(self) -> int:
        row = self.db.conn.execute("SELECT id FROM project ORDER BY id LIMIT 1").fetchone()
        if row is not None:
            return int(row["id"])
        row = self.db.conn.execute(
            "INSERT INTO project(name) VALUES ('既定プロジェクト') RETURNING id"
        ).fetchone()
        self.db.conn.commit()
        return int(row["id"])

    # -- コーディング -----------------------------------------------------------
    def _ensure_coder(self) -> int:
        row = self.db.conn.execute(
            "SELECT id FROM coder WHERE project_id = ? ORDER BY id LIMIT 1", (self.project_id,)
        ).fetchone()
        if row is not None:
            return int(row["id"])
        row = self.db.conn.execute(
            "INSERT INTO coder(project_id, name, role) VALUES (?, '既定コーダー', 'admin') "
            "RETURNING id",
            (self.project_id,),
        ).fetchone()
        self.db.conn.commit()
        return int(row["id"])

    def open_coding(self) -> None:
        doc_id = self.panel.current_document_id()
        if doc_id is None:
            QMessageBox.information(self, "コーディング", "史料を選択してください。")
            return
        self._open_coding_for(doc_id)

    def _open_coding_for(self, document_id: int) -> "object":
        from shiryo_coder.ui.coding import CodingWidget

        self._ensure_coder()
        window = QMainWindow(self)
        window.setWindowTitle("コーディング")
        widget = CodingWidget(self.db, self.project_id)
        window.setCentralWidget(widget)
        widget.open_document(document_id)
        window.resize(1100, 720)
        window.show()
        self._coding_window = window
        return widget

    # -- 信頼性検証 -------------------------------------------------------------
    def open_reliability(self) -> "object":
        from shiryo_coder.ui.reliability import ReliabilityPanel

        window = QMainWindow(self)
        window.setWindowTitle("信頼性検証")
        panel = ReliabilityPanel(self.db, self.project_id)
        window.setCentralWidget(panel)
        window.resize(820, 620)
        window.show()
        self._reliability_window = window
        return panel

    # -- Obsidian Vault 取り込み ------------------------------------------------
    def import_vault(self) -> None:
        from shiryo_coder.modules.library import obsidian

        folder = QFileDialog.getExistingDirectory(self, "Obsidian Vault を選択")
        if not folder:
            return
        ids = obsidian.import_vault(self.db, self.project_id, folder)
        self._reload_library()
        QMessageBox.information(self, "取り込み", f"{len(ids)} 件のノートを取り込みました。")

    # -- OCR 取り込みワークフロー -----------------------------------------------
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
            pipeline.persist(self.db, self.project_id, doc)
            self._reload_library()

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
