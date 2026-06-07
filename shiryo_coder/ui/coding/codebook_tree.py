"""コードブックツリー（左ペイン）。

無制限階層、色スウォッチ、ドラッグ&ドロップによる親子変更、コンテキストメニュー
（子追加・改名・削除）。頻用コードには数字キー 1–9 のヒントを表示する。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QInputDialog,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
)

from shiryo_coder.modules.coding import CodebookRepository
from shiryo_coder.modules.coding.codebook import CycleError

_CODE_ROLE = Qt.ItemDataRole.UserRole


def _color_icon(color: str | None) -> QIcon:
    pix = QPixmap(14, 14)
    pix.fill(QColor(color) if color else QColor("#cccccc"))
    return QIcon(pix)


class CodebookTree(QTreeWidget):
    """コードブックの階層表示・編集。"""

    code_selected = Signal(int)
    codebook_changed = Signal()

    def __init__(self, repo: CodebookRepository, project_id: int, parent=None) -> None:
        super().__init__(parent)
        self.repo = repo
        self.project_id = project_id
        self._quick: list[int] = []        # 数字キー割当（先頭 9 件）

        self.setHeaderLabel("コードブック")
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self.currentItemChanged.connect(self._on_current_changed)
        self.reload()

    # -- 表示 ------------------------------------------------------------------
    def reload(self) -> None:
        self.blockSignals(True)
        self.clear()
        self._quick = []
        for root in self.repo.tree(self.project_id):
            self._add_node(root, self)
        self.expandAll()
        self.blockSignals(False)

    def _add_node(self, node, parent) -> None:
        quick_hint = ""
        if len(self._quick) < 9:
            self._quick.append(node.id)
            quick_hint = f"[{len(self._quick)}] "
        item = QTreeWidgetItem(parent, [f"{quick_hint}{node.name}"])
        item.setData(0, _CODE_ROLE, node.id)
        item.setIcon(0, _color_icon(node.color))
        if node.definition:
            item.setToolTip(0, node.definition)
        for child in node.children:
            self._add_node(child, item)

    # -- 参照 ------------------------------------------------------------------
    def current_code_id(self) -> int | None:
        item = self.currentItem()
        return item.data(0, _CODE_ROLE) if item else None

    def quick_code(self, index: int) -> int | None:
        """数字キー（1–9）に対応するコード id。"""
        return self._quick[index - 1] if 1 <= index <= len(self._quick) else None

    def _on_current_changed(self, current, _previous) -> None:
        if current is not None:
            self.code_selected.emit(current.data(0, _CODE_ROLE))

    # -- 編集操作 ---------------------------------------------------------------
    def add_code(self, parent_id: int | None) -> None:
        name, ok = QInputDialog.getText(self, "コード追加", "コード名:")
        if ok and name.strip():
            self.repo.create_code(self.project_id, name.strip(), parent_id=parent_id)
            self.reload()
            self.codebook_changed.emit()

    def rename_code(self, code_id: int, current_name: str) -> None:
        name, ok = QInputDialog.getText(self, "改名", "新しい名前:", text=current_name)
        if ok and name.strip():
            self.repo.update_code(code_id, name=name.strip())
            self.reload()
            self.codebook_changed.emit()

    def delete_code(self, code_id: int) -> None:
        self.repo.delete_code(code_id)
        self.reload()
        self.codebook_changed.emit()

    def reparent(self, code_id: int, new_parent_id: int | None) -> bool:
        """コードを別の親へ移動する。循環なら False。"""
        try:
            self.repo.move_code(code_id, new_parent_id)
        except CycleError:
            return False
        self.reload()
        self.codebook_changed.emit()
        return True

    # -- ドラッグ&ドロップ ------------------------------------------------------
    def dropEvent(self, event) -> None:
        dragged = self.currentItem()
        if dragged is None:
            event.ignore()
            return
        target = self.itemAt(event.position().toPoint())
        new_parent_id = target.data(0, _CODE_ROLE) if target else None
        # DB を真実とし、ウィジェット側の自動移動は行わず reload で再構築する
        self.reparent(dragged.data(0, _CODE_ROLE), new_parent_id)
        event.acceptProposedAction()

    # -- コンテキストメニュー ---------------------------------------------------
    def _show_menu(self, pos) -> None:
        item = self.itemAt(pos)
        menu = QMenu(self)
        if item is not None:
            code_id = item.data(0, _CODE_ROLE)
            menu.addAction("子コードを追加", lambda: self.add_code(code_id))
            menu.addAction("改名", lambda: self.rename_code(code_id, item.text(0)))
            menu.addAction("最上位へ移動", lambda: self.reparent(code_id, None))
            menu.addSeparator()
            menu.addAction("削除", lambda: self.delete_code(code_id))
        else:
            menu.addAction("最上位コードを追加", lambda: self.add_code(None))
        menu.exec(self.viewport().mapToGlobal(pos))
