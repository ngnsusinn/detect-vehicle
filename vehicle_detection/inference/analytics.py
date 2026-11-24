"""Aggregate line crossings and their valid speed samples for one session."""
from collections import Counter, defaultdict
from statistics import mean

import numpy as np


class TrafficStats:
    def __init__(self, limits, *, report_overspeed=True):
        self.limits = limits
        self.report_overspeed = report_overspeed
        self.directions = defaultdict(Counter)
        self.classes = defaultdict(Counter)
        self.hours = defaultdict(Counter)
        self.speeds = defaultdict(list)
        self.overspeed = Counter()

    def record(self, line_id, direction, name, timestamp, speed):
        self.directions[line_id][direction] += 1
        self.classes[line_id][name] += 1
        self.hours[int(timestamp // 3600)][line_id] += 1
        if speed is not None:
            self.speeds[line_id].append(float(speed))
            if self.report_overspeed:
                self.overspeed[line_id] += speed > self.limits[line_id]

    def report(self):
        lines = {}
        for line_id, limit in self.limits.items():
            speeds = self.speeds[line_id]
            directions = {direction: self.directions[line_id][direction] for direction in ("IN", "OUT")}
            classes = dict(self.classes[line_id])
            total = sum(directions.values())
            lines[line_id] = {
                "crossings": total, "directions": directions, "classes": classes,
                "modal_share": {name: count / total for name, count in classes.items()},
                "speed_samples_at_crossing": len(speeds), "speed_limit_kmh": limit,
                "average_speed_kmh": mean(speeds) if speeds else None,
                "p85_speed_kmh": float(np.percentile(speeds, 85)) if speeds else None,
                "overspeed_crossings": int(self.overspeed[line_id]) if self.report_overspeed else None,
            }
        return {"lines": lines, "by_video_hour": {hour: dict(counts) for hour, counts in self.hours.items()}}
