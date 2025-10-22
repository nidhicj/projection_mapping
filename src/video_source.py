from typing import Tuple

import cv2
import numpy as np

class VideoSource:
    """Handles image or video using OpenCV. Unifies get_frame()."""

    def __init__(self):
        self.cap = None
        self.single_frame = None
        self.path = None

    def load(self, path: str):
        self.path = path
        # Try video first
        cap = cv2.VideoCapture(path)
        if cap.isOpened() and int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) > 1:
            self.cap = cap
            self.single_frame = None
            return
        # Fallback image
        cap.release()
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to load media. Unsupported or missing file.")
        self.single_frame = img
        self.cap = None

    def get_frame(self) -> np.ndarray:
        if self.cap is not None:
            ok, frame = self.cap.read()
            if not ok:
                # loop
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self.cap.read()
            return frame
        return self.single_frame

    def get_source_size(self) -> Tuple[int, int]:
        if self.cap is not None:
            w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return w, h
        if self.single_frame is not None:
            h, w, _ = self.single_frame.shape
            return w, h
        return 1920, 1080  # default
