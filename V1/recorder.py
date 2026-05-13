import tkinter as tk
from tkinter import messagebox
import subprocess
import threading
import os
from datetime import datetime
import sys
import ctypes

# Enable DPI awareness so mouse coordinates match the screen properly on Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

class RegionSelector:
    def __init__(self, master, callback):
        self.top = tk.Toplevel(master)
        self.top.attributes('-fullscreen', True)
        self.top.attributes('-alpha', 0.3)
        self.top.configure(cursor="cross")
        
        self.canvas = tk.Canvas(self.top, bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.rect = None
        self.start_x = None
        self.start_y = None
        self.callback = callback
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Escape>", lambda e: self.top.destroy())

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y, 
            outline='red', width=2, fill='gray'
        )

    def on_drag(self, event):
        cur_x, cur_y = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_release(self, event):
        if not self.rect:
            self.top.destroy()
            return
            
        x1, y1, x2, y2 = self.canvas.coords(self.rect)
        x, y = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1), abs(y2 - y1)
        
        # FFmpeg requires width and height to be even numbers
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
        self.root.geometry("260x255")
        
        # Make the window frameless but keep it on top
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        
        # Dark Theme Colors
        self.bg_color = "#2b2d31"
        self.title_bg = "#1e1f22"
        self.fg_color = "#f2f3f5"
        self.root.configure(bg=self.bg_color, highlightthickness=1, highlightbackground="#1e1f22")
        
        self.region = None
        self.process = None
        self.start_time = None
        self.border_win = None
        
        self.setup_ui()

    def setup_ui(self):
        # --- Custom Title Bar ---
        self.title_bar = tk.Frame(self.root, bg=self.title_bg, relief="flat", bd=0)
        self.title_bar.pack(fill=tk.X)
        
        self.title_label = tk.Label(self.title_bar, text="  TinyRec", bg=self.title_bg, fg=self.fg_color, font=("Segoe UI", 9, "bold"))
        self.title_label.pack(side=tk.LEFT, pady=4)
        
        self.close_btn = tk.Button(self.title_bar, text="✕", bg=self.title_bg, fg="#a3a6aa", bd=0, 
                                   activebackground="#da373c", activeforeground="white", relief="flat", 
                                   font=("Segoe UI", 10), command=self.close_app)
        self.close_btn.pack(side=tk.RIGHT, padx=5)
        
        # Bindings for dragging the window
        self.title_bar.bind("<ButtonPress-1>", self.start_move)
        self.title_label.bind("<ButtonPress-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)
        self.title_label.bind("<B1-Motion>", self.do_move)

        # --- Main Body ---
        self.body = tk.Frame(self.root, bg=self.bg_color)
        self.body.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)
        
        # Select Area Button
        self.btn_select = self.create_button(self.body, "Select Recording Area", self.select_area, "#5865f2", "#4752c4")
        self.btn_select.pack(fill=tk.X, pady=(10, 5))
        
        # Options Frame
        self.opts_frame = tk.Frame(self.body, bg=self.bg_color)
        self.opts_frame.pack(fill=tk.X, pady=5)
        
        # Custom Toggle for Cursor
        self.show_cursor_var = tk.IntVar(value=1)
        self.cursor_frame = tk.Frame(self.opts_frame, bg=self.bg_color)
        self.cursor_frame.pack(fill=tk.X, pady=(0, 5))
        tk.Label(self.cursor_frame, text="Capture Cursor", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        
        self.btn_cursor_toggle = tk.Label(self.cursor_frame, text="ON", bg="#23a559", fg="white", font=("Segoe UI", 8, "bold"), width=5, cursor="hand2")
        self.btn_cursor_toggle.pack(side=tk.RIGHT)
        self.btn_cursor_toggle.bind("<Button-1>", self.toggle_cursor)
        
        # Custom Segment Control for Quality
        self.quality_var = tk.StringVar(value="High")
        self.qual_frame = tk.Frame(self.opts_frame, bg=self.bg_color)
        self.qual_frame.pack(fill=tk.X, pady=(5, 0))
        tk.Label(self.qual_frame, text="Recording Quality", bg=self.bg_color, fg=self.fg_color, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        
        self.qual_btn_frame = tk.Frame(self.qual_frame, bg=self.bg_color)
        self.qual_btn_frame.pack(side=tk.RIGHT)
        
        self.lbl_hq = tk.Label(self.qual_btn_frame, text="HQ", bg="#5865f2", fg="white", font=("Segoe UI", 8, "bold"), width=5, cursor="hand2")
        self.lbl_hq.pack(side=tk.LEFT, padx=(0, 2))
        self.lbl_lq = tk.Label(self.qual_btn_frame, text="LQ", bg="#4f545c", fg="#b5bac1", font=("Segoe UI", 8, "bold"), width=5, cursor="hand2")
        self.lbl_lq.pack(side=tk.LEFT)
        
        self.lbl_hq.bind("<Button-1>", lambda e: self.set_quality("High"))
        self.lbl_lq.bind("<Button-1>", lambda e: self.set_quality("Low"))

        # Controls Frame
        self.frame_btns = tk.Frame(self.body, bg=self.bg_color)
        self.frame_btns.pack(fill=tk.X, pady=10)
        
        # Start/Stop Buttons
        self.btn_start = self.create_button(self.frame_btns, "▶ Start", self.start_recording, "#23a559", "#1e8f4c")
        self.btn_start.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        
        self.btn_stop = self.create_button(self.frame_btns, "■ Stop", self.stop_recording, "#da373c", "#b52c31")
        self.btn_stop.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))
        self.btn_stop.config(state=tk.DISABLED)
        
        # Status Label
        self.lbl_status = tk.Label(self.body, text="Ready (Full Screen)", bg=self.bg_color, fg="#949ba4", font=("Segoe UI", 9, "italic"))
        self.lbl_status.pack(side=tk.BOTTOM, pady=5)

    def create_button(self, parent, text, command, bg, hover_bg):
        btn = tk.Button(parent, text=text, command=command, bg=bg, fg="white", 
                        activebackground=hover_bg, activeforeground="white", 
                        relief="flat", bd=0, font=("Segoe UI", 9, "bold"), pady=4)
        
        def on_enter(e):
            if btn['state'] != 'disabled':
                btn.config(bg=hover_bg)
                
        def on_leave(e):
            if btn['state'] != 'disabled':
                btn.config(bg=bg)
                
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def toggle_cursor(self, event=None):
        if self.show_cursor_var.get() == 1:
            self.show_cursor_var.set(0)
            self.btn_cursor_toggle.config(text="OFF", bg="#da373c")
        else:
            self.show_cursor_var.set(1)
            self.btn_cursor_toggle.config(text="ON", bg="#23a559")

    def set_quality(self, mode):
        self.quality_var.set(mode)
        if mode == "High":
            self.lbl_hq.config(bg="#5865f2", fg="white")
            self.lbl_lq.config(bg="#4f545c", fg="#b5bac1")
        else:
            self.lbl_hq.config(bg="#4f545c", fg="#b5bac1")
            self.lbl_lq.config(bg="#5865f2", fg="white")

    def start_move(self, event):
        self._offset_x = event.x_root - self.root.winfo_x()
        self._offset_y = event.y_root - self.root.winfo_y()

    def do_move(self, event):
        x = event.x_root - self._offset_x
        y = event.y_root - self._offset_y
        self.root.geometry(f"+{x}+{y}")

    def close_app(self):
        self.stop_recording()
        self.root.destroy()

    def select_area(self):
        self.clear_border()
        RegionSelector(self.root, self.set_region)

    def set_region(self, x, y, w, h):
        self.region = (x, y, w, h)
        self.lbl_status.config(text=f"Target: {w}x{h}", fg="#949ba4")
        self.show_border(x, y, w, h)

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

    def get_ffmpeg_path(self):
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        ffmpeg_exe = os.path.join(base_path, "ffmpeg.exe")
        if os.path.exists(ffmpeg_exe):
            return ffmpeg_exe
        return "ffmpeg"

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
        self.floating_widget = tk.Toplevel(self.root)
        self.floating_widget.overrideredirect(True)
        self.floating_widget.attributes("-topmost", True)
        self.floating_widget.configure(bg="#1e1f22", highlightthickness=1, highlightbackground="#da373c")
        
        w = 120
        h = 36
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = sw - w - 20
        y = sh - h - 60
        self.floating_widget.geometry(f"{w}x{h}+{x}+{y}")
        
        # Ensure OS creates the window immediately so we can exclude it before FFmpeg starts
        self.floating_widget.update()
        self.exclude_from_capture(self.floating_widget)
        
        self.lbl_float_timer = tk.Label(self.floating_widget, text="00:00", bg="#1e1f22", fg="#da373c", font=("Segoe UI", 10, "bold"))
        self.lbl_float_timer.pack(side=tk.LEFT, padx=10)
        
        btn_float_stop = tk.Button(self.floating_widget, text="■ Stop", bg="#da373c", fg="white", 
                                   activebackground="#b52c31", activeforeground="white", 
                                   relief="flat", bd=0, font=("Segoe UI", 9, "bold"), command=self.stop_recording)
        btn_float_stop.pack(side=tk.RIGHT, fill=tk.Y)

    def update_timer(self):
        if self.process is not None and self.start_time is not None:
            elapsed = datetime.now() - self.start_time
            secs = int(elapsed.total_seconds())
            mins = secs // 60
            secs = secs % 60
            time_str = f"{mins:02d}:{secs:02d}"
            
            self.lbl_status.config(text=f"Recording: {time_str}", fg="#da373c")
            if hasattr(self, 'lbl_float_timer') and self.lbl_float_timer.winfo_exists():
                self.lbl_float_timer.config(text=time_str)
                
            self.root.after(1000, self.update_timer)

    def start_recording(self):
        if self.process is not None:
            return
            
        # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp = datetime.now().strftime("%d-%b-%Y_%I-%M-%S_%p")
        output_file = os.path.abspath(f"Tiny_Recorder_{timestamp}.mp4")
        
        ffmpeg_path = self.get_ffmpeg_path()
        
        cmd = [
            ffmpeg_path,
            "-y",
            "-f", "gdigrab",
            "-draw_mouse", str(self.show_cursor_var.get()),
            "-framerate", "30"
        ]
        
        if self.region:
            x, y, w, h = self.region
            cmd.extend([
                "-offset_x", str(x),
                "-offset_y", str(y),
                "-video_size", f"{w}x{h}"
            ])
            
        crf_val = "22" if self.quality_var.get() == "High" else "32"
        audio_br = "192k" if self.quality_var.get() == "High" else "64k"
        preset_val = "fast" if self.quality_var.get() == "High" else "veryfast"
        
        cmd.extend([
            "-i", "desktop",
            "-f", "dshow",
            "-i", "audio=virtual-audio-capturer",
            "-c:v", "libx264",
            "-preset", preset_val,
            "-crf", crf_val,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", audio_br,
            output_file
        ])
        
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            # Disable start, select buttons
            self.btn_start.config(state=tk.DISABLED, bg="#4f545c")
            self.btn_select.config(state=tk.DISABLED, bg="#4f545c")
            self.btn_stop.config(state=tk.NORMAL, bg="#da373c")
            
            # Hide main window and show the ghost floating widget BEFORE FFmpeg starts
            self.root.withdraw()
            self.show_floating_widget()
            
            # Force Tkinter to process all UI updates (hiding main window) immediately
            self.root.update()
            
            self.process = subprocess.Popen(
                cmd, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                startupinfo=startupinfo
            )
            
            self.start_time = datetime.now()
            self.update_timer()
            
        except FileNotFoundError:
            messagebox.showerror("Error", "FFmpeg not found! Please place ffmpeg.exe in the same folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start recording:\n{e}")

    def stop_recording(self):
        if self.process:
            try:
                self.process.communicate(input=b'q', timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            
            self.process = None
            self.start_time = None
            
            self.clear_border()
            self.region = None
            
            if hasattr(self, 'floating_widget') and self.floating_widget:
                self.floating_widget.destroy()
                self.floating_widget = None
                
            # Restore the main window
            self.root.deiconify()
            
            self.lbl_status.config(text="Saved successfully!", fg="#23a559")
            
            self.btn_start.config(state=tk.NORMAL, bg="#23a559")
            self.btn_select.config(state=tk.NORMAL, bg="#5865f2")
            self.btn_stop.config(state=tk.DISABLED, bg="#4f545c")
            
            self.root.after(3000, lambda: self.lbl_status.config(text="Ready (Full Screen)", fg="#949ba4") if self.process is None else None)

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenRecorderApp(root)
    root.mainloop()
