"""Windows desktop monitor for traffic video and interactive camera calibration."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
from queue import Empty, Queue, SimpleQueue
import re
import sys
from threading import Event, Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlsplit

import cv2
from PIL import Image, ImageTk

from vehicle_detection.inference.calibration import MAP_SPEED_SOURCE, load_calibration, load_camera_speed_profile
from vehicle_detection.inference.camera_view import CameraView
from vehicle_detection.inference.demo import open_video_source, run_pipeline
from vehicle_detection.inference.desktop_geometry import ImageViewport, make_config, positive_number
from vehicle_detection.inference.stream_catalog import load_stream
from vehicle_detection.paths import OUTPUTS_DIR, PROJECT_ROOT

DEFAULT_WEIGHTS = PROJECT_ROOT / "models/vehicle_detection/colab-retrain-20261124/best.pt"
PRESET_PATH = PROJECT_ROOT / "configs/cameras/traffic-monitor.local.json"
ROAD_COLOR = "#50dbf9"
LINE_COLOR = "#ffc45e"


class TrafficMonitor:
    def __init__(self, root, camera_list=None, camera_id=None, model=DEFAULT_WEIGHTS):
        self.root = root
        self.catalog = Path(camera_list) if camera_list else None
        self.source = tk.StringVar()
        self.source_visible = tk.BooleanVar()
        self.camera_id = tk.StringVar(value="" if camera_id is None else str(camera_id))
        self.catalog_name = tk.StringVar(value=self.catalog.name if self.catalog else "Chưa chọn danh sách")
        self.model = tk.StringVar(value=str(model))
        self.width_m = tk.StringVar()
        self.length_m = tk.StringVar()
        self.measurement_note = ""
        self.config_camera = None
        self.speed_profile = None
        self.lane_id = tk.StringVar(value="main")
        self.limit = tk.StringVar(value="60")
        self.confidence = tk.StringVar()
        self.timing = tk.StringVar(value="auto")
        self.measure = tk.BooleanVar()
        self.save_csv = tk.BooleanVar(value=True)
        self.save_video = tk.BooleanVar()
        self.save_evidence = tk.BooleanVar()
        self.status = tk.StringVar(value="Chọn nguồn rồi mở khung hình để hiệu chỉnh.")
        self.metrics = {key: tk.StringVar(value="—") for key in ("size", "in", "out", "tracks", "mode")}

        self.reference = self.reference_source = self.image_size = None
        self.current_frame = self.viewport = self.photo = None
        self.showing_reference = False
        self.road = []
        self.lines = {}
        self.editing = None
        self.draft = []
        self.draft_limit = None
        self.job = self.cancel = self.last_output = None
        self.latest_frame = Queue(maxsize=1)
        self.notifications = SimpleQueue()
        self.closing = False
        self.controls = []
        self._build()
        self.root.after(35, self._poll)

    def _entry(self, group, label, variable, **options):
        ttk.Label(group, text=label).pack(anchor="w", pady=(5, 1))
        widget = ttk.Entry(group, textvariable=variable, **options)
        widget.pack(fill="x")
        self.controls.append(widget)
        return widget

    def _button(self, parent, text, command, **pack):
        widget = ttk.Button(parent, text=text, command=command)
        widget.pack(**pack)
        self.controls.append(widget)
        return widget

    def _check(self, parent, text, variable, command=None):
        widget = ttk.Checkbutton(parent, text=text, variable=variable, command=command)
        widget.pack(anchor="w", pady=2)
        self.controls.append(widget)
        return widget

    def _build(self):
        root = self.root
        root.title("Giám sát giao thông")
        root.geometry("1260x800")
        root.minsize(880, 590)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
        style.configure("Metric.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Primary.TButton", foreground="white", background="#0868a5", padding=(10, 6))
        style.map("Primary.TButton", background=[("disabled", "#a8b3bc"), ("active", "#075480")])
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))

        header = ttk.Frame(root, padding=(14, 10))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="Giám sát giao thông", style="Title.TLabel").pack(side="left")
        self.stop_button = ttk.Button(header, text="Dừng", command=self.stop, state="disabled")
        self.stop_button.pack(side="right", padx=(6, 0))
        start = self._button(header, "Bắt đầu", self.start, side="right", padx=(6, 0))
        start.configure(style="Primary.TButton")
        self._button(header, "Mở khung hình", self.preview, side="right")

        body = ttk.Frame(root, padding=(14, 0, 14, 0))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        sidebar = ttk.Frame(body)
        sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        scroll = tk.Canvas(sidebar, width=306, highlightthickness=0, background=style.lookup("TFrame", "background"))
        scrollbar = ttk.Scrollbar(sidebar, orient="vertical", command=scroll.yview)
        scroll.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        scroll.pack(side="left", fill="y")
        settings = ttk.Frame(scroll, padding=(0, 0, 4, 0))
        scroll_window = scroll.create_window((0, 0), window=settings, anchor="nw")
        settings.bind("<Configure>", lambda _: scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda event: scroll.itemconfigure(scroll_window, width=event.width))

        def wheel(event):
            widget = root.winfo_containing(event.x_root, event.y_root)
            if widget and str(widget).startswith(str(sidebar)):
                scroll.yview_scroll(-int(event.delta / 120), "units")

        root.bind("<MouseWheel>", wheel, add=True)

        sources = ttk.LabelFrame(settings, text="Nguồn và mô hình", padding=8)
        sources.pack(fill="x", pady=(0, 7))
        self.source_entry = self._entry(sources, "URL luồng hoặc tệp video", self.source, show="•")
        source_actions = ttk.Frame(sources)
        source_actions.pack(fill="x")
        self.controls.append(ttk.Checkbutton(source_actions, text="Hiện URL", variable=self.source_visible,
                                            command=self._change_source_visibility))
        self.controls[-1].pack(side="left")
        self._button(source_actions, "Chọn video…", self.choose_video, side="right", pady=2)
        self._button(sources, "Chọn danh sách camera…", self.choose_catalog, anchor="w", pady=(3, 0))
        ttk.Label(sources, textvariable=self.catalog_name, wraplength=265).pack(anchor="w")
        self._entry(sources, "ID camera trong danh sách", self.camera_id)
        self._entry(sources, "Trọng số mô hình", self.model)
        self._button(sources, "Đổi mô hình…", self.choose_model, anchor="w", pady=(4, 0))

        calibration = ttk.LabelFrame(settings, text="Vùng đo và vạch đếm", padding=8)
        calibration.pack(fill="x", pady=(0, 7))
        self.road_button = self._button(calibration, "Chọn 4 điểm vùng đo", lambda: self.begin_edit("road"), fill="x")
        dimensions = ttk.Frame(calibration)
        dimensions.pack(fill="x")
        self.road_inputs = [self.road_button]
        for label, value in (("Rộng (m)", self.width_m), ("Dài (m)", self.length_m)):
            field = ttk.Frame(dimensions)
            field.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self.road_inputs.append(self._entry(field, label, value, width=10))
        self.speed_check = self._check(calibration, "Đo tốc độ bằng kích thước đã đo", self.measure)
        ttk.Label(calibration, text="Tên vạch / làn").pack(anchor="w")
        self.lane_picker = ttk.Combobox(calibration, textvariable=self.lane_id)
        self.lane_picker.pack(fill="x")
        self.lane_picker.bind("<<ComboboxSelected>>", self.select_lane)
        self.controls.append(self.lane_picker)
        threshold = self._entry(calibration, "Ngưỡng của vạch (km/h)", self.limit)
        threshold.bind("<FocusOut>", self.apply_limit)
        line_actions = ttk.Frame(calibration)
        line_actions.pack(fill="x", pady=4)
        self._button(line_actions, "Chọn 2 đầu vạch", lambda: self.begin_edit("line"), side="left")
        self._button(line_actions, "Đảo chiều", self.reverse_line, side="left", padx=3)
        self._button(line_actions, "Xóa vạch", self.delete_line, side="left")
        config_actions = ttk.Frame(calibration)
        config_actions.pack(fill="x")
        self._button(config_actions, "Mở cấu hình…", self.open_config, side="left", padx=(0, 5))
        self._button(config_actions, "Lưu cấu hình…", self.save_config, side="left")

        output = ttk.LabelFrame(settings, text="Xử lý và lưu kết quả", padding=8)
        output.pack(fill="x")
        options = ttk.Frame(output)
        options.pack(fill="x")
        confidence = ttk.Frame(options)
        confidence.pack(side="left", fill="x", expand=True)
        self._entry(confidence, "Confidence (0–1)", self.confidence, width=14)
        time_base = ttk.Frame(options)
        time_base.pack(side="left", padx=(6, 0))
        ttk.Label(time_base, text="Thời gian").pack(anchor="w", pady=(5, 1))
        clock = ttk.Combobox(time_base, textvariable=self.timing, state="readonly", values=("auto", "fps", "pts"), width=6)
        clock.pack(fill="x")
        self.controls.append(clock)
        self._check(output, "Lưu CSV và thống kê", self.save_csv)
        self._check(output, "Lưu video đã vẽ", self.save_video)
        self.evidence_check = self._check(output, "Lưu clip vượt ngưỡng", self.save_evidence)
        self.open_output_button = ttk.Button(output, text="Mở thư mục kết quả", command=self.open_output, state="disabled")
        self.open_output_button.pack(anchor="w", pady=(4, 0))

        self.canvas = tk.Canvas(body, highlightthickness=0, background="#101b2c")
        self.canvas.grid(row=0, column=1, sticky="nsew")
        self.canvas.bind("<Configure>", self._render)
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<Button-3>", self._undo)

        footer = ttk.Frame(root, padding=(14, 8))
        footer.grid(row=2, column=0, sticky="ew")
        for index, (key, label) in enumerate((("size", "Nguồn"), ("in", "IN"), ("out", "OUT"),
                                               ("tracks", "Xe đang bám"), ("mode", "Chế độ"))):
            footer.columnconfigure(index, weight=1)
            ttk.Label(footer, text=label).grid(row=0, column=index, sticky="w")
            ttk.Label(footer, textvariable=self.metrics[key], style="Metric.TLabel").grid(row=1, column=index, sticky="w")
        ttk.Label(footer, textvariable=self.status, wraplength=820).grid(row=2, column=0, columnspan=5, sticky="w", pady=(5, 0))

    def _change_source_visibility(self):
        self.source_entry.configure(show="" if self.source_visible.get() else "•")

    def choose_video(self):
        file = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mkv *.avi *.mov"), ("Tất cả", "*.*")])
        if file:
            self.source.set(file)
            self.source_visible.set(True)
            self._change_source_visibility()

    def choose_catalog(self):
        file = filedialog.askopenfilename(filetypes=[("Danh sách camera", "*.json *.txt"), ("Tất cả", "*.*")])
        if file:
            self.catalog = Path(file)
            self.catalog_name.set(self.catalog.name)
            self.source.set("")

    def choose_model(self):
        file = filedialog.askopenfilename(initialdir=DEFAULT_WEIGHTS.parent,
                                          filetypes=[("YOLO, ONNX, OpenVINO", "*.pt *.onnx *.xml"), ("Tất cả", "*.*")])
        if file:
            path = Path(file)
            self.model.set(str(path.parent if path.suffix.lower() == ".xml" else path))

    def _source(self):
        text = self.source.get().strip().replace(r"rtsp\://", "rtsp://", 1)
        if text:
            if text.isdecimal():
                return int(text), "webcam", f"Webcam {text}"
            if "://" in text:
                parsed = urlsplit(text)
                if parsed.scheme not in ("rtsp", "rtsps", "http", "https") or not parsed.hostname:
                    raise ValueError("URL cần là RTSP, RTSPS, HTTP hoặc HTTPS")
                selected = self.camera_id.get().strip()
                if self.catalog and selected.isdecimal():
                    try:
                        catalog_source, name = load_stream(self.catalog, int(selected))
                    except (ValueError, OSError):
                        pass
                    else:
                        if text == catalog_source:
                            return text, f"camera-{int(selected)}", name or f"Camera {selected}"
                return text, "stream", "Luồng trực tiếp"
            if not Path(text).is_file():
                raise ValueError("Không tìm thấy tệp video đã chọn")
            return str(Path(text).resolve()), "video", Path(text).name
        if self.catalog:
            value = self.camera_id.get().strip()
            if not value.isdecimal():
                raise ValueError("Nhập ID dạng số của camera trong danh sách")
            camera_id = int(value)
            url, name = load_stream(self.catalog, camera_id)
            return url, f"camera-{camera_id}", name or f"Camera {camera_id}"
        raise ValueError("Nhập URL, chọn video hoặc chọn danh sách camera")

    def _start_job(self, job, worker, source):
        self.job = job
        self.cancel = Event()
        self.editing = None
        for control in self.controls:
            control.state(["disabled"])
        self.stop_button.state(["!disabled"])

        def run():
            try:
                result = worker(self.cancel)
            except Exception as exc:
                error = str(exc)
                if isinstance(source, str) and "://" in source:
                    error = error.replace(source, "[luồng video]")
                self.notifications.put((job, None, error or type(exc).__name__))
            else:
                self.notifications.put((job, result, None))

        Thread(target=run, daemon=True, name=f"traffic-{job}").start()

    def preview(self):
        if self.job:
            return
        try:
            source, camera, name = self._source()
        except (ValueError, OSError) as exc:
            self.status.set(str(exc))
            return
        self.status.set(f"Đang mở {name}…")

        def capture(cancel):
            cap = open_video_source(source)
            try:
                if cancel.is_set():
                    return None
                ok, frame = cap.read()
                if not ok:
                    raise OSError("Không đọc được khung hình. Kiểm tra luồng hoặc kết nối camera.")
                profile = load_camera_speed_profile(camera)
                matches = profile is not None and CameraView(profile).matches(frame)
                return frame, source, name, profile, matches
            finally:
                cap.release()

        self._start_job("preview", capture, source)

    def _accept_preview(self, frame, source, name, profile, matches):
        size = (frame.shape[1], frame.shape[0])
        if ((self.reference_source is not None and self.reference_source != source)
                or (self.image_size and self.image_size != size)):
            self.road.clear()
            self.lines.clear()
            self.measure.set(False)
            self.width_m.set("")
            self.length_m.set("")
            self.measurement_note = ""
            self.config_camera = None
            self.speed_profile = None
            self._update_lanes()
        self.image_size = size
        self.reference = frame
        self.reference_source = source
        self.metrics["size"].set(f"{size[0]} × {size[1]}")
        status = "Chọn vùng đo hoặc vạch đếm trên khung hình."
        apply_profile = matches and (self.speed_profile is not None or self.config_camera is None)
        if apply_profile:
            if self.speed_profile is None:
                self.measure.set(True)
            self.speed_profile = profile
            self.road = profile["source_points_px"][:]
            self.save_evidence.set(False)
            self.config_camera = profile["camera_id"]
            self.measurement_note = profile["measurement_note"]
            self.metrics["mode"].set("Tốc độ ước lượng" if self.measure.get() else "Chỉ đếm")
            status = "Đã nạp hiệu chuẩn bản đồ. Chọn 2 đầu vạch."
        elif profile is not None and not matches and (self.speed_profile is not None or self.config_camera is None):
            if self.speed_profile is not None:
                self.road.clear()
                self.lines.clear()
                self._update_lanes()
                self.speed_profile = None
                self.config_camera = None
                self.measurement_note = ""
            self.measure.set(False)
            self.metrics["mode"].set("Chỉ đếm")
            status = "Góc quay khác hồ sơ bản đồ. Chọn vạch để chỉ đếm."
        self._update_speed_controls()
        self.status.set(f"{name} · {status}")
        if apply_profile and not self.lines:
            self.begin_edit("line")
        else:
            self._show_reference()

    def _update_speed_controls(self):
        automatic = self.speed_profile is not None
        for widget in (*self.road_inputs, self.evidence_check):
            widget.state(["disabled" if automatic else "!disabled"])
        self.speed_check.configure(text=("Ước lượng tốc độ theo bản đồ" if automatic
                                         else "Đo tốc độ bằng kích thước đã đo"))

    def _show_reference(self):
        self.current_frame = self.reference
        self.showing_reference = True
        self._render()

    def _render(self, _event=None):
        canvas = self.canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if self.current_frame is None:
            canvas.create_text(width / 2, height / 2, text="Mở khung hình từ camera hoặc video",
                               fill="#b9cde0", font=("Segoe UI", 13))
            return
        frame = self.current_frame
        view = self.viewport = ImageViewport.fit(frame.shape[1], frame.shape[0], max(width, 1), max(height, 1))
        resized = cv2.resize(frame, (view.width, view.height), interpolation=cv2.INTER_LINEAR)
        self.photo = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)))
        canvas.create_image(view.left, view.top, image=self.photo, anchor="nw")
        if not self.showing_reference:
            return
        road = self.draft if self.editing == ("road", "") else self.road
        self._draw_points(road, ROAD_COLOR, closed=len(road) == 4)
        for lane, data in self.lines.items():
            if self.editing != ("line", lane):
                self._draw_points(data["points_px"], LINE_COLOR, label=lane, arrow=True)
        if self.editing and self.editing[0] == "line":
            self._draw_points(self.draft, LINE_COLOR, label=self.editing[1], arrow=True)

    def _draw_points(self, points, color, *, closed=False, label="", arrow=False):
        positions = [self.viewport.canvas_point(point) for point in points]
        if len(positions) >= 2:
            sequence = positions + positions[:1] if closed else positions
            self.canvas.create_line(*(coord for point in sequence for coord in point), fill=color, width=2,
                                    arrow="last" if arrow else "none")
        for index, (x, y) in enumerate(positions, 1):
            self.canvas.create_oval(x-5, y-5, x+5, y+5, fill=color, outline="#101b2c")
            self.canvas.create_text(x+9, y-9, anchor="sw", text=f"{label} {index}" if label else f"P{index}",
                                    fill=color, font=("Segoe UI", 9, "bold"))

    def begin_edit(self, kind):
        if self.reference is None:
            self.status.set("Mở khung hình trước khi chọn điểm.")
            return
        name = self.lane_id.get().strip() if kind == "line" else ""
        if kind == "line" and not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", name):
            self.status.set("Tên vạch chỉ gồm chữ ASCII, số, dấu - hoặc _.")
            return
        if kind == "line" and any(key != name and key.casefold() == name.casefold() for key in self.lines):
            self.status.set("Tên vạch đã tồn tại với cách viết hoa khác.")
            return
        if kind == "line":
            try:
                self.draft_limit = positive_number(self.limit.get(), "Ngưỡng tốc độ")
            except ValueError as exc:
                self.status.set(str(exc))
                return
        self.editing = (kind, name)
        self.draft = []
        self._point_hint()
        self._show_reference()

    def _point_hint(self):
        kind, name = self.editing
        if kind == "road":
            points = ("trái xa", "phải xa", "phải gần", "trái gần")
            self.status.set(f"Chọn P{len(self.draft)+1} ({points[len(self.draft)]}). Nhấp phải để lùi một điểm.")
        else:
            self.status.set(f"Vạch {name} · Chọn đầu {len(self.draft)+1}/2. Nhấp phải để lùi một điểm.")

    def _click(self, event):
        if not self.editing or not self.showing_reference or not self.viewport:
            return
        point = self.viewport.source_point(event.x, event.y)
        if point is None or point in self.draft:
            return
        self.draft.append(point)
        kind, name = self.editing
        limit = 4 if kind == "road" else 2
        if len(self.draft) == limit:
            if kind == "road":
                self.road = self.draft[:]
                self.status.set("Đã chọn vùng đo. Nhập chiều rộng và chiều dài thực địa.")
            else:
                self.lines[name] = {"line_id": name, "points_px": self.draft[:], "speed_limit_kmh": self.draft_limit}
                self.lane_id.set(name)
                self.limit.set(f"{self.draft_limit:g}")
                self._update_lanes()
                self.status.set(f"Đã đặt vạch {name}. Đảo chiều nếu muốn đổi quy ước IN/OUT.")
            self.editing = None
        else:
            self._point_hint()
        self._render()

    def _undo(self, _event):
        if self.editing and self.draft:
            self.draft.pop()
            self._point_hint()
            self._render()

    def _update_lanes(self):
        self.lane_picker.configure(values=tuple(self.lines))

    def select_lane(self, _event=None):
        line = self.lines.get(self.lane_id.get())
        if line:
            self.limit.set(f"{line['speed_limit_kmh'] or 60:g}")

    def apply_limit(self, _event=None):
        line = self.lines.get(self.lane_id.get().strip())
        if line:
            try:
                line["speed_limit_kmh"] = positive_number(self.limit.get(), "Ngưỡng tốc độ")
            except ValueError as exc:
                self.status.set(str(exc))

    def reverse_line(self):
        line = self.lines.get(self.lane_id.get().strip())
        if line:
            line["points_px"].reverse()
            self._show_reference()

    def delete_line(self):
        name = self.lane_id.get().strip()
        if self.lines.pop(name, None) is not None:
            self._update_lanes()
            self._show_reference()

    def _config(self, camera, *, allow_defaults=False):
        if self.editing:
            raise ValueError("Chọn đủ điểm trước khi chạy hoặc lưu cấu hình")
        if self.config_camera and camera.startswith("camera-") and camera != self.config_camera:
            raise ValueError(f"Cấu hình này thuộc {self.config_camera}. Chọn cấu hình đúng nguồn camera.")
        speed_limit = positive_number(self.limit.get(), "Ngưỡng tốc độ")
        if not self.lines and allow_defaults and not self.measure.get():
            return None, speed_limit
        if not self.image_size or not self.lines:
            raise ValueError("Mở khung hình và đặt ít nhất một vạch đếm")
        lane = self.lane_id.get().strip()
        if lane in self.lines:
            self.lines[lane]["speed_limit_kmh"] = speed_limit
        dimensions = None
        if self.measure.get() and self.speed_profile is None:
            dimensions = (positive_number(self.width_m.get(), "Chiều rộng"),
                          positive_number(self.length_m.get(), "Chiều dài"))
        config = make_config(camera, self.image_size, self.road, self.lines, dimensions=dimensions,
                             note=self.measurement_note,
                             speed_profile=self.speed_profile if self.measure.get() else None)
        return config, speed_limit

    def save_config(self):
        try:
            source, camera, _ = self._source()
            if self.reference_source is not None and self.reference_source != source:
                raise ValueError("Nguồn đã đổi. Mở khung hình mới trước khi lưu cấu hình.")
            config, _ = self._config(camera)
            path = filedialog.asksaveasfilename(initialdir=PROJECT_ROOT / "configs/cameras", initialfile=f"{camera}.json",
                                                defaultextension=".json", filetypes=[("Cấu hình JSON", "*.json")])
            if path:
                Path(path).write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                self.status.set(f"Đã lưu {Path(path).name}.")
        except (ValueError, OSError) as exc:
            self.status.set(str(exc))

    def open_config(self):
        file = filedialog.askopenfilename(initialdir=PROJECT_ROOT / "configs/cameras", filetypes=[("Cấu hình JSON", "*.json")])
        if file:
            try:
                self._apply_config(load_calibration(file), Path(file))
            except (ValueError, OSError) as exc:
                self.status.set(str(exc))

    def _apply_config(self, config, path):
        size = tuple(config["image_size"])
        if self.reference is not None and self.image_size != size:
            raise ValueError("Độ phân giải cấu hình khác khung hình đã mở")
        target = config.get("target_points_m")
        automatic = config.get("speed_source") == MAP_SPEED_SOURCE
        if automatic and self.reference is not None and not CameraView(config).matches(self.reference):
            raise ValueError("Góc quay hiện tại không khớp hồ sơ bản đồ")
        if target and not automatic:
            width, length = target[1][0], target[2][1]
            if width <= 0 or length <= 0 or target != [[0, 0], [width, 0], [width, length], [0, length]]:
                raise ValueError("Trình chỉnh sửa cần hệ tọa độ thực địa hình chữ nhật bắt đầu từ (0, 0)")
        self.image_size = size
        self.road = config.get("source_points_px", [])
        entries = config.get("count_lines") or [{"line_id": "main", "points_px": config["count_line_px"]}]
        self.lines = {entry["line_id"]: {**entry, "speed_limit_kmh": entry.get("speed_limit_kmh")} for entry in entries}
        self.lane_id.set(next(iter(self.lines)))
        self.select_lane()
        self._update_lanes()
        self.measurement_note = str(config.get("measurement_note") or "")
        camera_id = str(config.get("camera_id") or "")
        self.config_camera = camera_id if re.fullmatch(r"camera-\d+", camera_id) else None
        self.speed_profile = config if automatic else None
        illustrative = (path.stem.casefold().endswith(".example")
                        or self.measurement_note.strip().casefold().startswith("example only:"))
        self.measure.set(config.get("speed_enabled", True) and not illustrative)
        if target and not illustrative and not automatic:
            self.width_m.set(f"{width:g}")
            self.length_m.set(f"{length:g}")
        else:
            self.width_m.set("")
            self.length_m.set("")
        if illustrative:
            self.measurement_note = ""
        if automatic:
            self.save_evidence.set(False)
        self._update_speed_controls()
        self.editing = None
        self._show_reference()
        self.status.set(f"Đã mở {path.name}. Kiểm tra điểm trên đúng khung hình camera.")

    def start(self):
        if self.job:
            return
        try:
            source, camera, name = self._source()
            if self.reference_source is not None and self.reference_source != source and (self.lines or self.measure.get()):
                raise ValueError("Nguồn đã đổi. Mở khung hình mới để đặt lại vùng và vạch.")
            config, limit = self._config(camera, allow_defaults=True)
            model = Path(self.model.get().strip())
            if not self.model.get().strip() or not model.exists():
                raise ValueError("Không tìm thấy model. Chọn best.pt, ONNX hoặc thư mục OpenVINO.")
            confidence = self.confidence.get().strip()
            confidence = positive_number(confidence, "Confidence") if confidence else None
            if confidence is not None and confidence > 1:
                raise ValueError("Confidence cần lớn hơn 0 và không quá 1")
            measure = self.measure.get()
            save_csv, save_video, save_evidence = self.save_csv.get(), self.save_video.get(), self.save_evidence.get()
            if save_evidence and not measure:
                raise ValueError("Bật đo tốc độ và nhập số đo thực địa để lưu clip vượt ngưỡng")
            timing = self.timing.get()
        except (ValueError, OSError) as exc:
            self.status.set(str(exc))
            return
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        output = OUTPUTS_DIR / "inference" / "desktop" / f"{camera}-{timestamp}"
        self.last_output = output if any((save_csv, save_video, save_evidence)) else None
        self.open_output_button.state(["disabled"])
        for key in ("in", "out", "tracks"):
            self.metrics[key].set("0")
        self.metrics["mode"].set("Tốc độ ước lượng" if measure and self.speed_profile else
                                 "Đo tốc độ" if measure else "Chỉ đếm")
        self.status.set(f"Đang khởi động {name} · {model.name}…")

        def process(cancel):
            return run_pipeline(source, str(model.resolve()), limit, show=False, calibration_config=config,
                                measure_speed=measure, stream_id=camera, timing=timing, confidence=confidence,
                                events_dir=output if save_csv else None,
                                output_path=output / "annotated.mp4" if save_video else None,
                                evidence_dir=output / "evidence" if save_evidence else None,
                                on_frame=self._publish_frame, stop_event=cancel)

        self._start_job("run", process, source)

    def _publish_frame(self, frame, progress):
        try:
            self.latest_frame.get_nowait()
        except Empty:
            pass
        self.latest_frame.put_nowait((frame, progress))

    def _poll(self):
        try:
            frame, info = self.latest_frame.get_nowait()
        except Empty:
            pass
        else:
            if not self.closing:
                self.current_frame = frame
                self.showing_reference = False
                self.metrics["size"].set(f"{frame.shape[1]} × {frame.shape[0]} · {info['source_fps']:g} FPS")
                self.metrics["in"].set(str(info["total_in"]))
                self.metrics["out"].set(str(info["total_out"]))
                self.metrics["tracks"].set(str(info["active_tracks"]))
                if not self.cancel.is_set():
                    self.status.set(f"Đang xử lý · Khung hình {info['frame']}")
                self._render()
        try:
            job, result, error = self.notifications.get_nowait()
        except Empty:
            pass
        else:
            self.job = None
            self.stop_button.state(["disabled"])
            for control in self.controls:
                control.state(["!disabled"])
            self._update_speed_controls()
            if self.closing:
                self.root.destroy()
                return
            if error:
                self.status.set(error)
            elif job == "preview" and result:
                self._accept_preview(*result)
            elif job == "run":
                self.status.set(f"Đã xử lý {result['frames']} khung hình · {result['processing_fps']:.1f} FPS xử lý.")
            else:
                self.status.set("Đã dừng.")
            if self.last_output and self.last_output.is_dir():
                self.open_output_button.state(["!disabled"])
        self.root.after(35, self._poll)

    def stop(self):
        if self.job:
            self.cancel.set()
            self.status.set("Đang dừng và hoàn tất tệp kết quả…")
            self.stop_button.state(["disabled"])

    def close(self):
        if self.job:
            self.closing = True
            self.stop()
        else:
            self.root.destroy()

    def open_output(self):
        if self.last_output and self.last_output.is_dir():
            if hasattr(os, "startfile"):
                os.startfile(self.last_output)
            else:
                messagebox.showinfo("Kết quả", str(self.last_output))


def create_window():
    if sys.platform == "win32":
        library = Path(sys.base_prefix) / "tcl"
        for name, component, script in (("TCL_LIBRARY", "tcl", "init.tcl"), ("TK_LIBRARY", "tk", "tk.tcl")):
            folder = library / f"{component}{tk.TclVersion:g}"
            if (folder / script).is_file():
                os.environ.setdefault(name, str(folder))
    return tk.Tk()


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Giám sát giao thông với giao diện Python")
    parser.add_argument("--camera-list", type=Path)
    parser.add_argument("--camera-id", type=int)
    parser.add_argument("--model", type=Path, default=DEFAULT_WEIGHTS)
    args = parser.parse_args()
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    if args.camera_list is None and args.camera_id is None and PRESET_PATH.is_file():
        try:
            local = json.loads(PRESET_PATH.read_text(encoding="utf-8-sig"))
            args.camera_list, args.camera_id = Path(local["camera_list"]), int(local["camera_id"])
        except (OSError, ValueError, TypeError, KeyError):
            pass
    if bool(args.camera_list) != (args.camera_id is not None):
        parser.error("--camera-list và --camera-id phải dùng cùng nhau")
    try:
        root = create_window()
    except tk.TclError as exc:
        parser.exit(1, f"Không mở được giao diện Tkinter: {exc}\n")
    app = TrafficMonitor(root, args.camera_list, args.camera_id, args.model)
    if args.camera_list and args.camera_list.is_file() and args.camera_id is not None:
        root.after(200, app.preview)
    root.mainloop()


if __name__ == "__main__":
    main()
