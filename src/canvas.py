import os
from typing import List, Tuple
import cv2
import numpy as np
from PySide6 import QtCore
from PySide6.QtCore import Qt, QPointF, QRect
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath
from PySide6.QtWidgets import (
    QWidget,
)

from projections import Projection
from utils import cv_to_qimage


class Canvas(QWidget):
    """Render widget with draggable 4-point quad per media; live homography warp."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

        # NEW: list of projections (media + quad)
        self.projections: List[Projection] = []
        self.selected_idx: int = -1  # which projection we are editing

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(16)  # ~60 fps
        self.timer.timeout.connect(self.update)
        self.timer.start()

        self.live_warp = True
        self.show_mesh = True
        self.drag_idx = -1
        self.handle_radius = 10
        self.bg_color = QColor(18, 18, 18)

        self._cached_frame: np.ndarray = None

    def _default_quad(self) -> List[QPointF]:
        """Quad inset from widget edges."""
        w = max(1, self.width())
        h = max(1, self.height())
        margin = min(w, h) * 0.1
        return [
            QPointF(margin, margin),
            QPointF(w - margin, margin),
            QPointF(w - margin, h - margin),
            QPointF(margin, h - margin),
        ]

    def reset_quad(self):
        """Reset currently selected quad; if none, reset all."""
        if self.selected_idx >= 0 and self.selected_idx < len(self.projections):
            self.projections[self.selected_idx].target_quad = self._default_quad()
        else:
            for p in self.projections:
                p.target_quad = self._default_quad()
        self.update()

    # --- MULTI-MEDIA API ---

    def add_media(self, paths: List[str]):
        """Add one or more media files. Each becomes its own projection."""
        if not paths:
            return
        # If canvas size unknown yet, just use default hardcoded quad; it will still be editable
        base_quad = self._default_quad()

        # Stagger quads a bit so multiple are visible initially
        offset_step = 40
        start_offset = len(self.projections) * offset_step

        for i, path in enumerate(paths):
            quad = [QPointF(p.x() + start_offset + i*10, p.y() + start_offset + i*10) for p in base_quad]
            try:
                proj = Projection(path, quad)
                self.projections.append(proj)
            except Exception as e:
                print(f"[WARN] Failed to load {path}: {e}")

        if self.projections and self.selected_idx == -1:
            self.selected_idx = 0

        self.update()

    def select_next(self, direction: int = +1):
        if not self.projections:
            self.selected_idx = -1
            return
        self.selected_idx = (self.selected_idx + direction) % len(self.projections)
        self.update()

    # --- RENDERING ---

    # canvas.py
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.bg_color)

        if not self.projections:
            painter.setPen(QPen(QColor(220, 220, 220)))
            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                "Add media (Toolbar → Add Media) to begin.\nDrag corner handles to align.",
            )
            self.draw_overlay(painter)
            return

        w, h = self.width(), self.height()

        for idx, proj in enumerate(self.projections):
            frame = proj.media.get_frame()
            if frame is None:
                continue

            # source and destination quads
            src_w, src_h = proj.media.get_source_size()
            src_quad = np.array(
                [[0, 0], [src_w - 1, 0], [src_w - 1, src_h - 1], [0, src_h - 1]],
                dtype=np.float32,
            )
            dst_quad = np.array([[p.x(), p.y()] for p in proj.target_quad], dtype=np.float32)

            # Build clip path for this quad (ALWAYS clip!)
            path = QPainterPath()
            path.moveTo(dst_quad[0][0], dst_quad[0][1])
            for i in range(1, 4):
                path.lineTo(dst_quad[i][0], dst_quad[i][1])
            path.closeSubpath()

            painter.save()
            painter.setClipPath(path)

            if self.live_warp:
                # Warp into full-canvas buffer, then draw under clip
                H = cv2.getPerspectiveTransform(src_quad, dst_quad)
                warped = cv2.warpPerspective(frame, H, (w, h))
                qimg = cv_to_qimage(warped)
                painter.drawImage(0, 0, qimg)
            else:
                # Non-live mode: draw the raw frame scaled to the quad’s bounding box, still clipped to quad
                qimg = cv_to_qimage(frame)
                # simple bounding-rect fit (keeps aspect)
                minx, miny = np.min(dst_quad, axis=0).astype(int)
                maxx, maxy = np.max(dst_quad, axis=0).astype(int)
                bw = max(1, maxx - minx)
                bh = max(1, maxy - miny)
                scaled = qimg.scaled(bw, bh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                # center inside the bounding rect
                ox = minx + (bw - scaled.width()) // 2
                oy = miny + (bh - scaled.height()) // 2
                painter.drawImage(ox, oy, scaled)

            painter.restore()

        # Draw overlays LAST, so handles/mesh are always visible
        self.draw_overlay(painter)


    def draw_overlay(self, painter: QPainter):
        if not self.show_mesh:
            return

        for idx, proj in enumerate(self.projections):
            # Highlight selected projection differently
            color = QColor(0, 200, 255, 220) if idx != self.selected_idx else QColor(255, 180, 0, 230)
            pen = QPen(color, 2, Qt.SolidLine)
            painter.setPen(pen)

            quad = proj.target_quad
            for i in range(4):
                a = quad[i]
                b = quad[(i + 1) % 4]
                painter.drawLine(a, b)

            # Handles
            for i, p in enumerate(quad):
                painter.setBrush(QBrush(QColor(255, 255, 255)))
                painter.setPen(QPen(Qt.black, 1))
                r = self.handle_radius
                painter.drawEllipse(QtCore.QPointF(p.x(), p.y()), r, r)

        # Legend
        painter.setPen(QPen(QColor(220, 220, 220)))
        painter.drawText(
            QRect(10, 10, 500, 60),
            Qt.AlignLeft | Qt.AlignTop,
            "Tip: Use Prev/Next Surface to choose which quad to edit.\nSelected quad = orange.",
        )

    # --- INPUT ---

    def _hit_handle(self, pos: QPointF):
        """Return (proj_idx, handle_idx) of the first handle under cursor, else (-1,-1)."""
        for pidx, proj in enumerate(self.projections):
            for i, pt in enumerate(proj.target_quad):
                if (pos - pt).manhattanLength() <= self.handle_radius * 1.5:
                    return pidx, i
        return -1, -1

    # canvas.py
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position()
            pidx, hidx = self._hit_handle(pos)
            if pidx != -1:
                self.selected_idx = pidx
                self.drag_idx = hidx
                # raise selected to top so it renders last
                if 0 <= pidx < len(self.projections):
                    self.projections.append(self.projections.pop(pidx))
                    self.selected_idx = len(self.projections) - 1
                self.update()
                return
        super().mousePressEvent(event)


    def mouseMoveEvent(self, event):
        if self.drag_idx >= 0 and 0 <= self.selected_idx < len(self.projections):
            pos = event.position()
            x = max(0, min(self.width(), pos.x()))
            y = max(0, min(self.height(), pos.y()))
            self.projections[self.selected_idx].target_quad[self.drag_idx] = QPointF(x, y)
            self.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_idx = -1
        super().mouseReleaseEvent(event)

    # --- PRESET I/O ---

    def serialize(self) -> dict:
        return {
            "live_warp": self.live_warp,
            "show_mesh": self.show_mesh,
            # NEW: array of projections
            "projections": [
                {
                    "media_path": p.path,
                    "target_quad": [[pt.x(), pt.y()] for pt in p.target_quad],
                }
                for p in self.projections
            ],
        }

    def deserialize(self, data: dict):
        self.live_warp = bool(data.get("live_warp", True))
        self.show_mesh = bool(data.get("show_mesh", True))

        self.projections = []
        projections = data.get("projections")

        # Back-compat: support old single-media schema if present
        if not projections:
            tq = data.get("target_quad")
            media_path = data.get("media_path")
            if media_path:
                quad = [QPointF(float(x), float(y)) for x, y in tq] if tq else self._default_quad()
                try:
                    self.projections.append(Projection(media_path, quad))
                except Exception as e:
                    print(f"[WARN] failed to load legacy preset media: {e}")
        else:
            for item in projections:
                media_path = item.get("media_path")
                tq = item.get("target_quad") or []
                quad = [QPointF(float(x), float(y)) for x, y in tq] if len(tq) == 4 else self._default_quad()
                if media_path and os.path.exists(media_path):
                    try:
                        self.projections.append(Projection(media_path, quad))
                    except Exception as e:
                        print(f"[WARN] failed to load {media_path}: {e}")

        self.selected_idx = 0 if self.projections else -1
        self.update()
