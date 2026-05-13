import tkinter as tk
from tkinter import messagebox
import subprocess
import threading
import os
from datetime import datetime
import sys
import ctypes
import math
import time

from ctypes import wintypes

class CountdownOverlay:
    def __init__(self, root, on_complete):
        self.root = root
        self.on_complete = on_complete
        self.top = tk.Toplevel(root)
        self.top.attributes("-fullscreen", True)
        self.top.attributes("-topmost", True)
        self.top.attributes("-alpha", 0.8)
        self.top.configure(bg="#000000")
        
        # Make transparent on Windows
        self.top.attributes("-transparentcolor", "#000000")
        
        self.canvas = tk.Canvas(self.top, bg="#000000", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        sw = self.top.winfo_screenwidth()
        sh = self.top.winfo_screenheight()
        
        self.text_id = self.canvas.create_text(
            sw // 2, sh // 2, 
            text="3", 
            fill="#7c3aed", 
            font=("Segoe UI", 120, "bold")
        )
        
        self.count = 3
        self.animate_step()

    def animate_step(self):
        if self.count > 0:
            self.canvas.itemconfig(self.text_id, text=str(self.count))
            # Subtle pulse effect
            self.pulse(120, 150, 0)
            self.count -= 1
            self.top.after(1000, self.animate_step)
        else:
            self.top.destroy()
            self.on_complete()

    def pulse(self, start_size, end_size, step):
        if step > 10: return
        new_size = start_size + (end_size - start_size) * (step / 10)
        self.canvas.itemconfig(self.text_id, font=("Segoe UI", int(new_size), "bold"))
        self.top.after(20, lambda: self.pulse(start_size, end_size, step + 1))


class SplashScreen:
    def __init__(self, root, on_complete):
        self.splash = tk.Toplevel(root)
        self.splash.overrideredirect(True)
        self.splash.attributes("-topmost", True)
        W, H = 220, 220
        self.splash.configure(bg="#13141a", highlightthickness=1, highlightbackground="#7c3aed")

        sw = self.splash.winfo_screenwidth()
        sh = self.splash.winfo_screenheight()
        self.splash.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        self.canvas = tk.Canvas(self.splash, width=W, height=H, bg="#13141a", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Outer ring (dim)
        self.canvas.create_oval(60, 35, 160, 135, outline="#2d2f3a", width=6)
        # Spinner arc
        self.arc = self.canvas.create_arc(60, 35, 160, 135, start=90, extent=270,
                                           outline="#7c3aed", width=6, style=tk.ARC)
        # Inner glow dot
        self.canvas.create_oval(96, 71, 124, 99, fill="#7c3aed", outline="")
        self.canvas.create_oval(102, 77, 118, 93, fill="#c4b5fd", outline="")

        self.canvas.create_text(W//2, 155, text="TinyRec",
                                fill="#f0f0f5", font=("Segoe UI", 13, "bold"))
        self.canvas.create_text(W//2, 178, text="Starting up...",
                                fill="#6b7280", font=("Segoe UI", 9))

        self.angle = 90
        self.running = True
        self.animate()
        self.splash.after(2200, lambda: self.finish(on_complete))

    def animate(self):
        if not self.running: return
        self.angle = (self.angle - 8) % 360
        self.canvas.itemconfig(self.arc, start=self.angle)
        self.splash.after(16, self.animate)

    def finish(self, on_complete):
        self.running = False
        self.splash.destroy()
        on_complete()


# Enable DPI awareness so mouse coordinates match the screen properly on Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

class RegionSelector:
    def __init__(self, master, callback):
        self.callback = callback
        self.start_x = self.start_y = None
        self.dragging = False

        # Fullscreen transparent window — the dark overlay
        self.top = tk.Toplevel(master)
        self.top.attributes('-fullscreen', True)
        self.top.attributes('-alpha', 0.75)
        self.top.attributes('-topmost', True)
        self.top.configure(cursor="none", bg="#000010")

        self.canvas = tk.Canvas(self.top, bg="#000010", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        sw = self.top.winfo_screenwidth()
        sh = self.top.winfo_screenheight()
        self.sw = sw
        self.sh = sh

        # Dark overlay rectangles (4 surrounding the selection - updated on drag)
        # We'll use a stipple approach: one full-screen dark rect + transparent hole
        # Achieved by drawing 4 rects around the selection area
        self.overlay_rects = [
            self.canvas.create_rectangle(0, 0, sw, sh, fill="#000010", outline="", stipple="gray50"),
        ]

        # Crosshair lines (horizontal + vertical) - follow mouse before drag
        self.ch_h = self.canvas.create_line(0, 0, sw, 0, fill="#7c3aed", width=1, dash=(4, 4))
        self.ch_v = self.canvas.create_line(0, 0, 0, sh, fill="#7c3aed", width=1, dash=(4, 4))

        # Selection rectangle (shown after drag starts)
        self.sel_rect = self.canvas.create_rectangle(0, 0, 0, 0,
                                                      outline="#7c3aed", width=2, fill="")
        # Bright border for the selection
        self.sel_border = self.canvas.create_rectangle(0, 0, 0, 0,
                                                        outline="white", width=1, fill="",
                                                        dash=(2, 4))

        # Corner handles (8 small squares)
        self.handles = []
        for _ in range(4):
            h = self.canvas.create_rectangle(0, 0, 6, 6, fill="#7c3aed", outline="white", width=1)
            self.handles.append(h)

        # Live size label — bg first, text on top (z-order matters)
        self.size_bg = self.canvas.create_rectangle(0, 0, 0, 0,
                                                     fill="#7c3aed", outline="", state="hidden")
        self.size_label = self.canvas.create_text(0, 0, text="",
                                                   fill="white", font=("Segoe UI", 9, "bold"),
                                                   anchor="center", state="hidden")

        # Hint label (before drag)
        self.hint = self.canvas.create_text(sw // 2, sh // 2,
                                             text="Click and drag to select recording area  •  Esc to cancel",
                                             fill="#c4b5fd", font=("Segoe UI", 13, "bold"),
                                             anchor="center")

        self.canvas.bind("<ButtonPress-1>",   self.on_press)
        self.canvas.bind("<B1-Motion>",        self.on_drag)
        self.canvas.bind("<ButtonRelease-1>",  self.on_release)
        self.canvas.bind("<Motion>",           self.on_mouse_move)
        # Bind Escape on both canvas AND toplevel — force focus so keys register
        cancel = lambda e: self.top.destroy()
        self.canvas.bind("<Escape>", cancel)
        self.top.bind("<Escape>",    cancel)
        self.canvas.focus_set()

    # ── crosshair follows mouse before drag ──────────────────────
    def on_mouse_move(self, event):
        if self.dragging:
            return
        self.canvas.coords(self.ch_h, 0, event.y, self.sw, event.y)
        self.canvas.coords(self.ch_v, event.x, 0, event.x, self.sh)

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.dragging = True
        # Hide hint and static crosshair once drag begins
        self.canvas.itemconfig(self.hint, state="hidden")
        self.canvas.coords(self.ch_h, 0, -1, 0, -1)
        self.canvas.coords(self.ch_v, 0, -1, 0, -1)

    def on_drag(self, event):
        if not self.dragging:
            return
        x1, y1 = self.start_x, self.start_y
        x2, y2 = event.x, event.y
        lx, rx = min(x1, x2), max(x1, x2)
        ty, by = min(y1, y2), max(y1, y2)
        w, h = rx - lx, by - ty

        # Main selection rect
        self.canvas.coords(self.sel_rect,   lx, ty, rx, by)
        self.canvas.coords(self.sel_border, lx + 1, ty + 1, rx - 1, by - 1)

        # Update 4 corner handles
        corners = [(lx, ty), (rx, ty), (lx, by), (rx, by)]
        for i, (cx, cy) in enumerate(corners):
            self.canvas.coords(self.handles[i], cx - 3, cy - 3, cx + 3, cy + 3)

        # Size label — follows cursor, offset 14px below-right
        label_text = f" {w} × {h} "
        char_w = 7
        pill_w = len(label_text) * char_w
        pill_h = 20

        # Place pill to right/below cursor; flip if too close to screen edge
        px = event.x + 14
        py = event.y + 14
        if px + pill_w > self.sw:
            px = event.x - pill_w - 6
        if py + pill_h > self.sh:
            py = event.y - pill_h - 6

        self.canvas.coords(self.size_bg, px, py, px + pill_w, py + pill_h)
        self.canvas.coords(self.size_label, px + pill_w // 2, py + pill_h // 2)
        self.canvas.itemconfig(self.size_bg,    state="normal")
        self.canvas.itemconfig(self.size_label, text=label_text,
                               state="normal", anchor="center")


    def on_release(self, event):
        if not self.dragging:
            self.top.destroy()
            return

        x1, y1, x2, y2 = (self.start_x, self.start_y, event.x, event.y)
        x, y = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1), abs(y2 - y1)

        w = int(w)
        h = int(h)
        if w % 2 != 0: w += 1
        if h % 2 != 0: h += 1

        if w > 10 and h > 10:
            self.callback(int(x), int(y), w, h)
        self.top.destroy()



class ScreenRecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TinyRec")
        self.app_w = 320
        self.app_h = 430
        self.root.geometry(f"{self.app_w}x{self.app_h}")
        
        # Center the window on screen at startup
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        cx = (sw - self.app_w) // 2
        cy = (sh - self.app_h) // 2
        self.root.geometry(f"{self.app_w}x{self.app_h}+{cx}+{cy}")
        
        # Make the window frameless but keep it on top
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        
        # Premium Dark Palette
        self.bg_color   = "#13141a"   # deep dark base
        self.card_color = "#1c1d26"   # slightly lighter cards
        self.title_bg   = "#0d0e13"   # darkest – title bar
        self.accent     = "#7c3aed"   # violet primary
        self.accent2    = "#6d28d9"   # violet hover
        self.green      = "#10b981"   # emerald
        self.green2     = "#059669"
        self.red        = "#ef4444"
        self.red2       = "#dc2626"
        self.fg_color   = "#f0f0f5"
        self.muted      = "#6b7280"
        self.root.configure(bg=self.bg_color, highlightthickness=1, highlightbackground="#7c3aed")
        
        self.region = None
        self.process = None
        self.start_time = None
        self.elapsed_before_pause = 0
        self.is_paused = False
        self.segments = []
        self.temp_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "TinyRec")
        os.makedirs(self.temp_dir, exist_ok=True)
        
        self.border_win = None
        
        # Setup Global Hotkeys (F9 = Pause/Resume, F10 = Stop)
        self.hotkey_thread = threading.Thread(target=self._setup_hotkeys, daemon=True)
        self.hotkey_thread.start()
        
        # Load custom icon if available
        icon_path = self.resource_path(os.path.join("icon", "icon.png"))
        if os.path.exists(icon_path):
            try:
                img = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, img)
            except Exception:
                pass
        
        self.setup_ui()
        
        # Hide main window initially and show splash screen
        self.root.withdraw()
        SplashScreen(self.root, self.on_splash_complete)

    def on_splash_complete(self):
        self.root.deiconify()
        # Check and install drivers on a background thread so UI doesn't freeze
        threading.Thread(target=self.check_audio_driver, daemon=True).start()

    def setup_ui(self):
        APP_W = 280

        # ── Title Bar ──────────────────────────────────────────────
        self.title_bar = tk.Frame(self.root, bg=self.title_bg, relief="flat", bd=0)
        self.title_bar.pack(fill=tk.X)

        # Red dot indicator (idle state)
        self.dot_canvas = tk.Canvas(self.title_bar, width=10, height=10,
                                    bg=self.title_bg, highlightthickness=0)
        self.dot_canvas.pack(side=tk.LEFT, padx=(10, 4), pady=8)
        self.dot = self.dot_canvas.create_oval(1, 1, 9, 9, fill="#374151", outline="")

        self.title_label = tk.Label(self.title_bar, text="TinyRec",
                                    bg=self.title_bg, fg=self.fg_color,
                                    font=("Segoe UI", 9, "bold"))
        self.title_label.pack(side=tk.LEFT)

        self.close_btn = tk.Button(self.title_bar, text="✕",
                                   bg=self.title_bg, fg="#4b5563", bd=0,
                                   activebackground="#ef4444", activeforeground="white",
                                   relief="flat", font=("Segoe UI", 10),
                                   command=self.close_app, cursor="hand2")
        self.close_btn.pack(side=tk.RIGHT, padx=(0, 6))
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.config(fg="white"))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.config(fg="#4b5563"))

        self.min_btn = tk.Button(self.title_bar, text="—",
                                 bg=self.title_bg, fg="#4b5563", bd=0,
                                 activebackground="#374151", activeforeground="white",
                                 relief="flat", font=("Segoe UI", 10),
                                 command=self.minimize_app, cursor="hand2")
        self.min_btn.pack(side=tk.RIGHT, padx=(0, 2))
        self.min_btn.bind("<Enter>", lambda e: self.min_btn.config(fg="white"))
        self.min_btn.bind("<Leave>", lambda e: self.min_btn.config(fg="#4b5563"))

        for w in (self.title_bar, self.title_label, self.dot_canvas):
            w.bind("<ButtonPress-1>", self.start_move)
            w.bind("<B1-Motion>", self.do_move)

        # ── Thin accent line under title bar ───────────────────────
        tk.Frame(self.root, bg=self.accent, height=1).pack(fill=tk.X)

        # ── Body ───────────────────────────────────────────────────
        self.body = tk.Frame(self.root, bg=self.bg_color)
        self.body.pack(expand=True, fill=tk.BOTH, padx=12, pady=8)

        # Select Area button (full-width, prominent)
        self.btn_select = self.create_button(
            self.body, "⬡  Select Recording Area",
            self.select_area, self.accent, self.accent2)
        self.btn_select.pack(fill=tk.X, pady=(4, 10))

        # ── Divider ────────────────────────────────────────────────
        tk.Frame(self.body, bg="#1f2030", height=1).pack(fill=tk.X, pady=(0, 8))

        # ── Options card ───────────────────────────────────────────
        card = tk.Frame(self.body, bg=self.card_color,
                        highlightthickness=1, highlightbackground="#252636")
        card.pack(fill=tk.X, pady=(0, 15))

        # Helper for card rows
        def create_card_row(parent, label_text):
            row = tk.Frame(parent, bg=self.card_color)
            row.pack(fill=tk.X, padx=12, pady=10)
            tk.Label(row, text=label_text, bg=self.card_color, fg=self.fg_color,
                     font=("Segoe UI", 9)).pack(side=tk.LEFT)
            container = tk.Frame(row, bg=self.card_color)
            container.pack(side=tk.RIGHT)
            return container

        # Row: Capture Cursor
        self.show_cursor_var = tk.IntVar(value=1)
        cf = create_card_row(card, "Capture Cursor")
        self.lbl_cur_on = tk.Label(cf, text=" ON ", bg=self.green, fg="white",
                                   font=("Segoe UI", 8, "bold"), cursor="hand2", padx=5)
        self.lbl_cur_on.pack(side=tk.LEFT, padx=(0, 2))
        self.lbl_cur_off = tk.Label(cf, text=" OFF ", bg="#252636", fg=self.muted,
                                    font=("Segoe UI", 8, "bold"), cursor="hand2", padx=5)
        self.lbl_cur_off.pack(side=tk.LEFT)
        self.lbl_cur_on.bind("<Button-1>",  lambda e: self.set_cursor(1))
        self.lbl_cur_off.bind("<Button-1>", lambda e: self.set_cursor(0))

        tk.Frame(card, bg="#252636", height=1).pack(fill=tk.X, padx=10)

        # Row: Capture Audio
        self.audio_var = tk.IntVar(value=1)
        af = create_card_row(card, "System Audio")
        self.lbl_aud_on = tk.Label(af, text=" ON ", bg=self.green, fg="white",
                                   font=("Segoe UI", 8, "bold"), cursor="hand2", padx=5)
        self.lbl_aud_on.pack(side=tk.LEFT, padx=(0, 2))
        self.lbl_aud_off = tk.Label(af, text=" OFF ", bg="#252636", fg=self.muted,
                                    font=("Segoe UI", 8, "bold"), cursor="hand2", padx=5)
        self.lbl_aud_off.pack(side=tk.LEFT)
        self.lbl_aud_on.bind("<Button-1>",  lambda e: self.set_audio(1))
        self.lbl_aud_off.bind("<Button-1>", lambda e: self.set_audio(0))

        tk.Frame(card, bg="#252636", height=1).pack(fill=tk.X, padx=10)

        # Row: Frame Rate (FPS)
        self.fps_var = tk.IntVar(value=30)
        ff = create_card_row(card, "Frame Rate")
        self.lbl_fps30 = tk.Label(ff, text=" 30 FPS ", bg=self.accent, fg="white",
                                   font=("Segoe UI", 8, "bold"), cursor="hand2", padx=5)
        self.lbl_fps30.pack(side=tk.LEFT, padx=(0, 2))
        self.lbl_fps60 = tk.Label(ff, text=" 60 FPS ", bg="#252636", fg=self.muted,
                                    font=("Segoe UI", 8, "bold"), cursor="hand2", padx=5)
        self.lbl_fps60.pack(side=tk.LEFT)
        self.lbl_fps30.bind("<Button-1>",  lambda e: self.set_fps(30))
        self.lbl_fps60.bind("<Button-1>", lambda e: self.set_fps(60))

        tk.Frame(card, bg="#252636", height=1).pack(fill=tk.X, padx=10)

        # Row: Recording Quality
        self.quality_var = tk.StringVar(value="High")
        qf = create_card_row(card, "Quality")
        self.lbl_hq = tk.Label(qf, text=" High ", bg=self.accent, fg="white",
                               font=("Segoe UI", 8, "bold"), cursor="hand2", padx=5)
        self.lbl_hq.pack(side=tk.LEFT, padx=(0, 2))
        self.lbl_lq = tk.Label(qf, text=" Low ", bg="#252636", fg=self.muted,
                               font=("Segoe UI", 8, "bold"), cursor="hand2", padx=5)
        self.lbl_lq.pack(side=tk.LEFT)
        self.lbl_hq.bind("<Button-1>", lambda e: self.set_quality("High"))
        self.lbl_lq.bind("<Button-1>", lambda e: self.set_quality("Low"))

        # ── Start / Stop buttons ────────────────────────────────────
        bf = tk.Frame(self.body, bg=self.bg_color)
        bf.pack(fill=tk.X, pady=(0, 4))
        self.btn_start = self.create_button(
            bf, "▶  Start", self.start_recording, self.green, self.green2)
        self.btn_start.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        self.btn_stop = self.create_button(
            bf, "■  Stop", self.stop_recording, self.red, self.red2)
        self.btn_stop.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0))
        self.btn_stop.config(state=tk.DISABLED, bg="#374151")

        # ── Shortcuts hint ─────────────────────────────────────────
        hint_frame = tk.Frame(self.body, bg=self.bg_color)
        hint_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 5))
        
        tk.Label(hint_frame, text="F9: Pause/Resume   •   F10: Start/Stop",
                 bg=self.bg_color, fg="#949ba4", font=("Segoe UI", 7, "bold")).pack()

        # ── Status bar ─────────────────────────────────────────────
        self.lbl_status = tk.Label(
            self.body, text="Ready  ·  Full Screen",
            bg=self.bg_color, fg=self.muted, font=("Segoe UI", 8, "italic"))
        self.lbl_status.pack(side=tk.BOTTOM, pady=(0, 2))

    def create_button(self, parent, text, command, bg, hover_bg):
        btn = tk.Button(parent, text=text, command=command, bg=bg, fg="white",
                        activebackground=hover_bg, activeforeground="white",
                        relief="flat", bd=0, font=("Segoe UI", 9, "bold"),
                        pady=6, cursor="hand2")
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg) if btn['state'] != 'disabled' else None)
        btn.bind("<Leave>", lambda e: btn.config(bg=bg)      if btn['state'] != 'disabled' else None)
        return btn

    def set_cursor(self, value):
        self.show_cursor_var.set(value)
        if value == 1:
            self.lbl_cur_on.config(bg=self.green,  fg="white")
            self.lbl_cur_off.config(bg="#252636", fg=self.muted)
        else:
            self.lbl_cur_on.config(bg="#252636", fg=self.muted)
            self.lbl_cur_off.config(bg=self.red,  fg="white")

    def set_audio(self, value):
        self.audio_var.set(value)
        if value == 1:
            self.lbl_aud_on.config(bg=self.green,  fg="white")
            self.lbl_aud_off.config(bg="#252636", fg=self.muted)
        else:
            self.lbl_aud_on.config(bg="#252636", fg=self.muted)
            self.lbl_aud_off.config(bg=self.red,  fg="white")

    def set_fps(self, value):
        self.fps_var.set(value)
        if value == 30:
            self.lbl_fps30.config(bg=self.accent,  fg="white")
            self.lbl_fps60.config(bg="#252636", fg=self.muted)
        else:
            self.lbl_fps30.config(bg="#252636", fg=self.muted)
            self.lbl_fps60.config(bg=self.accent,  fg="white")

    def toggle_cursor(self, event=None):
        self.set_cursor(0 if self.show_cursor_var.get() == 1 else 1)

    def set_quality(self, mode):
        self.quality_var.set(mode)
        if mode == "High":
            self.lbl_hq.config(bg=self.accent,  fg="white")
            self.lbl_lq.config(bg="#252636", fg=self.muted)
        else:
            self.lbl_hq.config(bg="#252636", fg=self.muted)
            self.lbl_lq.config(bg=self.accent,  fg="white")

    def start_move(self, event):
        self._offset_x = event.x_root - self.root.winfo_x()
        self._offset_y = event.y_root - self.root.winfo_y()

    def do_move(self, event):
        x = event.x_root - self._offset_x
        y = event.y_root - self._offset_y
        self.root.geometry(f"+{x}+{y}")

    def minimize_app(self):
        # Capture current window position before hiding
        win_x = self.root.winfo_x()
        win_y = self.root.winfo_y()
        self.root.withdraw()
        self.show_floating_restore_icon(win_x, win_y)

    def show_floating_restore_icon(self, win_x, win_y):
        self.restore_win = tk.Toplevel(self.root)
        self.restore_win.overrideredirect(True)
        self.restore_win.attributes("-topmost", True)
        self.restore_win.configure(bg="#1e1f22", highlightthickness=2, highlightbackground="#5865f2")
        
        # Place icon centered over where the main window was
        icon_size = 48
        ix = win_x + (self.app_w - icon_size) // 2
        iy = win_y + (self.app_h - icon_size) // 2
        self.restore_win.geometry(f"{icon_size}x{icon_size}+{ix}+{iy}")
        
        icon_path = self.resource_path(os.path.join("icon", "icon.png"))
        if os.path.exists(icon_path):
            try:
                img = tk.PhotoImage(file=icon_path).subsample(2, 2)
                lbl = tk.Label(self.restore_win, image=img, bg="#1e1f22", cursor="hand2")
                lbl.image = img
            except:
                lbl = tk.Label(self.restore_win, text="❐", bg="#1e1f22", fg="#5865f2",
                               font=("Segoe UI", 18, "bold"), cursor="hand2")
        else:
            lbl = tk.Label(self.restore_win, text="❐", bg="#1e1f22", fg="#5865f2",
                           font=("Segoe UI", 18, "bold"), cursor="hand2")
            
        lbl.pack(expand=True, fill=tk.BOTH)
        
        lbl.bind("<ButtonPress-1>", self.start_move_restore)
        lbl.bind("<B1-Motion>", self.do_move_restore)
        lbl.bind("<ButtonRelease-1>", self.restore_app)
        
    def start_move_restore(self, event):
        self._restore_offset_x = event.x_root - self.restore_win.winfo_x()
        self._restore_offset_y = event.y_root - self.restore_win.winfo_y()
        self._dragged = False

    def do_move_restore(self, event):
        x = event.x_root - self._restore_offset_x
        y = event.y_root - self._restore_offset_y
        self.restore_win.geometry(f"+{x}+{y}")
        self._dragged = True

    def restore_app(self, event=None):
        if getattr(self, '_dragged', False):
            self._dragged = False
            return
        if hasattr(self, 'restore_win') and self.restore_win:
            # Restore the main window centered on wherever the icon currently is
            ix = self.restore_win.winfo_x()
            iy = self.restore_win.winfo_y()
            rx = ix - (self.app_w - 48) // 2
            ry = iy - (self.app_h - 48) // 2
            self.restore_win.destroy()
            self.restore_win = None
        else:
            ry = self.root.winfo_y()
        self.root.geometry(f"{self.app_w}x{self.app_h}+{rx}+{ry}")
        self.root.deiconify()

    def _setup_hotkeys(self):
        user32 = ctypes.windll.user32
        # F9 = 0x78, F10 = 0x79
        # MOD_NONE = 0
        if not user32.RegisterHotKey(None, 1, 0, 0x78): # F9
            print("Failed to register F9")
        if not user32.RegisterHotKey(None, 2, 0, 0x79): # F10
            print("Failed to register F10")
            
        try:
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == 0x0312: # WM_HOTKEY
                    if msg.wParam == 1: # F9
                        self.root.after(0, self.toggle_pause)
                    elif msg.wParam == 2: # F10
                        if self.process or self.is_paused:
                            self.root.after(0, self.stop_recording)
                        else:
                            self.root.after(0, self.start_recording)
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            user32.UnregisterHotKey(None, 1)
            user32.UnregisterHotKey(None, 2)

    def close_app(self):
        self.stop_recording()
        # Unregister hotkeys
        try:
            ctypes.windll.user32.UnregisterHotKey(None, 1)
            ctypes.windll.user32.UnregisterHotKey(None, 2)
        except:
            pass
        self.root.destroy()

    def select_area(self):
        self.clear_border()
        RegionSelector(self.root, self.set_region)

    def set_region(self, x, y, w, h):
        self.region = (x, y, w, h)
        self.lbl_status.config(text=f"Target: {w}×{h}  ·  Esc to cancel", fg="#a78bfa")
        self.show_border(x, y, w, h)
        # Allow Esc to cancel the committed selection
        self.root.bind("<Escape>", lambda e: self.cancel_region())

    def cancel_region(self):
        self.clear_border()
        self.region = None
        self.root.unbind("<Escape>")
        self.lbl_status.config(text="Ready  ·  Full Screen", fg=self.muted)

    def show_border(self, x, y, w, h):
        self.clear_border()
        self.border_win = tk.Toplevel(self.root)
        self.border_win.overrideredirect(True)
        self.border_win.attributes('-topmost', True)
        self.border_win.attributes('-transparentcolor', 'black')
        self.border_win.config(bg='black')
        self.border_win.geometry(f"{w}x{h}+{x}+{y}")
        self.border_win.after(100, lambda: self.exclude_from_capture(self.border_win))
        
        canvas = tk.Canvas(self.border_win, bg='black', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.create_rectangle(0, 0, w, h, outline='#da373c', width=4)

    def clear_border(self):
        if self.border_win:
            self.border_win.destroy()
            self.border_win = None

    def resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and PyInstaller onefile."""
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

    def check_audio_driver(self):
        ffmpeg_path = self.resource_path(os.path.join("dependency", "ffmpeg.exe"))
        if not os.path.exists(ffmpeg_path):
            return

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        try:
            # Check if virtual-audio-capturer is listed in DirectShow devices
            result = subprocess.run([ffmpeg_path, "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                                    stderr=subprocess.PIPE, stdout=subprocess.PIPE, startupinfo=startupinfo, text=True)
            if "virtual-audio-capturer" not in result.stderr:
                # Need to use after() to show messagebox from main thread
                self.root.after(100, self.install_audio_driver)
        except Exception:
            pass

    def install_audio_driver(self):
        installer_path = self.resource_path(os.path.join("dependency", "Setup.Screen.Capturer.Recorder.v0.13.3.exe"))
        if not os.path.exists(installer_path):
            messagebox.showwarning("Missing Driver", "Audio driver is missing and installer was not found.\nSystem audio recording won't work.")
            return
            
        msg = "First-time setup:\n\nTinyRec needs to install a small virtual audio driver to capture system sounds.\n\nPlease click 'Yes' on the administrator prompt."
        messagebox.showinfo("First-Time Setup", msg)
        
        # Run installer with UAC prompt in silent mode
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", installer_path, "/S", None, 1)
        if int(ret) > 32:
            self.lbl_status.config(text="Installing audio drivers...", fg="#5865f2")
            self.root.after(15000, lambda: self.lbl_status.config(text="Ready (Full Screen)", fg="#949ba4"))
        else:
            messagebox.showerror("Setup Failed", "Failed to start driver installation. You may need to run the installer manually.")

    def exclude_from_capture(self, window):
        try:
            hwnd = window.winfo_id()
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x11)
            parent = ctypes.windll.user32.GetParent(hwnd)
            if parent:
                ctypes.windll.user32.SetWindowDisplayAffinity(parent, 0x11)
        except Exception:
            pass

    def show_floating_widget(self):
        W, H = 240, 60
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        self.floating_widget = tk.Toplevel(self.root)
        self.floating_widget.overrideredirect(True)
        self.floating_widget.attributes("-topmost", True)
        self.floating_widget.configure(bg="#0d0e13",
                                       highlightthickness=1,
                                       highlightbackground="#7c3aed")
        self.floating_widget.geometry(f"{W}x{H}+{sw - W - 24}+{sh - H - 60}")

        self.floating_widget.update()
        self.exclude_from_capture(self.floating_widget)

        # ── Canvas for the whole HUD ────────────────────────────────
        self.fw_canvas = tk.Canvas(self.floating_widget, width=W, height=H,
                                   bg="#0d0e13", highlightthickness=0)
        self.fw_canvas.pack(fill=tk.BOTH, expand=True)

        # Pulse dot (will animate)
        self.fw_dot = self.fw_canvas.create_oval(14, H//2-5, 24, H//2+5,
                                                  fill=self.red, outline="")
        self.fw_dot_visible = True

        # REC label
        self.fw_canvas.create_text(32, H//2, text="REC", anchor="w",
                                   fill="#6b7280", font=("Segoe UI", 7, "bold"))

        # Timer text
        self.fw_timer_id = self.fw_canvas.create_text(W//2 - 15, H//2,
                                                       text="00:00", anchor="center",
                                                       fill="white",
                                                       font=("Segoe UI", 16, "bold"))

        # Buttons area
        btn_y = H // 2
        
        # Pause/Resume Button
        self.fw_pause_bg = self.fw_canvas.create_rectangle(
            W - 84, 10, W - 46, H - 10,
            fill="#374151", outline="", tags="pause_btn")
        self.fw_pause_text = self.fw_canvas.create_text(
            W - 65, btn_y,
            text="⏸", fill="white",
            font=("Segoe UI", 12), tags="pause_btn")

        # Stop button area
        self.fw_stop_bg = self.fw_canvas.create_rectangle(
            W - 42, 10, W - 6, H - 10,
            fill=self.red, outline="", tags="stop_btn")
        self.fw_canvas.create_text(
            W - 24, btn_y,
            text="■", fill="white",
            font=("Segoe UI", 12, "bold"), tags="stop_btn")

        # Bindings
        self.fw_canvas.tag_bind("pause_btn", "<Enter>", lambda e: (self.fw_canvas.itemconfig(self.fw_pause_bg, fill="#4b5563"), self.fw_canvas.config(cursor="hand2")))
        self.fw_canvas.tag_bind("pause_btn", "<Leave>", lambda e: (self.fw_canvas.itemconfig(self.fw_pause_bg, fill="#374151"), self.fw_canvas.config(cursor="")))
        self.fw_canvas.tag_bind("pause_btn", "<ButtonRelease-1>", lambda e: self.toggle_pause())

        self.fw_canvas.tag_bind("stop_btn", "<Enter>", lambda e: (self.fw_canvas.itemconfig(self.fw_stop_bg, fill=self.red2), self.fw_canvas.config(cursor="hand2")))
        self.fw_canvas.tag_bind("stop_btn", "<Leave>", lambda e: (self.fw_canvas.itemconfig(self.fw_stop_bg, fill=self.red), self.fw_canvas.config(cursor="")))
        self.fw_canvas.tag_bind("stop_btn", "<ButtonRelease-1>", lambda e: self.stop_recording())

        # Make HUD draggable
        self.fw_canvas.bind("<ButtonPress-1>",  self._fw_start_move)
        self.fw_canvas.bind("<B1-Motion>",       self._fw_do_move)

        # Start pulse animation
        self._pulse_dot()

    def _fw_start_move(self, event):
        if self.fw_canvas.find_withtag("stop_btn") and \
           self.fw_canvas.find_closest(event.x, event.y)[0] in self.fw_canvas.find_withtag("stop_btn"):
            return
        self._fw_ox = event.x_root - self.floating_widget.winfo_x()
        self._fw_oy = event.y_root - self.floating_widget.winfo_y()

    def _fw_do_move(self, event):
        if hasattr(self, '_fw_ox'):
            self.floating_widget.geometry(
                f"+{event.x_root - self._fw_ox}+{event.y_root - self._fw_oy}")

    def _pulse_dot(self):
        if not (hasattr(self, 'floating_widget') and self.floating_widget.winfo_exists()):
            return
        self.fw_dot_visible = not self.fw_dot_visible
        color = self.red if self.fw_dot_visible else "#0d0e13"
        self.fw_canvas.itemconfig(self.fw_dot, fill=color)
        self.floating_widget.after(600, self._pulse_dot)

    def update_timer(self):
        if self.process is not None and self.start_time is not None:
            elapsed = datetime.now() - self.start_time
            total_secs = int(elapsed.total_seconds() + self.elapsed_before_pause)
            mins = total_secs // 60
            secs = total_secs % 60
            time_str = f"{mins:02d}:{secs:02d}"

            self.lbl_status.config(text=f"● REC  {time_str}", fg=self.red)
            if hasattr(self, 'fw_timer_id') and \
               hasattr(self, 'floating_widget') and self.floating_widget.winfo_exists():
                self.fw_canvas.itemconfig(self.fw_timer_id, text=time_str)

            self.root.after(1000, self.update_timer)
        elif self.is_paused:
            total_secs = int(self.elapsed_before_pause)
            mins = total_secs // 60
            secs = total_secs % 60
            time_str = f"{mins:02d}:{secs:02d}"
            self.lbl_status.config(text=f"⏸ PAUSED {time_str}", fg=self.muted)
            if hasattr(self, 'fw_timer_id') and \
               hasattr(self, 'floating_widget') and self.floating_widget.winfo_exists():
                self.fw_canvas.itemconfig(self.fw_timer_id, text=time_str)



    def start_recording(self):
        if self.process is not None:
            return
            
        if not self.is_paused:
            # Start fresh: show countdown first
            self.root.withdraw()
            CountdownOverlay(self.root, self.actual_start_recording)
        else:
            # Resume: go straight to start
            self.actual_start_recording()

    def actual_start_recording(self):
        if self.process is not None: return

        # Unique name for each segment
        seg_id = len(self.segments)
        temp_file = os.path.join(self.temp_dir, f"seg_{seg_id}.ts")
        self.segments.append(temp_file)

        ffmpeg_path = self.resource_path(os.path.join("dependency", "ffmpeg.exe"))
        if not os.path.exists(ffmpeg_path):
            ffmpeg_path = "ffmpeg"
        
        # Optimized flags for instant startup
        cmd = [
            ffmpeg_path,
            "-y",
            "-loglevel", "error",
            "-probesize", "32",
            "-analyzeduration", "0",
            "-fflags", "nobuffer",
            "-f", "gdigrab",
            "-draw_mouse", str(self.show_cursor_var.get()),
            "-framerate", str(self.fps_var.get()),
            "-i", "desktop"
        ]
        
        if self.region:
            x, y, w, h = self.region
            # Note: -offset_x/y must come before -i desktop for gdigrab
            # but we already have -i desktop in the list. Let's fix the order.
            cmd = [
                ffmpeg_path, "-y", "-loglevel", "error",
                "-probesize", "32", "-analyzeduration", "0", "-fflags", "nobuffer",
                "-f", "gdigrab", "-draw_mouse", str(self.show_cursor_var.get()),
                "-framerate", str(self.fps_var.get()),
                "-offset_x", str(x), "-offset_y", str(y),
                "-video_size", f"{w}x{h}",
                "-i", "desktop"
            ]

        if self.audio_var.get() == 1:
            cmd.extend([
                "-f", "dshow",
                "-probesize", "32",
                "-analyzeduration", "0",
                "-i", "audio=virtual-audio-capturer"
            ])

        # Use fast settings for segments
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-crf", "22" if self.quality_var.get() == "High" else "30",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-f", "mpegts",
            temp_file
        ])
        
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            self.btn_start.config(state=tk.DISABLED, bg="#374151")
            self.btn_select.config(state=tk.DISABLED, bg="#374151")
            self.btn_stop.config(state=tk.NORMAL, bg=self.red)
            self.dot_canvas.itemconfig(self.dot, fill=self.red)
            
            if not self.is_paused:
                self.root.withdraw()
                self.show_floating_widget()
            else:
                # Update HUD button to Pause icon
                self.fw_canvas.itemconfig(self.fw_pause_text, text="⏸")
            
            self.root.update()
            
            self.process = subprocess.Popen(
                cmd, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                startupinfo=startupinfo
            )
            
            self.start_time = datetime.now()
            self.is_paused = False
            self.update_timer()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start recording:\n{e}")

    def toggle_pause(self):
        if self.is_paused:
            self.actual_start_recording()
        else:
            if self.process:
                # Update UI instantly
                self.is_paused = True
                self.fw_canvas.itemconfig(self.fw_pause_text, text="▶")
                self.dot_canvas.itemconfig(self.dot, fill=self.muted)
                
                # Capture elapsed time
                elapsed = datetime.now() - self.start_time
                self.elapsed_before_pause += elapsed.total_seconds()
                
                # Stop FFmpeg in background so it feels instant
                proc_to_stop = self.process
                self.process = None
                threading.Thread(target=self._stop_proc_bg, args=(proc_to_stop,), daemon=True).start()

    def _stop_proc_bg(self, proc):
        try:
            proc.communicate(input=b'q', timeout=2)
        except:
            try: proc.kill()
            except: pass

    def stop_recording(self):
        # Update UI instantly
        self.btn_stop.config(state=tk.DISABLED, bg="#374151")
        self.dot_canvas.itemconfig(self.dot, fill="#374151")
        
        if self.process or self.is_paused:
            if self.process:
                # Stop last process synchronously for finalization
                try:
                    self.process.communicate(input=b'q', timeout=3)
                except:
                    self.process.kill()
                self.process = None
            
            self.start_time = None
            self.clear_border()
            self.region = None
            
            # Show "Processing..." status
            self.lbl_status.config(text="⌛ Finalizing...", fg=self.accent)
            self.root.update()
            
            # Combine segments
            self.finalize_recording()
            
            if hasattr(self, 'floating_widget') and self.floating_widget:
                self.floating_widget.destroy()
                self.floating_widget = None
                
            self.root.deiconify()
            self.btn_start.config(state=tk.NORMAL, bg=self.green)
            self.btn_select.config(state=tk.NORMAL, bg=self.accent)
            
            self.is_paused = False
            self.elapsed_before_pause = 0

    def finalize_recording(self):
        if not self.segments: return

        # Final output path
        timestamp = datetime.now().strftime("%d-%b-%Y_%I-%M-%S_%p")
        save_dir = os.path.join(os.path.expanduser("~"), "Desktop", "Tiny Recorder")
        os.makedirs(save_dir, exist_ok=True)
        final_output = os.path.join(save_dir, f"Tiny_Recorder_{timestamp}.mp4")
        self.last_saved_file = final_output

        if len(self.segments) == 1:
            # Just move the single segment
            os.rename(self.segments[0], final_output)
            self.segments = []
        else:
            # Concatenate multiple segments
            concat_list = os.path.join(self.temp_dir, "list.txt")
            with open(concat_list, "w") as f:
                for seg in self.segments:
                    # Fix paths for FFmpeg concat file (forward slashes and escape)
                    path = seg.replace("\\", "/")
                    f.write(f"file '{path}'\n")
            
            ffmpeg_path = self.resource_path(os.path.join("dependency", "ffmpeg.exe"))
            if not os.path.exists(ffmpeg_path): ffmpeg_path = "ffmpeg"
            
            cmd = [
                ffmpeg_path, "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-c", "copy",
                final_output
            ]
            
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            subprocess.run(cmd, startupinfo=startupinfo)
            
            # Cleanup segments
            for seg in self.segments:
                try: os.remove(seg)
                except: pass
            try: os.remove(concat_list)
            except: pass
            self.segments = []

        self.lbl_status.config(text="✔  Saved successfully!", fg=self.green)
        self.root.after(400, lambda: self.show_toast(final_output))
        self.root.after(3000, lambda: self.lbl_status.config(text="Ready  ·  Full Screen", fg=self.muted))

    def show_toast(self, filepath):
        folder = os.path.dirname(filepath)
        fname  = os.path.basename(filepath)

        TW, TH = 320, 72
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        tx = sw - TW - 20
        ty_end   = sh - TH - 50
        ty_start = sh + 10          # starts below screen

        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg="#1c1d26", highlightthickness=1, highlightbackground="#10b981")
        toast.geometry(f"{TW}x{TH}+{tx}+{ty_start}")

        # ── Layout ────────────────────────────────────────────────
        top_row = tk.Frame(toast, bg="#1c1d26")
        top_row.pack(fill=tk.X, padx=12, pady=(10, 2))

        tk.Label(top_row, text="✔  Recording saved", bg="#1c1d26",
                 fg="#10b981", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)

        tk.Button(top_row, text="✕", bg="#1c1d26", fg="#4b5563", bd=0,
                  activebackground="#1c1d26", activeforeground="white",
                  relief="flat", font=("Segoe UI", 9), cursor="hand2",
                  command=toast.destroy).pack(side=tk.RIGHT)

        bot_row = tk.Frame(toast, bg="#1c1d26")
        bot_row.pack(fill=tk.X, padx=12, pady=(0, 8))

        # Truncate filename if too long
        short = fname if len(fname) <= 32 else fname[:29] + "…"
        tk.Label(bot_row, text=short, bg="#1c1d26",
                 fg="#6b7280", font=("Segoe UI", 8)).pack(side=tk.LEFT)

        tk.Button(bot_row, text="Open Folder →", bg="#1c1d26", fg="#a78bfa",
                  bd=0, activebackground="#1c1d26", activeforeground="#c4b5fd",
                  relief="flat", font=("Segoe UI", 8, "bold"), cursor="hand2",
                  command=lambda: os.startfile(folder)).pack(side=tk.RIGHT)

        # ── Slide-up animation ────────────────────────────────────
        def slide_up(y):
            if y <= ty_end:
                toast.geometry(f"{TW}x{TH}+{tx}+{ty_end}")
                # Auto-dismiss after 5 seconds
                toast.after(5000, lambda: slide_down(ty_end))
                return
            toast.geometry(f"{TW}x{TH}+{tx}+{y}")
            toast.after(12, lambda: slide_up(y - 6))

        def slide_down(y):
            if not toast.winfo_exists(): return
            if y >= sh + 10:
                toast.destroy()
                return
            toast.geometry(f"{TW}x{TH}+{tx}+{y}")
            toast.after(12, lambda: slide_down(y + 6))

        slide_up(ty_start)

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenRecorderApp(root)
    root.mainloop()
