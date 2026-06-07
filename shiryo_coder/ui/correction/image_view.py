"""左ペイン: 元画像＋行バウンディングボックス表示。

行ボックスをクリックすると `line_clicked(index)` を送出し、
外部からの `highlight(index)` で選択行を強調する。
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsView

from shiryo_coder.ui.correction.model import CorrectionModel

_NORMAL_PEN = QPen(QColor(0, 120, 215), 1)
_SELECTED_PEN = QPen(QColor(220, 50, 50), 3)
_SELECTED_BRUSH = QBrush(QColor(220, 50, 50, 60))
_EMPTY_BRUSH = QBrush(Qt.BrushStyle.NoBrush)


def to_qpixmap(image) -> QPixmap:
    """numpy 配列（BGR/グレースケール）またはパスを QPixmap に変換する。"""
    if isinstance(image, (str, bytes)) or hasattr(image, "__fspath__"):
        return QPixmap(str(image))

    import numpy as np

    arr = np.ascontiguousarray(image)
    h, w = arr.shape[:2]
    if arr.ndim == 2:
        qimg = QImage(arr.data, w, h, w, QImage.Format.Format_Grayscale8)
    else:
        rgb = np.ascontiguousarray(arr[:, :, ::-1])  # BGR -> RGB
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    # QImage はバッファを参照するだけなので、所有権を持つコピーを返す
    return QPixmap.fromImage(qimg.copy())


class ImageBoxView(QGraphicsView):
    """行ボックス付きの画像ビュー。"""

    line_clicked = Signal(int)

    def __init__(self, model: CorrectionModel, image, parent=None) -> None:
        super().__init__(parent)
        self._model = model
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self._pixmap_item = self._scene.addPixmap(to_qpixmap(image))
        self._rects: dict[int, QGraphicsRectItem] = {}
        for line in model.lines:
            b = line.bbox
            rect = self._scene.addRect(
                QRectF(b.x, b.y, b.w, b.h), _NORMAL_PEN, _EMPTY_BRUSH
            )
            rect.setData(0, line.index)
            rect.setToolTip(line.original)
            self._rects[line.index] = rect
        self._scene.setSceneRect(self._pixmap_item.boundingRect())

    # -- 操作 ------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        scene_pos = self.mapToScene(event.position().toPoint())
        index = self._model.line_at_point(scene_pos.x(), scene_pos.y())
        if index is not None:
            self.line_clicked.emit(index)
        super().mousePressEvent(event)

    def highlight(self, index: int | None) -> None:
        """選択行のボックスを強調し、対象を表示範囲に入れる。"""
        for i, rect in self._rects.items():
            if i == index:
                rect.setPen(_SELECTED_PEN)
                rect.setBrush(_SELECTED_BRUSH)
            else:
                rect.setPen(_NORMAL_PEN)
                rect.setBrush(_EMPTY_BRUSH)
        if index is not None and index in self._rects:
            self.ensureVisible(self._rects[index])

    def fit(self) -> None:
        if self._pixmap_item is not None:
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        super().showEvent(event)
        self.fit()
