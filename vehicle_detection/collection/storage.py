"""Shared hourly storage layout used by the collection tools."""
import os
from datetime import datetime


def get_slot_info(now=None):
    now = now if now is not None else datetime.now()
    return now.hour, now.hour + 1, f"{now.hour:02d}h-{now.hour + 1:02d}h"


def get_current_storage_directory(base_dir, camera_tag, now=None):
    now = now if now is not None else datetime.now()
    _, _, slot = get_slot_info(now)
    folder_name = f"{now:%Y-%m-%d}_{slot}"
    target_dir = os.path.join(base_dir, camera_tag, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    return target_dir, folder_name
