"""Check fixed landmarks before reusing a map-based camera calibration."""
import cv2
import numpy as np

from vehicle_detection.paths import DATA_DIR


def landmark_edges(gray):
    dx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    dy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    return np.abs(dx) + np.abs(dy)


class CameraView:
    def __init__(self, profile):
        self.size = tuple(profile["image_size"])
        path = DATA_DIR / "calibration" / profile["camera_id"] / "view.npz"
        try:
            with np.load(path, allow_pickle=False) as data:
                self.landmarks = [(tuple(box), data[f"patch{i}"]) for i, box in enumerate(data["boxes"])]
        except (OSError, KeyError, ValueError) as exc:
            raise ValueError("Thiếu hoặc lỗi bộ mốc kiểm tra góc camera") from exc

    def matches(self, frame):
        height, width = frame.shape[:2]
        if (width, height) != self.size:
            return False
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        padding = 16
        matched_sides = set()
        for (x, y, w, h), patch in self.landmarks:
            search = gray[y-padding:y+h+padding, x-padding:x+w+padding]
            response = cv2.matchTemplate(landmark_edges(search), patch, cv2.TM_CCOEFF_NORMED)
            _, score, _, (dx, dy) = cv2.minMaxLoc(response)
            if score >= 0.54 and abs(dx - padding) <= 5 and abs(dy - padding) <= 5:
                matched_sides.add(x >= width / 2)
        return len(matched_sides) == 2
