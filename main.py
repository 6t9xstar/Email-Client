"""
MT DEVELOPER v2.0 PRO
Unified Inbox Manager for 100+ Gmail Accounts
Features: Auto-Discovery | Bulk Import | Live Notifications | Premium UI
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
import json
import threading
import time
import re
import base64
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import webbrowser
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import hashlib

# Google API
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    _HAS_GOOGLE_API = True
except ImportError:
    _HAS_GOOGLE_API = False

# openpyxl for export
try:
    import openpyxl
    _HAS_OPENPYXL = True
except ImportError:
    _HAS_OPENPYXL = False

# Gmail API Scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


@dataclass
class GmailAccount:
    """Represents one Gmail account."""
    credentials_path: str
    account_name: str
    email_address: str = ""
    service: Any = None
    authenticated: bool = False
    last_error: str = ""
    last_sync: Optional[datetime] = None
    unread_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "credentials_path": self.credentials_path,
            "account_name": self.account_name,
            "email_address": self.email_address
        }


@dataclass
class EmailMessage:
    """Represents an email message from any account."""
    message_id: str
    thread_id: str
    account_email: str
    account_name: str
    sender: str
    recipient: str
    subject: str
    body: str
    snippet: str
    date: str
    labels: List[str] = field(default_factory=list)
    is_read: bool = False
    is_starred: bool = False
    internal_date: int = 0


class ToastNotification:
    """Premium toast notification popup."""
    def __init__(self, title: str, message: str, msg_type: str = "info", duration: int = 5000):
        self.root = tk.Toplevel()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.0)
        
        # Colors based on type
        colors = {
            "info": ("#6366f1", "#818cf8"),
            "success": ("#22c55e", "#4ade80"),
            "warning": ("#eab308", "#facc15"),
            "error": ("#ef4444", "#f87171"),
            "new_email": ("#8b5cf6", "#a78bfa")
        }
        bg_color, accent_color = colors.get(msg_type, colors["info"])
        
        # Frame
        frame = tk.Frame(self.root, bg=bg_color, padx=2, pady=2)
        frame.pack(fill="both", expand=True)
        
        inner = tk.Frame(frame, bg="#1a2137", padx=20, pady=15)
        inner.pack(fill="both", expand=True)
        
        # Icon
        icons = {
            "info": "ℹ️", "success": "✅", "warning": "⚠️", 
            "error": "❌", "new_email": "📧"
        }
        icon = icons.get(msg_type, "ℹ️")
        
        tk.Label(inner, text=icon, bg="#1a2137", font=("Segoe UI", 24)).pack(anchor="w")
        
        # Title
        tk.Label(inner, text=title, bg="#1a2137", fg="white",
                font=("Segoe UI Black", 12)).pack(anchor="w", pady=(5, 0))
        
        # Message
        tk.Label(inner, text=message, bg="#1a2137", fg="#94a3b8",
                font=("Segoe UI", 10), wraplength=280, justify="left").pack(anchor="w", pady=(5, 0))
        
        # Progress bar
        self.progress = tk.Frame(inner, bg=accent_color, height=3)
        self.progress.pack(fill="x", pady=(15, 0))
        
        # Position at bottom right of screen
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = 320
        height = self.root.winfo_reqheight()
        x = screen_width - width - 20
        y = screen_height - height - 60
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # Fade in animation
        self._fade_in()
        
        # Auto close
        self.root.after(duration, self._fade_out)
        
        # Click to close
        self.root.bind("<Button-1>", lambda e: self._fade_out())
    
    def _fade_in(self, alpha=0.0):
        if alpha < 1.0:
            self.root.attributes("-alpha", alpha)
            self.root.after(16, lambda: self._fade_in(alpha + 0.1))
    
    def _fade_out(self, alpha=1.0):
        if alpha > 0:
            self.root.attributes("-alpha", alpha)
            self.root.after(16, lambda: self._fade_out(alpha - 0.1))
        else:
            self.root.destroy()


class PremiumButton:
    """Premium animated button."""
    def __init__(self, parent, text, command, color="accent", width=None):
        colors = {
            "accent": ("#6366f1", "#4f46e5"),
            "success": ("#22c55e", "#16a34a"),
            "danger": ("#ef4444", "#dc2626"),
            "warning": ("#eab308", "#ca8a04"),
            "panel": ("#141a2e", "#1a2137")
        }
        self.bg, self.hover = colors.get(color, colors["accent"])
        self.fg = "white" if color != "panel" else "#e2e8f0"
        
        self.btn = tk.Button(parent, text=text, bg=self.bg, fg=self.fg,
                           font=("Segoe UI Semibold", 10),
                           relief="flat", padx=20, pady=10,
                           cursor="hand2", command=command,
                           activebackground=self.hover, activeforeground=self.fg)
        if width:
            self.btn.configure(width=width)
        
        self.btn.bind("<Enter>", self._on_enter)
        self.btn.bind("<Leave>", self._on_leave)
    
    def _on_enter(self, e):
        self.btn.configure(bg=self.hover)
    
    def _on_leave(self, e):
        self.btn.configure(bg=self.bg)
    
    def pack(self, **kwargs):
        self.btn.pack(**kwargs)
    
    def grid(self, **kwargs):
        self.btn.grid(**kwargs)


class GmailAllMailboxApp(tk.Frame):
    """Main application for unified Gmail inbox management."""
    
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        
        # Window setup
        master.title("GMAIL ALL MAILBOX v2.0 PRO - Unified Inbox Manager - Apex Developer")
        master.geometry("1800x1000")
        master.minsize(1600, 900)
        master.configure(bg="#0a0e1a")
        
        self.config_dir = Path(os.environ.get("APPDATA", str(Path.home() / ".config"))) / "GmailAllMailbox"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.accounts_file = self.config_dir / "accounts.json"
        self.cache_dir = self.config_dir / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.settings_file = self.config_dir / "settings.json"
        
        self.accounts: List[GmailAccount] = []
        self.all_messages: List[EmailMessage] = []
        self.filtered_messages: List[EmailMessage] = []
        self.selected_message: Optional[EmailMessage] = None
        
        self._stop_event = threading.Event()
        self._sync_thread: Optional[threading.Thread] = None
        self._auto_sync_thread: Optional[threading.Thread] = None
        self._message_cache: Dict[str, EmailMessage] = {}
        self._last_message_ids: set = set()
        self._is_auto_syncing = False
        self._auto_sync_interval = 60  # seconds
        
        # Thread pool for parallel processing (optimized for 100+ accounts)
        self._thread_pool = ThreadPoolExecutor(max_workers=10)
        self._message_queue = Queue()
        self._sender_filter = ""  # Current sender filter
        
        # Premium Colors
        self.COLORS = {
            "bg": "#0a0e1a",
            "sidebar": "#0d1220",
            "panel": "#141a2e",
            "card": "#1a2137",
            "accent": "#6366f1",
            "accent_hover": "#818cf8",
            "accent_gradient": ["#6366f1", "#8b5cf6", "#a78bfa"],
            "fg": "#e2e8f0",
            "fg_dim": "#94a3b8",
            "fg_muted": "#64748b",
            "entry_bg": "#1e293b",
            "red": "#ef4444",
            "green": "#22c55e",
            "green_glow": "#4ade80",
            "yellow": "#eab308",
            "orange": "#f97316",
            "purple": "#8b5cf6",
            "border": "#1e293b",
            "hover": "#334155",
            "glass": "#1a2137"
        }
        
        self.settings = self._load_settings()
        self._build_style()
        self._build_ui()
        self._load_accounts()
        self._start_auto_sync()
        
        if not _HAS_GOOGLE_API:
            self._show_notification("Missing Dependencies", 
                "Google API libraries not found.\nRun: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client", 
                "warning")
    
    def _load_settings(self) -> dict:
        """Load user settings."""
        defaults = {
            "auto_sync": True,
            "auto_sync_interval": 60,
            "notifications": True,
            "sound_enabled": False,
            "theme": "dark"
        }
        if self.settings_file.exists():
            try:
                data = json.loads(self.settings_file.read_text())
                defaults.update(data)
            except Exception:
                pass
        return defaults
    
    def _save_settings(self):
        """Save user settings."""
        try:
            self.settings_file.write_text(json.dumps(self.settings, indent=2))
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    # ===============================
    # UI BUILDING
    # ===============================
    
    def _build_style(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use("clam")
        
        # Treeview
        style.configure("Custom.Treeview",
            background=self.COLORS["card"],
            foreground=self.COLORS["fg"],
            fieldbackground=self.COLORS["card"],
            rowheight=42,
            font=("Segoe UI", 10),
            borderwidth=0
        )
        style.configure("Custom.Treeview.Heading",
            background=self.COLORS["panel"],
            foreground=self.COLORS["fg"],
            font=("Segoe UI Semibold", 11),
            borderwidth=1,
            relief="flat"
        )
        style.map("Custom.Treeview",
            background=[("selected", self.COLORS["accent"])],
            foreground=[("selected", "#ffffff")]
        )
        
        # Unread row style
        style.configure("Unread.Treeview",
            background=self.COLORS["card"],
            foreground=self.COLORS["fg"],
            fieldbackground=self.COLORS["card"],
            rowheight=42,
            font=("Segoe UI Semibold", 10)
        )
        
        # Notebook
        style.configure("Custom.TNotebook",
            background=self.COLORS["bg"],
            tabmargins=[0, 0, 0, 0]
        )
        style.configure("Custom.TNotebook.Tab",
            background=self.COLORS["panel"],
            foreground=self.COLORS["fg_dim"],
            padding=[20, 12],
            font=("Segoe UI Semibold", 10)
        )
        style.map("Custom.TNotebook.Tab",
            background=[("selected", self.COLORS["accent"])],
            foreground=[("selected", "#ffffff")]
        )
        
        # Scrollbar
        style.configure("Custom.Vertical.TScrollbar",
            background=self.COLORS["panel"],
            troughcolor=self.COLORS["bg"],
            borderwidth=0,
            arrowsize=0
        )
    
    def _build_ui(self):
        """Build the main UI layout."""
        self.configure(bg=self.COLORS["bg"])
        
        # Main container
        main = tk.Frame(self, bg=self.COLORS["bg"])
        main.pack(fill="both", expand=True)
        
        # ========== LEFT SIDEBAR ==========
        sidebar = tk.Frame(main, bg=self.COLORS["sidebar"], width=280)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        
        # Logo / Title
        logo_frame = tk.Frame(sidebar, bg=self.COLORS["sidebar"])
        logo_frame.pack(fill="x", padx=20, pady=20)
        
        tk.Label(logo_frame, text="📧", bg=self.COLORS["sidebar"], 
                font=("Segoe UI", 24)).pack(side="left")
        
        tk.Label(logo_frame, text="GMAIL ALL\nMAILBOX", bg=self.COLORS["sidebar"],
                fg=self.COLORS["fg"], font=("Segoe UI Black", 14),
                justify="left").pack(side="left", padx=10)
        
        # Version
        tk.Label(sidebar, text="v2.0 PRO", bg=self.COLORS["sidebar"],
                fg=self.COLORS["accent"], font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=20)
        
        # Separator
        tk.Frame(sidebar, bg=self.COLORS["border"], height=1).pack(fill="x", padx=20, pady=15)
        
        # Quick Stats
        self.stats_frame = tk.Frame(sidebar, bg=self.COLORS["sidebar"])
        self.stats_frame.pack(fill="x", padx=20, pady=10)
        
        self.lbl_total_accounts = self._stat_label(self.stats_frame, "Total Accounts", "0")
        self.lbl_total_messages = self._stat_label(self.stats_frame, "Total Messages", "0")
        self.lbl_unread_count = self._stat_label(self.stats_frame, "Unread", "0")
        
        # Separator
        tk.Frame(sidebar, bg=self.COLORS["border"], height=1).pack(fill="x", padx=20, pady=15)
        
        # Folders / Filters
        tk.Label(sidebar, text="QUICK FILTERS", bg=self.COLORS["sidebar"],
                fg=self.COLORS["fg_muted"], font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=20, pady=(0, 10))
        
        filters = [
            ("📥  All Messages", lambda: self._filter_messages("all")),
            ("🔴  Unread", lambda: self._filter_messages("unread")),
            ("⭐  Starred", lambda: self._filter_messages("starred")),
            ("📤  Sent", lambda: self._filter_messages("sent")),
            ("🗑  Trash", lambda: self._filter_messages("trash")),
        ]
        
        for text, cmd in filters:
            btn = tk.Button(sidebar, text=text, bg=self.COLORS["sidebar"],
                          fg=self.COLORS["fg"], font=("Segoe UI", 10),
                          relief="flat", anchor="w", padx=15, pady=8,
                          activebackground=self.COLORS["hover"],
                          activeforeground=self.COLORS["fg"],
                          cursor="hand2", command=cmd)
            btn.pack(fill="x", padx=15)
            btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=self.COLORS["hover"]))
            btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=self.COLORS["sidebar"]))
        
        # Separator
        tk.Frame(sidebar, bg=self.COLORS["border"], height=1).pack(fill="x", padx=20, pady=15)
        
        # Account Management Button
        self._sidebar_btn(sidebar, "⚙️  Manage Accounts", self._show_account_manager)
        self._sidebar_btn(sidebar, "🔐  Connect All", self._authenticate_all_accounts)
        self._sidebar_btn(sidebar, "📁  Bulk Import", self._bulk_import_dialog)
        self._sidebar_btn(sidebar, "🔄  Sync All Now", self._sync_all_accounts)
        
        # Status at bottom
        tk.Frame(sidebar, bg=self.COLORS["sidebar"]).pack(fill="both", expand=True)
        
        self.status_label = tk.Label(sidebar, text="● Ready", bg=self.COLORS["sidebar"],
                                     fg=self.COLORS["green"], font=("Segoe UI Semibold", 10))
        self.status_label.pack(anchor="w", padx=20, pady=20)
        
        # ========== RIGHT CONTENT AREA ==========
        content = tk.Frame(main, bg=self.COLORS["bg"])
        content.pack(side="left", fill="both", expand=True, padx=20, pady=20)
        
        # Top Bar - Search & Actions
        top_bar = tk.Frame(content, bg=self.COLORS["bg"])
        top_bar.pack(fill="x", pady=(0, 15))
        
        # Search box
        search_frame = tk.Frame(top_bar, bg=self.COLORS["entry_bg"], highlightbackground=self.COLORS["border"],
                               highlightthickness=1)
        search_frame.pack(side="left", fill="x", expand=True)
        
        tk.Label(search_frame, text="🔍", bg=self.COLORS["entry_bg"],
                fg=self.COLORS["fg_muted"], font=("Segoe UI", 12)).pack(side="left", padx=10)
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_search_change())
        search_entry = tk.Entry(search_frame, textvariable=self.search_var,
                               bg=self.COLORS["entry_bg"], fg=self.COLORS["fg"],
                               font=("Segoe UI", 11), relief="flat", insertbackground="white")
        search_entry.pack(side="left", fill="x", expand=True, padx=5, pady=8)
        
        # Action buttons
        PremiumButton(top_bar, "➕ Add Account", self._add_account_dialog, "accent").pack(side="left", padx=(10, 0))
        PremiumButton(top_bar, "📁 Bulk Import", self._bulk_import_dialog, "success").pack(side="left", padx=(10, 0))
        PremiumButton(top_bar, "🔄 Refresh", self._sync_all_accounts, "panel").pack(side="left", padx=(10, 0))
        PremiumButton(top_bar, "🔍 Sender Filter", self._show_sender_filter_dialog, "warning").pack(side="left", padx=(10, 0))
        
        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(content, variable=self.progress_var, maximum=100)
        self.progress.pack(fill="x", pady=(0, 10))
        self.progress.pack_forget()  # Hide initially
        
        # Split view: Message List | Message Detail
        paned = tk.PanedWindow(content, bg=self.COLORS["border"], sashwidth=4, orient="horizontal")
        paned.pack(fill="both", expand=True)
        
        # ========== LEFT PANE: Message List ==========
        list_frame = tk.Frame(paned, bg=self.COLORS["panel"])
        paned.add(list_frame, width=600)
        
        # Message list header
        list_header = tk.Frame(list_frame, bg=self.COLORS["panel"], height=45)
        list_header.pack(fill="x")
        list_header.pack_propagate(False)
        
        tk.Label(list_header, text="INBOX", bg=self.COLORS["panel"],
                fg=self.COLORS["fg"], font=("Segoe UI Black", 12)).pack(side="left", padx=15)
        
        self.lbl_message_count = tk.Label(list_header, text="0 messages", bg=self.COLORS["panel"],
                                         fg=self.COLORS["fg_dim"], font=("Segoe UI", 10))
        self.lbl_message_count.pack(side="right", padx=15)
        
        # Message list tree
        columns = ("sender", "subject", "account", "date")
        self.message_tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                          style="Custom.Treeview", height=20)
        
        self.message_tree.heading("sender", text="FROM")
        self.message_tree.heading("subject", text="SUBJECT")
        self.message_tree.heading("account", text="ACCOUNT")
        self.message_tree.heading("date", text="DATE")
        
        self.message_tree.column("sender", width=200, minwidth=150)
        self.message_tree.column("subject", width=280, minwidth=200)
        self.message_tree.column("account", width=130, minwidth=100)
        self.message_tree.column("date", width=130, minwidth=100)
        
        # Scrollbar
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.message_tree.yview,
                           style="Custom.Vertical.TScrollbar")
        self.message_tree.configure(yscrollcommand=vsb.set)
        
        self.message_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        # Bind selection
        self.message_tree.bind("<<TreeviewSelect>>", self._on_message_select)
        self.message_tree.bind("<Double-1>", self._on_message_double_click)
        
        # ========== RIGHT PANE: Message Detail ==========
        detail_frame = tk.Frame(paned, bg=self.COLORS["card"])
        paned.add(detail_frame, width=600)
        
        # Empty state
        self.empty_state = tk.Frame(detail_frame, bg=self.COLORS["card"])
        self.empty_state.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(self.empty_state, text="📧", bg=self.COLORS["card"],
                font=("Segoe UI", 64)).pack()
        tk.Label(self.empty_state, text="Select a message to view", bg=self.COLORS["card"],
                fg=self.COLORS["fg_dim"], font=("Segoe UI", 14)).pack(pady=10)
        
        # Message detail view (initially hidden)
        self.detail_view = tk.Frame(detail_frame, bg=self.COLORS["card"])
        
        # Message header
        detail_header = tk.Frame(self.detail_view, bg=self.COLORS["card"], padx=20, pady=15)
        detail_header.pack(fill="x")
        
        # Action buttons in header
        btn_frame = tk.Frame(detail_header, bg=self.COLORS["card"])
        btn_frame.pack(fill="x", pady=(0, 10))
        
        self._detail_btn(btn_frame, "↩️ Reply", self._reply_message, self.COLORS["accent"])
        self._detail_btn(btn_frame, "🗑 Delete", self._delete_message, self.COLORS["red"])
        self._detail_btn(btn_frame, "⭐ Star", self._star_message, self.COLORS["yellow"])
        self._detail_btn(btn_frame, "✓ Mark Read", self._manual_mark_read, self.COLORS["green"])
        self._detail_btn(btn_frame, "📧 Open in Gmail", self._open_in_gmail, self.COLORS["panel"])
        
        # Email metadata
        self.lbl_detail_subject = tk.Label(detail_header, text="", bg=self.COLORS["card"],
                                          fg=self.COLORS["fg"], font=("Segoe UI Black", 14),
                                          wraplength=550, justify="left")
        self.lbl_detail_subject.pack(anchor="w", pady=(10, 5))
        
        self.lbl_detail_from = tk.Label(detail_header, text="", bg=self.COLORS["card"],
                                       fg=self.COLORS["fg_dim"], font=("Segoe UI", 11))
        self.lbl_detail_from.pack(anchor="w")
        
        self.lbl_detail_to = tk.Label(detail_header, text="", bg=self.COLORS["card"],
                                     fg=self.COLORS["fg_muted"], font=("Segoe UI", 10))
        self.lbl_detail_to.pack(anchor="w")
        
        self.lbl_detail_date = tk.Label(detail_header, text="", bg=self.COLORS["card"],
                                       fg=self.COLORS["fg_muted"], font=("Segoe UI", 10))
        self.lbl_detail_date.pack(anchor="w", pady=(5, 0))
        
        # Read status indicator
        self.lbl_read_status = tk.Label(detail_header, text="", bg=self.COLORS["card"],
                                       fg=self.COLORS["green"], font=("Segoe UI Semibold", 10))
        self.lbl_read_status.pack(anchor="w", pady=(5, 0))
        
        # Separator
        tk.Frame(detail_header, bg=self.COLORS["border"], height=1).pack(fill="x", pady=15)
        
        # Message body
        body_frame = tk.Frame(self.detail_view, bg=self.COLORS["card"])
        body_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.txt_body = scrolledtext.ScrolledText(body_frame, wrap=tk.WORD,
                                                 bg=self.COLORS["card"], fg=self.COLORS["fg"],
                                                 font=("Segoe UI", 11), relief="flat",
                                                 padx=10, pady=10, state="disabled")
        self.txt_body.pack(fill="both", expand=True)
    
    # ===============================
    # HELPER METHODS
    # ===============================
    
    def _ui(self, callable_func):
        """Thread-safe UI updates using after() method."""
        self.after(0, callable_func)
    
    def _stat_label(self, parent, label, value):
        """Create a stat display in sidebar."""
        frame = tk.Frame(parent, bg=self.COLORS["sidebar"])
        frame.pack(fill="x", pady=3)
        
        tk.Label(frame, text=label, bg=self.COLORS["sidebar"],
                fg=self.COLORS["fg_muted"], font=("Segoe UI", 9)).pack(side="left")
        
        lbl = tk.Label(frame, text=value, bg=self.COLORS["sidebar"],
                      fg=self.COLORS["accent"], font=("Segoe UI Bold", 11))
        lbl.pack(side="right")
        return lbl
    
    def _sidebar_btn(self, parent, text, command):
        """Create a sidebar button."""
        btn = tk.Button(parent, text=text, bg=self.COLORS["accent"],
                       fg="white", font=("Segoe UI Semibold", 10),
                       relief="flat", anchor="w", padx=15, pady=10,
                       activebackground=self.COLORS["accent_hover"],
                       cursor="hand2", command=command)
        btn.pack(fill="x", padx=15, pady=5)
        return btn
    
    def _action_btn(self, parent, text, command, bg):
        """Create an action button."""
        btn = tk.Button(parent, text=text, bg=bg,
                       fg=self.COLORS["fg"] if bg != self.COLORS["accent"] else "white",
                       font=("Segoe UI Semibold", 10),
                       relief="flat", padx=20, pady=8,
                       activebackground=self.COLORS["hover"],
                       cursor="hand2", command=command)
        btn.pack(side="left", padx=(10, 0))
        return btn
    
    def _detail_btn(self, parent, text, command, bg):
        """Create a detail view button."""
        fg = "white" if bg in [self.COLORS["accent"], self.COLORS["red"], self.COLORS["green"]] else self.COLORS["fg"]
        btn = tk.Button(parent, text=text, bg=bg, fg=fg,
                       font=("Segoe UI Semibold", 9),
                       relief="flat", padx=12, pady=6,
                       activebackground=self.COLORS["hover"],
                       cursor="hand2", command=command)
        btn.pack(side="left", padx=(0, 6))
        return btn
    
    # ===============================
    # CORE FUNCTIONALITY
    # ===============================
    
    def _load_accounts(self):
        """Load accounts from disk."""
        if not self.accounts_file.exists():
            return
        
        try:
            data = json.loads(self.accounts_file.read_text(encoding="utf-8"))
            for item in data:
                acc = GmailAccount(
                    credentials_path=item.get("credentials_path", ""),
                    account_name=item.get("account_name", "Account"),
                    email_address=item.get("email_address", "")
                )
                self.accounts.append(acc)
            
            self._update_stats()
        except Exception as e:
            print(f"Error loading accounts: {e}")
    
    def _save_accounts(self):
        """Save accounts to disk."""
        try:
            data = [a.to_dict() for a in self.accounts]
            self.accounts_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Error saving accounts: {e}")
    
    def _authenticate_account(self, account: GmailAccount) -> bool:
        """Authenticate a single Gmail account."""
        if not _HAS_GOOGLE_API:
            return False
        
        try:
            creds = None
            
            # First, check if the credentials_path file is a token file (already authenticated)
            creds_path = Path(account.credentials_path)
            if creds_path.exists():
                try:
                    data = json.loads(creds_path.read_text(encoding="utf-8"))
                    # Check if this is a token file (has 'token' and 'refresh_token')
                    if 'token' in data and 'refresh_token' in data:
                        # This is a token file - use it directly
                        creds = Credentials.from_authorized_user_info(data, SCOPES)
                        # Ensure email is set
                        if 'account_email' in data:
                            account.email_address = data['account_email']
                except Exception:
                    pass  # Not a token file, continue with normal flow
            
            # If no valid creds yet, use stored token or do OAuth flow
            if not creds or not creds.valid:
                token_path = self.config_dir / f"token_{account.account_name}.json"
                
                if token_path.exists():
                    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
                
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        # Check if credentials file is client_secrets format
                        if creds_path.exists():
                            try:
                                data = json.loads(creds_path.read_text(encoding="utf-8"))
                                # Check for client secrets format
                                if 'installed' in data or 'web' in data:
                                    flow = InstalledAppFlow.from_client_secrets_file(
                                        str(creds_path), SCOPES)
                                    creds = flow.run_local_server(port=0)
                                else:
                                    account.last_error = "Invalid credentials file format. Need token file or OAuth client secrets."
                                    return False
                            except Exception as e:
                                account.last_error = f"Failed to load credentials: {str(e)}"
                                return False
                        else:
                            account.last_error = f"Credentials file not found: {creds_path}"
                            return False
                    
                    # Save token for future use
                    if creds:
                        token_path.write_text(creds.to_json(), encoding="utf-8")
            
            # Build service
            if not creds:
                account.last_error = "No valid credentials"
                return False
                
            account.service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
            
            # Get email address if not already set
            if not account.email_address:
                profile = account.service.users().getProfile(userId='me').execute()
                account.email_address = profile.get('emailAddress', '')
            
            account.authenticated = True
            account.last_error = ""
            
            return True
            
        except Exception as e:
            account.last_error = str(e)
            account.authenticated = False
            return False
    
    def _sync_all_accounts(self):
        """Sync messages from all accounts."""
        if self._sync_thread and self._sync_thread.is_alive():
            messagebox.showinfo("Sync in Progress", "Already syncing messages...")
            return
        
        if not self.accounts:
            messagebox.showinfo("No Accounts", "Please add Gmail accounts first.")
            return
        
        self._stop_event.clear()
        self._sync_thread = threading.Thread(target=self._sync_worker, daemon=True)
        self._sync_thread.start()
    
    def _sync_worker(self):
        """Background worker to fetch messages using parallel processing."""
        self._ui(lambda: (
            self.status_label.configure(text="● Syncing...", fg=self.COLORS["yellow"]),
            self.progress.pack(fill="x", pady=(0, 10)),
            self.message_tree.delete(*self.message_tree.get_children())
        ))
        
        total_accounts = len(self.accounts)
        all_fetched = []
        completed = 0
        lock = threading.Lock()
        
        def fetch_account(account):
            """Fetch messages from a single account."""
            nonlocal completed
            
            # Authenticate if needed
            if not account.authenticated:
                if not self._authenticate_account(account):
                    return []
            
            # Fetch messages
            messages = self._fetch_messages(account)
            
            with lock:
                completed += 1
                progress = (completed / total_accounts) * 100
                self._ui(lambda p=progress, c=completed, t=total_accounts: (
                    self.progress_var.set(p),
                    self.status_label.configure(text=f"● Syncing {c}/{t} accounts...", fg=self.COLORS["yellow"])
                ))
            
            return messages
        
        # Use thread pool for parallel fetching
        futures = []
        for account in self.accounts:
            if self._stop_event.is_set():
                break
            future = self._thread_pool.submit(fetch_account, account)
            futures.append(future)
        
        # Collect results
        for future in as_completed(futures):
            if self._stop_event.is_set():
                break
            try:
                messages = future.result(timeout=60)
                all_fetched.extend(messages)
            except Exception as e:
                print(f"Error fetching from account: {e}")
        
        # Update UI
        self.all_messages = all_fetched
        self.all_messages.sort(key=lambda x: x.internal_date, reverse=True)
        self.filtered_messages = self.all_messages.copy()
        
        self._ui(lambda: (
            self._populate_message_list(),
            self._update_stats(),
            self.progress.pack_forget(),
            self.status_label.configure(text=f"● Ready ({len(all_fetched)} messages)", 
                                       fg=self.COLORS["green"]),
            self.lbl_message_count.configure(text=f"{len(self.filtered_messages)} messages")
        ))
    
    def _fetch_messages(self, account: GmailAccount, max_results: int = 100) -> List[EmailMessage]:
        """Fetch messages from a single account."""
        messages = []
        
        try:
            # Get message list
            results = account.service.users().messages().list(
                userId='me', 
                maxResults=max_results,
                labelIds=['INBOX']
            ).execute()
            
            message_list = results.get('messages', [])
            
            for msg_info in message_list:
                if self._stop_event.is_set():
                    break
                
                try:
                    msg = account.service.users().messages().get(
                        userId='me', 
                        id=msg_info['id'],
                        format='full'
                    ).execute()
                    
                    email_msg = self._parse_message(msg, account)
                    if email_msg:
                        messages.append(email_msg)
                        
                except Exception as e:
                    print(f"Error fetching message {msg_info['id']}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error fetching from {account.account_name}: {e}")
        
        return messages
    
    def _parse_message(self, msg: dict, account: GmailAccount) -> Optional[EmailMessage]:
        """Parse Gmail API message into EmailMessage."""
        try:
            headers = msg.get('payload', {}).get('headers', [])
            
            def get_header(name):
                for h in headers:
                    if h['name'].lower() == name.lower():
                        return h['value']
                return ''
            
            # Extract data
            subject = get_header('Subject') or '(No Subject)'
            sender = get_header('From') or '(Unknown)'
            recipient = get_header('To') or ''
            date_str = get_header('Date') or ''
            
            # Get body
            body = self._extract_body(msg.get('payload', {}))
            
            # Parse date
            internal_date = int(msg.get('internalDate', 0)) // 1000
            date_formatted = datetime.fromtimestamp(internal_date).strftime('%b %d, %H:%M')
            
            # Labels
            labels = msg.get('labelIds', [])
            is_read = 'UNREAD' not in labels
            is_starred = 'STARRED' in labels
            
            return EmailMessage(
                message_id=msg['id'],
                thread_id=msg['threadId'],
                account_email=account.email_address,
                account_name=account.account_name,
                sender=sender,
                recipient=recipient,
                subject=subject,
                body=body,
                snippet=msg.get('snippet', ''),
                date=date_formatted,
                labels=labels,
                is_read=is_read,
                is_starred=is_starred,
                internal_date=internal_date
            )
            
        except Exception as e:
            print(f"Error parsing message: {e}")
            return None
    
    def _extract_body(self, payload: dict) -> str:
        """Extract text body from message payload."""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                mime_type = part.get('mimeType', '')
                if mime_type == 'text/plain':
                    data = part.get('body', {}).get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        break
                elif mime_type == 'text/html':
                    # Use HTML if no plain text
                    if not body:
                        data = part.get('body', {}).get('data', '')
                        if data:
                            html = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                            # Simple HTML to text conversion
                            body = re.sub(r'<[^>]+>', ' ', html)
                            body = re.sub(r'\s+', ' ', body).strip()
        else:
            # Single part message
            data = payload.get('body', {}).get('data', '')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        
        return body
    
    # ===============================
    # UI UPDATE METHODS
    # ===============================
    
    def _populate_message_list(self):
        """Populate the message treeview."""
        self.message_tree.delete(*self.message_tree.get_children())
        
        for msg in self.filtered_messages:
            # Format sender (extract email from "Name <email>")
            sender_display = msg.sender
            if '<' in sender_display:
                sender_display = sender_display.split('<')[0].strip()
            if len(sender_display) > 25:
                sender_display = sender_display[:22] + "..."
            
            # Format subject with unread indicator
            subject_display = msg.subject
            if len(subject_display) > 40:
                subject_display = subject_display[:37] + "..."
            
            # Add visual indicator for unread
            if not msg.is_read:
                subject_display = "● " + subject_display
            
            # Font weight for unread
            tags = ()
            if not msg.is_read:
                tags = ('unread',)
                self.message_tree.tag_configure('unread', font=('Segoe UI Semibold', 10))
            
            self.message_tree.insert('', 'end', values=(
                sender_display,
                subject_display,
                msg.account_name,
                msg.date
            ), tags=tags)
    
    def _on_message_select(self, event):
        """Handle message selection."""
        selection = self.message_tree.selection()
        if not selection:
            return
        
        idx = self.message_tree.index(selection[0])
        if 0 <= idx < len(self.filtered_messages):
            self.selected_message = self.filtered_messages[idx]
            self._show_message_detail(self.selected_message)
    
    def _on_message_double_click(self, event):
        """Handle double-click on message."""
        self._on_message_select(event)
        # Could open in new window here
    
    def _show_message_detail(self, msg: EmailMessage):
        """Display message in detail view."""
        # Hide empty state, show detail
        self.empty_state.place_forget()
        self.detail_view.pack(fill="both", expand=True)
        
        # Update fields
        self.lbl_detail_subject.configure(text=msg.subject)
        self.lbl_detail_from.configure(text=f"From: {msg.sender}")
        self.lbl_detail_to.configure(text=f"To: {msg.recipient}")
        self.lbl_detail_date.configure(text=f"Date: {msg.date} | Account: {msg.account_name}")
        
        # Show read status indicator
        read_status = "✓ Read" if msg.is_read else "● Unread"
        read_color = self.COLORS["green"] if msg.is_read else self.COLORS["accent"]
        self.lbl_read_status.configure(text=read_status, fg=read_color)
        
        # Update body
        self.txt_body.configure(state="normal")
        self.txt_body.delete("1.0", "end")
        self.txt_body.insert("1.0", msg.body)
        self.txt_body.configure(state="disabled")
        
        # Mark as read on Gmail if currently unread
        if not msg.is_read:
            self._mark_message_as_read(msg)
    
    def _update_stats(self):
        """Update sidebar statistics."""
        total = len(self.all_messages)
        unread = sum(1 for m in self.all_messages if not m.is_read)
        
        self.lbl_total_accounts.configure(text=str(len(self.accounts)))
        self.lbl_total_messages.configure(text=str(total))
        self.lbl_unread_count.configure(text=str(unread))
    
    def _filter_messages(self, filter_type: str):
        """Filter messages by type."""
        if filter_type == "all":
            self.filtered_messages = self.all_messages.copy()
        elif filter_type == "unread":
            self.filtered_messages = [m for m in self.all_messages if not m.is_read]
        elif filter_type == "starred":
            self.filtered_messages = [m for m in self.all_messages if m.is_starred]
        elif filter_type == "sent":
            # TODO: Fetch sent messages separately
            self.filtered_messages = []
        elif filter_type == "trash":
            # TODO: Fetch trash separately
            self.filtered_messages = []
        
        self._populate_message_list()
        self.lbl_message_count.configure(text=f"{len(self.filtered_messages)} messages")
    
    def _on_search_change(self):
        """Handle search box changes."""
        query = self.search_var.get().lower()
        
        if not query:
            self.filtered_messages = self.all_messages.copy()
        else:
            self.filtered_messages = [
                m for m in self.all_messages
                if query in m.subject.lower() 
                or query in m.sender.lower()
                or query in m.body.lower()
                or query in m.account_name.lower()
            ]
        
        self._populate_message_list()
        self.lbl_message_count.configure(text=f"{len(self.filtered_messages)} messages")
    
    # ===============================
    # MESSAGE ACTIONS
    # ===============================
    
    def _reply_message(self):
        """Open reply dialog."""
        if not self.selected_message:
            return
        
        msg = self.selected_message
        
        # Create reply window
        reply_win = tk.Toplevel(self)
        reply_win.title(f"Reply to: {msg.subject}")
        reply_win.geometry("700x500")
        reply_win.configure(bg=self.COLORS["card"])
        
        # Header
        header = tk.Frame(reply_win, bg=self.COLORS["card"], padx=20, pady=15)
        header.pack(fill="x")
        
        tk.Label(header, text=f"To: {msg.sender}", bg=self.COLORS["card"],
                fg=self.COLORS["fg"], font=("Segoe UI", 11)).pack(anchor="w")
        
        tk.Label(header, text=f"Subject: Re: {msg.subject}", bg=self.COLORS["card"],
                fg=self.COLORS["fg"], font=("Segoe UI", 11)).pack(anchor="w", pady=(5, 0))
        
        # Body
        body_frame = tk.Frame(reply_win, bg=self.COLORS["card"], padx=20)
        body_frame.pack(fill="both", expand=True, pady=10)
        
        txt_reply = scrolledtext.ScrolledText(body_frame, wrap=tk.WORD,
                                             bg=self.COLORS["entry_bg"],
                                             fg=self.COLORS["fg"],
                                             font=("Segoe UI", 11),
                                             relief="flat",
                                             insertbackground="white")
        txt_reply.pack(fill="both", expand=True)
        
        # Insert quoted original
        quoted = f"\n\n--- Original Message ---\nFrom: {msg.sender}\nDate: {msg.date}\n\n{msg.body[:500]}..."
        txt_reply.insert("1.0", quoted)
        
        # Buttons
        btn_frame = tk.Frame(reply_win, bg=self.COLORS["card"], padx=20, pady=15)
        btn_frame.pack(fill="x")
        
        def do_reply():
            body = txt_reply.get("1.0", "end").strip()
            if self._send_reply(msg, body):
                reply_win.destroy()
                messagebox.showinfo("Sent", "Reply sent successfully!")
            else:
                messagebox.showerror("Error", "Failed to send reply.")
        
        tk.Button(btn_frame, text="Send Reply", bg=self.COLORS["accent"],
                 fg="white", font=("Segoe UI Bold", 10),
                 relief="flat", padx=25, pady=10,
                 cursor="hand2", command=do_reply).pack(side="left")
        
        tk.Button(btn_frame, text="Cancel", bg=self.COLORS["panel"],
                 fg=self.COLORS["fg"], font=("Segoe UI", 10),
                 relief="flat", padx=20, pady=10,
                 cursor="hand2", command=reply_win.destroy).pack(side="left", padx=10)
    
    def _send_reply(self, original: EmailMessage, body: str) -> bool:
        """Send reply via Gmail API."""
        if not _HAS_GOOGLE_API:
            return False
        
        try:
            # Find account
            account = None
            for acc in self.accounts:
                if acc.email_address == original.account_email and acc.authenticated:
                    account = acc
                    break
            
            if not account:
                return False
            
            # Create reply message
            message = MIMEMultipart()
            message['to'] = original.sender
            message['subject'] = f"Re: {original.subject}"
            message['In-Reply-To'] = original.message_id
            message['References'] = original.message_id
            
            msg_body = MIMEText(body, 'plain')
            message.attach(msg_body)
            
            # Encode and send
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            account.service.users().messages().send(
                userId='me',
                body={'raw': raw, 'threadId': original.thread_id}
            ).execute()
            
            return True
            
        except Exception as e:
            print(f"Error sending reply: {e}")
            return False
    
    def _delete_message(self):
        """Delete selected message immediately without confirmation."""
        if not self.selected_message:
            return
        
        msg = self.selected_message
        
        # Find account and delete directly without confirmation
        for acc in self.accounts:
            if acc.email_address == msg.account_email and acc.authenticated:
                try:
                    acc.service.users().messages().trash(
                        userId='me',
                        id=msg.message_id
                    ).execute()
                    
                    # Remove from lists safely
                    try:
                        self.all_messages.remove(msg)
                    except ValueError:
                        pass
                    try:
                        if msg in self.filtered_messages:
                            self.filtered_messages.remove(msg)
                    except ValueError:
                        pass
                    
                    self._populate_message_list()
                    self._update_stats()
                    
                    # Hide detail view
                    self.detail_view.pack_forget()
                    self.empty_state.place(relx=0.5, rely=0.5, anchor="center")
                    
                    # Show success notification
                    self._show_notification("🗑️ Deleted", "Message moved to trash successfully", "success", 3000)
                    return
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete: {e}")
                    return
    
    def _star_message(self):
        """Star/unstar selected message."""
        if not self.selected_message:
            return
        
        msg = self.selected_message
        
        for acc in self.accounts:
            if acc.email_address == msg.account_email and acc.authenticated:
                try:
                    if msg.is_starred:
                        acc.service.users().messages().modify(
                            userId='me',
                            id=msg.message_id,
                            body={'removeLabelIds': ['STARRED']}
                        ).execute()
                        msg.is_starred = False
                    else:
                        acc.service.users().messages().modify(
                            userId='me',
                            id=msg.message_id,
                            body={'addLabelIds': ['STARRED']}
                        ).execute()
                        msg.is_starred = True
                    
                    self._populate_message_list()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to star: {e}")
                return
    
    def _mark_message_as_read(self, msg: EmailMessage):
        """Mark message as read on Gmail and update local state."""
        for acc in self.accounts:
            if acc.email_address == msg.account_email and acc.authenticated:
                try:
                    acc.service.users().messages().modify(
                        userId='me',
                        id=msg.message_id,
                        body={'removeLabelIds': ['UNREAD']}
                    ).execute()
                    
                    # Update local state
                    msg.is_read = True
                    if 'UNREAD' in msg.labels:
                        msg.labels.remove('UNREAD')
                    
                    # Refresh the message list to show updated read status
                    self._populate_message_list()
                    self._update_stats()
                    
                except Exception as e:
                    print(f"Error marking as read: {e}")
                return
    
    def _manual_mark_read(self):
        """Manually mark selected message as read (button action)."""
        if not self.selected_message:
            return
        
        if self.selected_message.is_read:
            self._show_notification("Already Read", "This message is already marked as read", "info", 2000)
            return
        
        self._mark_message_as_read(self.selected_message)
        self._show_notification("✓ Marked as Read", "Message has been marked as read", "success", 2000)
    
    def _open_in_gmail(self):
        """Open message in Gmail web interface."""
        if not self.selected_message:
            return
        
        msg = self.selected_message
        url = f"https://mail.google.com/mail/u/{msg.account_email}/#inbox/{msg.message_id}"
        webbrowser.open(url)
    
    # ===============================
    # SENDER FILTER & BULK DELETE
    # ===============================
    
    def _show_sender_filter_dialog(self):
        """Show dialog to filter by sender and bulk delete."""
        dialog = tk.Toplevel(self)
        dialog.title("Sender Filter & Bulk Delete")
        dialog.geometry("800x600")
        dialog.configure(bg=self.COLORS["card"])
        dialog.transient(self)
        dialog.grab_set()
        
        # Header
        header = tk.Frame(dialog, bg=self.COLORS["accent"], height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="🔍 SENDER FILTER & BULK DELETE", bg=self.COLORS["accent"],
                fg="white", font=("Segoe UI Black", 16)).pack(expand=True)
        
        # Content
        content = tk.Frame(dialog, bg=self.COLORS["card"], padx=30, pady=20)
        content.pack(fill="both", expand=True)
        
        # Sender input
        tk.Label(content, text="Enter sender email or name to filter:", bg=self.COLORS["card"],
                fg=self.COLORS["fg"], font=("Segoe UI", 11)).pack(anchor="w")
        
        sender_frame = tk.Frame(content, bg=self.COLORS["card"])
        sender_frame.pack(fill="x", pady=10)
        
        sender_var = tk.StringVar()
        sender_entry = tk.Entry(sender_frame, textvariable=sender_var, bg=self.COLORS["entry_bg"],
                               fg=self.COLORS["fg"], font=("Segoe UI", 11), relief="flat",
                               insertbackground="white")
        sender_entry.pack(side="left", fill="x", expand=True)
        
        # Results count
        result_label = tk.Label(content, text="", bg=self.COLORS["card"],
                               fg=self.COLORS["fg_dim"], font=("Segoe UI", 10))
        result_label.pack(anchor="w", pady=5)
        
        # Message list
        list_frame = tk.Frame(content, bg=self.COLORS["card"])
        list_frame.pack(fill="both", expand=True, pady=10)
        
        columns = ("sender", "subject", "account", "date")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                           style="Custom.Treeview", height=15)
        
        tree.heading("sender", text="FROM")
        tree.heading("subject", text="SUBJECT")
        tree.heading("account", text="ACCOUNT")
        tree.heading("date", text="DATE")
        
        tree.column("sender", width=200)
        tree.column("subject", width=280)
        tree.column("account", width=130)
        tree.column("date", width=130)
        
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        # Store filtered messages
        filtered_msgs = []
        
        def apply_filter(*args):
            """Filter messages by sender."""
            nonlocal filtered_msgs
            tree.delete(*tree.get_children())
            filtered_msgs.clear()
            
            query = sender_var.get().lower().strip()
            if not query:
                result_label.configure(text="Enter a sender name or email to filter")
                return
            
            for msg in self.all_messages:
                if query in msg.sender.lower():
                    filtered_msgs.append(msg)
                    sender_display = msg.sender.split('<')[0].strip() if '<' in msg.sender else msg.sender
                    if len(sender_display) > 25:
                        sender_display = sender_display[:22] + "..."
                    subject_display = msg.subject[:37] + "..." if len(msg.subject) > 40 else msg.subject
                    tree.insert('', 'end', values=(sender_display, subject_display, msg.account_name, msg.date))
            
            result_label.configure(text=f"Found {len(filtered_msgs)} messages from sender containing '{query}'")
        
        sender_var.trace_add("write", apply_filter)
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.COLORS["card"], padx=30, pady=20)
        btn_frame.pack(fill="x")
        
        def select_all():
            """Select all items in tree."""
            for item in tree.get_children():
                tree.selection_add(item)
            count = len(tree.get_children())
            result_label.configure(text=f"Selected {count} messages")
        
        def delete_selected():
            """Delete all selected messages."""
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("No Selection", "Please select messages to delete.")
                return
            
            count = len(selected)
            if not messagebox.askyesno("Confirm Delete", 
                                       f"Are you sure you want to delete {count} messages?\n\nThis action cannot be undone!"):
                return
            
            deleted = 0
            failed = 0
            
            for item in selected:
                idx = tree.index(item)
                if 0 <= idx < len(filtered_msgs):
                    msg = filtered_msgs[idx]
                    
                    # Find account and delete
                    for acc in self.accounts:
                        if acc.email_address == msg.account_email and acc.authenticated:
                            try:
                                acc.service.users().messages().trash(
                                    userId='me',
                                    id=msg.message_id
                                ).execute()
                                
                                # Remove from lists
                                if msg in self.all_messages:
                                    self.all_messages.remove(msg)
                                if msg in self.filtered_messages:
                                    self.filtered_messages.remove(msg)
                                
                                deleted += 1
                            except Exception as e:
                                print(f"Error deleting: {e}")
                                failed += 1
                            break
            
            # Refresh UI
            self._populate_message_list()
            self._update_stats()
            
            dialog.destroy()
            self._show_notification("Bulk Delete Complete", 
                                   f"✓ Deleted: {deleted}\n✗ Failed: {failed}",
                                   "success" if failed == 0 else "warning")
        
        tk.Button(btn_frame, text="☑ Select All", bg=self.COLORS["accent"],
                 fg="white", font=("Segoe UI Semibold", 10), relief="flat",
                 padx=20, pady=8, cursor="hand2", command=select_all).pack(side="left", padx=5)
        
        tk.Button(btn_frame, text="🗑 Delete Selected", bg=self.COLORS["red"],
                 fg="white", font=("Segoe UI Semibold", 10), relief="flat",
                 padx=20, pady=8, cursor="hand2", command=delete_selected).pack(side="left", padx=5)
        
        tk.Button(btn_frame, text="Cancel", bg=self.COLORS["panel"],
                 fg=self.COLORS["fg"], font=("Segoe UI", 10), relief="flat",
                 padx=20, pady=8, cursor="hand2", command=dialog.destroy).pack(side="left", padx=10)
    
    # ===============================
    # ACCOUNT MANAGEMENT
    # ===============================
    
    def _add_account_dialog(self):
        """Open dialog to add new account."""
        dialog = tk.Toplevel(self)
        dialog.title("Add Gmail Account")
        dialog.geometry("500x300")
        dialog.configure(bg=self.COLORS["card"])
        dialog.transient(self)
        dialog.grab_set()
        
        # Form
        frame = tk.Frame(dialog, bg=self.COLORS["card"], padx=30, pady=30)
        frame.pack(fill="both", expand=True)
        
        tk.Label(frame, text="Add New Gmail Account", bg=self.COLORS["card"],
                fg=self.COLORS["fg"], font=("Segoe UI Black", 14)).pack(anchor="w")
        
        tk.Label(frame, text="Account Name:", bg=self.COLORS["card"],
                fg=self.COLORS["fg_dim"], font=("Segoe UI", 10)).pack(anchor="w", pady=(20, 5))
        
        name_var = tk.StringVar()
        tk.Entry(frame, textvariable=name_var, bg=self.COLORS["entry_bg"],
                fg=self.COLORS["fg"], font=("Segoe UI", 11), relief="flat",
                insertbackground="white").pack(fill="x", pady=5)
        
        tk.Label(frame, text="Credentials JSON File:", bg=self.COLORS["card"],
                fg=self.COLORS["fg_dim"], font=("Segoe UI", 10)).pack(anchor="w", pady=(15, 5))
        
        creds_frame = tk.Frame(frame, bg=self.COLORS["card"])
        creds_frame.pack(fill="x", pady=5)
        
        creds_var = tk.StringVar()
        tk.Entry(creds_frame, textvariable=creds_var, bg=self.COLORS["entry_bg"],
                fg=self.COLORS["fg"], font=("Segoe UI", 11), relief="flat",
                insertbackground="white").pack(side="left", fill="x", expand=True)
        
        def browse_creds():
            path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
            if path:
                creds_var.set(path)
                if not name_var.get():
                    name_var.set(Path(path).stem.title())
        
        tk.Button(creds_frame, text="Browse...", bg=self.COLORS["panel"],
                 fg=self.COLORS["fg"], relief="flat", command=browse_creds).pack(side="left", padx=5)
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.COLORS["card"], padx=30, pady=20)
        btn_frame.pack(fill="x")
        
        def save_account():
            name = name_var.get().strip()
            creds = creds_var.get().strip()
            
            if not name or not creds:
                messagebox.showerror("Error", "Please fill all fields.")
                return
            
            if not Path(creds).exists():
                messagebox.showerror("Error", "Credentials file not found.")
                return
            
            # Add account
            account = GmailAccount(credentials_path=creds, account_name=name)
            self.accounts.append(account)
            self._save_accounts()
            self._update_stats()
            
            dialog.destroy()
            
            # Offer to authenticate
            if messagebox.askyesno("Authenticate", f"Authenticate {name} now?"):
                threading.Thread(target=lambda: (
                    self._authenticate_account(account),
                    self._ui(self._update_stats)
                ), daemon=True).start()
        
        tk.Button(btn_frame, text="Add Account", bg=self.COLORS["accent"],
                 fg="white", font=("Segoe UI Bold", 10), relief="flat",
                 padx=25, pady=10, cursor="hand2", command=save_account).pack(side="left")
        
        tk.Button(btn_frame, text="Cancel", bg=self.COLORS["panel"],
                 fg=self.COLORS["fg"], font=("Segoe UI", 10), relief="flat",
                 padx=20, pady=10, cursor="hand2", command=dialog.destroy).pack(side="left", padx=10)
    
    def _show_account_manager(self):
        """Show account management window."""
        win = tk.Toplevel(self)
        win.title("Manage Accounts")
        win.geometry("800x500")
        win.configure(bg=self.COLORS["bg"])
        
        # Header
        header = tk.Frame(win, bg=self.COLORS["panel"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="Account Management", bg=self.COLORS["panel"],
                fg=self.COLORS["fg"], font=("Segoe UI Black", 14)).pack(side="left", padx=20)
        
        tk.Button(header, text="➕ Add New", bg=self.COLORS["accent"],
                 fg="white", font=("Segoe UI Semibold", 10), relief="flat",
                 padx=15, pady=5, cursor="hand2", command=lambda: (win.destroy(), self._add_account_dialog())).pack(side="right", padx=20)
        
        # Account list
        list_frame = tk.Frame(win, bg=self.COLORS["bg"])
        list_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        columns = ("name", "email", "status", "actions")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                           style="Custom.Treeview", height=15)
        
        tree.heading("name", text="ACCOUNT NAME")
        tree.heading("email", text="EMAIL ADDRESS")
        tree.heading("status", text="STATUS")
        tree.heading("actions", text="ACTIONS")
        
        tree.column("name", width=150)
        tree.column("email", width=250)
        tree.column("status", width=100)
        tree.column("actions", width=150)
        
        # Scrollbar
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        # Populate - show simple offline status unless there's an actual error
        for acc in self.accounts:
            status = "✅ Online" if acc.authenticated else "❌ Offline"
            # Only show error if account is NOT authenticated AND has an error
            if not acc.authenticated and acc.last_error:
                status = f"⚠️ Error"
            
            tree.insert('', 'end', values=(acc.account_name, acc.email_address, status, ''))
        
        # Button frame below tree
        btn_frame = tk.Frame(win, bg=self.COLORS["bg"])
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        def refresh_status():
            """Refresh account statuses in the tree."""
            for i, acc in enumerate(self.accounts):
                item = tree.get_children()[i] if i < len(tree.get_children()) else None
                if item:
                    status = "✅ Online" if acc.authenticated else "❌ Offline"
                    if acc.last_error and not acc.authenticated:
                        status = f"⚠️ {acc.last_error[:25]}..."
                    tree.item(item, values=(acc.account_name, acc.email_address, status, ''))
        
        tk.Button(btn_frame, text="🔄 Refresh Status", bg=self.COLORS["panel"],
                 fg=self.COLORS["fg"], font=("Segoe UI Semibold", 10), relief="flat",
                 padx=20, pady=8, cursor="hand2", command=refresh_status).pack(side="left", padx=5)
        
        def authenticate_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select Account", "Please select an account first.")
                return
            idx = tree.index(sel[0])
            if 0 <= idx < len(self.accounts):
                acc = self.accounts[idx]
                if acc.authenticated:
                    messagebox.showinfo("Already Connected", f"{acc.account_name} is already authenticated.")
                    return
                    
                def auth_worker():
                    self._ui(lambda: tree.item(sel[0], values=(acc.account_name, acc.email_address, 
                                                               "🔐 Authenticating...", '')))
                    success = self._authenticate_account(acc)
                    
                    if success:
                        self._ui(lambda: (
                            tree.item(sel[0], values=(acc.account_name, acc.email_address, "✅ Online", "")),
                            self._update_stats()
                        ))
                    else:
                        self._ui(lambda: tree.item(sel[0], values=(acc.account_name, acc.email_address, 
                                                                  f"⚠️ Error: {acc.last_error[:40]}...", '')))
                
                threading.Thread(target=auth_worker, daemon=True).start()
        
        tk.Button(btn_frame, text="🔐 Connect Selected", bg=self.COLORS["accent"],
                 fg="white", font=("Segoe UI Semibold", 10), relief="flat",
                 padx=20, pady=8, cursor="hand2", command=authenticate_selected).pack(side="left", padx=5)
        
        # Double-click to see error details
        def on_double_click(event):
            sel = tree.selection()
            if sel:
                idx = tree.index(sel[0])
                if 0 <= idx < len(self.accounts):
                    acc = self.accounts[idx]
                    if acc.last_error:
                        messagebox.showerror("Error Details", 
                                           f"Account: {acc.account_name}\n\nError:\n{acc.last_error}\n\n" +
                                           f"Credentials File:\n{acc.credentials_path}")
                    elif acc.authenticated:
                        messagebox.showinfo("Account Info", 
                                           f"Account: {acc.account_name}\nEmail: {acc.email_address}\nStatus: Online")
        
        tree.bind("<Double-1>", on_double_click)
        
        # Context menu
        def delete_account():
            sel = tree.selection()
            if sel:
                idx = tree.index(sel[0])
                if 0 <= idx < len(self.accounts):
                    acc = self.accounts[idx]
                    if messagebox.askyesno("Confirm", f"Remove {acc.account_name}?"):
                        self.accounts.pop(idx)
                        self._save_accounts()
                        tree.delete(sel[0])
                        self._update_stats()
        
        menu = tk.Menu(tree, tearoff=0)
        menu.add_command(label="Remove Account", command=delete_account)
        
        def show_menu(event):
            sel = tree.identify_row(event.y)
            if sel:
                tree.selection_set(sel)
                menu.post(event.x_root, event.y_root)
        
        tree.bind("<Button-3>", show_menu)
    
    # ===============================
    # AUTO-DISCOVERY & BULK IMPORT
    # ===============================
    
    def _discover_credentials(self, folder_path: str) -> List[dict]:
        """Auto-discover all valid credential files in a folder."""
        discovered = []
        folder = Path(folder_path)
        
        if not folder.exists():
            return discovered
        
        # Look for all JSON files
        json_files = list(folder.glob("*.json"))
        
        for file_path in json_files:
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                
                # Check if it's a token file (our format)
                if 'token' in data and 'refresh_token' in data:
                    email = data.get('account_email', '')
                    name = data.get('account_id', file_path.stem)
                    
                    # Clean up name
                    name = name.replace('_', ' ').title()
                    if '_credentials' in name.lower():
                        name = name.replace('_credentials', '').replace('Credentials', '')
                    
                    discovered.append({
                        'path': str(file_path),
                        'name': name,
                        'email': email,
                        'type': 'token'
                    })
            except Exception:
                continue
        
        return discovered
    
    def _bulk_import_dialog(self):
        """Open bulk import dialog for importing multiple accounts at once."""
        dialog = tk.Toplevel(self)
        dialog.title("Bulk Import Accounts")
        dialog.geometry("700x550")
        dialog.configure(bg=self.COLORS["card"])
        dialog.transient(self)
        dialog.grab_set()
        
        # Header
        header = tk.Frame(dialog, bg=self.COLORS["accent"], height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="📁 BULK ACCOUNT IMPORT", bg=self.COLORS["accent"],
                fg="white", font=("Segoe UI Black", 16)).pack(expand=True)
        
        # Content
        content = tk.Frame(dialog, bg=self.COLORS["card"], padx=30, pady=20)
        content.pack(fill="both", expand=True)
        
        tk.Label(content, text="Select folder containing all credential files:",
                bg=self.COLORS["card"], fg=self.COLORS["fg"],
                font=("Segoe UI", 11)).pack(anchor="w")
        
        # Folder selection
        folder_frame = tk.Frame(content, bg=self.COLORS["card"])
        folder_frame.pack(fill="x", pady=10)
        
        folder_var = tk.StringVar()
        tk.Entry(folder_frame, textvariable=folder_var, bg=self.COLORS["entry_bg"],
                fg=self.COLORS["fg"], font=("Segoe UI", 11), relief="flat").pack(side="left", fill="x", expand=True)
        
        def browse_folder():
            path = filedialog.askdirectory()
            if path:
                folder_var.set(path)
                scan_folder(path)
        
        tk.Button(folder_frame, text="Browse...", bg=self.COLORS["panel"],
                 fg=self.COLORS["fg"], relief="flat", command=browse_folder).pack(side="left", padx=5)
        
        # Discovered accounts list
        tk.Label(content, text="Discovered Accounts:", bg=self.COLORS["card"],
                fg=self.COLORS["fg"], font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(15, 5))
        
        list_frame = tk.Frame(content, bg=self.COLORS["card"])
        list_frame.pack(fill="both", expand=True)
        
        # Treeview for discovered accounts
        columns = ("name", "email", "status")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                           style="Custom.Treeview", height=10)
        
        tree.heading("name", text="ACCOUNT NAME")
        tree.heading("email", text="EMAIL")
        tree.heading("status", text="STATUS")
        
        tree.column("name", width=200)
        tree.column("email", width=250)
        tree.column("status", width=100)
        
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        
        # Status label - MUST be defined before scan_folder
        status_label = tk.Label(content, text="No folder selected", bg=self.COLORS["card"],
                                fg=self.COLORS["fg_dim"], font=("Segoe UI", 10))
        status_label.pack(anchor="w", pady=5)
        
        discovered_accounts = []
        
        # Use a nonlocal or object attribute to persist across function calls
        discovered_accounts_ref = {'accounts': []}
        
        # Buttons - MUST be defined before scan_folder function
        btn_frame = tk.Frame(dialog, bg=self.COLORS["card"], padx=30, pady=20)
        btn_frame.pack(fill="x")
        
        add_btn = tk.Button(btn_frame, text="➕ Add Selected", bg=self.COLORS["accent"],
                 fg="white", font=("Segoe UI Semibold", 10), relief="flat",
                 padx=20, pady=8, cursor="hand2")
        add_btn.pack(side="left", padx=5)
        add_btn.configure(state="disabled")
        
        import_btn = PremiumButton(btn_frame, "📥 Import All", lambda: None, "success")
        import_btn.pack(side="left")
        import_btn.btn.configure(state="disabled")
        
        cancel_btn = tk.Button(btn_frame, text="Cancel", bg=self.COLORS["panel"],
                 fg=self.COLORS["fg"], font=("Segoe UI", 10), relief="flat",
                 padx=20, pady=8, cursor="hand2", command=dialog.destroy)
        cancel_btn.pack(side="left", padx=10)
        
        def add_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Select Account", "Please select an account first.")
                return
            idx = tree.index(sel[0])
            if 0 <= idx < len(discovered_accounts_ref['accounts']):
                acc_data = discovered_accounts_ref['accounts'][idx]
                exists = any(a.credentials_path == acc_data['path'] for a in self.accounts)
                if exists:
                    messagebox.showinfo("Already Exists", f"{acc_data['name']} is already in your accounts.")
                    return
                account = GmailAccount(
                    credentials_path=acc_data['path'],
                    account_name=acc_data['name'],
                    email_address=acc_data['email']
                )
                self.accounts.append(account)
                self._save_accounts()
                self._update_stats()
                tree.delete(sel[0])
                discovered_accounts_ref['accounts'].pop(idx)
                self._show_notification("Account Added", f"{acc_data['name']} added!", "success")
                threading.Thread(target=lambda: (self._authenticate_account(account), self._ui(self._update_stats)), daemon=True).start()
        
        add_btn.configure(command=add_selected)
        
        def import_all():
            accounts_to_import = discovered_accounts_ref['accounts']
            if not accounts_to_import:
                messagebox.showwarning("No Accounts", "No accounts discovered to import.\nPlease select a folder first.")
                return
            
            added = 0
            skipped = 0
            for acc_data in accounts_to_import:
                # Check if already exists
                exists = any(a.credentials_path == acc_data['path'] for a in self.accounts)
                if not exists:
                    account = GmailAccount(
                        credentials_path=acc_data['path'],
                        account_name=acc_data['name'],
                        email_address=acc_data['email']
                    )
                    self.accounts.append(account)
                    added += 1
                else:
                    skipped += 1
            
            self._save_accounts()
            self._update_stats()
            
            dialog.destroy()
            
            if added > 0:
                self._show_notification("Import Complete", 
                                       f"✓ Added {added} accounts\n⚠ Skipped {skipped} (already exist)",
                                       "success")
                
                # Auto-authenticate all new accounts
                self._authenticate_all_accounts()
            else:
                messagebox.showinfo("Import Complete", f"No new accounts added.\n{skipped} accounts already exist.")
        
        import_btn.btn.configure(command=import_all)
        
        def scan_folder(path):
            tree.delete(*tree.get_children())
            discovered_accounts.clear()
            discovered_accounts_ref['accounts'].clear()
            
            discovered = self._discover_credentials(path)
            
            for acc in discovered:
                discovered_accounts.append(acc)
                discovered_accounts_ref['accounts'].append(acc)
                status = "✓ Ready" if acc['email'] else "? Needs Auth"
                tree.insert('', 'end', values=(acc['name'], acc['email'], status))
            
            status_label.configure(text=f"Found {len(discovered)} accounts")
            if len(discovered) > 0:
                import_btn.btn.configure(state="normal")
                add_btn.configure(state="normal")
    
    def _authenticate_all_accounts(self):
        """Bulk authenticate all offline accounts."""
        def auth_worker():
            total = len(self.accounts)
            authenticated = 0
            failed = 0
            
            for idx, account in enumerate(self.accounts):
                if account.authenticated:
                    continue
                
                self._ui(lambda a=account: self._show_notification(
                    "Authenticating", f"Connecting {a.account_name}...", "info", 2000))
                
                if self._authenticate_account(account):
                    authenticated += 1
                else:
                    failed += 1
                
                # Small delay to prevent rate limiting
                time.sleep(0.5)
            
            if authenticated > 0:
                self._ui(lambda: self._show_notification(
                    "Authentication Complete", 
                    f"✓ {authenticated} accounts connected\n✗ {failed} failed",
                    "success" if failed == 0 else "warning"))
            
            self._ui(self._update_stats)
        
        threading.Thread(target=auth_worker, daemon=True).start()
    
    # ===============================
    # AUTO-SYNC & LIVE NOTIFICATIONS
    # ===============================
    
    def _start_auto_sync(self):
        """Start automatic background sync."""
        if not self.settings.get("auto_sync", True):
            return
        
        self._auto_sync_interval = self.settings.get("auto_sync_interval", 60)
        
        def auto_sync_worker():
            while not self._stop_event.is_set():
                try:
                    # Check for new messages every interval
                    time.sleep(self._auto_sync_interval)
                    
                    if self.accounts and not self._is_auto_syncing:
                        self._check_new_messages()
                        
                except Exception as e:
                    print(f"Auto-sync error: {e}")
        
        self._auto_sync_thread = threading.Thread(target=auto_sync_worker, daemon=True)
        self._auto_sync_thread.start()
        print(f"[AUTO-SYNC] Started with {self._auto_sync_interval}s interval")
    
    def _check_new_messages(self):
        """Quick check for new messages across all accounts."""
        if self._is_auto_syncing:
            return
        
        self._is_auto_syncing = True
        new_messages = []
        
        for account in self.accounts:
            if not account.authenticated:
                continue
            
            try:
                # Quick check - only get IDs of recent messages
                results = account.service.users().messages().list(
                    userId='me',
                    maxResults=10,
                    labelIds=['INBOX', 'UNREAD']
                ).execute()
                
                messages = results.get('messages', [])
                
                for msg_info in messages:
                    msg_id = msg_info['id']
                    # Check if this is a new message we haven't seen
                    cache_key = f"{account.email_address}:{msg_id}"
                    if cache_key not in self._last_message_ids:
                        self._last_message_ids.add(cache_key)
                        
                        # Get message details for notification
                        msg = account.service.users().messages().get(
                            userId='me',
                            id=msg_id,
                            format='metadata',
                            metadataHeaders=['Subject', 'From']
                        ).execute()
                        
                        headers = msg.get('payload', {}).get('headers', [])
                        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '(No Subject)')
                        sender = next((h['value'] for h in headers if h['name'] == 'From'), '(Unknown)')
                        
                        new_messages.append({
                            'subject': subject,
                            'sender': sender,
                            'account': account.account_name
                        })
                        
            except Exception as e:
                print(f"Error checking {account.account_name}: {e}")
        
        # Show notification for new messages
        if new_messages and self.settings.get("notifications", True):
            if len(new_messages) == 1:
                self._ui(lambda: self._show_notification(
                    "New Email",
                    f"From: {new_messages[0]['sender'][:30]}...\nSubject: {new_messages[0]['subject'][:40]}...",
                    "new_email",
                    8000
                ))
            else:
                self._ui(lambda: self._show_notification(
                    f"{len(new_messages)} New Emails",
                    f"From: {', '.join(m['account'] for m in new_messages[:3])}...",
                    "new_email",
                    8000
                ))
        
        # Refresh message list if new messages found
        if new_messages:
            self._ui(self._sync_all_accounts)
        
        self._is_auto_syncing = False
    
    def _show_notification(self, title: str, message: str, msg_type: str = "info", duration: int = 5000):
        """Show a toast notification."""
        if not self.settings.get("notifications", True):
            return
        ToastNotification(title, message, msg_type, duration)
    
    # ===============================
    # TOKEN REFRESH HANDLING
    # ===============================
    
    def _refresh_token_if_needed(self, account: GmailAccount) -> bool:
        """Refresh token if expired."""
        if not account.service:
            return False
        
        try:
            # Try a simple API call to check if token is valid
            account.service.users().getProfile(userId='me').execute()
            return True
        except HttpError as e:
            if e.resp.status == 401:
                # Token expired, try to refresh
                print(f"[TOKEN] Refreshing for {account.account_name}")
                return self._authenticate_account(account)
            raise
    
    def _refresh_all_tokens(self):
        """Refresh tokens for all authenticated accounts."""
        def refresh_worker():
            refreshed = 0
            for account in self.accounts:
                if account.authenticated:
                    if self._refresh_token_if_needed(account):
                        refreshed += 1
                    time.sleep(0.5)
            
            if refreshed > 0:
                self._ui(lambda: self._show_notification(
                    "Tokens Refreshed", f"Updated {refreshed} accounts", "success"))
        
        threading.Thread(target=refresh_worker, daemon=True).start()


# ===============================
# MAIN ENTRY
# ===============================


def main():
    import os
    root = tk.Tk()
    app = GmailAllMailboxApp(root)
    app.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()