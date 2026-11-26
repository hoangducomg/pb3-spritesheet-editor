# sprite_studio.py
# Run with: python sprite_studio.py
# Requires Python 3 and: pip install -U pillow opencv-python

import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageTk, ImageSequence, ImageOps
except ImportError:
    raise SystemExit("Pillow is required. Install it with: pip install -U pillow")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    cv2 = None
    HAS_CV2 = False


IMAGE_EXTS = (".png", ".gif", ".bmp", ".jpg", ".jpeg", ".webp")
VIDEO_EXTS = (".mp4", ".webm", ".mov", ".avi", ".mkv")
PREVIEW_MAX = (560, 420)


def natural_key(text):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def to_int(text, default=0):
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default


def to_float(text, default=0.0):
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def fmt(value):
    """Format a number without trailing .0"""
    f = float(value)
    return str(int(f)) if f.is_integer() else f"{f:g}"


def safe_filename(text):
    """Make a string safe to use as a file name."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._")
    return cleaned or "frame"


class SpriteStudio:
    def __init__(self, root):
        self.root = root
        self.root.title("Sprite Studio")
        self.root.geometry("1360x860")

        self.source_frames = []   # untouched originals: {"img", "name"}
        self.frames = []          # processed working frames: {"img", "name", "hold"}
        self.animations = []

        self.sheet = None
        self.sheet_info = None

        self.preview_photo = None
        self.sheet_photo = None
        self.preview_index = 0
        self.playing = False
        self.play_job = None

        self._build_ui()
        self._add_default_animation()

    # =========================================================
    # UI
    # =========================================================

    def _build_ui(self):
        top = ttk.LabelFrame(self.root, text="1. Input", padding=6)
        top.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Button(top, text="Pick folder", command=self.open_folder).pack(side="left")
        ttk.Button(top, text="Pick images", command=self.pick_images).pack(side="left", padx=4)
        ttk.Button(top, text="Pick GIF", command=self.open_gif).pack(side="left")
        ttk.Button(top, text="Pick video", command=self.open_video).pack(side="left", padx=4)
        ttk.Button(top, text="Clear all", command=self.clear_all).pack(side="left")
        self.info = ttk.Label(top, text="No frames loaded.", foreground="gray")
        self.info.pack(side="left", padx=12)

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=8)

        # Left column: processing + decoration (scrollable)
        left_outer = ttk.Frame(body, width=360)
        left_outer.pack(side="left", fill="y")
        left_outer.pack_propagate(False)

        self.left_canvas = tk.Canvas(left_outer, highlightthickness=0, width=345)
        lscroll = ttk.Scrollbar(left_outer, orient="vertical", command=self.left_canvas.yview)
        self.left_canvas.configure(yscrollcommand=lscroll.set)
        lscroll.pack(side="right", fill="y")
        self.left_canvas.pack(side="left", fill="both", expand=True)

        left = ttk.Frame(self.left_canvas)
        self.left_canvas.create_window((0, 0), window=left, anchor="nw")
        left.bind("<Configure>", lambda e: self.left_canvas.configure(
            scrollregion=self.left_canvas.bbox("all")))

        self._build_processing_panel(left)
        self._build_decoration_panel(left)

        # Middle column: preview, sequence, animations
        middle = ttk.Frame(body, padding=(8, 0))
        middle.pack(side="left", fill="both", expand=True)
        self._build_preview_panel(middle)
        self._build_sequence_panel(middle)

        # Right column: output
        right = ttk.Frame(body, width=340)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        self._build_output_panel(right)

        self.status = ttk.Label(self.root, text="Ready. Load frames to begin.", foreground="gray")
        self.status.pack(fill="x", padx=8, pady=(0, 6), anchor="w")

    def _section(self, parent, title):
        f = ttk.LabelFrame(parent, text=title, padding=6)
        f.pack(fill="x", pady=4)
        return f

    def _labeled_entry(self, parent, label, var, row, width=10):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=1)
        ttk.Entry(parent, textvariable=var, width=width).grid(row=row, column=1, sticky="w", padx=4, pady=1)

    # ---- processing ----

    def _build_processing_panel(self, parent):
        sec = self._section(parent, "2. Processing (applies to source frames)")

        ttk.Label(sec, text="Rescale by percentage (100 = original)").grid(
            row=0, column=0, columnspan=4, sticky="w")
        self.var_percent = tk.StringVar(value="100")
        ttk.Entry(sec, textvariable=self.var_percent, width=8).grid(row=1, column=0, sticky="w", padx=2)
        ttk.Label(sec, text="%").grid(row=1, column=1, sticky="w")

        ttk.Label(sec, text="Or resize W x H (blank = keep)").grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.var_rw = tk.StringVar()
        self.var_rh = tk.StringVar()
        ttk.Entry(sec, textvariable=self.var_rw, width=6).grid(row=3, column=0, sticky="w", padx=2)
        ttk.Label(sec, text="x").grid(row=3, column=1)
        ttk.Entry(sec, textvariable=self.var_rh, width=6).grid(row=3, column=2, sticky="w", padx=2)

        ttk.Label(sec, text="Resample").grid(row=4, column=0, sticky="w", pady=(4, 0))
        self.var_resample = tk.StringVar(value="Nearest (pixel art)")
        ttk.Combobox(sec, textvariable=self.var_resample, state="readonly", width=20,
                     values=["Nearest (pixel art)", "Bilinear", "Lanczos (smooth)"]).grid(
            row=4, column=1, columnspan=3, sticky="w")

        ttk.Label(sec, text="Crop: left / top / right / bottom (px)").grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.crop_vars = [tk.StringVar() for _ in range(4)]
        for i, v in enumerate(self.crop_vars):
            ttk.Entry(sec, textvariable=v, width=6).grid(row=6, column=i, padx=2, pady=2)

        self.var_autotrim = tk.BooleanVar(value=False)
        ttk.Checkbutton(sec, text="Auto-trim transparent edges", variable=self.var_autotrim).grid(
            row=7, column=0, columnspan=4, sticky="w", pady=(4, 0))

        ttk.Label(sec, text="Flip / rotate").grid(row=8, column=0, sticky="w", pady=(4, 0))
        self.var_transform = tk.StringVar(value="None")
        ttk.Combobox(sec, textvariable=self.var_transform, state="readonly", width=20,
                     values=["None", "Flip horizontal", "Flip vertical",
                             "Rotate 90", "Rotate 180", "Rotate 270"]).grid(
            row=8, column=1, columnspan=3, sticky="w")

        ttk.Label(sec, text="Optimize (choose several)").grid(
            row=9, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.opt_vars = {
            "dupes": tk.BooleanVar(value=False),
            "every_n": tk.BooleanVar(value=False),
            "quantize": tk.BooleanVar(value=False),
        }
        ttk.Checkbutton(sec, text="Merge duplicate frames (adds hold)",
                        variable=self.opt_vars["dupes"]).grid(row=10, column=0, columnspan=4, sticky="w")
        ttk.Checkbutton(sec, text="Remove every n-th frame",
                        variable=self.opt_vars["every_n"]).grid(row=11, column=0, columnspan=2, sticky="w")
        self.var_every_n = tk.StringVar(value="2")
        ttk.Label(sec, text="n =").grid(row=11, column=2, sticky="e")
        ttk.Entry(sec, textvariable=self.var_every_n, width=4).grid(row=11, column=3, sticky="w", padx=2)
        ttk.Checkbutton(sec, text="Quantize colors (256)",
                        variable=self.opt_vars["quantize"]).grid(row=12, column=0, columnspan=4, sticky="w")

        ttk.Button(sec, text="Apply processing", command=self.apply_processing).grid(
            row=13, column=0, columnspan=4, sticky="we", pady=(8, 0))

    # ---- decoration ----

    def _build_decoration_panel(self, parent):
        sec = self._section(parent, "3. Decoration properties (pb2Decoration)")
        self.dv = {}

        def entry(key, label, default, row):
            var = tk.StringVar(value=str(default))
            self.dv[key] = var
            self._labeled_entry(sec, label, var, row)

        def check(key, label, default, row):
            var = tk.BooleanVar(value=default)
            self.dv[key] = var
            ttk.Checkbutton(sec, text=label, variable=var).grid(row=row, column=0, columnspan=2, sticky="w")

        entry("source", "Source name", "user_data.UID", 0)

        # Comment gets its own full-width row so it is easy to read and edit
        comment_var = tk.StringVar(value="::For A Better Experience::")
        self.dv["comment"] = comment_var
        ttk.Label(sec, text="Comment").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Entry(sec, textvariable=comment_var, width=38).grid(
            row=2, column=0, columnspan=2, sticky="we", pady=(0, 4))

        entry("x", "X", 0, 3)
        entry("y", "Y", 0, 4)
        entry("z", "Z", 0, 5)
        entry("scale_x", "scaleX", 0, 6)
        entry("scale_y", "scaleY", 0, 7)
        entry("scale_z", "scaleZ", 0, 8)
        entry("offset_x", "Offset X", 0, 9)
        entry("offset_y", "Offset Y", 0, 10)
        entry("offset_z", "Offset Z", 0, 11)
        entry("frame_off_x", "Frame offset X", 0, 12)
        entry("frame_off_y", "Frame offset Y", 0, 13)
        entry("frame_off_z", "Frame offset Z", 0, 14)
        entry("start_frame", "Starting frame", 0, 15)
        entry("frame_progress", "Starting progress (0-1)", 0, 16)
        entry("fps", "Speed FPS", 10, 17)
        entry("timescale", "Timescale (ticks/s)", 30, 18)
        entry("anim_id", "Default animation id", 0, 19)
        check("pixelated", "Pixelated", False, 20)
        check("is_static", "Static (no animation)", False, 21)
        check("is_playing", "Start playing", True, 22)
        check("relative_world", "Timing relative to world", True, 23)

    # ---- preview ----

    def _build_preview_panel(self, parent):
        sec = self._section(parent, "Preview")
        self.preview_box = tk.Frame(sec, bg="#202020", width=PREVIEW_MAX[0], height=PREVIEW_MAX[1])
        self.preview_box.pack(fill="both", expand=True)
        self.preview_box.pack_propagate(False)
        self.preview = tk.Label(self.preview_box, bg="#202020", fg="#888888", text="Load frames to preview")
        self.preview.pack(expand=True, fill="both")

        bar = ttk.Frame(sec)
        bar.pack(fill="x", pady=(4, 0))
        ttk.Button(bar, text="Play / Pause", command=self.toggle_play).pack(side="left")
        ttk.Button(bar, text="< Prev", command=lambda: self.step(-1)).pack(side="left", padx=4)
        ttk.Button(bar, text="Next >", command=lambda: self.step(1)).pack(side="left")
        self.frame_label = ttk.Label(bar, text="")
        self.frame_label.pack(side="left", padx=10)

    # ---- sequence + animations ----

    def _build_sequence_panel(self, parent):
        sec = self._section(parent, "4. Sequence (play order)")

        list_row = ttk.Frame(sec)
        list_row.pack(fill="x")
        self.seq_list = tk.Listbox(list_row, height=7, exportselection=False, font=("Courier", 9))
        self.seq_list.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_row, orient="vertical", command=self.seq_list.yview)
        sb.pack(side="right", fill="y")
        self.seq_list.configure(yscrollcommand=sb.set)
        self.seq_list.bind("<<ListboxSelect>>", self.on_seq_select)
        self.seq_list.bind("<Double-Button-1>", lambda e: self.delete_selected())

        btns = ttk.Frame(sec)
        btns.pack(fill="x", pady=4)
        ttk.Button(btns, text="Up", command=lambda: self.move_selected(-1)).pack(side="left")
        ttk.Button(btns, text="Down", command=lambda: self.move_selected(1)).pack(side="left", padx=2)
        ttk.Button(btns, text="Duplicate", command=self.duplicate_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="Delete", command=self.delete_selected).pack(side="left", padx=2)
        ttk.Button(btns, text="Hold +", command=lambda: self.change_hold(1)).pack(side="left", padx=2)
        ttk.Button(btns, text="Hold -", command=lambda: self.change_hold(-1)).pack(side="left", padx=2)

        # Save buttons for individual frames
        save_row = ttk.Frame(sec)
        save_row.pack(fill="x", pady=(0, 4))
        ttk.Button(save_row, text="Save selected frame (PNG)",
                   command=self.save_selected_frame).pack(side="left")
        ttk.Button(save_row, text="Save all frames to folder",
                   command=self.save_all_frames).pack(side="left", padx=4)

        anim_sec = self._section(parent, "5. Animations (ranges of the sheet)")
        ttk.Label(anim_sec, text="first = first cell index, count = frames (0 = to end)",
                  foreground="gray").pack(anchor="w")
        self.anim_container = ttk.Frame(anim_sec)
        self.anim_container.pack(fill="x", pady=4)

        abtns = ttk.Frame(anim_sec)
        abtns.pack(fill="x")
        ttk.Button(abtns, text="+ Add animation", command=self.add_animation).pack(side="left")
        ttk.Button(abtns, text="Use whole sequence", command=self.fill_whole_sequence).pack(side="left", padx=4)

    def _add_default_animation(self):
        self.add_animation(name="idle", first=0, count=0, loop=True, rel=1, report=False)

    def add_animation(self, name=None, first=0, count=0, loop=True, rel=1, report=False):
        idx = len(self.animations)
        name = name or f"anim_{idx}"
        row = ttk.Frame(self.anim_container, padding=(0, 2))
        row.pack(fill="x")

        vars_ = {
            "name": tk.StringVar(value=name),
            "first": tk.StringVar(value=str(first)),
            "count": tk.StringVar(value=str(count)),
            "rel": tk.StringVar(value=str(rel)),
            "loop": tk.BooleanVar(value=loop),
            "report": tk.BooleanVar(value=report),
        }
        ttk.Entry(row, textvariable=vars_["name"], width=10).grid(row=0, column=0, padx=1)
        ttk.Label(row, text="first").grid(row=0, column=1)
        ttk.Entry(row, textvariable=vars_["first"], width=4).grid(row=0, column=2, padx=1)
        ttk.Label(row, text="count").grid(row=0, column=3)
        ttk.Entry(row, textvariable=vars_["count"], width=4).grid(row=0, column=4, padx=1)
        ttk.Label(row, text="spd").grid(row=0, column=5)
        ttk.Entry(row, textvariable=vars_["rel"], width=4).grid(row=0, column=6, padx=1)
        ttk.Checkbutton(row, text="loop", variable=vars_["loop"]).grid(row=0, column=7)
        ttk.Checkbutton(row, text="report", variable=vars_["report"]).grid(row=0, column=8)
        ttk.Button(row, text="x", width=2, command=lambda: self.remove_animation(row)).grid(row=0, column=9, padx=2)

        self.animations.append({"frame": row, "vars": vars_})

    def remove_animation(self, row):
        for i, a in enumerate(self.animations):
            if a["frame"] is row:
                a["frame"].destroy()
                del self.animations[i]
                break

    def fill_whole_sequence(self):
        if not self.animations:
            self.add_animation()
        a = self.animations[0]["vars"]
        a["first"].set("0")
        a["count"].set("0")

    # ---- output ----

    def _build_output_panel(self, parent):
        sec = self._section(parent, "6. Output")
        ttk.Button(sec, text="Build sheet and code", command=self.build_output).pack(fill="x", pady=2)
        ttk.Button(sec, text="Save sprite sheet WebP", command=self.save_sheet).pack(fill="x", pady=2)
        ttk.Button(sec, text="Save code (.js)", command=self.save_code).pack(fill="x", pady=2)
        ttk.Button(sec, text="Copy code", command=self.copy_code).pack(fill="x", pady=2)

        ttk.Label(sec, text="Sheet columns (0 = one row)").pack(anchor="w", pady=(6, 0))
        self.var_cols = tk.StringVar(value="5")
        ttk.Entry(sec, textvariable=self.var_cols, width=8).pack(anchor="w")

        ttk.Label(sec, text="WebP quality (1-100)").pack(anchor="w", pady=(6, 0))
        quality_row = ttk.Frame(sec)
        quality_row.pack(fill="x")
        self.var_webp_quality = tk.IntVar(value=100)
        self.quality_scale = ttk.Scale(quality_row, from_=1, to=100, variable=self.var_webp_quality,
                                       orient="horizontal", command=self._on_quality_change)
        self.quality_scale.pack(side="left", fill="x", expand=True)
        self.quality_label = ttk.Label(quality_row, text="", width=8, anchor="e")
        self.quality_label.pack(side="right", padx=(6, 0))

        self.var_webp_lossless = tk.BooleanVar(value=True)
        ttk.Checkbutton(sec, text="Lossless",
                        variable=self.var_webp_lossless,
                        command=self._update_quality_label).pack(anchor="w")
        self._update_quality_label()

        ttk.Label(sec, text="Sheet preview").pack(anchor="w", pady=(6, 0))
        self.sheet_label = tk.Label(sec, bg="#202020", fg="#888888", text="(not built)", height=7)
        self.sheet_label.pack(fill="x")

        ttk.Label(sec, text="Generated code").pack(anchor="w", pady=(6, 0))
        self.code_text = tk.Text(sec, height=16, width=40, font=("Courier", 9), wrap="none")
        self.code_text.pack(fill="both", expand=True)

    def _on_quality_change(self, value=None):
        self._update_quality_label()

    def _update_quality_label(self):
        q = int(round(float(self.var_webp_quality.get())))
        self.var_webp_quality.set(q)
        if self.var_webp_lossless.get():
            self.quality_label.config(text=f"{q}%  off", foreground="gray")
            self.quality_scale.state(["disabled"])
        else:
            self.quality_label.config(text=f"{q}%", foreground="black")
            self.quality_scale.state(["!disabled"])

    # =========================================================
    # Loading
    # =========================================================

    def open_folder(self):
        folder = filedialog.askdirectory(title="Choose folder with frame images")
        if not folder:
            return
        names = [n for n in os.listdir(folder) if n.lower().endswith(IMAGE_EXTS)]
        if not names:
            messagebox.showwarning("No images", "No supported images in that folder.")
            return
        names.sort(key=natural_key)
        self._load([os.path.join(folder, n) for n in names])

    def pick_images(self):
        paths = filedialog.askopenfilenames(
            title="Choose images",
            filetypes=[("Images", " ".join("*" + e for e in IMAGE_EXTS)), ("All files", "*.*")],
        )
        if not paths:
            return
        paths = sorted(paths, key=lambda p: natural_key(os.path.basename(p)))
        self._load(list(paths))

    def open_gif(self):
        path = filedialog.askopenfilename(title="Choose GIF", filetypes=[("GIF", "*.gif")])
        if not path:
            return
        try:
            frames = []
            for i, fr in enumerate(ImageSequence.Iterator(Image.open(path))):
                frames.append({"img": fr.convert("RGBA").copy(),
                               "name": f"{os.path.basename(path)}#{i}"})
        except Exception as e:
            messagebox.showerror("Error", f"Could not read GIF:\n{e}")
            return
        self._set_source(frames, f"GIF: {len(frames)} frames")

    # ---- video ----

    def open_video(self):
        if not HAS_CV2:
            messagebox.showerror("OpenCV missing",
                                 "Video input needs OpenCV. Install it with:\n\npip install -U opencv-python")
            return
        path = filedialog.askopenfilename(
            title="Choose video",
            filetypes=[("Video", " ".join("*" + e for e in VIDEO_EXTS)), ("All files", "*.*")],
        )
        if not path:
            return
        dlg = VideoOptionsDialog(self.root, path)
        self.root.wait_window(dlg.top)
        if dlg.result is None:
            return
        try:
            frames = self._extract_video_frames(path, dlg.result)
        except Exception as e:
            messagebox.showerror("Video error", f"Could not extract frames:\n{e}")
            return
        if not frames:
            messagebox.showwarning("No frames", "No frames were extracted. Check the time range.")
            return
        self._set_source(frames, f"Video: {len(frames)} frames from {os.path.basename(path)}")

    def _extract_video_frames(self, path, opt):
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise RuntimeError("OpenCV could not open this video file.")
        try:
            src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            duration = total / src_fps if total else None

            start = max(0.0, opt["start"])
            end = opt["end"] if opt["end"] > 0 else duration
            if end is not None and end <= start:
                raise ValueError("End time must be after start time.")

            if opt["mode"] == "fps":
                target = max(0.1, opt["fps"])
                step = max(1, round(src_fps / target))
            else:
                step = max(1, opt["every_n"])

            cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
            frames = []
            index = 0
            max_frames = opt["max_frames"]

            while True:
                ok, bgr = cap.read()
                if not ok:
                    break
                pos_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                if end is not None and pos_sec > end:
                    break
                if index % step == 0:
                    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
                    img = Image.fromarray(rgb, "RGBA")
                    if opt["resize_w"] > 0 or opt["resize_h"] > 0:
                        w, h = opt["resize_w"], opt["resize_h"]
                        if w <= 0:
                            w = max(1, round(img.width * h / img.height))
                        if h <= 0:
                            h = max(1, round(img.height * w / img.width))
                        img = img.resize((w, h), Image.LANCZOS)
                    frames.append({"img": img, "name": f"{os.path.basename(path)}@{pos_sec:.2f}s",
                                   "hold": 1})
                    if max_frames > 0 and len(frames) >= max_frames:
                        break
                index += 1
        finally:
            cap.release()
        return frames

    def _load(self, paths):
        frames, failed = [], 0
        for p in paths:
            try:
                frames.append({"img": Image.open(p).convert("RGBA"), "name": os.path.basename(p)})
            except Exception:
                failed += 1
        if not frames:
            messagebox.showerror("Error", "No images could be opened.")
            return
        msg = f"{len(frames)} images" + (f" ({failed} failed)" if failed else "")
        self._set_source(frames, msg)

    def _set_source(self, frames, text):
        self.source_frames = frames
        self.info.config(text=text, foreground="black")
        self.apply_processing(silent=True)
        self.status.config(text="Loaded. Adjust processing, then click Apply processing.")

    def clear_all(self):
        self.source_frames = []
        self.frames = []
        self.sheet = None
        self.sheet_info = None
        self.playing = False
        self.seq_list.delete(0, "end")
        self.code_text.delete("1.0", "end")
        self.sheet_label.config(image="", text="(not built)")
        self.preview.config(image="", text="Load frames to preview")
        self.frame_label.config(text="")
        self.info.config(text="No frames loaded.", foreground="gray")

    # =========================================================
    # Processing (always from source frames, so it can be re-run)
    # =========================================================

    def _parse_crop(self):
        vals = [v.get().strip() for v in self.crop_vars]
        if all(v == "" for v in vals):
            return None
        out = []
        for v in vals:
            if v == "":
                out.append(0)
                continue
            try:
                n = int(v)
            except ValueError:
                raise ValueError("Crop values must be whole numbers.")
            if n < 0:
                raise ValueError("Crop values cannot be negative.")
            out.append(n)
        return tuple(out)

    def _resample_mode(self):
        return {
            "Nearest (pixel art)": Image.NEAREST,
            "Bilinear": Image.BILINEAR,
            "Lanczos (smooth)": Image.LANCZOS,
        }[self.var_resample.get()]

    def _process_image(self, img):
        crop = self._parse_crop()
        if crop:
            l, t, r, b = crop
            img = img.crop((l, t, max(l + 1, img.width - r), max(t + 1, img.height - b)))

        if self.var_autotrim.get():
            bbox = img.getchannel("A").getbbox()
            if bbox:
                img = img.crop(bbox)

        pct = to_float(self.var_percent.get().strip(), 100)
        if pct <= 0:
            raise ValueError("Percentage must be greater than 0.")

        rw, rh = self.var_rw.get().strip(), self.var_rh.get().strip()
        if abs(pct - 100) > 1e-9:
            w = max(1, round(img.width * pct / 100))
            h = max(1, round(img.height * pct / 100))
            img = img.resize((w, h), self._resample_mode())
        elif rw or rh:
            w, h = to_int(rw, 0), to_int(rh, 0)
            if w <= 0 and h <= 0:
                raise ValueError("Resize values must be positive whole numbers.")
            if w <= 0:
                w = max(1, round(img.width * h / img.height))
            if h <= 0:
                h = max(1, round(img.height * w / img.width))
            img = img.resize((w, h), self._resample_mode())

        t = self.var_transform.get()
        if t == "Flip horizontal":
            img = ImageOps.mirror(img)
        elif t == "Flip vertical":
            img = ImageOps.flip(img)
        elif t == "Rotate 90":
            img = img.rotate(-90, expand=True)
        elif t == "Rotate 180":
            img = img.rotate(180, expand=True)
        elif t == "Rotate 270":
            img = img.rotate(90, expand=True)
        return img

    def apply_processing(self, silent=False):
        if not self.source_frames:
            if not silent:
                messagebox.showwarning("No frames", "Load frames first.")
            return
        try:
            processed = [{"img": self._process_image(f["img"]), "name": f["name"], "hold": 1}
                         for f in self.source_frames]

            if self.opt_vars["every_n"].get():
                n = to_int(self.var_every_n.get(), 0)
                if n < 2:
                    raise ValueError("n must be 2 or more (n = 1 would remove every frame).")
                processed = [f for i, f in enumerate(processed, start=1) if i % n != 0]
                if not processed:
                    raise ValueError("Every frame would be removed. Use a larger n.")

            if self.opt_vars["dupes"].get():
                processed = self._merge_duplicates(processed)

            if self.opt_vars["quantize"].get():
                for f in processed:
                    f["img"] = f["img"].convert("RGB").quantize(colors=256).convert("RGBA")

        except ValueError as e:
            if not silent:
                messagebox.showerror("Invalid input", str(e))
            return
        except Exception as e:
            messagebox.showerror("Error", f"Processing failed:\n{e}")
            return

        self.frames = processed
        self.preview_index = 0
        self.sheet = None
        self.sheet_info = None
        self.refresh_sequence()
        self.show_preview_frame()
        self.status.config(text=f"Processed: {len(processed)} frames.")

    def _merge_duplicates(self, items):
        out = []
        for f in items:
            if out and out[-1]["img"].size == f["img"].size \
                    and out[-1]["img"].tobytes() == f["img"].tobytes():
                out[-1]["hold"] += f["hold"]
            else:
                out.append(f)
        return out

    # =========================================================
    # Sequence editing
    # =========================================================

    def refresh_sequence(self):
        self.seq_list.delete(0, "end")
        for i, f in enumerate(self.frames):
            self.seq_list.insert(
                "end",
                f"{i:>3}  {f['name'][:30]:<30}  {f['img'].width}x{f['img'].height}  hold x{f['hold']}")
        self._update_counts()

    def _selected(self):
        sel = self.seq_list.curselection()
        return sel[0] if sel else None

    def on_seq_select(self, event=None):
        i = self._selected()
        if i is not None:
            self.preview_index = i
            self.show_preview_frame()

    def move_selected(self, delta):
        i = self._selected()
        if i is None:
            return
        j = i + delta
        if 0 <= j < len(self.frames):
            self.frames[i], self.frames[j] = self.frames[j], self.frames[i]
            self.sheet = None
            self.refresh_sequence()
            self.seq_list.selection_set(j)
            self.preview_index = j
            self.show_preview_frame()

    def duplicate_selected(self):
        i = self._selected()
        if i is None:
            return
        self.frames.insert(i + 1, dict(self.frames[i]))
        self.sheet = None
        self.refresh_sequence()

    def delete_selected(self):
        i = self._selected()
        if i is None:
            return
        del self.frames[i]
        self.sheet = None
        self.preview_index = min(i, max(0, len(self.frames) - 1))
        self.refresh_sequence()
        self.show_preview_frame()

    def change_hold(self, delta):
        i = self._selected()
        if i is None:
            return
        self.frames[i]["hold"] = max(1, self.frames[i]["hold"] + delta)
        self.sheet = None
        self.refresh_sequence()
        self.seq_list.selection_set(i)

    def _expanded_frames(self):
        out = []
        for f in self.frames:
            out.extend([f] * f["hold"])
        return out

    def _update_counts(self):
        self.frame_label.config(
            text=f"{len(self.frames)} frames / {len(self._expanded_frames())} sheet cells")

    # =========================================================
    # Save individual frames
    # =========================================================

    def _frame_file_name(self, index, frame):
        base = os.path.splitext(frame["name"])[0]
        return f"{index:03d}_{safe_filename(base)}.png"

    def save_selected_frame(self):
        i = self._selected()
        if i is None:
            if not self.frames:
                messagebox.showwarning("No frames", "Load frames first.")
            else:
                messagebox.showinfo("No selection", "Click a frame in the sequence list first.")
            return
        frame = self.frames[i]
        path = filedialog.asksaveasfilename(
            title="Save selected frame",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
            initialfile=self._frame_file_name(i, frame),
        )
        if not path:
            return
        try:
            frame["img"].save(path, "PNG")
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save frame:\n{e}")
            return
        self.status.config(text=f"Saved frame {i} to {path} ({frame['img'].width}x{frame['img'].height}px)")

    def save_all_frames(self):
        if not self.frames:
            messagebox.showwarning("No frames", "Load frames first.")
            return
        folder = filedialog.askdirectory(title="Choose folder to save all frames")
        if not folder:
            return
        try:
            for i, frame in enumerate(self.frames):
                frame["img"].save(os.path.join(folder, self._frame_file_name(i, frame)), "PNG")
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save frames:\n{e}")
            return
        self.status.config(text=f"Saved {len(self.frames)} frames to {folder}")

    # =========================================================
    # Preview
    # =========================================================

    def show_preview_frame(self):
        if not self.frames:
            self.preview.config(image="", text="Load frames to preview")
            return
        self.preview_index %= len(self.frames)
        img = self.frames[self.preview_index]["img"]

        max_w, max_h = PREVIEW_MAX
        scale = min(max_w / img.width, max_h / img.height)
        if scale >= 1:
            scale = int(scale)          # whole-number zoom keeps pixel art sharp
        scale = max(scale, 0.05)
        size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
        self.preview_photo = ImageTk.PhotoImage(img.resize(size, Image.NEAREST))
        self.preview.config(image=self.preview_photo, text="")

        self.frame_label.config(
            text=f"Frame {self.preview_index}  ({img.width}x{img.height}, zoom {scale:g}x)  "
                 f"{len(self.frames)} frames / {len(self._expanded_frames())} cells")

    def step(self, delta):
        if not self.frames:
            return
        self.preview_index = (self.preview_index + delta) % len(self.frames)
        self.seq_list.selection_clear(0, "end")
        self.seq_list.selection_set(self.preview_index)
        self.seq_list.see(self.preview_index)
        self.show_preview_frame()

    def toggle_play(self):
        self.playing = not self.playing
        if self.playing:
            self._tick()
        elif self.play_job:
            self.root.after_cancel(self.play_job)
            self.play_job = None

    def _tick(self):
        if not self.playing or not self.frames:
            self.play_job = None
            return
        fps = max(0.1, to_float(self.dv["fps"].get(), 10))
        hold = self.frames[self.preview_index]["hold"]
        self.step(1)
        self.play_job = self.root.after(int(1000 / fps * hold), self._tick)

    # =========================================================
    # Build output
    # =========================================================

    def build_sheet(self):
        cells = self._expanded_frames()
        if not cells:
            return None, None
        fw = max(f["img"].width for f in cells)
        fh = max(f["img"].height for f in cells)
        n = len(cells)

        cols = to_int(self.var_cols.get(), 0)
        if cols <= 0:
            cols = n
        cols = min(cols, n)
        rows = -(-n // cols)

        sheet = Image.new("RGBA", (cols * fw, rows * fh), (0, 0, 0, 0))
        for i, f in enumerate(cells):
            c, r = i % cols, i // cols
            x = c * fw + (fw - f["img"].width) // 2
            y = r * fh + (fh - f["img"].height) // 2
            sheet.paste(f["img"], (x, y), f["img"])
        return sheet, (fw, fh, cols, rows, n)

    def _collect_animations(self, total):
        out = []
        for i, a in enumerate(self.animations):
            v = a["vars"]
            name = v["name"].get().strip() or f"anim_{i}"
            first = to_int(v["first"].get(), -1)
            count = to_int(v["count"].get(), -1)
            if count == 0:
                count = total - first if first >= 0 else 0
            if first < 0 or count <= 0:
                raise ValueError(f"Animation '{name}': first must be >= 0 and count must be > 0 (0 = to end).")
            if first + count > total:
                raise ValueError(
                    f"Animation '{name}' goes past the end of the sheet ({first}+{count} > {total} cells).")
            out.append({
                "name": name,
                "first": first,
                "count": count,
                "rel": to_float(v["rel"].get(), 1),
                "loop": bool(v["loop"].get()),
                "report": bool(v["report"].get()),
            })
        if not out:
            raise ValueError("Add at least one animation.")
        return out

    def build_output(self):
        if not self.frames:
            messagebox.showwarning("No frames", "Load frames first.")
            return
        sheet, info = self.build_sheet()
        if sheet is None:
            return
        fw, fh, cols, rows, n = info

        try:
            anims = self._collect_animations(n)
        except ValueError as e:
            messagebox.showerror("Animation error", str(e))
            return

        self.sheet = sheet
        self.sheet_info = info

        thumb = sheet.copy()
        thumb.thumbnail((310, 110), Image.NEAREST)
        self.sheet_photo = ImageTk.PhotoImage(thumb)
        self.sheet_label.config(image=self.sheet_photo, text="", height=0)

        self.code_text.delete("1.0", "end")
        self.code_text.insert("1.0", self.make_code(fw, fh, anims))
        self.status.config(text=f"Built sheet {sheet.width}x{sheet.height}px "
                                f"({cols} cols x {rows} rows, {n} cells, {len(anims)} animation(s)).")

    def make_code(self, fw, fh, anims):
        g = lambda k: self.dv[k].get().strip()
        b = lambda k: "true" if self.dv[k].get() else "false"

        def num(k, default=0):
            return fmt(to_float(g(k), default))

        comment = g("comment")
        head = f"// {comment}\n" if comment else ""
        speed = f"{num('fps', 10)} / {num('timescale', 30)}"

        blocks = []
        for i, a in enumerate(anims):
            blocks.append(
                f"\t\t\t{{ // {i}: {a['name']}\n"
                f"\t\t\t\tfirstFrame: {a['first']},\n"
                f"\t\t\t\tframesTotal: {a['count']},\n"
                f"\t\t\t\trelativeSpeed: {fmt(a['rel'])},\n"
                f"\t\t\t\tlooped: {'true' if a['loop'] else 'false'},\n"
                f"\t\t\t\treport_animation_end: {'true' if a['report'] else 'false'}\n"
                f"\t\t\t}}"
            )
        anim_text = ",\n".join(blocks)

        return (
            f"{head}var decoration = pb2Decoration.CreateDecoration({{\n"
            f"\tsource: '{g('source')}',\n"
            f"\tx: {num('x')},\n"
            f"\ty: {num('y')},\n"
            f"\tz: {num('z')},\n"
            f"\tscaleX: {num('scale_x')},\n"
            f"\tscaleY: {num('scale_y')},\n"
            f"\tscaleZ: {num('scale_z')},\n"
            f"\tframeWidth: {fw},\n"
            f"\tframeHeight: {fh},\n"
            f"\tframeOffsetX: {num('frame_off_x')},\n"
            f"\tframeOffsetY: {num('frame_off_y')},\n"
            f"\tframeOffsetZ: {num('frame_off_z')},\n"
            f"\toffsetX: {num('offset_x')},\n"
            f"\toffsetY: {num('offset_y')},\n"
            f"\toffsetZ: {num('offset_z')},\n"
            f"\tpixelated: {b('pixelated')},\n"
            f"\tis_static: {b('is_static')},\n"
            f"\tanimation_info:\n"
            f"\t{{\n"
            f"\t\tframe: {num('start_frame')},\n"
            f"\t\tisPlaying: {b('is_playing')},\n"
            f"\t\tisRelativeToWorld: {b('relative_world')},\n"
            f"\t\tframeProgress: {num('frame_progress')},\n"
            f"\t\tspeed: {speed},\n"
            f"\t\tanimation_id: {num('anim_id')},\n"
            f"\t\tanimations:\n"
            f"\t\t[\n"
            f"{anim_text}\n"
            f"\t\t]\n"
            f"\t}}\n"
            f"}});\n"
        )

    # =========================================================
    # Save / copy
    # =========================================================

    def save_sheet(self):
        if self.sheet is None:
            messagebox.showwarning("Not built", "Click 'Build sheet and code' first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".webp",
            filetypes=[("WebP image", "*.webp")],
            initialfile="sprite_sheet.webp",
        )
        if not path:
            return
        try:
            if self.var_webp_lossless.get():
                self.sheet.save(path, "WEBP", lossless=True, method=6)
            else:
                self.sheet.save(path, "WEBP", quality=int(self.var_webp_quality.get()), method=6)
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save WebP:\n{e}")
            return
        self.status.config(text=f"Saved {path}")

    def save_code(self):
        code = self.code_text.get("1.0", "end").strip()
        if not code:
            messagebox.showwarning("No code", "Click 'Build sheet and code' first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".js",
                                            filetypes=[("JavaScript", "*.js"), ("Text", "*.txt")],
                                            initialfile="decoration.js")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(code + "\n")
            self.status.config(text=f"Saved {path}")

    def copy_code(self):
        code = self.code_text.get("1.0", "end").strip()
        if not code:
            messagebox.showwarning("No code", "Click 'Build sheet and code' first.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self.status.config(text="Code copied to clipboard.")


class VideoOptionsDialog:
    """Modal dialog for video extraction settings."""

    def __init__(self, parent, path):
        self.result = None
        self.top = tk.Toplevel(parent)
        self.top.title("Video extraction options")
        self.top.transient(parent)
        self.top.resizable(False, False)

        frm = ttk.Frame(self.top, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=os.path.basename(path), font=("", 10, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self.v_start = tk.StringVar(value="0")
        self.v_end = tk.StringVar(value="0")
        self.v_mode = tk.StringVar(value="fps")
        self.v_fps = tk.StringVar(value="10")
        self.v_every = tk.StringVar(value="2")
        self.v_max = tk.StringVar(value="120")
        self.v_rw = tk.StringVar(value="0")
        self.v_rh = tk.StringVar(value="0")

        rows = [
            ("Start time (seconds)", self.v_start),
            ("End time (seconds, 0 = end of video)", self.v_end),
        ]
        r = 1
        for label, var in rows:
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=2)
            ttk.Entry(frm, textvariable=var, width=10).grid(row=r, column=1, sticky="w", padx=6)
            r += 1

        ttk.Label(frm, text="Sampling").grid(row=r, column=0, sticky="w", pady=(8, 2))
        ttk.Radiobutton(frm, text="Target FPS", variable=self.v_mode, value="fps").grid(
            row=r, column=1, sticky="w", pady=(8, 2))
        r += 1
        ttk.Label(frm, text="Target FPS").grid(row=r, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=self.v_fps, width=10).grid(row=r, column=1, sticky="w", padx=6)
        r += 1
        ttk.Radiobutton(frm, text="Every n-th source frame", variable=self.v_mode, value="every").grid(
            row=r, column=0, sticky="w", pady=2)
        ttk.Entry(frm, textvariable=self.v_every, width=10).grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(frm, text="Max frames (0 = no limit)").grid(row=r, column=0, sticky="w", pady=(8, 2))
        ttk.Entry(frm, textvariable=self.v_max, width=10).grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        ttk.Label(frm, text="Resize on extract W x H (0 = keep)").grid(row=r, column=0, sticky="w", pady=(8, 2))
        size = ttk.Frame(frm)
        size.grid(row=r, column=1, sticky="w", padx=6)
        ttk.Entry(size, textvariable=self.v_rw, width=6).pack(side="left")
        ttk.Label(size, text="x").pack(side="left", padx=4)
        ttk.Entry(size, textvariable=self.v_rh, width=6).pack(side="left")
        r += 1

        btns = ttk.Frame(frm)
        btns.grid(row=r, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", command=self.top.destroy).pack(side="right")
        ttk.Button(btns, text="Extract", command=self._ok).pack(side="right", padx=6)

        self.top.bind("<Return>", lambda e: self._ok())
        self.top.bind("<Escape>", lambda e: self.top.destroy())

    def _ok(self):
        try:
            start = float(self.v_start.get())
            end = float(self.v_end.get())
            fps = float(self.v_fps.get())
            every = int(float(self.v_every.get()))
            max_frames = int(float(self.v_max.get()))
            rw = int(float(self.v_rw.get()))
            rh = int(float(self.v_rh.get()))
        except ValueError:
            messagebox.showerror("Invalid input", "Enter numbers only.", parent=self.top)
            return
        if start < 0 or end < 0 or rw < 0 or rh < 0 or max_frames < 0:
            messagebox.showerror("Invalid input", "Values cannot be negative.", parent=self.top)
            return
        if fps <= 0 or every < 1:
            messagebox.showerror("Invalid input", "FPS must be > 0 and n must be 1 or more.", parent=self.top)
            return
        self.result = {
            "start": start,
            "end": end,
            "mode": self.v_mode.get(),
            "fps": fps,
            "every_n": every,
            "max_frames": max_frames,
            "resize_w": rw,
            "resize_h": rh,
        }
        self.top.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SpriteStudio(root)
    root.mainloop()