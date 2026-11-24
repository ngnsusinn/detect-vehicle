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

    def forget(self, track_id):
        self.counted_ids.discard(track_id)
        self.prev_positions.pop(track_id, None)

    def _side(self, pt):
        """Tính hướng của điểm pt so với đường thẳng p1-p2 bằng tích có hướng."""
        return (self.p2[0] - self.p1[0]) * (pt[1] - self.p1[1]) - (self.p2[1] - self.p1[1]) * (pt[0] - self.p1[0])

    def update(self, track_id, current_pt, cls_name):
        """
        Cập nhật vị trí và phát hiện cắt vạch.
        :return: 'IN', 'OUT' hoặc None
        """
        if track_id in self.counted_ids:
            return None

        side = self._side(current_pt)
        if side == 0:
            return None
        previous = self.prev_positions.get(track_id)
        self.prev_positions[track_id] = (current_pt, side)
        if previous is None or (previous[1] < 0) == (side < 0):
            return None
        point, previous_side = previous
        fraction = previous_side / (previous_side - side)
        crossing = np.asarray(point) + fraction * (np.asarray(current_pt) - point)
        line = self.p2 - self.p1
        projection = np.dot(crossing - self.p1, line)
        if not 0 <= projection <= np.dot(line, line):
            return None
        if side > 0:
            direction = "IN"
            self.total_in += 1
        else:
            direction = "OUT"
            self.total_out += 1
        self.counted_ids.add(track_id)
        del self.prev_positions[track_id]
        self.class_counts[cls_name] += 1
        return direction


