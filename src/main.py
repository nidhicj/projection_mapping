
import json
import math
import os
import sys
from pathlib import Path
from typing import List, Tuple
from canvas import Canvas
import signal

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QPointF, QRect, QTimer
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

from PySide6.QtGui import QAction, QImage, QPainter, QPen, QBrush, QColor, QKeySequence
from PySide6.QtWidgets import (  # ensure these are imported
    QApplication, QMainWindow, QFileDialog, QMessageBox, QCheckBox, QPushButton, QToolBar
)
from PySide6.QtGui import QShortcut


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Projection Mapper — MVP")
        self.resize(1200, 800)

        self.canvas = Canvas(self)
        self.setCentralWidget(self.canvas)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

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
        self.chk_live.toggled.connect(self.toggle_live)
        toolbar.addWidget(self.chk_live)

        self.chk_mesh = QCheckBox("Show Mesh")
        self.chk_mesh.setChecked(True)
        self.chk_mesh.toggled.connect(self.toggle_mesh)
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

        # --- inside __init__ right after you create the toolbar and other widgets ---

        # Hide toolbar button (make it an instance attr so we can sync it from shortcuts)
        self.btn_hide_toolbar = QPushButton("Hide Toolbar")
        self.btn_hide_toolbar.setCheckable(True)
        self.btn_hide_toolbar.clicked.connect(self.toggle_toolbar)
        toolbar.addWidget(self.btn_hide_toolbar)

        # Keyboard shortcut: H toggles toolbar visibility and syncs the button
        self.shortcut_hide_toolbar = QShortcut(QKeySequence("H"), self)
        self.shortcut_hide_toolbar.activated.connect(self._shortcut_toggle_toolbar)



        # Status tip
        self.statusBar().showMessage("Load media to begin (File → Open Media). Drag corner handles to align.")

    def tick(self):
        # update any state variables here
        self.canvas.update()  # schedules paintEvent()

    def closeEvent(self, event):
        # Stop background activity before closing
        self.timer.stop()
        if hasattr(self, "canvas"):
            self.canvas._closing = True  # optional flag for paint guard
        super().closeEvent(event)

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

    # def toggle_live(self, state: int):
    #     print(f"[DEBUG] toggle_live state={state} checked={state == Qt.Checked}")
    #     self.canvas.live_warp = state == Qt.Checked
    #     self.canvas.update()

    # def toggle_mesh(self, state: int):
    #     print(f"[DEBUG] toggle_mesh state={state} checked={state == Qt.Checked}")
    #     self.canvas.show_mesh = state == Qt.Checked
    #     self.canvas.update()

    # --- replace these handlers ---
    def toggle_live(self, checked: bool):
        print(f"[DEBUG] toggle_live checked={checked}")
        self.canvas.live_warp = checked
        self.canvas.update()

    def toggle_mesh(self, checked: bool):
        print(f"[DEBUG] toggle_mesh checked={checked}")
        self.canvas.show_mesh = checked
        self.canvas.update()


    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # def toggle_toolbar(self, checked: bool):
    #     for tb in self.findChildren(QtWidgets.QToolBar):
    #         tb.setVisible(not checked)
    #         print(f"[DEBUG] toolbar visible={not checked}")
    #     msg = "Toolbar hidden (press H to toggle back)" if checked else "Toolbar visible"
    #     self.statusBar().showMessage(msg)
    # --- add these methods on the MainWindow class ---

    def _shortcut_toggle_toolbar(self):
        # Flip the button state and reuse the same slot
        new_checked = not self.btn_hide_toolbar.isChecked()
        self.btn_hide_toolbar.setChecked(new_checked)
        self.toggle_toolbar(new_checked)

    def toggle_toolbar(self, checked: bool):
        # True => hide, False => show
        for tb in self.findChildren(QToolBar):
            tb.setVisible(not checked)
        # keep UX hint accurate
        msg = "Toolbar hidden (press H to toggle back)" if checked else "Toolbar visible"
        self.statusBar().showMessage(msg)

def sigint_handler(signum, frame):
    # Stop timers/threads if you have them, then quit.
    QApplication.quit()

def main():
    app = QApplication(sys.argv)
    
   
    signal.signal(signal.SIGINT, sigint_handler)
    
    win = MainWindow()
    win.show()
    app.exec()




if __name__ == "__main__":
    main()
