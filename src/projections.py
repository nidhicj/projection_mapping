
import json
import math
import os
import sys

from pathlib import Path
from typing import List
from video_source import VideoSource
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QPointF

class Projection:
    """One mapped media on its own quad."""
    def __init__(self, path: str, quad: List[QPointF] | None = None):
        self.media = VideoSource()
        self.media.load(path)
        self.path = path
        self.target_quad: List[QPointF] = quad or [
            QPointF(200, 150),
            QPointF(800, 150),
            QPointF(800, 550),
            QPointF(200, 550),
        ]