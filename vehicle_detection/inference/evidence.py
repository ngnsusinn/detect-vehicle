"""Capture annotated local evidence around a calibrated overspeed crossing."""
from collections import deque
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np


@dataclass
class EvidenceEvent:
    info: dict
    frames: list[tuple[float, bytes]] = field(default_factory=list)


class EvidenceRecorder:
    seconds = 3.0

    def __init__(self, directory, fps, size):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.fps = fps
        self.size = size
        self.previous = deque(maxlen=math.ceil(max(30, fps) * self.seconds) + 1)
        self.pending = []
        self.saved = []

    def observe(self, timestamp, frame, events):
        while self.previous and self.previous[0][0] < timestamp - self.seconds - 1e-6:
            self.previous.popleft()
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            raise OSError("Không thể mã hóa ảnh bằng chứng")
        encoded = jpg.tobytes()
        active = []
        for event in self.pending:
            if timestamp <= event.info["timestamp_s"] + self.seconds + 1e-6:
                event.frames.append((timestamp, encoded))
            if timestamp >= event.info["timestamp_s"] + self.seconds:
                self._save(event, complete_post=True)
            else:
                active.append(event)
        for info in events:
            event = EvidenceEvent(info, [*self.previous, (timestamp, encoded)])
            snapshot = self.directory / f"{info['line_id']}-{info['track_id']}-{info['frame_index']}.jpg"
            snapshot.write_bytes(encoded)
            event.info = {**info, "snapshot": snapshot.name}
            active.append(event)
        self.pending = active
        self.previous.append((timestamp, encoded))

    def _save(self, event, *, complete_post):
        info = event.info
        snapshot = self.directory / info["snapshot"]
        clip = snapshot.with_suffix(".mp4")
        writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), self.fps, self.size)
        try:
            if not writer.isOpened():
                raise OSError(f"Không thể ghi clip {clip}")
            for _, jpg in event.frames:
                frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    raise OSError(f"Không thể đọc ảnh trung gian cho {clip}")
                writer.write(frame)
        finally:
            writer.release()
        checksums = {}
        for path in (snapshot, clip):
            with path.open("rb") as stream:
                checksums[path.name] = hashlib.file_digest(stream, "sha256").hexdigest()
        start, end = event.frames[0][0], event.frames[-1][0]
        self.saved.append({**info, "clip": clip.name, "frames": len(event.frames), "sha256": checksums,
                           "clip_start_s": start, "clip_end_s": end,
                           "complete_pre": start <= info["timestamp_s"] - self.seconds + 1 / self.fps,
                           "complete_post": complete_post and end + 1 / self.fps + 1e-6
                           >= info["timestamp_s"] + self.seconds})

    def close(self):
        for event in self.pending:
            self._save(event, complete_post=False)
        self.pending.clear()
        (self.directory / "evidence.json").write_text(
            json.dumps(self.saved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
        )
