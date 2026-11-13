"""Count unique tracks crossing a configured line."""
from collections import defaultdict
import numpy as np


class LineCrossingCounter:
    """
    Module đếm xe qua vạch ảo (Virtual Tripwire Line).
    Hỗ trợ đếm theo hướng (IN / OUT) và theo từng chủng loại phương tiện.
    """
    def __init__(self, line_pt1, line_pt2):
        self.p1 = np.array(line_pt1, dtype=np.float32)
        self.p2 = np.array(line_pt2, dtype=np.float32)
        self.counted_ids = set()
        self.prev_positions = {}

        # Thống kê số lượng
        self.total_in = 0
        self.total_out = 0
        self.class_counts = defaultdict(int)

    def _side(self, pt):
        """Tính hướng của điểm pt so với đường thẳng p1-p2 bằng tích có hướng."""
        return (self.p2[0] - self.p1[0]) * (pt[1] - self.p1[1]) - (self.p2[1] - self.p1[1]) * (pt[0] - self.p1[0])

    def _intersect(self, a, b, c, d):
        """Kiểm tra 2 đoạn thẳng ab và cd có cắt nhau không."""
        def ccw(p, q, r):
            return (r[1] - p[1]) * (q[0] - p[0]) > (q[1] - p[1]) * (r[0] - p[0])
        return (ccw(a, c, d) != ccw(b, c, d)) and (ccw(a, b, c) != ccw(a, b, d))

    def update(self, track_id, current_pt, cls_name):
        """
        Cập nhật vị trí và phát hiện cắt vạch.
        :return: 'IN', 'OUT' hoặc None
        """
        if track_id in self.counted_ids:
            return None

        prev_pt = self.prev_positions.get(track_id)
        self.prev_positions[track_id] = current_pt

        if prev_pt is None:
            return None

        # Kiểm tra cắt vạch
        if self._intersect(prev_pt, current_pt, self.p1, self.p2):
            side_prev = self._side(prev_pt)
            side_curr = self._side(current_pt)

            if side_prev < 0 and side_curr >= 0:
                direction = "IN"
                self.total_in += 1
            else:
                direction = "OUT"
                self.total_out += 1

            self.counted_ids.add(track_id)
            self.class_counts[cls_name] += 1
            return direction

        return None


