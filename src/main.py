
import json
import math
import os
import sys
from pathlib import Path
from typing import List, Tuple
from canvas import Canvas

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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Projection Mapper — MVP")
        self.resize(1200, 800)

        self.canvas = Canvas(self)
        self.setCentralWidget(self.canvas)

        # Controls
        toolbar = self.addToolBar("Main")

        # NEW: Add Media(s)
        act_add = QAction("Add Media", self)
        act_add.setToolTip("Add one or more image/video files")
        act_add.triggered.connect(self.open_media_multi)
        toolbar.addAction(act_add)

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

        # NEW: select which projection to edit
        btn_prev = QPushButton("Prev Surface")
        btn_prev.clicked.connect(lambda: self.canvas.select_next(-1))
        toolbar.addWidget(btn_prev)

        btn_next = QPushButton("Next Surface")
        btn_next.clicked.connect(lambda: self.canvas.select_next(+1))
        toolbar.addWidget(btn_next)

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

    def open_media_multi(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Images/Videos",
            "",
            "Media Files (*.png *.jpg *.jpeg *.bmp *.mp4 *.mov *.avi *.mkv);;All Files (*)",
        )
        if paths:
            self.canvas.add_media(paths)
            self.statusBar().showMessage(f"Added {len(paths)} media file(s)")


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
