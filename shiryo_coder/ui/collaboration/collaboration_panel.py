"""共同作業パネル（仕様書 3.7）。

操作ユーザー（コーダー）を選び、アカウント管理・変更履歴・承認ワークフロー・
ロックをタブで扱う。承認系は管理者役割のときのみ実行できる。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from shiryo_coder.modules.collaboration import (
    ROLES,
    AccountRepository,
    ApprovalWorkflow,
    AuditRepository,
    LockRepository,
    PermissionError,
    WorkflowError,
)


class CollaborationPanel(QWidget):
    """アカウント・履歴・承認・ロック。"""

    def __init__(self, db, project_id: int, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.project_id = project_id
        self.accounts = AccountRepository(db)
        self.audit = AuditRepository(db)
        self.workflow = ApprovalWorkflow(db)
        self.locks = LockRepository(db)

        self.user_combo = QComboBox()
        top = QHBoxLayout()
        top.addWidget(QLabel("操作ユーザー"))
        top.addWidget(self.user_combo, 1)

        tabs = QTabWidget()
        tabs.addTab(self._build_accounts_tab(), "アカウント")
        tabs.addTab(self._build_history_tab(), "変更履歴")
        tabs.addTab(self._build_approval_tab(), "承認")
        tabs.addTab(self._build_locks_tab(), "ロック")

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(tabs)
        self.reload()

    @property
    def current_user(self):
        return self.user_combo.currentData()

    # -- アカウントタブ --------------------------------------------------------
    def _build_accounts_tab(self) -> QWidget:
        self.account_table = QTableWidget(0, 2)
        self.account_table.setHorizontalHeaderLabels(["名前", "役割"])
        self.account_table.horizontalHeader().setStretchLastSection(True)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("コーダー名")
        self.role_combo = QComboBox()
        self.role_combo.addItems(ROLES)
        add_btn = QPushButton("追加")
        add_btn.clicked.connect(self.add_account)
        setrole_btn = QPushButton("選択者の役割を変更")
        setrole_btn.clicked.connect(self.change_role)

        controls = QHBoxLayout()
        controls.addWidget(self.name_edit, 1)
        controls.addWidget(self.role_combo)
        controls.addWidget(add_btn)
        controls.addWidget(setrole_btn)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self.account_table, 1)
        layout.addLayout(controls)
        return tab

    def _build_history_tab(self) -> QWidget:
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["日時", "ユーザー", "対象", "操作"])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        refresh = QPushButton("更新")
        refresh.clicked.connect(self.refresh_history)
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self.history_table, 1)
        layout.addWidget(refresh)
        return tab

    def _build_approval_tab(self) -> QWidget:
        self.draft_list = QListWidget()
        self.reviewed_list = QListWidget()
        approve_btn = QPushButton("主任承認（draft→reviewed）")
        approve_btn.clicked.connect(self.approve_selected)
        confirm_btn = QPushButton("確定（reviewed→confirmed）")
        confirm_btn.clicked.connect(self.confirm_selected)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(QLabel("下書き（承認待ち）"))
        layout.addWidget(self.draft_list)
        layout.addWidget(approve_btn)
        layout.addWidget(QLabel("承認済み（確定待ち）"))
        layout.addWidget(self.reviewed_list)
        layout.addWidget(confirm_btn)
        return tab

    def _build_locks_tab(self) -> QWidget:
        self.lock_doc_combo = QComboBox()
        acquire_btn = QPushButton("ロック取得")
        acquire_btn.clicked.connect(self.acquire_lock)
        release_btn = QPushButton("ロック解放")
        release_btn.clicked.connect(self.release_lock)
        controls = QHBoxLayout()
        controls.addWidget(self.lock_doc_combo, 1)
        controls.addWidget(acquire_btn)
        controls.addWidget(release_btn)

        self.lock_list = QListWidget()
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addLayout(controls)
        layout.addWidget(self.lock_list, 1)
        return tab

    # -- 読み込み --------------------------------------------------------------
    def reload(self) -> None:
        accounts = self.accounts.list(self.project_id)
        self.user_combo.clear()
        for a in accounts:
            self.user_combo.addItem(f"{a.name}（{a.role}）", a.id)

        self.account_table.setRowCount(len(accounts))
        for r, a in enumerate(accounts):
            name = QTableWidgetItem(a.name)
            name.setData(Qt.ItemDataRole.UserRole, a.id)
            self.account_table.setItem(r, 0, name)
            self.account_table.setItem(r, 1, QTableWidgetItem(a.role))

        self.lock_doc_combo.clear()
        for row in self.db.conn.execute(
            "SELECT id, title FROM document WHERE project_id = ? ORDER BY id", (self.project_id,)
        ):
            self.lock_doc_combo.addItem(row["title"], row["id"])

        self.refresh_history()
        self.refresh_pending()
        self.refresh_locks()

    # -- アカウント操作 ---------------------------------------------------------
    def add_account(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            return
        self.accounts.create(self.project_id, name, role=self.role_combo.currentText())
        self.name_edit.clear()
        self.reload()

    def _selected_account_id(self):
        row = self.account_table.currentRow()
        if row < 0:
            return None
        return self.account_table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def change_role(self) -> None:
        coder_id = self._selected_account_id()
        if coder_id is None:
            return
        self.accounts.set_role(coder_id, self.role_combo.currentText())
        self.reload()

    # -- 履歴 ------------------------------------------------------------------
    def refresh_history(self) -> None:
        names = {a.id: a.name for a in self.accounts.list(self.project_id)}
        entries = self.audit.for_project(self.project_id)
        self.history_table.setRowCount(len(entries))
        for r, e in enumerate(entries):
            self.history_table.setItem(r, 0, QTableWidgetItem(e.created_at))
            self.history_table.setItem(r, 1, QTableWidgetItem(names.get(e.coder_id, "—")))
            self.history_table.setItem(r, 2, QTableWidgetItem(f"{e.entity}#{e.entity_id}"))
            self.history_table.setItem(r, 3, QTableWidgetItem(e.action))

    # -- 承認 ------------------------------------------------------------------
    def refresh_pending(self) -> None:
        self.draft_list.clear()
        for sid in self.workflow.pending(self.project_id, "draft"):
            self._add_segment_item(self.draft_list, sid)
        self.reviewed_list.clear()
        for sid in self.workflow.pending(self.project_id, "reviewed"):
            self._add_segment_item(self.reviewed_list, sid)

    def _add_segment_item(self, listw: QListWidget, sid: int) -> None:
        row = self.db.conn.execute(
            "SELECT c.name AS code, s.char_start AS a, s.char_end AS b "
            "FROM segment s JOIN code c ON c.id = s.code_id WHERE s.id = ?", (sid,)
        ).fetchone()
        label = f"#{sid} {row['code']} [{row['a']}–{row['b']}]" if row else f"#{sid}"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, sid)
        listw.addItem(item)

    def approve_selected(self) -> None:
        self._transition(self.draft_list, self.workflow.approve)

    def confirm_selected(self) -> None:
        self._transition(self.reviewed_list, self.workflow.confirm)

    def _transition(self, listw: QListWidget, fn) -> None:
        item = listw.currentItem()
        if item is None or self.current_user is None:
            return
        try:
            fn(item.data(Qt.ItemDataRole.UserRole), self.current_user)
        except (PermissionError, WorkflowError) as exc:
            QMessageBox.warning(self, "承認", str(exc))
            return
        self.refresh_pending()
        self.refresh_history()

    # -- ロック ----------------------------------------------------------------
    def acquire_lock(self) -> None:
        doc = self.lock_doc_combo.currentData()
        if doc is None or self.current_user is None:
            return
        if not self.locks.acquire(doc, self.current_user):
            QMessageBox.warning(self, "ロック", "他のコーダーがロック中です。")
        self.refresh_locks()

    def release_lock(self) -> None:
        doc = self.lock_doc_combo.currentData()
        if doc is None or self.current_user is None:
            return
        self.locks.release(doc, self.current_user)
        self.refresh_locks()

    def refresh_locks(self) -> None:
        names = {a.id: a.name for a in self.accounts.list(self.project_id)}
        titles = {
            row["id"]: row["title"]
            for row in self.db.conn.execute(
                "SELECT id, title FROM document WHERE project_id = ?", (self.project_id,)
            )
        }
        self.lock_list.clear()
        for lock in self.locks.locks(self.project_id):
            self.lock_list.addItem(
                f"{titles.get(lock.document_id, lock.document_id)} → "
                f"{names.get(lock.coder_id, lock.coder_id)}（{lock.acquired_at}）"
            )
