#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ALIAS MODULE: Khởi chạy trực tiếp Bộ thu thập ảnh Stream từ thư mục training/
"""
import os
import sys
import subprocess

# Thêm thư mục gốc vào đường dẫn hệ thống
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if __name__ == "__main__":
    target_script = os.path.join(ROOT_DIR, "collector_gui.py")
    subprocess.run([sys.executable, target_script] + sys.argv[1:])
