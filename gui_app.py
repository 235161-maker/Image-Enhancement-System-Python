import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageTk, ImageDraw, ImageFilter
import numpy as np
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as ReportImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import io

from image_processor import ImageProcessor

# ── Colour palette (Discord-ish purple/dark) ─────────────────────────────────
BG_DARK     = "#1a1225"   # deepest background
BG_SIDEBAR  = "#211533"   # left sidebar
BG_CARD     = "#2a1d3e"   # cards / panels
BG_SURFACE  = "#321f4a"   # lighter surface
ACCENT      = "#b44fde"   # primary purple accent
ACCENT2     = "#e040a0"   # pink accent
ACCENT_SOFT = "#7b3fa8"   # softer purple
TEXT_PRIMARY = "#f0e8ff"
TEXT_SEC     = "#a89cc0"
TEXT_MUTED   = "#6b5f82"
SUCCESS      = "#43b581"
DANGER       = "#f04747"
INFO         = "#7289da"
BORDER       = "#3d2960"

FONT_TITLE  = ("Segoe UI", 20, "bold")
FONT_HEAD   = ("Segoe UI", 12, "bold")
FONT_BODY   = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 9)
FONT_MONO   = ("Consolas", 9)

# ── Custom styled widgets ─────────────────────────────────────────────────────
def make_rounded_btn(parent, text, command, bg=ACCENT, fg=TEXT_PRIMARY,
                     font=FONT_BODY, width=None, padx=16, pady=8):
    btn = tk.Button(parent, text=text, command=command,
                    bg=bg, fg=fg, font=font,
                    relief=tk.FLAT, cursor="hand2",
                    activebackground=ACCENT2, activeforeground="white",
                    borderwidth=0, padx=padx, pady=pady)
    if width:
        btn.config(width=width)
    # Hover effect
    def on_enter(e): btn.config(bg=ACCENT2)
    def on_leave(e): btn.config(bg=bg)
    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn

def make_section_label(parent, text):
    lbl = tk.Label(parent, text=text.upper(), font=("Segoe UI", 8, "bold"),
                   bg=BG_SIDEBAR, fg=TEXT_MUTED)
    lbl.pack(anchor=tk.W, padx=16, pady=(14, 4))

def make_sidebar_btn(parent, text, icon="", command=None, active=False):
    color = ACCENT if active else BG_SIDEBAR
    fg    = TEXT_PRIMARY if active else TEXT_SEC
    btn = tk.Button(parent, text=f"  {icon}  {text}", command=command,
                    bg=color, fg=fg, font=FONT_BODY,
                    relief=tk.FLAT, anchor=tk.W, cursor="hand2",
                    activebackground=BG_SURFACE, activeforeground=TEXT_PRIMARY,
                    borderwidth=0, padx=8, pady=10)
    btn.pack(fill=tk.X, padx=8, pady=1)
    def on_enter(e): btn.config(bg=BG_SURFACE if not active else ACCENT_SOFT, fg=TEXT_PRIMARY)
    def on_leave(e): btn.config(bg=color, fg=fg)
    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn

# ── Main Application ──────────────────────────────────────────────────────────
class ImageEnhancementApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DIP — Image Enhancement System")
        self.root.geometry("1440x860")
        self.root.configure(bg=BG_DARK)
        self.root.resizable(True, True)

        self.processor = ImageProcessor()
        self.current_image = None
        self.active_tab = tk.StringVar(value="load")

        # ttk style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG_DARK)
        style.configure("Card.TFrame", background=BG_CARD)
        style.configure("TLabel", background=BG_DARK, foreground=TEXT_PRIMARY)
        style.configure("TNotebook", background=BG_DARK, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG_SURFACE, foreground=TEXT_SEC,
                         padding=[14, 8], font=FONT_SMALL, borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT), ("active", BG_SURFACE)],
                  foreground=[("selected", "white"), ("active", TEXT_PRIMARY)])

        self._build_ui()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Top bar ──────────────────────────────────────────────────────────
        topbar = tk.Frame(self.root, bg=BG_SIDEBAR, height=52)
        topbar.pack(fill=tk.X, side=tk.TOP)
        topbar.pack_propagate(False)

        logo = tk.Label(topbar, text="  ✦ DIP Studio", font=("Segoe UI", 15, "bold"),
                        bg=BG_SIDEBAR, fg=ACCENT)
        logo.pack(side=tk.LEFT, padx=20)

        tagline = tk.Label(topbar, text="Image Enhancement System",
                           font=FONT_SMALL, bg=BG_SIDEBAR, fg=TEXT_MUTED)
        tagline.pack(side=tk.LEFT)

        # right side buttons in topbar
        for txt, cmd, col in [("⬇ Save", self.save_output, INFO),
                               ("📄 Report", self.generate_report, SUCCESS),
                               ("✖ Reset", self.reset_all, DANGER)]:
            make_rounded_btn(topbar, txt, cmd, bg=col, padx=12, pady=6).pack(
                side=tk.RIGHT, padx=6, pady=10)

        # ── Body: sidebar + main ──────────────────────────────────────────────
        body = tk.Frame(self.root, bg=BG_DARK)
        body.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        self.sidebar = tk.Frame(body, bg=BG_SIDEBAR, width=220)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        # Divider
        tk.Frame(body, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        # Main area
        main = tk.Frame(body, bg=BG_DARK)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_main(main)

    def _build_sidebar(self):
        # Avatar / user area
        user_frame = tk.Frame(self.sidebar, bg=BG_SURFACE, height=72)
        user_frame.pack(fill=tk.X)
        user_frame.pack_propagate(False)

        avatar = tk.Label(user_frame, text="🎨", font=("Segoe UI", 22),
                          bg=ACCENT, fg="white", width=3)
        avatar.pack(side=tk.LEFT, padx=10, pady=12)

        info = tk.Frame(user_frame, bg=BG_SURFACE)
        info.pack(side=tk.LEFT, pady=10)
        tk.Label(info, text="DIP Studio", font=("Segoe UI", 10, "bold"),
                 bg=BG_SURFACE, fg=TEXT_PRIMARY).pack(anchor=tk.W)
        tk.Label(info, text="v1.0 Professional", font=FONT_SMALL,
                 bg=BG_SURFACE, fg=ACCENT).pack(anchor=tk.W)

        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill=tk.X, padx=12, pady=8)

        make_section_label(self.sidebar, "Navigation")
        self.nav_btns = {}
        nav_items = [
            ("load",      "📁", "Load Image"),
            ("sampling",  "🔲", "Sampling & Quantization"),
            ("transform", "🔄", "Transformations"),
            ("intensity", "🌗", "Intensity & Histogram"),
            ("enhance",   "✨", "Enhancement Pipeline"),
        ]
        for key, icon, label in nav_items:
            btn = make_sidebar_btn(self.sidebar, label, icon,
                                   command=lambda k=key: self._switch_tab(k),
                                   active=(key == "load"))
            self.nav_btns[key] = btn

        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill=tk.X, padx=12, pady=8)
        make_section_label(self.sidebar, "Image Info")

        self.info_vars = {}
        for field in ["Resolution", "Channels", "Data Type", "File Size"]:
            row = tk.Frame(self.sidebar, bg=BG_SIDEBAR)
            row.pack(fill=tk.X, padx=16, pady=2)
            tk.Label(row, text=field, font=FONT_SMALL, bg=BG_SIDEBAR,
                     fg=TEXT_MUTED, width=10, anchor=tk.W).pack(side=tk.LEFT)
            var = tk.StringVar(value="—")
            lbl = tk.Label(row, textvariable=var, font=FONT_SMALL,
                           bg=BG_SIDEBAR, fg=TEXT_PRIMARY, anchor=tk.W)
            lbl.pack(side=tk.LEFT)
            self.info_vars[field] = var

    def _build_main(self, parent):
        # ── Content panes (stacked, only one visible) ─────────────────────────
        self.tab_frames = {}
        pane_host = tk.Frame(parent, bg=BG_DARK)
        pane_host.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        # Split: left = controls  /  right = viewer
        controls_host = tk.Frame(pane_host, bg=BG_DARK, width=340)
        controls_host.pack(side=tk.LEFT, fill=tk.Y)
        controls_host.pack_propagate(False)

        tk.Frame(pane_host, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))

        viewer_host = tk.Frame(pane_host, bg=BG_DARK)
        viewer_host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Build all tab panels into controls_host
        for key, builder in [
            ("load",      self._tab_load),
            ("sampling",  self._tab_sampling),
            ("transform", self._tab_transform),
            ("intensity", self._tab_intensity),
            ("enhance",   self._tab_enhance),
        ]:
            f = tk.Frame(controls_host, bg=BG_DARK)
            builder(f)
            self.tab_frames[key] = f

        self.tab_frames["load"].pack(fill=tk.BOTH, expand=True)

        # Viewer
        self._build_viewer(viewer_host)

    def _switch_tab(self, key):
        for k, f in self.tab_frames.items():
            f.pack_forget()
        self.tab_frames[key].pack(fill=tk.BOTH, expand=True)
        for k, btn in self.nav_btns.items():
            btn.config(bg=ACCENT if k == key else BG_SIDEBAR,
                       fg=TEXT_PRIMARY if k == key else TEXT_SEC)

    # ── Viewer (right side) ───────────────────────────────────────────────────
    def _build_viewer(self, parent):
        # Image card
        img_card = tk.Frame(parent, bg=BG_CARD, relief=tk.FLAT, bd=0)
        img_card.pack(fill=tk.BOTH, expand=True)

        # Header strip
        hdr = tk.Frame(img_card, bg=BG_SURFACE, height=40)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text="◉  Preview Canvas", font=("Segoe UI", 10, "bold"),
                 bg=BG_SURFACE, fg=TEXT_PRIMARY).pack(side=tk.LEFT, padx=14)
        tk.Label(hdr, text="PNG  ·  Grayscale", font=FONT_SMALL,
                 bg=BG_SURFACE, fg=TEXT_MUTED).pack(side=tk.RIGHT, padx=14)

        self.image_label = tk.Label(img_card, bg=BG_CARD,
                                    text="Drop an image or click  📁 Load Image",
                                    font=("Segoe UI", 13), fg=TEXT_MUTED)
        self.image_label.pack(expand=True, fill=tk.BOTH, padx=30, pady=30)

        # Log panel
        log_card = tk.Frame(parent, bg=BG_CARD, height=160)
        log_card.pack(fill=tk.X, pady=(8, 0))
        log_card.pack_propagate(False)

        log_hdr = tk.Frame(log_card, bg=BG_SURFACE, height=32)
        log_hdr.pack(fill=tk.X)
        log_hdr.pack_propagate(False)
        tk.Label(log_hdr, text="⬡  Activity Log", font=("Segoe UI", 9, "bold"),
                 bg=BG_SURFACE, fg=TEXT_PRIMARY).pack(side=tk.LEFT, padx=12, pady=6)

        self.info_text = tk.Text(log_card, font=FONT_MONO, bg=BG_DARK, fg=SUCCESS,
                                 insertbackground=SUCCESS, relief=tk.FLAT, bd=0,
                                 wrap=tk.WORD, padx=12, pady=8)
        self.info_text.pack(fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(self.info_text, command=self.info_text.yview)
        self.info_text.config(yscrollcommand=scrollbar.set)

    # ── Control Tabs ──────────────────────────────────────────────────────────
    def _card(self, parent, title):
        """A labelled card section."""
        outer = tk.Frame(parent, bg=BG_CARD, relief=tk.FLAT)
        outer.pack(fill=tk.X, padx=0, pady=(0, 10))

        hdr = tk.Frame(outer, bg=BG_SURFACE, height=30)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"  {title}", font=("Segoe UI", 9, "bold"),
                 bg=BG_SURFACE, fg=ACCENT).pack(side=tk.LEFT, pady=5)

        inner = tk.Frame(outer, bg=BG_CARD)
        inner.pack(fill=tk.X, padx=12, pady=10)
        return inner

    def _tab_load(self, parent):
        tk.Label(parent, text="Load Image", font=FONT_TITLE,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor=tk.W, pady=(0, 6))
        tk.Label(parent, text="Import a photo to get started",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor=tk.W, pady=(0, 16))

        card = self._card(parent, "📁  Image Source")
        make_rounded_btn(card, "  Choose Image File", self.load_image,
                         bg=ACCENT, padx=20, pady=10).pack(fill=tk.X, pady=(0, 6))
        tk.Label(card, text="Supports: JPG · PNG · BMP · TIFF",
                 font=FONT_SMALL, bg=BG_CARD, fg=TEXT_MUTED).pack()

        card2 = self._card(parent, "ℹ  Format Info")
        note = ("Images are auto-converted to Grayscale upon loading.\n"
                "All enhancements are applied on the grayscale copy.")
        tk.Label(card2, text=note, font=FONT_SMALL, bg=BG_CARD, fg=TEXT_SEC,
                 wraplength=280, justify=tk.LEFT).pack(anchor=tk.W)

    def _tab_sampling(self, parent):
        tk.Label(parent, text="Sampling & Quantization", font=FONT_TITLE,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor=tk.W, pady=(0, 6))
        tk.Label(parent, text="Resize and reduce bit depth",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor=tk.W, pady=(0, 16))

        card = self._card(parent, "🔲  Resampling")
        for label, scale, col in [
            ("0.25×  Thumbnail", 0.25, BG_SURFACE),
            ("0.5×   Half size",  0.50, BG_SURFACE),
            ("1.0×   Original",   1.00, ACCENT_SOFT),
            ("1.5×   Large",      1.50, BG_SURFACE),
            ("2.0×   Double",     2.00, BG_SURFACE),
        ]:
            make_rounded_btn(card, label, lambda s=scale: self.apply_resampling(s),
                             bg=col, padx=10, pady=6).pack(fill=tk.X, pady=2)

        card2 = self._card(parent, "🎨  Bit Depth Reduction")
        for label, bits, col in [
            ("8-bit  — Full quality  (256 levels)", 8, ACCENT_SOFT),
            ("4-bit  — Reduced       (16 levels)",  4, BG_SURFACE),
            ("2-bit  — Minimal       (4 levels)",   2, DANGER),
        ]:
            make_rounded_btn(card2, label, lambda b=bits: self.apply_quantization(b),
                             bg=col, padx=10, pady=6).pack(fill=tk.X, pady=2)

    def _tab_transform(self, parent):
        tk.Label(parent, text="Transformations", font=FONT_TITLE,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor=tk.W, pady=(0, 6))
        tk.Label(parent, text="Geometric operations on the image",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor=tk.W, pady=(0, 16))

        card = self._card(parent, "🔄  Rotation")
        row1 = tk.Frame(card, bg=BG_CARD)
        row1.pack(fill=tk.X, pady=2)
        row2 = tk.Frame(card, bg=BG_CARD)
        row2.pack(fill=tk.X, pady=2)
        for i, angle in enumerate([30, 45, 60, 90, 120, 150, 180]):
            r = row1 if i < 4 else row2
            make_rounded_btn(r, f"{angle}°", lambda a=angle: self.apply_rotation(a),
                             bg=ACCENT_SOFT, padx=6, pady=6).pack(side=tk.LEFT, padx=2)

        card2 = self._card(parent, "↔  Translation (50px)")
        grid = tk.Frame(card2, bg=BG_CARD)
        grid.pack()
        make_rounded_btn(grid, "▲ Up",    lambda: self.apply_translation(0, -50),
                         bg=INFO, padx=12, pady=6).grid(row=0, column=1, padx=3, pady=3)
        make_rounded_btn(grid, "◀ Left",  lambda: self.apply_translation(-50, 0),
                         bg=INFO, padx=12, pady=6).grid(row=1, column=0, padx=3)
        make_rounded_btn(grid, "▶ Right", lambda: self.apply_translation(50, 0),
                         bg=INFO, padx=12, pady=6).grid(row=1, column=2, padx=3)
        make_rounded_btn(grid, "▼ Down",  lambda: self.apply_translation(0, 50),
                         bg=INFO, padx=12, pady=6).grid(row=2, column=1, padx=3, pady=3)

        card3 = self._card(parent, "↗  Shearing")
        shear_row = tk.Frame(card3, bg=BG_CARD)
        shear_row.pack()
        make_rounded_btn(shear_row, "Shear X  (0.3)", lambda: self.apply_shearing(0.3),
                         bg=ACCENT2, padx=10, pady=6).pack(side=tk.LEFT, padx=4)
        make_rounded_btn(shear_row, "Shear Y  (0.5)", lambda: self.apply_shearing(0.5),
                         bg=ACCENT2, padx=10, pady=6).pack(side=tk.LEFT, padx=4)

        make_rounded_btn(parent, "⟳  Reset to Original", self.reset_to_original,
                         bg=DANGER, padx=16, pady=8).pack(fill=tk.X, pady=(12, 0))

    def _tab_intensity(self, parent):
        tk.Label(parent, text="Intensity & Histogram", font=FONT_TITLE,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor=tk.W, pady=(0, 6))
        tk.Label(parent, text="Pixel-level intensity transformations",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor=tk.W, pady=(0, 16))

        card = self._card(parent, "🌗  Intensity Transforms")
        for label, cmd, col in [
            ("Negative  (Invert)",        self.apply_negative,              "#7b3fa8"),
            ("Log Transform",             self.apply_log,                   "#7b3fa8"),
            ("Gamma  γ = 0.5  (Brighten)", lambda: self.apply_gamma(0.5),  ACCENT),
            ("Gamma  γ = 1.5  (Darken)",   lambda: self.apply_gamma(1.5),  ACCENT_SOFT),
        ]:
            make_rounded_btn(card, label, cmd, bg=col, padx=10, pady=7).pack(fill=tk.X, pady=2)

        card2 = self._card(parent, "📊  Histogram")
        make_rounded_btn(card2, "Show Histogram",         self.show_histogram,
                         bg=INFO, padx=10, pady=7).pack(fill=tk.X, pady=2)
        make_rounded_btn(card2, "Histogram Equalization", self.apply_equalization,
                         bg=SUCCESS, padx=10, pady=7).pack(fill=tk.X, pady=2)

    def _tab_enhance(self, parent):
        tk.Label(parent, text="Enhancement Pipeline", font=FONT_TITLE,
                 bg=BG_DARK, fg=TEXT_PRIMARY).pack(anchor=tk.W, pady=(0, 6))
        tk.Label(parent, text="Full automatic image enhancement",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack(anchor=tk.W, pady=(0, 16))

        card = self._card(parent, "✨  Pipeline Steps")
        steps = [
            ("1", "Gamma Correction  (γ = 1.2)", "Adjust brightness distribution"),
            ("2", "Histogram Equalization",        "Enhance contrast uniformly"),
            ("3", "Log Transform",                 "Reveal shadow details"),
        ]
        for num, title, desc in steps:
            row = tk.Frame(card, bg=BG_SURFACE, relief=tk.FLAT)
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=num, font=("Segoe UI", 11, "bold"),
                     bg=ACCENT, fg="white", width=3).pack(side=tk.LEFT, padx=(0, 10), ipady=6)
            col = tk.Frame(row, bg=BG_SURFACE)
            col.pack(side=tk.LEFT, pady=6)
            tk.Label(col, text=title, font=("Segoe UI", 9, "bold"),
                     bg=BG_SURFACE, fg=TEXT_PRIMARY).pack(anchor=tk.W)
            tk.Label(col, text=desc, font=FONT_SMALL,
                     bg=BG_SURFACE, fg=TEXT_MUTED).pack(anchor=tk.W)

        make_rounded_btn(parent, "▶  Run Complete Enhancement", self.run_enhancement,
                         bg=SUCCESS, padx=20, pady=12).pack(fill=tk.X, pady=(16, 0))

    # ── Core methods (unchanged logic) ────────────────────────────────────────
    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.info_text.insert(tk.END, f"[{ts}]  {msg}\n")
        self.info_text.see(tk.END)

    def load_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff")])
        if path:
            try:
                self.processor.load_image(path)
                self.processor.convert_to_grayscale()
                self.current_image = self.processor.grayscale_image
                self.display_image(self.current_image)
                self.update_image_info()
                self._log(f"Loaded: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def display_image(self, image):
        if image is None:
            return
        pil = Image.fromarray(image) if image.dtype == np.uint8 else \
              Image.fromarray(image.astype(np.uint8))
        # give it a nice dark border feel
        pil.thumbnail((680, 480), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(pil)
        self.image_label.config(image=photo, text="", bg=BG_CARD)
        self.image_label.image = photo

    def update_image_info(self):
        info = self.processor.get_image_info()
        if info:
            self.info_vars["Resolution"].set(info["resolution"])
            self.info_vars["Channels"].set(str(info["channels"]))
            self.info_vars["Data Type"].set(info["data_type"])
            self.info_vars["File Size"].set(info["file_size"])

    def apply_resampling(self, scale):
        if self.processor.grayscale_image is not None:
            img = self.processor.resample_image(scale)
            self.current_image = img; self.display_image(img)
            self._log(f"Resampled ×{scale}")

    def apply_quantization(self, bits):
        if self.processor.grayscale_image is not None:
            img = self.processor.reduce_bit_depth(bits)
            self.current_image = img; self.display_image(img)
            self._log(f"Bit depth → {bits}-bit  ({2**bits} levels)")

    def apply_rotation(self, angle):
        if self.processor.grayscale_image is not None:
            img = self.processor.rotate_image(angle)
            self.current_image = img; self.display_image(img)
            self._log(f"Rotated {angle}°")

    def apply_translation(self, x, y):
        if self.processor.grayscale_image is not None:
            img = self.processor.translate_image(x, y)
            self.current_image = img; self.display_image(img)
            self._log(f"Translated ({x}, {y}) px")

    def apply_shearing(self, shear):
        if self.processor.grayscale_image is not None:
            img = self.processor.shear_image(shear)
            self.current_image = img; self.display_image(img)
            self._log(f"Sheared factor={shear}")

    def apply_negative(self):
        if self.current_image is not None:
            img = self.processor.negative_transform(self.current_image)
            self.current_image = img; self.display_image(img)
            self._log("Applied negative transform")

    def apply_log(self):
        if self.current_image is not None:
            img = self.processor.log_transform(self.current_image)
            self.current_image = img; self.display_image(img)
            self._log("Applied log transform")

    def apply_gamma(self, gamma):
        if self.current_image is not None:
            img = self.processor.gamma_correction(gamma, self.current_image)
            self.current_image = img; self.display_image(img)
            self._log(f"Gamma correction γ={gamma}")

    def apply_equalization(self):
        if self.current_image is not None:
            img = self.processor.histogram_equalization(self.current_image)
            self.current_image = img; self.display_image(img)
            self._log("Histogram equalization applied")

    def show_histogram(self):
        if self.current_image is None:
            return
        fig = Figure(figsize=(8, 5), facecolor=BG_DARK)
        ax  = fig.add_subplot(111, facecolor=BG_CARD)
        hist = self.processor.compute_histogram(self.current_image)
        ax.fill_between(range(256), hist.flatten(), color=ACCENT, alpha=0.7)
        ax.plot(hist, color=ACCENT2, linewidth=1.5)
        ax.set_xlabel("Pixel Intensity", color=TEXT_SEC)
        ax.set_ylabel("Frequency",       color=TEXT_SEC)
        ax.set_title("Image Histogram",  color=TEXT_PRIMARY, fontsize=13)
        ax.tick_params(colors=TEXT_MUTED)
        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER)
        ax.grid(True, alpha=0.2, color=TEXT_MUTED)

        win = tk.Toplevel(self.root)
        win.title("Histogram")
        win.geometry("820x520")
        win.configure(bg=BG_DARK)
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def run_enhancement(self):
        if self.processor.grayscale_image is None:
            messagebox.showwarning("No Image", "Please load an image first.")
            return
        enhanced = self.processor.enhance_image()
        self.current_image = enhanced
        self.display_image(enhanced)
        self._log("─── Enhancement Pipeline complete ───")
        self._log("  ① Gamma correction γ=1.2")
        self._log("  ② Histogram equalization")
        self._log("  ③ Log transform (c=0.8)")

        fig, axes = plt.subplots(1, 3, figsize=(13, 4),
                                  facecolor=BG_DARK)
        for ax in axes:
            ax.set_facecolor(BG_CARD)
            ax.tick_params(colors=TEXT_MUTED)
            for sp in ax.spines.values():
                sp.set_edgecolor(BORDER)

        axes[0].imshow(self.processor.grayscale_image, cmap="gray")
        axes[0].set_title("Original",  color=TEXT_PRIMARY); axes[0].axis("off")
        axes[1].imshow(enhanced,       cmap="gray")
        axes[1].set_title("Enhanced",  color=TEXT_PRIMARY); axes[1].axis("off")

        h_o = self.processor.compute_histogram(self.processor.grayscale_image)
        h_e = self.processor.compute_histogram(enhanced)
        axes[2].fill_between(range(256), h_o.flatten(), color=INFO,   alpha=0.5, label="Original")
        axes[2].fill_between(range(256), h_e.flatten(), color=ACCENT2, alpha=0.5, label="Enhanced")
        axes[2].set_title("Histogram Comparison", color=TEXT_PRIMARY)
        axes[2].legend(facecolor=BG_SURFACE, labelcolor=TEXT_PRIMARY)
        axes[2].grid(True, alpha=0.2, color=TEXT_MUTED)

        plt.tight_layout()
        plt.show()

    def reset_to_original(self):
        if self.processor.grayscale_image is not None:
            self.current_image = self.processor.grayscale_image
            self.display_image(self.current_image)
            self._log("Reset to original grayscale")

    def reset_all(self):
        self.current_image = None
        self.image_label.config(image="", bg=BG_CARD,
                                text="Drop an image or click  📁 Load Image",
                                font=("Segoe UI", 13), fg=TEXT_MUTED)
        self.info_text.delete(1.0, tk.END)
        for v in self.info_vars.values():
            v.set("—")
        self._log("Workspace cleared")

    def save_output(self):
        if self.current_image is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")])
        if path:
            self.processor.save_image(self.current_image, path)
            self._log(f"Saved → {os.path.basename(path)}")
            messagebox.showinfo("Saved", f"Image saved to:\n{path}")

    def generate_report(self):
        if self.current_image is None:
            messagebox.showwarning("No Image", "Please load and process an image first.")
            return
        os.makedirs("results", exist_ok=True)
        path = f"results/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        doc  = SimpleDocTemplate(path, pagesize=letter)
        styles = getSampleStyleSheet()
        story  = []

        ts = ParagraphStyle("T", parent=styles["Heading1"], fontSize=16, spaceAfter=20)
        story.append(Paragraph("Digital Image Processing — Enhancement Report", ts))
        story.append(Spacer(1, 12))
        story.append(Paragraph("Student Information:", styles["Heading2"]))
        story.append(Paragraph("Name: [Your Name]",         styles["Normal"]))
        story.append(Paragraph("Registration ID: [Reg ID]", styles["Normal"]))
        story.append(Spacer(1, 12))

        info = self.processor.get_image_info()
        if info:
            story.append(Paragraph("Image Information:", styles["Heading2"]))
            for k, v in info.items():
                story.append(Paragraph(f"{k}: {v}", styles["Normal"]))
            story.append(Spacer(1, 12))

        qa = [
            ("1. Why does histogram equalization improve contrast?",
             "Histogram equalization redistributes pixel intensities across the full range, "
             "revealing detail in areas where the histogram was concentrated."),
            ("2. How does gamma affect brightness?",
             "γ < 1 brightens dark regions; γ > 1 darkens highlights. γ = 1 is linear."),
            ("3. What is the effect of quantization on image quality?",
             "Fewer bits → fewer intensity levels → false contours / posterization."),
            ("4. Which transformation is reversible and why?",
             "Geometric transforms are reversible given parameters, but may lose edge info. "
             "Intensity transforms can be irreversible when mapping is many-to-one."),
            ("5. How do transforms affect spatial structure?",
             "Geometric: moves pixels, may cause aliasing. Intensity: preserves positions, "
             "modifies values only."),
        ]
        story.append(Paragraph("Questions & Answers:", styles["Heading2"]))
        for q, a in qa:
            story.append(Paragraph(q, styles["Heading3"]))
            story.append(Paragraph(a, styles["Normal"]))
            story.append(Spacer(1, 6))

        doc.build(story)
        self._log(f"Report saved → {path}")
        messagebox.showinfo("Report", f"PDF generated:\n{path}")


def main():
    root = tk.Tk()
    app  = ImageEnhancementApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()