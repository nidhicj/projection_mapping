import os
import sys
import cv2
import numpy as np

from pathlib import Path
from typing import List, Tuple
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage





def cv_to_qimage(frame_bgr: np.ndarray) -> QImage:
    """Convert OpenCV BGR ndarray to QImage (RGB888)."""
    if frame_bgr is None:
        return QImage()
    if len(frame_bgr.shape) == 2:
        # Grayscale
        h, w = frame_bgr.shape
        qimg = QImage(frame_bgr.data, w, h, w, QImage.Format_Grayscale8)
        return qimg.copy()
    # Color
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = frame_rgb.shape
    bytes_per_line = ch * w
    qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
    return qimg.copy()


def order_quad_clockwise(points: List[QPointF]) -> List[QPointF]:
    """Return points ordered clockwise starting from top-left approx."""
    # Convert to array
    arr = np.array([[p.x(), p.y()] for p in points], dtype=np.float32)
    # Compute centroid
    c = arr.mean(axis=0)
    # Compute angles and sort clockwise (negative for Qt's y-down coords ok)
    angles = np.arctan2(arr[:, 1] - c[1], arr[:, 0] - c[0])
    order = np.argsort(angles)
    ordered = arr[order]
    # Heuristic: ensure first is top-left by y then x
    idx_tl = np.argmin(ordered[:, 1] + ordered[:, 0] * 0.001)
    ordered = np.roll(ordered, -idx_tl, axis=0)
    return [QPointF(float(x), float(y)) for x, y in ordered]
