"""Record a continuous video segment with FFmpeg for field evaluation."""
import argparse
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", required=True, help="URL RTSP/HLS hoặc tệp nguồn")
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Tệp MKV mới")
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        parser.error("Thời lượng phải là số dương hữu hạn")
    if args.output.suffix.lower() != ".mkv" or args.output.exists():
        parser.error("Đầu ra phải là một tệp .mkv mới")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        parser.error("Cần FFmpeg và FFprobe trong PATH")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-hide_banner", "-nostdin", "-v", "warning", "-n"]
    if args.stream.lower().startswith(("rtsp://", "rtsps://")):
        command += ["-rtsp_transport", "tcp"]
    command += ["-i", args.stream, "-t", str(args.seconds), "-map", "0:v:0", "-c:v", "copy"]
    try:
        with tempfile.TemporaryDirectory(dir=args.output.parent) as folder:
            staged = Path(folder) / "recording.mkv"
            subprocess.run([*command, str(staged)], check=True)
            packets = subprocess.check_output([ffprobe, "-v", "error", "-select_streams", "v:0",
                                               "-read_intervals", "%+#1", "-show_entries", "packet=stream_index",
                                               "-of", "csv=p=0", str(staged)], text=True)
            if not packets.strip():
                parser.error("Nguồn không tạo được gói video đọc được")
            if args.output.exists():
                parser.error("Tệp đầu ra đã tồn tại")
            staged.rename(args.output)
    except (OSError, subprocess.CalledProcessError):
        parser.error("FFmpeg không ghi xong nguồn video. Kiểm tra thông báo FFmpeg và tệp đầu ra.")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
