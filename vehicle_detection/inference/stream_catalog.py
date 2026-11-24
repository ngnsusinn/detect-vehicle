"""Read a camera stream from the JSON catalog without printing its URL."""
import json
from pathlib import Path
from urllib.parse import urlsplit


def load_stream(path, camera_id):
    catalog = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    entries = catalog.get("data") if isinstance(catalog, dict) else None
    if not isinstance(entries, list) or catalog.get("success") is False:
        raise ValueError("Danh sách camera cần là JSON thành công với trường data dạng mảng")

    matches = [entry for entry in entries if isinstance(entry, dict) and str(entry.get("ID")) == str(camera_id)]
    if len(matches) != 1:
        raise ValueError(f"Cần đúng một camera có ID {camera_id}. Tìm thấy {len(matches)} mục.")
    camera = matches[0]
    if str(camera.get("DELETED", 0)) == "1" or str(camera.get("STATUS", 1)) == "0":
        raise ValueError(f"Camera ID {camera_id} đã bị xóa hoặc ngưng hoạt động")
    source = camera.get("STSPLINK")
    if not isinstance(source, str) or not source.strip():
        raise ValueError(f"Camera ID {camera_id} thiếu STSPLINK")
    source = source.strip()
    try:
        parts = urlsplit(source)
        supported = parts.scheme in {"rtsp", "rtsps", "http", "https"} and parts.hostname
    except ValueError:
        supported = False
    if not supported:
        raise ValueError(f"Camera ID {camera_id} cần STSPLINK dạng RTSP hoặc HTTP(S)")
    name = " ".join(str(camera.get("TEN") or "").split())
    return source, name
