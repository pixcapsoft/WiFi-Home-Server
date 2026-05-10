import os
import threading
from turtle import width
import urllib.request
import json
import customtkinter as ctk
import tkinter.filedialog as fd
from tkinter import messagebox
import main
import tkinter as tk  # Add for tooltip support
import webbrowser

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ── Palette ────────────────────────────────────────────────────────────────
BG_DEEP      = "#101010"   # very dark grey — window bg
BG_PANEL     = "#181818"   # slightly lighter — panels
BG_CARD      = "#232323"   # card / list-row bg
BG_SIDEBAR   = "#161616"   # sidebar bg

ACCENT       = "#2979ff"   # electric blue accent
ACCENT_GLOW  = "#1565c0"   # hover / pressed
ACCENT_SOFT  = "#2979ff"   # subtle tint (selected nav item)

TEXT_PRIMARY = "#e8f0fe"   # near-white
TEXT_MUTED   = "#d9e2f1"   # muted blue-grey
TEXT_ACCENT  = "#ffffff"   # soft accent text

SUCCESS      = "#00e676"
DANGER       = "#ff1744"
WARN         = "#ffab40"

FONT_BODY    = ("Segoe UI", 12)
FONT_BOLD    = ("Segoe UI Semibold", 12)
FONT_TITLE   = ("Segoe UI Semibold", 22)
FONT_LABEL   = ("Segoe UI", 11)
FONT_MONO    = ("Consolas", 11)
FONT_BADGE   = ("Segoe UI Semibold", 10)


# ── Helpers ────────────────────────────────────────────────────────────────
def _btn(parent, text, cmd, fg=ACCENT, hover=ACCENT_GLOW, **kw):
    return ctk.CTkButton(
        parent, text=text, command=cmd,
        fg_color=fg, hover_color=hover,
        corner_radius=8, height=36,
        font=ctk.CTkFont(family="Segoe UI Semibold", size=12),
        text_color=TEXT_PRIMARY,
        **kw
    )

def _label(parent, text, size=12, weight="normal", color=TEXT_PRIMARY, **kw):
    return ctk.CTkLabel(
        parent, text=text,
        font=ctk.CTkFont(family="Segoe UI", size=size, weight=weight),
        text_color=color, **kw
    )

def _sep(parent):
    """Thin horizontal separator line."""
    return ctk.CTkFrame(parent, height=1, fg_color="#112244", corner_radius=0)


# ── Tooltip Helper ─────────────────────────────────────────────────────────
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x = x + self.widget.winfo_rootx() + 30
        y = y + self.widget.winfo_rooty() + 30
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify='left',
                        background="#222", foreground="#fff",
                        relief='solid', borderwidth=1,
                        font=("Segoe UI", 10))
        label.pack(ipadx=6, ipady=2)

    def hide_tip(self, event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


# ══════════════════════════════════════════════════════════════════════════════
class WiFiServerApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.configure(fg_color=BG_DEEP)
        self.title(f"WiFi Home Server - A lightweight file hosting via WiFi networks")
        self.geometry("1020x680")
        self.minsize(860, 560)

        self.server_instance   = None
        self.roots             = []
        self.active_connections = 0
        self.app_version       = "v0.5.7"
        self.title(f"WiFi Home Server {self.app_version} - A lightweight file hosting via WiFi networks")

        self.repo_var = ctk.StringVar(value="https://github.com/pixcapsoft/WiFi-Home-Server")
        self.port_var = ctk.StringVar(value="8765")

        main.LOG_CALLBACK        = self.handle_log
        main.CONNECTION_CALLBACK = self.handle_conn

        self._build_ui()
        self.select_frame("home")
        self.check_updates()

    # ── Layout skeleton ───────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_status_bar()

        # Content frames
        self.home_frame     = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.settings_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.credits_frame  = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")

        self._build_home()
        self._build_settings()
        self._build_credits()

    # ── Sidebar ───────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=210, corner_radius=0, fg_color=BG_SIDEBAR)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_rowconfigure(7, weight=1)   # spacer (moved to row 7)

        # Logo area
        logo_wrap = ctk.CTkFrame(sb, fg_color="transparent")
        logo_wrap.grid(row=0, column=0, padx=20, pady=(28, 4), sticky="ew")

        # Glowing dot
        dot = ctk.CTkFrame(logo_wrap, width=10, height=10,
                           corner_radius=5, fg_color=ACCENT)
        dot.pack(side="left", padx=(0, 10))

        _label(logo_wrap, "WiFi Home sServer",
               size=18, weight="bold", color=TEXT_PRIMARY).pack(side="left")

        _label(sb, self.app_version + " Build by PixCap Soft", size=10, color=TEXT_MUTED).grid(
            row=1, column=0, padx=20, pady=(0, 18), sticky="w")

        _sep(sb).grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))

        # Nav buttons
        self._nav_btns = {}
        nav_items = [
            ("home",     "🏠  Home", "Go to Home page"),
            ("settings", "⚙️  Settings", "Open Settings"),
            ("credits",  "✦  Credits", "Show Credits/About"),
            ("update",   "↑  Check for Updates", "Check for new updates on GitHub"),
        ]
        for i, (key, label, tip) in enumerate(nav_items, start=3):
            if key == "update":
                btn = ctk.CTkButton(
                    sb, text=label, anchor="w",
                    corner_radius=8, height=42, border_spacing=14,
                    fg_color="transparent",
                    text_color=TEXT_MUTED,
                    hover_color=ACCENT_SOFT,
                    font=ctk.CTkFont(family="Segoe UI", size=13),
                    command=self.check_updates
                )
            else:
                btn = ctk.CTkButton(
                    sb, text=label, anchor="w",
                    corner_radius=8, height=42, border_spacing=14,
                    fg_color="transparent",
                    text_color=TEXT_MUTED,
                    hover_color=ACCENT_SOFT,
                    font=ctk.CTkFont(family="Segoe UI", size=13),
                    command=lambda k=key: self.select_frame(k)
                )
            pady_val = 2 if i < 6 else (16, 22) if key == "update" else 0
            btn.grid(row=i, column=0, sticky="ew", padx=10, pady=pady_val)
            self._nav_btns[key] = btn
            ToolTip(btn, tip)

    # ── Status bar ────────────────────────────────────────────────────────
    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, height=34, corner_radius=0, fg_color=BG_SIDEBAR)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=0)
        bar.grid_propagate(False)

        self.lbl_ip = _label(bar, f"  📡  {main.get_local_ip()}", size=11, color="#1ed760")
        self.lbl_ip.grid(row=0, column=0, padx=16, pady=0, sticky="w")

        self.lbl_conn = _label(bar, "0 devices connected  ", size=11, color=TEXT_MUTED)
        self.lbl_conn.grid(row=0, column=1, padx=16, pady=0, sticky="e")

        self.refresh_ip_label()  # Start periodic IP refresh

    def refresh_ip_label(self):
        ip = main.get_local_ip()
        self.lbl_ip.configure(text=f"  📡  {ip}")
        self.after(10000, self.refresh_ip_label)

    # ── Nav selection ─────────────────────────────────────────────────────
    def select_frame(self, name):
        for key, btn in self._nav_btns.items():
            if key == name:
                btn.configure(fg_color=ACCENT_SOFT, text_color=TEXT_ACCENT)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_MUTED)

        for frame in (self.home_frame, self.settings_frame, self.credits_frame):
            frame.grid_forget()

        target = {"home": self.home_frame,
                  "settings": self.settings_frame,
                  "credits": self.credits_frame}[name]
        target.grid(row=0, column=1, sticky="nsew")

    # ── Home frame ────────────────────────────────────────────────────────
    def _build_home(self):
        f = self.home_frame
        f.configure(fg_color=BG_DEEP)
        f.grid_rowconfigure(0, weight=3)
        f.grid_rowconfigure(1, weight=2)
        f.grid_columnconfigure(0, weight=1)
        f.grid_columnconfigure(1, weight=0)

        # ── File list panel ───────────────────────────────────────────────
        list_panel = ctk.CTkFrame(f, fg_color=BG_PANEL, corner_radius=12)
        list_panel.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")
        list_panel.grid_rowconfigure(1, weight=1)
        list_panel.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(list_panel, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        _label(hdr, "Hosted Items", size=14, weight="bold").pack(side="left")
        self.lbl_count = _label(hdr, "0 items", size=11, color=TEXT_MUTED)
        self.lbl_count.pack(side="right")

        # _sep(list_panel).grid(row=1, column=0, sticky="ew", padx=12, pady=0)

        self.scroll_list = ctk.CTkScrollableFrame(
            list_panel, fg_color="transparent",
            scrollbar_button_color=ACCENT_SOFT,
            scrollbar_button_hover_color=ACCENT)
        self.scroll_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        #list_panel.grid_rowconfigure(2, weight=1)

        self.refresh_list_ui()

        # ── Controls panel ────────────────────────────────────────────────
        ctrl = ctk.CTkFrame(f, fg_color=BG_PANEL, corner_radius=12)
        ctrl.grid(row=0, column=1, padx=(0, 16), pady=16, sticky="nsew")
        ctrl.grid_rowconfigure(7, weight=1)  # Spacer row
        ctrl.grid_columnconfigure(0, weight=1)

        _label(ctrl, "Add Content", size=12, weight="bold",
               color=TEXT_MUTED).grid(row=0, column=0, pady=(18, 10), padx=16, sticky="w")
        self.btn_add_folder = _btn(ctrl, "＋  Add Folder", self.add_folder)
        self.btn_add_folder.grid(row=1, column=0, sticky="ew", padx=14, pady=4)
        self.btn_add_file = _btn(ctrl, "＋  Add Files",  self.add_file)
        self.btn_add_file.grid(row=2, column=0, sticky="ew", padx=14, pady=4)
        _btn(ctrl, "✕  Clear All",   self.clear_list,
             fg="#E00025", hover="#b71c1c").grid(row=3, column=0, sticky="ew", padx=14, pady=4)

        # Spacer
        ctk.CTkFrame(ctrl, fg_color="transparent").grid(row=4, column=0, sticky="nsew")
        ctrl.grid_rowconfigure(4, weight=1)

        _sep(ctrl).grid(row=5, column=0, sticky="ew", padx=14, pady=8)

        self.lbl_server_status = _label(ctrl, "⏸  Server Stopped",
                                        size=11, color=TEXT_MUTED)
        self.lbl_server_status.grid(row=6, column=0, pady=(4, 10), sticky="ew", padx=14)

        self.btn_start = _btn(ctrl, "▶  Start Server",
                              self.start_server, fg="#1ed760", hover="#21a366")
        self.btn_start.configure(text_color="#fff")
        self.btn_start.grid(row=8, column=0, sticky="ew", padx=14, pady=4)

        self.btn_stop = _btn(ctrl, "■  Stop Server",
                             self.stop_server, fg="#E00025", hover="#b71c1c")
        self.btn_stop.configure(state="disabled", text_color="#fff")
        self.btn_stop.grid(row=9, column=0, sticky="ew", padx=14, pady=(4, 18))
        # Add tooltips to control buttons
        ToolTip(self.btn_start, "Start the WiFi file server")
        ToolTip(self.btn_stop, "Stop the WiFi file server")
        # Add tooltips to add/clear buttons
        for row, tip in zip([1,2,3], ["Add a folder to host", "Add files to host", "Clear all hosted items"]):
            btn = ctrl.grid_slaves(row=row, column=0)[0]
            ToolTip(btn, tip)

        # ── Console panel ─────────────────────────────────────────────────
        console = ctk.CTkFrame(f, fg_color=BG_PANEL, corner_radius=12)
        console.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 16), sticky="nsew")
        console.grid_rowconfigure(1, weight=1)
        console.grid_columnconfigure(0, weight=1)

        hdr2 = ctk.CTkFrame(console, fg_color="transparent")
        hdr2.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        hdr2.grid_columnconfigure(0, weight=0)
        hdr2.grid_columnconfigure(1, weight=0)
        hdr2.grid_columnconfigure(2, weight=1)
        hdr2.grid_columnconfigure(3, weight=0)
        _label(hdr2, "Console", size=13, weight="bold").grid(row=0, column=0, sticky="w")
        _label(hdr2, "live output", size=12, color="#21a366").grid(row=0, column=1, sticky="w", padx=8)
        # Spacer column (2) expands
        self.btn_clear_log = _btn(hdr2, "🗑", self.clear_log, fg="#101010", hover="#b71c1c", border_width=0, border_color="#F5012A", width=50)
        self.btn_clear_log.configure(text_color="#fff")
        self.btn_clear_log.grid(row=0, column=3, sticky="e", padx=8)
        ToolTip(self.btn_clear_log, "Clear the console log")
        
        _sep(console).grid(row=1, column=0, sticky="ew", padx=12)

        self.log_box = ctk.CTkTextbox(
            console, wrap="word", state="disabled",
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#1C1E20", text_color="#c9d8f0",
            corner_radius=0, border_width=0,
            scrollbar_button_color=ACCENT_SOFT,
            scrollbar_button_hover_color=ACCENT)
        self.log_box.grid(row=2, column=0, sticky="nsew", padx=0, pady=(4, 0))
        console.grid_rowconfigure(2, weight=1)

        self.log_box.tag_config("info",    foreground=SUCCESS)
        self.log_box.tag_config("error",   foreground=DANGER)
        self.log_box.tag_config("warning", foreground=WARN)
        self.log_box.tag_config("normal",  foreground="#c9d8f0")

    # ── Settings frame ────────────────────────────────────────────────────
    def _build_settings(self):
        f = self.settings_frame
        f.configure(fg_color=BG_DEEP)

        wrap = ctk.CTkFrame(f, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=28, pady=28)

        _label(wrap, "Settings", size=20, weight="bold").pack(anchor="w", pady=(0, 6))
        _label(wrap, "Configure server behavior and update source",
               size=12, color=TEXT_MUTED).pack(anchor="w", pady=(0, 20))

        card = ctk.CTkFrame(wrap, fg_color=BG_PANEL, corner_radius=12)
        card.pack(fill="x")

        def _row(parent, row, label_text, widget_factory):
            _label(parent, label_text, size=12, weight="bold"
                   ).grid(row=row, column=0, padx=24, pady=18, sticky="w")
            widget_factory(parent).grid(row=row, column=1, padx=24, pady=18, sticky="w")
            if row > 0:
                _sep(parent).grid(row=row * 2 - 1, column=0,
                                  columnspan=2, sticky="ew", padx=16)

        card.grid_columnconfigure(1, weight=1)

        def port_widget(p):
            e = ctk.CTkEntry(p, textvariable=self.port_var, width=160,
                             fg_color=BG_CARD, border_color=ACCENT_SOFT,
                             text_color=TEXT_PRIMARY,
                             font=ctk.CTkFont(family="Segoe UI", size=12))
            return e

        def repo_widget(p):
            e = ctk.CTkEntry(p, textvariable=self.repo_var, width=320,
                             fg_color=BG_CARD, border_color=ACCENT_SOFT,
                             text_color=TEXT_PRIMARY,
                             font=ctk.CTkFont(family="Segoe UI", size=12))
            return e

        _row(card, 0, "Server Port", port_widget)
        _sep(card).grid(row=1, column=0, columnspan=2, sticky="ew", padx=16)
        _row(card, 2, "GitHub Repo  (for updates)", repo_widget)

        _label(wrap, "⚠  Port changes require a server restart to take effect.",
               size=11, color=TEXT_MUTED).pack(anchor="w", pady=(14, 0))
        

    # ── Credits frame ─────────────────────────────────────────────────────
    def _build_credits(self):
        f = self.credits_frame
        f.configure(fg_color=BG_DEEP)

        wrap = ctk.CTkFrame(f, fg_color="transparent")
        wrap.pack(fill="both", expand=True, padx=28, pady=28)

        _label(wrap, "About", size=20, weight="bold").pack(anchor="w", pady=(0, 6))
        _label(wrap, "Open-source WiFi file server for local networks built by PixCap Soft. Host your files & create your own home server.",
               size=12, color=TEXT_MUTED).pack(anchor="w", pady=(0, 20))

        card = ctk.CTkFrame(wrap, fg_color=BG_PANEL, corner_radius=12)
        card.pack(fill="x")

        body = (
    "WiFi-Home-Server\n\n"
    "A lightweight HTTP file server built with Python and CustomTkinter.\n"
    "Host any file or folder on your local network — no client app needed.\n"
    "Any device in same WiFi networks with a browser can browse and download instantly.\n\n"
    "Features\n"
    "  ◆  Multi-folder & multi-file hosting\n"
    "  ◆  Real-time connection tracking\n"
    "  ◆  Zero setup on client devices\n"
    "  ◆  Live console log\n"
    "  ◆  Lightweight & open source\n\n"
    "Contributors\n"
    "  ◆  PixCap Soft (Lead Developer)\n"
    "  ◆  Open-source community\n\n"
    "Links\n"
    "  ◆  GitHub: https://github.com/pixcapsoft/WiFi-Home-Server\n"
    "  ◆  Documentation: https://github.com/pixcapsoft/WiFi-Home-Server/wiki\n"
    "  ◆  Report Issues: https://github.com/pixcapsoft/WiFi-Home-Server/issues\n\n"
    "Thank you for using open-source software!\n"
    "If you enjoy this project, consider starring it on GitHub or contributing!"
)
        _label(card, body, size=13, color=TEXT_PRIMARY, justify="left").pack(padx=28, pady=28, anchor="nw")
        _label(card, "Special thanks to all contributors and users!", size=11, color=TEXT_MUTED).pack(anchor="w", padx=28, pady=(0, 10))
    
    # ── Server controls ───────────────────────────────────────────────────
    def start_server(self):
        if not self.roots:
            self.write_log("warning", "[WARN] No files or folders selected to host.")
            return
        if self.server_instance:
            self.write_log("warning", "[WARN] Server is already running.")
            return

        self.btn_start.configure(state="disabled", text="⌛  Starting...")
        self.lbl_server_status.configure(text="⌛  Starting...", text_color=WARN)
        
        def _start():
            try:
                port = int(self.port_var.get())
                instance = main.start_server_background(self.roots, port=port)
                self.after(0, lambda: self._on_server_started(instance, port))
            except Exception as e:
                self.after(0, lambda: self._on_server_start_error(e))
                
        threading.Thread(target=_start, daemon=True).start()

    def _on_server_started(self, instance, port):
        self.server_instance = instance
        self.btn_start.configure(text="▶  Start Server")
        self.btn_stop.configure(state="normal")
        self.lbl_server_status.configure(
            text=f"▶  Running  :{port}", text_color=SUCCESS)
        self.active_connections = 0
        self.lbl_conn.configure(text="0 devices connected  ")

    def _on_server_start_error(self, e):
        self.btn_start.configure(state="normal", text="▶  Start Server")
        self.lbl_server_status.configure(text="⏸  Server Stopped", text_color=TEXT_MUTED)
        self.write_log("error", f"[ERR] Could not start server: {e}")

    def stop_server(self):
        if not self.server_instance:
            return

        self.btn_stop.configure(state="disabled", text="⌛  Stopping...")
        self.lbl_server_status.configure(text="⌛  Stopping...", text_color=WARN)

        def _stop():
            self.server_instance.shutdown()
            self.after(0, self._on_server_stopped)

        threading.Thread(target=_stop, daemon=True).start()

    def _on_server_stopped(self):
        self.server_instance = None
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(text="■  Stop Server")
        self.lbl_server_status.configure(text="⏸  Server Stopped", text_color=TEXT_MUTED)
        self.active_connections = 0
        self.lbl_conn.configure(text="0 devices connected  ")
        self.write_log("warning", "[INFO] Server stopped.")

    def check_updates(self):
        repo = self.repo_var.get().strip()
        if not repo or "/" not in repo:
            messagebox.showwarning("Update Error",
                                   "Please set a valid 'User/Repo' in Settings.")
            return
        self._nav_btns["update"].configure(text="Checking…", state="disabled")
        self.write_log("normal", f"[UPDATE] Checking Updates…")

        def worker():
            url = f"https://api.github.com/repos/pixcapsoft/WiFi-Home-Server/releases/latest"
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "WiFi-Home-Server-App"})
                with urllib.request.urlopen(req, timeout=5) as r:
                    data = json.loads(r.read().decode())
                tag = data.get("tag_name", "")
                html_url = data.get("html_url", None)
                if not tag:
                    msg = "No releases found."
                elif tag == self.app_version:
                    msg = f"You are on the latest version ({self.app_version})."
                else:
                    msg = f"Update available: {tag}  (you have {self.app_version})"
                    if html_url:
                        webbrowser.open(html_url)
                self.after(0, lambda: self.write_log("info", f"[UPDATE] {msg}"))
                self.after(0, lambda: messagebox.showinfo("Update Check", msg))
            except Exception as e:
                self.after(0, lambda idx=str(e): self.write_log("error", f"[UPDATE ERR] {idx}"))
                self.after(0, lambda idx=str(e): messagebox.showerror("Update Failed", idx))
            finally:
                self.after(0, lambda: self._nav_btns["update"].configure(
                    text="↑  Check for Updates", state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    # ── Connection tracking ───────────────────────────────────────────────
    def handle_conn(self, action):
        self.after(0, lambda: self._update_conn(action))

    def _update_conn(self, action):
        if action == "connect":
            self.active_connections += 1
        elif action == "disconnect":
            self.active_connections = max(0, self.active_connections - 1)
        n = self.active_connections
        self.lbl_conn.configure(
            text=f"{n} device{'s' if n != 1 else ''} connected  ")

    # ── List management ───────────────────────────────────────────────────
    def add_folder(self):
        self.btn_add_folder.configure(state="disabled", text="⌛  Opening...")
        self.update()
        self.after(50, self._process_add_folder)

    def _process_add_folder(self):
        p = fd.askdirectory(title="Select Folder to Host")
        if p: 
            self._add_root(p)
            self.refresh_list_ui()
        self.btn_add_folder.configure(state="normal", text="＋  Add Folder")

    def add_file(self):
        self.btn_add_file.configure(state="disabled", text="⌛  Opening...")
        self.update()
        self.after(50, self._process_add_file)

    def _process_add_file(self):
        paths = fd.askopenfilenames(title="Select Files to Host")
        if paths:
            for p in paths:
                self._add_root(p)
            self.refresh_list_ui()
        self.btn_add_file.configure(state="normal", text="＋  Add Files")

    def _add_root(self, path):
        if any(r["local"] == path for r in self.roots):
            self.write_log("warning", f"[WARN] Already hosting: {path}")
            return
        self.roots.append({"local": path, "remote": ""})
        self.write_log("info", f"[ADDED]  {path}")

    def remove_item(self, path):
        self.roots = [r for r in self.roots if r["local"] != path]
        self.refresh_list_ui()
        self.write_log("normal", f"[REMOVED]  {path}")

    def clear_list(self):
        self.roots.clear()
        self.refresh_list_ui()
        self.write_log("normal", "[INFO] Cleared all hosted items.")

    def refresh_list_ui(self):
        for w in self.scroll_list.winfo_children():
            w.destroy()
        n = len(self.roots)
        self.lbl_count.configure(text=f"{n} item{'s' if n != 1 else ''}")

        if not self.roots:
            placeholder = ctk.CTkFrame(self.scroll_list,
                                       fg_color="transparent")
            placeholder.pack(fill="both", expand=True, pady=30)
            _label(placeholder, "No items yet",
                   size=13, color=TEXT_MUTED).pack()
            _label(placeholder,
                   "Click  ＋ Add Folder  or  ＋ Add Files  to get started.",
                   size=11, color="#8d97a5").pack(pady=4)
            return

        for r in self.roots:
            path = r["local"]
            is_dir = os.path.isdir(path)
            icon = "📁" if is_dir else "📄"
            name = os.path.basename(path.rstrip("/\\")) or path
            display = path if len(path) < 58 else "…" + path[-55:]

            row = ctk.CTkFrame(self.scroll_list,
                               fg_color=BG_CARD, corner_radius=8)
            row.pack(fill="x", pady=3, padx=2)

            # Icon badge
            badge = ctk.CTkFrame(row, width=32, height=32,
                                 fg_color=ACCENT_SOFT, corner_radius=6)
            badge.pack(side="left", padx=(10, 8), pady=8)
            badge.pack_propagate(False)
            _label(badge, icon, size=14).place(relx=.5, rely=.5, anchor="center")

            # Path text
            txt = ctk.CTkFrame(row, fg_color="transparent")
            txt.pack(side="left", fill="x", expand=True, pady=6)
            _label(txt, name, size=12, weight="bold").pack(anchor="w")
            _label(txt, display, size=10, color=TEXT_MUTED).pack(anchor="w")

            # Remove button
            rem = ctk.CTkButton(
                row, text="✕", width=28, height=28,
                fg_color="transparent", hover_color="#2a0a0a",
                text_color=TEXT_MUTED, corner_radius=6,
                font=ctk.CTkFont(size=13),
                command=lambda p=path: self.remove_item(p))
            rem.pack(side="right", padx=10, pady=8)
            ToolTip(rem, "Remove this item from hosting list")

    # ── Logging ───────────────────────────────────────────────────────────
    def handle_log(self, level, msg):
        self.after(0, lambda: self.write_log(level, msg))

    def write_log(self, level, msg):
        if level not in ("info", "error", "warning", "normal"):
            level = "normal"
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n", level)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")


if __name__ == "__main__":
    app = WiFiServerApp()
    app.mainloop()