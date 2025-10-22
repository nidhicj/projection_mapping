
import json
import math
import os
import sys
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QPointF, QRect
from PySide6.QtGui import QAction, QImage, QPainter, QPen, QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QWidget,
    QCheckBox,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
)



class Canvas(QWidget):
    """Render widget with draggable 4-point quad and live homography warp."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.media = VideoSource()
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(16)  # ~60 fps
        self.timer.timeout.connect(self.update)
        self.timer.start()

        self.live_warp = True
        self.show_mesh = True
        self.drag_idx = -1
        self.handle_radius = 10
        self.bg_color = QColor(18, 18, 18)

        # Target quad initialized as a margin inset rectangle
        self.target_quad: List[QPointF] = [
            QPointF(200, 150),
            QPointF(800, 150),
            QPointF(800, 550),
            QPointF(200, 550),
        ]

        self._cached_frame: np.ndarray = None

    def reset_quad(self):
        w = self.width()
        h = self.height()
        margin = min(w, h) * 0.1
        self.target_quad = [
            QPointF(margin, margin),
            QPointF(w - margin, margin),
            QPointF(w - margin, h - margin),
            QPointF(margin, h - margin),
        ]
        self.update()

    def load_media(self, path: str):
        self.media.load(path)
        self._cached_frame = None  # force refresh

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.bg_color)

        frame = self.media.get_frame()
        if frame is None:
            # Draw helper text
            painter.setPen(QPen(QColor(220, 220, 220)))
            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                "Load an image or video (File → Open)",
            )
            self.draw_overlay(painter)
            return

        src_w, src_h = self.media.get_source_size()
        src_quad = np.array(
            [[0, 0], [src_w - 1, 0], [src_w - 1, src_h - 1], [0, src_h - 1]],
            dtype=np.float32,
        )

        dst_quad = np.array(
            [[p.x(), p.y()] for p in self.target_quad], dtype=np.float32
        )

        # Compute homography and warp to widget size
        if self.live_warp:
            H = cv2.getPerspectiveTransform(src_quad, dst_quad)
            # Warp into a canvas same size as widget
            w, h = self.width(), self.height()
            warped = cv2.warpPerspective(frame, H, (w, h))
            qimg = cv_to_qimage(warped)
            painter.drawImage(0, 0, qimg)
        else:
            # Show unwarped, scaled to fit
            qimg = cv_to_qimage(frame)
            scaled = qimg.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)

        self.draw_overlay(painter)

    def draw_overlay(self, painter: QPainter):
        # Draw quad edges
        if self.show_mesh:
            pen = QPen(QColor(0, 200, 255, 200), 2, Qt.SolidLine)
            painter.setPen(pen)
            for i in range(4):
                a = self.target_quad[i]
                b = self.target_quad[(i + 1) % 4]
                painter.drawLine(a, b)
            # Draw handles
            for i, p in enumerate(self.target_quad):
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.setPen(QPen(Qt.black, 1))
                r = self.handle_radius
                painter.drawEllipse(QtCore.QPointF(p.x(), p.y()), r, r)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position()
            for i, p in enumerate(self.target_quad):
                if (pos - p).manhattanLength() <= self.handle_radius * 1.5:
                    self.drag_idx = i
                    return
        elif event.key() == Qt.Key_H:
            hidden = not any(tb.isVisible() for tb in self.findChildren(QtWidgets.QToolBar))
            for tb in self.findChildren(QtWidgets.QToolBar):
                tb.setVisible(hidden)
            print(f"[DEBUG] toolbar hidden={hidden}")
        
        super().mousePressEvent(event)



    def mouseMoveEvent(self, event):
        if self.drag_idx >= 0:
            pos = event.position()
            # Clamp to widget rect
            x = max(0, min(self.width(), pos.x()))
            y = max(0, min(self.height(), pos.y()))
            self.target_quad[self.drag_idx] = QPointF(x, y)
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_idx = -1
        super().mouseReleaseEvent(event)

    def serialize(self) -> dict:
        return {
            "target_quad": [[p.x(), p.y()] for p in self.target_quad],
            "live_warp": self.live_warp,
            "show_mesh": self.show_mesh,
            "media_path": self.media.path,
        }

    def deserialize(self, data: dict):
        tq = data.get("target_quad")
        if tq and len(tq) == 4:
            self.target_quad = [QPointF(float(x), float(y)) for x, y in tq]
        self.live_warp = bool(data.get("live_warp", True))
        self.show_mesh = bool(data.get("show_mesh", True))
        media_path = data.get("media_path")
        if media_path and os.path.exists(media_path):
            try:
                self.media.load(media_path)
            except Exception:
                pass
        self.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Projection Mapper — MVP")
        self.resize(1200, 800)

        self.canvas = Canvas(self)
        self.setCentralWidget(self.canvas)

        # Controls
        toolbar = self.addToolBar("Main")
        act_open = QAction("Open Media", self)
        act_open.triggered.connect(self.open_media)
        toolbar.addAction(act_open)

        act_save = QAction("Save Preset", self)
        act_save.triggered.connect(self.save_preset)
        toolbar.addAction(act_save)

        act_load = QAction("Load Preset", self)
        act_load.triggered.connect(self.load_preset)
        toolbar.addAction(act_load)

        act_reset = QAction("Reset Quad", self)
        act_reset.triggered.connect(self.canvas.reset_quad)
        toolbar.addAction(act_reset)

        toolbar.addSeparator()

        self.chk_live = QCheckBox("Live Warp")
        self.chk_live.setChecked(True)
        self.chk_live.stateChanged.connect(self.toggle_live)
        toolbar.addWidget(self.chk_live)

        self.chk_mesh = QCheckBox("Show Mesh")
        self.chk_mesh.setChecked(True)
        self.chk_mesh.stateChanged.connect(self.toggle_mesh)
        toolbar.addWidget(self.chk_mesh)

        toolbar.addSeparator()

        btn_full = QPushButton("Toggle Fullscreen")
        btn_full.clicked.connect(self.toggle_fullscreen)
        toolbar.addWidget(btn_full)

        btn_hide_toolbar = QPushButton("Hide Toolbar")
        btn_hide_toolbar.setCheckable(True)
        btn_hide_toolbar.clicked.connect(self.toggle_toolbar)
        toolbar.addWidget(btn_hide_toolbar)


        # Status tip
        self.statusBar().showMessage("Load media to begin (File → Open Media). Drag corner handles to align.")

    def open_media(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Image/Video",
            "",
            "Media Files (*.png *.jpg *.jpeg *.bmp *.mp4 *.mov *.avi *.mkv);;All Files (*)",
        )
        if path:
            try:
                self.canvas.load_media(path)
                self.statusBar().showMessage(f"Loaded: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", str(e))

    def save_preset(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Preset", "preset.json", "JSON (*.json)"
        )
        if path:
            try:
                data = self.canvas.serialize()
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                self.statusBar().showMessage(f"Saved preset: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e))

    def load_preset(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Preset", "", "JSON (*.json);;All Files (*)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.canvas.deserialize(data)
                self.statusBar().showMessage(f"Loaded preset: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Load Error", str(e))

    def toggle_live(self, state: int):
        print(f"[DEBUG] toggle_live state={state} checked={state == Qt.Checked}")
        self.canvas.live_warp = state == Qt.Checked
        self.canvas.update()

    def toggle_mesh(self, state: int):
        print(f"[DEBUG] toggle_mesh state={state} checked={state == Qt.Checked}")
        self.canvas.show_mesh = state == Qt.Checked
        self.canvas.update()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def toggle_toolbar(self, checked: bool):
        for tb in self.findChildren(QtWidgets.QToolBar):
            tb.setVisible(not checked)
            print(f"[DEBUG] toolbar visible={not checked}")
        msg = "Toolbar hidden (press H to toggle back)" if checked else "Toolbar visible"
        self.statusBar().showMessage(msg)


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
