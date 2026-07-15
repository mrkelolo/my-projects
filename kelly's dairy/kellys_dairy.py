#!/usr/bin/env python3
"""
Kelly's Dairy 🥛 v2.0
=====================
A beautiful, single-file note-taking app with a stunning UI.
Features: Taskbar with save button, gorgeous gradient background, 
pinning, tagging, search, and rock-solid save functionality.

Usage:
    python kellys_dairy.py

Requirements:
    Python 3.8+ with tkinter (usually included)
"""

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from tkinter import (
    Tk, Frame, Label, Button, Entry, Text, Scrollbar, Canvas,
    StringVar, IntVar, messagebox, simpledialog, filedialog,
    Toplevel, Menu, ttk, PhotoImage, Checkbutton, font as tkfont
)
from tkinter import TclError

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION & CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
APP_NAME = "Kelly's Dairy 🥛"
VERSION = "2.0"
DATA_FILE = "kellys_dairy_notes.json"
BACKUP_DIR = "kellys_dairy_backups"

# ═══════════════════════════════════════════════════════════════════════════
# DATA MANAGER — Rock-solid persistence
# ═══════════════════════════════════════════════════════════════════════════
class NoteManager:
    """Handles all note CRUD operations and persistence."""

    def __init__(self, data_file: str = DATA_FILE):
        self.data_file = Path(data_file).resolve()
        self.notes = []
        self.tags = set()
        self.load_notes()

    def load_notes(self):
        """Load notes from JSON file."""
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.notes = data.get("notes", [])
                    self.tags = set(data.get("tags", []))
            except (json.JSONDecodeError, IOError) as e:
                messagebox.showwarning(
                    "Load Error",
                    f"Could not load notes: {e}\nStarting with empty diary."
                )
                self.notes = []
                self.tags = set()
        else:
            self.notes = []
            self.tags = set()

    def save_notes(self):
        """Save notes to JSON file with backup."""
        try:
            # Create backup directory if needed
            backup_dir = Path(BACKUP_DIR).resolve()
            backup_dir.mkdir(exist_ok=True)

            # Backup existing file
            if self.data_file.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = backup_dir / f"notes_backup_{timestamp}.json"
                shutil.copy(self.data_file, backup_file)
                # Keep only last 10 backups
                backups = sorted(backup_dir.glob("notes_backup_*.json"))
                for old in backups[:-10]:
                    old.unlink()

            # Save current data
            data = {
                "app": APP_NAME,
                "version": VERSION,
                "last_saved": datetime.now().isoformat(),
                "notes": self.notes,
                "tags": sorted(list(self.tags))
            }
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            messagebox.showerror("Save Error", f"Could not save notes: {e}")
            return False

    def add_note(self, title: str, content: str, tags: list = None, 
                 category: str = "General", pinned: bool = False) -> dict:
        """Add a new note."""
        note = {
            "id": self._generate_id(),
            "title": title.strip(),
            "content": content.strip(),
            "tags": tags or [],
            "category": category,
            "pinned": pinned,
            "archived": False,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.notes.insert(0, note)
        if tags:
            self.tags.update(tags)
        self.save_notes()
        return note

    def update_note(self, note_id: str, **kwargs) -> bool:
        """Update an existing note."""
        for note in self.notes:
            if note["id"] == note_id:
                for key, value in kwargs.items():
                    if key in note:
                        note[key] = value
                note["updated_at"] = datetime.now().isoformat()
                if "tags" in kwargs:
                    self.tags.update(kwargs["tags"])
                self.save_notes()
                return True
        return False

    def delete_note(self, note_id: str) -> bool:
        """Delete a note permanently."""
        for i, note in enumerate(self.notes):
            if note["id"] == note_id:
                self.notes.pop(i)
                self.save_notes()
                return True
        return False

    def archive_note(self, note_id: str) -> bool:
        """Toggle archive status."""
        for note in self.notes:
            if note["id"] == note_id:
                note["archived"] = not note.get("archived", False)
                note["updated_at"] = datetime.now().isoformat()
                self.save_notes()
                return True
        return False

    def pin_note(self, note_id: str) -> bool:
        """Toggle pin status."""
        for note in self.notes:
            if note["id"] == note_id:
                note["pinned"] = not note.get("pinned", False)
                note["updated_at"] = datetime.now().isoformat()
                self.save_notes()
                return True
        return False

    def search_notes(self, query: str, include_archived: bool = False) -> list:
        """Search notes by title, content, or tags."""
        if not query.strip():
            return self.get_notes(include_archived=include_archived)

        query_lower = query.lower()
        results = []
        for note in self.notes:
            if not include_archived and note.get("archived", False):
                continue
            if (query_lower in note["title"].lower() or
                query_lower in note["content"].lower() or
                any(query_lower in tag.lower() for tag in note.get("tags", []))):
                results.append(note)
        return results

    def get_notes(self, include_archived: bool = False, 
                  tag_filter: str = None, category_filter: str = None) -> list:
        """Get notes with optional filters."""
        results = []
        for note in self.notes:
            if not include_archived and note.get("archived", False):
                continue
            if tag_filter and tag_filter not in note.get("tags", []):
                continue
            if category_filter and note.get("category") != category_filter:
                continue
            results.append(note)

        # Sort: pinned first, then by updated_at desc
        results.sort(key=lambda n: (-n.get("pinned", False), 
                                    n.get("updated_at", "")), reverse=True)
        return results

    def get_categories(self) -> list:
        """Get all unique categories."""
        cats = set(note.get("category", "General") for note in self.notes)
        return sorted(cats)

    def export_to_txt(self, filepath: str):
        """Export all notes to a text file."""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"{APP_NAME} - Export\n")
            f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("=" * 50 + "\n")
            for note in self.notes:
                if note.get("archived"):
                    continue
                f.write(f"📌 {note['title']}\n")
                f.write(f"   Category: {note.get('category', 'General')}\n")
                f.write(f"   Tags: {', '.join(note.get('tags', []))}\n")
                f.write(f"   Created: {note['created_at'][:10]}\n")
                f.write("-" * 40 + "\n")
                f.write(note['content'] + "\n")

    def _generate_id(self) -> str:
        """Generate unique note ID."""
        import uuid
        return str(uuid.uuid4())[:8]


# ═══════════════════════════════════════════════════════════════════════════
# CUSTOM WIDGETS
# ═══════════════════════════════════════════════════════════════════════════
class NoteCard(Frame):
    """A clickable card widget representing a single note."""

    def __init__(self, parent, note: dict, on_click, on_pin, on_archive, 
                 on_delete, colors, **kwargs):
        super().__init__(parent, **kwargs)
        self.note = note
        self.on_click = on_click
        self.on_pin = on_pin
        self.on_archive = on_archive
        self.on_delete = on_delete
        self.colors = colors

        self._build_ui()
        self._bind_events()

    def _build_ui(self):
        bg = self.colors["pinned"] if self.note.get("pinned") else self.colors["card_bg"]
        self.configure(bg=bg, padx=12, pady=12)

        # Title row
        title_frame = Frame(self, bg=bg)
        title_frame.pack(fill="x", pady=(0, 6))

        pin_icon = "📌" if self.note.get("pinned") else "  "
        lbl_pin = Label(title_frame, text=pin_icon, font=("Segoe UI", 12),
                       bg=bg, fg=self.colors["text_primary"])
        lbl_pin.pack(side="left")

        title_text = self.note["title"] or "Untitled Note"
        if len(title_text) > 30:
            title_text = title_text[:27] + "..."

        lbl_title = Label(title_frame, text=title_text, 
                         font=("Segoe UI", 11, "bold"),
                         bg=bg, fg=self.colors["text_primary"])
        lbl_title.pack(side="left", padx=(5, 0))

        # Date
        date_str = self.note.get("updated_at", "")[:10]
        lbl_date = Label(title_frame, text=date_str, 
                        font=("Segoe UI", 8),
                        bg=bg, fg=self.colors["text_muted"])
        lbl_date.pack(side="right")

        # Preview
        preview = self.note["content"].replace("\n", " ")[:60]
        if len(self.note["content"]) > 60:
            preview += "..."

        lbl_preview = Label(self, text=preview, font=("Segoe UI", 9),
                           bg=bg, fg=self.colors["text_muted"],
                           wraplength=280, justify="left")
        lbl_preview.pack(anchor="w", pady=(5, 5))

        # Tags
        if self.note.get("tags"):
            tags_frame = Frame(self, bg=bg)
            tags_frame.pack(anchor="w", pady=(0, 5))
            for tag in self.note["tags"][:3]:
                lbl_tag = Label(tags_frame, text=f"#{tag}", 
                               font=("Segoe UI", 7),
                               bg=self.colors["tag_bg"], fg=self.colors["text_muted"],
                               padx=4, pady=1)
                lbl_tag.pack(side="left", padx=(0, 4))

        # Action buttons
        btn_frame = Frame(self, bg=bg)
        btn_frame.pack(fill="x")

        pin_text = "Unpin" if self.note.get("pinned") else "Pin"
        btn_pin = Button(btn_frame, text=f"📍 {pin_text}", 
                        font=("Segoe UI", 8),
                        bg=self.colors["card_bg"], fg=self.colors["text_primary"],
                        relief="flat", cursor="hand2",
                        command=lambda: self.on_pin(self.note["id"]))
        btn_pin.pack(side="left", padx=(0, 2))

        arch_text = "Unarchive" if self.note.get("archived") else "Archive"
        btn_arch = Button(btn_frame, text=f"📦 {arch_text}", 
                         font=("Segoe UI", 8),
                         bg=self.colors["card_bg"], fg=self.colors["text_primary"],
                         relief="flat", cursor="hand2",
                         command=lambda: self.on_archive(self.note["id"]))
        btn_arch.pack(side="left", padx=(0, 2))

        btn_del = Button(btn_frame, text="🗑️ Delete", 
                        font=("Segoe UI", 8),
                        bg=self.colors["danger"], fg="white",
                        relief="flat", cursor="hand2",
                        command=lambda: self.on_delete(self.note["id"]))
        btn_del.pack(side="right")

    def _bind_events(self):
        self.bind("<Button-1>", lambda e: self.on_click(self.note["id"]))
        for child in self.winfo_children():
            child.bind("<Button-1>", lambda e: self.on_click(self.note["id"]))
            for grandchild in child.winfo_children():
                grandchild.bind("<Button-1>", lambda e: self.on_click(self.note["id"]))


# ═══════════════════════════════════════════════════════════════════════════
# STUNNING BACKGROUND CANVAS
# ═══════════════════════════════════════════════════════════════════════════
class GradientCanvas(Canvas):
    """Canvas with a beautiful gradient background."""

    def __init__(self, parent, colors, **kwargs):
        super().__init__(parent, **kwargs)
        self.colors = colors
        self._draw_gradient()

    def _draw_gradient(self):
        """Draw a warm, dairy-themed gradient."""
        width = self.winfo_width()
        height = self.winfo_height()

        if width <= 1 or height <= 1:
            # Not ready yet, retry after a short delay
            self.after(100, self._draw_gradient)
            return

        self.delete("all")

        # Create a warm cream-to-caramel gradient
        # Top: light cream, Bottom: warm caramel
        steps = 100
        for i in range(steps):
            ratio = i / steps
            # Interpolate colors
            r = int(255 - ratio * 40)      # 255 -> 215
            g = int(248 - ratio * 60)      # 248 -> 188
            b = int(240 - ratio * 80)      # 240 -> 160
            color = f"#{r:02x}{g:02x}{b:02x}"

            y1 = (height / steps) * i
            y2 = (height / steps) * (i + 1)
            self.create_rectangle(0, y1, width, y2, fill=color, outline="")

        # Add subtle decorative circles (milk drops)
        for _ in range(8):
            import random
            x = random.randint(50, width - 50)
            y = random.randint(50, height - 50)
            r = random.randint(20, 60)
            alpha = random.randint(20, 40)
            circle_color = f"#{255:02x}{255:02x}{255:02x}"
            self.create_oval(x-r, y-r, x+r, y+r, fill=circle_color, 
                          outline="", stipple="gray50")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════
class KellysDairyApp:
    """Main application window with beautiful UI."""

    def __init__(self, root: Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1100x750")
        self.root.minsize(900, 650)

        # Beautiful color scheme
        self.colors = {
            "bg_top": "#FFF8F0",
            "bg_bottom": "#F5E6D3",
            "card_bg": "#FFFDF8",
            "card_hover": "#FFF5E6",
            "text_primary": "#3D2914",
            "text_muted": "#8B7355",
            "accent": "#D4A574",
            "accent_hover": "#C49464",
            "success": "#7CB342",
            "danger": "#E57373",
            "warning": "#FFB74D",
            "info": "#64B5F6",
            "pinned": "#FFF3E0",
            "tag_bg": "#E8D5C4",
            "taskbar": "#3D2914",
            "taskbar_text": "#FFF8F0",
            "editor_bg": "#FFFDF8",
            "input_bg": "#FFFFFF",
            "border": "#D4A574",
        }

        self.manager = NoteManager()
        self.current_note_id = None
        self.search_var = StringVar()
        self.show_archived = IntVar(value=0)
        self.selected_tag = StringVar(value="All")
        self.selected_category = StringVar(value="All")

        self._build_ui()
        self._refresh_notes_list()
        self._setup_autosave()

    def _build_ui(self):
        """Build the complete UI with gradient background and taskbar."""
        # ═══ GRADIENT BACKGROUND ═══
        self.bg_canvas = GradientCanvas(self.root, self.colors, 
                                        highlightthickness=0)
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        # Bind resize to redraw gradient
        self.root.bind("<Configure>", lambda e: self.bg_canvas._draw_gradient())

        # ═══ MAIN CONTAINER (on top of canvas) ═══
        self.main_frame = Frame(self.root, bg=self.colors["bg_top"])
        self.main_frame.place(x=0, y=0, relwidth=1, relheight=1)

        # Make main_frame transparent-ish by matching canvas color
        self.main_frame.configure(bg=self.colors["bg_top"])

        # ═══ TASKBAR (top) ═══
        self._build_taskbar()

        # ═══ CONTENT AREA ═══
        content_frame = Frame(self.main_frame, bg=self.colors["bg_top"])
        content_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # ═══ SIDEBAR + NOTES LIST + EDITOR ═══
        self._build_sidebar(content_frame)
        self._build_notes_list(content_frame)
        self._build_editor(content_frame)

    def _build_taskbar(self):
        """Build the top taskbar with save button and app info."""
        taskbar = Frame(self.main_frame, bg=self.colors["taskbar"], height=45)
        taskbar.pack(fill="x", side="top")
        taskbar.pack_propagate(False)

        # App title (left)
        lbl_title = Label(taskbar, text=f"🥛 {APP_NAME}", 
                         font=("Segoe UI", 13, "bold"),
                         bg=self.colors["taskbar"], fg=self.colors["taskbar_text"])
        lbl_title.pack(side="left", padx=(15, 20))

        # Taskbar buttons
        btn_frame = Frame(taskbar, bg=self.colors["taskbar"])
        btn_frame.pack(side="left")

        # 💾 SAVE BUTTON (prominent)
        btn_save = Button(btn_frame, text="💾 Save Note", 
                         font=("Segoe UI", 10, "bold"),
                         bg=self.colors["success"], fg="white",
                         relief="flat", cursor="hand2", padx=15, pady=3,
                         command=self._save_current_note)
        btn_save.pack(side="left", padx=(0, 8))

        # New Note
        btn_new = Button(btn_frame, text="➕ New", 
                        font=("Segoe UI", 10),
                        bg=self.colors["accent"], fg=self.colors["text_primary"],
                        relief="flat", cursor="hand2", padx=12, pady=3,
                        command=self._new_note)
        btn_new.pack(side="left", padx=(0, 8))

        # Export
        btn_export = Button(btn_frame, text="📤 Export", 
                           font=("Segoe UI", 10),
                           bg=self.colors["info"], fg="white",
                           relief="flat", cursor="hand2", padx=12, pady=3,
                           command=self._export_txt)
        btn_export.pack(side="left", padx=(0, 8))

        # Search (right side of taskbar)
        search_frame = Frame(taskbar, bg=self.colors["taskbar"])
        search_frame.pack(side="right", padx=(0, 15))

        self.search_entry = Entry(search_frame, font=("Segoe UI", 10),
                                  bg=self.colors["input_bg"], 
                                  fg=self.colors["text_primary"],
                                  insertbackground=self.colors["text_primary"],
                                  width=25, relief="flat")
        self.search_entry.pack(side="left", padx=(0, 5))
        self.search_entry.bind("<KeyRelease>", lambda e: self._refresh_notes_list())

        btn_search = Button(search_frame, text="🔍", 
                           font=("Segoe UI", 10),
                           bg=self.colors["taskbar"], fg=self.colors["taskbar_text"],
                           relief="flat", cursor="hand2",
                           command=self._refresh_notes_list)
        btn_search.pack(side="left")

        # Status label (right of search)
        self.lbl_status = Label(taskbar, text="Ready", 
                               font=("Segoe UI", 9),
                               bg=self.colors["taskbar"], 
                               fg=self.colors["taskbar_text"])
        self.lbl_status.pack(side="right", padx=(0, 15))

    def _build_sidebar(self, parent):
        """Build the left sidebar."""
        sidebar = Frame(parent, bg=self.colors["card_bg"], width=200)
        sidebar.pack(side="left", fill="y", padx=(0, 10))
        sidebar.pack_propagate(False)

        # Sidebar header
        lbl_header = Label(sidebar, text="📂 Filters", 
                          font=("Segoe UI", 11, "bold"),
                          bg=self.colors["card_bg"], fg=self.colors["text_primary"])
        lbl_header.pack(anchor="w", padx=15, pady=(15, 10))

        # Separator
        sep = Frame(sidebar, bg=self.colors["border"], height=2)
        sep.pack(fill="x", padx=15, pady=(0, 10))

        # Category filter
        lbl_cat = Label(sidebar, text="Category:", 
                       font=("Segoe UI", 9, "bold"),
                       bg=self.colors["card_bg"], fg=self.colors["text_muted"])
        lbl_cat.pack(anchor="w", padx=15)

        self.category_combo = ttk.Combobox(sidebar, textvariable=self.selected_category,
                                           values=["All"], state="readonly", width=18)
        self.category_combo.pack(padx=15, pady=(0, 15))
        self.category_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_notes_list())

        # Tag filter
        lbl_tag = Label(sidebar, text="Tag:", 
                       font=("Segoe UI", 9, "bold"),
                       bg=self.colors["card_bg"], fg=self.colors["text_muted"])
        lbl_tag.pack(anchor="w", padx=15)

        self.tag_combo = ttk.Combobox(sidebar, textvariable=self.selected_tag,
                                      values=["All"], state="readonly", width=18)
        self.tag_combo.pack(padx=15, pady=(0, 15))
        self.tag_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_notes_list())

        # Show archived
        lbl_view = Label(sidebar, text="👁 View:", 
                        font=("Segoe UI", 9, "bold"),
                        bg=self.colors["card_bg"], fg=self.colors["text_muted"])
        lbl_view.pack(anchor="w", padx=15, pady=(10, 5))

        chk_archived = Checkbutton(sidebar, text="Show Archived", 
                                   variable=self.show_archived,
                                   bg=self.colors["card_bg"], 
                                   fg=self.colors["text_primary"],
                                   selectcolor=self.colors["input_bg"],
                                   command=self._refresh_notes_list)
        chk_archived.pack(anchor="w", padx=15)

        # Stats
        sep2 = Frame(sidebar, bg=self.colors["border"], height=2)
        sep2.pack(fill="x", padx=15, pady=(20, 10))

        self.lbl_stats = Label(sidebar, text="Notes: 0", 
                              font=("Segoe UI", 10, "bold"),
                              bg=self.colors["card_bg"], 
                              fg=self.colors["text_primary"])
        self.lbl_stats.pack(anchor="w", padx=15, pady=(5, 5))

        self.lbl_last_saved = Label(sidebar, text="", 
                                   font=("Segoe UI", 8),
                                   bg=self.colors["card_bg"], 
                                   fg=self.colors["text_muted"])
        self.lbl_last_saved.pack(anchor="w", padx=15)

    def _build_notes_list(self, parent):
        """Build the center notes list panel."""
        list_frame = Frame(parent, bg=self.colors["bg_top"])
        list_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Header
        lbl_header = Label(list_frame, text="📝 Your Notes", 
                          font=("Segoe UI", 12, "bold"),
                          bg=self.colors["bg_top"], fg=self.colors["text_primary"])
        lbl_header.pack(anchor="w", pady=(0, 10))

        # Scrollable container for note cards
        self.canvas_container = Canvas(list_frame, bg=self.colors["bg_top"], 
                                       highlightthickness=0)
        scrollbar = Scrollbar(list_frame, orient="vertical", 
                              command=self.canvas_container.yview)
        self.canvas_container.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas_container.pack(side="left", fill="both", expand=True)

        self.notes_inner = Frame(self.canvas_container, bg=self.colors["bg_top"])
        self.canvas_container.create_window((0, 0), window=self.notes_inner, 
                                           anchor="nw", width=350)

        self.notes_inner.bind("<Configure>", 
                             lambda e: self.canvas_container.configure(
                                 scrollregion=self.canvas_container.bbox("all")))

    def _build_editor(self, parent):
        """Build the right editor panel."""
        editor_outer = Frame(parent, bg=self.colors["card_bg"], width=420)
        editor_outer.pack(side="right", fill="y")
        editor_outer.pack_propagate(False)

        # Editor header
        lbl_header = Label(editor_outer, text="✏️ Editor", 
                          font=("Segoe UI", 12, "bold"),
                          bg=self.colors["card_bg"], fg=self.colors["text_primary"])
        lbl_header.pack(anchor="w", padx=15, pady=(15, 10))

        sep = Frame(editor_outer, bg=self.colors["border"], height=2)
        sep.pack(fill="x", padx=15, pady=(0, 10))

        # Title
        lbl_title = Label(editor_outer, text="Title", 
                           font=("Segoe UI", 9, "bold"),
                           bg=self.colors["card_bg"], fg=self.colors["text_muted"])
        lbl_title.pack(anchor="w", padx=15, pady=(0, 2))

        self.title_entry = Entry(editor_outer, font=("Segoe UI", 12),
                                bg=self.colors["input_bg"], 
                                fg=self.colors["text_primary"],
                                insertbackground=self.colors["text_primary"],
                                relief="solid", bd=1)
        self.title_entry.pack(fill="x", padx=15, pady=(0, 10))

        # Meta row (Category + Tags)
        meta_frame = Frame(editor_outer, bg=self.colors["card_bg"])
        meta_frame.pack(fill="x", padx=15, pady=(0, 10))

        # Category
        cat_frame = Frame(meta_frame, bg=self.colors["card_bg"])
        cat_frame.pack(side="left", fill="x", expand=True)

        lbl_cat = Label(cat_frame, text="Category", 
                       font=("Segoe UI", 9, "bold"),
                       bg=self.colors["card_bg"], fg=self.colors["text_muted"])
        lbl_cat.pack(anchor="w")

        self.edit_category = Entry(cat_frame, font=("Segoe UI", 10),
                                  bg=self.colors["input_bg"], 
                                  fg=self.colors["text_primary"],
                                  insertbackground=self.colors["text_primary"],
                                  relief="solid", bd=1)
        self.edit_category.pack(fill="x")
        self.edit_category.insert(0, "General")

        # Tags
        tag_frame = Frame(meta_frame, bg=self.colors["card_bg"])
        tag_frame.pack(side="left", fill="x", expand=True, padx=(10, 0))

        lbl_tags = Label(tag_frame, text="Tags (comma sep)", 
                        font=("Segoe UI", 9, "bold"),
                        bg=self.colors["card_bg"], fg=self.colors["text_muted"])
        lbl_tags.pack(anchor="w")

        self.edit_tags = Entry(tag_frame, font=("Segoe UI", 10),
                              bg=self.colors["input_bg"], 
                              fg=self.colors["text_primary"],
                              insertbackground=self.colors["text_primary"],
                              relief="solid", bd=1)
        self.edit_tags.pack(fill="x")
        self.edit_tags.insert(0, "tag1, tag2, tag3")
        self.edit_tags.bind("<FocusIn>", self._clear_tags_placeholder)

        # Content label
        lbl_content = Label(editor_outer, text="Content", 
                           font=("Segoe UI", 9, "bold"),
                           bg=self.colors["card_bg"], fg=self.colors["text_muted"])
        lbl_content.pack(anchor="w", padx=15, pady=(0, 2))

        # Content text area
        text_frame = Frame(editor_outer, bg=self.colors["card_bg"])
        text_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        scrollbar = Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        self.content_text = Text(text_frame, font=("Segoe UI", 11),
                                bg=self.colors["input_bg"], 
                                fg=self.colors["text_primary"],
                                insertbackground=self.colors["text_primary"],
                                wrap="word", yscrollcommand=scrollbar.set,
                                relief="solid", bd=1, padx=8, pady=8)
        self.content_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.content_text.yview)

        # Editor action buttons
        btn_frame = Frame(editor_outer, bg=self.colors["card_bg"])
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        btn_clear = Button(btn_frame, text="🆕 Clear", 
                          font=("Segoe UI", 10),
                          bg=self.colors["warning"], 
                          fg=self.colors["text_primary"],
                          relief="flat", cursor="hand2", padx=15,
                          command=self._clear_editor)
        btn_clear.pack(side="left", padx=(0, 5))

        btn_pin = Button(btn_frame, text="📍 Pin/Unpin", 
                        font=("Segoe UI", 10),
                        bg=self.colors["info"], fg="white",
                        relief="flat", cursor="hand2", padx=15,
                        command=self._pin_current)
        btn_pin.pack(side="left", padx=(0, 5))

        btn_del = Button(btn_frame, text="🗑️ Delete", 
                        font=("Segoe UI", 10),
                        bg=self.colors["danger"], fg="white",
                        relief="flat", cursor="hand2", padx=15,
                        command=self._delete_current)
        btn_del.pack(side="right")

    def _clear_tags_placeholder(self, event):
        if self.edit_tags.get() == "tag1, tag2, tag3":
            self.edit_tags.delete(0, "end")

    def _refresh_notes_list(self):
        """Refresh the notes list display."""
        # Clear existing cards
        for widget in self.notes_inner.winfo_children():
            widget.destroy()

        # Get filtered notes
        query = self.search_entry.get()
        include_archived = bool(self.show_archived.get())
        tag_filter = self.selected_tag.get() if self.selected_tag.get() != "All" else None
        cat_filter = self.selected_category.get() if self.selected_category.get() != "All" else None

        if query:
            notes = self.manager.search_notes(query, include_archived)
        else:
            notes = self.manager.get_notes(include_archived, tag_filter, cat_filter)

        # Update stats
        self.lbl_stats.config(text=f"Notes: {len(notes)}")
        last_saved = ""
        if self.manager.data_file.exists():
            mtime = self.manager.data_file.stat().st_mtime
            last_saved = datetime.fromtimestamp(mtime).strftime("%H:%M")
        self.lbl_last_saved.config(text=f"Last saved: {last_saved}")

        # Update filter dropdowns
        categories = ["All"] + self.manager.get_categories()
        self.category_combo["values"] = categories

        tags = ["All"] + sorted(self.manager.tags)
        self.tag_combo["values"] = tags

        # Display notes
        if not notes:
            lbl_empty = Label(self.notes_inner, 
                             text="No notes yet.\nClick '➕ New' to start! 🥛",
                             font=("Segoe UI", 12),
                             bg=self.colors["bg_top"], 
                             fg=self.colors["text_muted"])
            lbl_empty.pack(pady=50)
            return

        for note in notes:
            card = NoteCard(
                self.notes_inner, note,
                on_click=self._load_note,
                on_pin=self._pin_note,
                on_archive=self._archive_note,
                on_delete=self._delete_note,
                colors=self.colors,
                bg=self.colors["card_bg"],
                relief="solid", bd=1
            )
            card.pack(fill="x", pady=(0, 8), padx=5)

    def _new_note(self):
        """Clear editor for a new note."""
        self.current_note_id = None
        self.title_entry.delete(0, "end")
        self.edit_category.delete(0, "end")
        self.edit_category.insert(0, "General")
        self.edit_tags.delete(0, "end")
        self.edit_tags.insert(0, "tag1, tag2, tag3")
        self.content_text.delete("1.0", "end")
        self.title_entry.focus()
        self.lbl_status.config(text="New note ready")

    def _load_note(self, note_id: str):
        """Load a note into the editor."""
        for note in self.manager.notes:
            if note["id"] == note_id:
                self.current_note_id = note_id
                self.title_entry.delete(0, "end")
                self.title_entry.insert(0, note["title"])

                self.edit_category.delete(0, "end")
                self.edit_category.insert(0, note.get("category", "General"))

                self.edit_tags.delete(0, "end")
                tags = note.get("tags", [])
                self.edit_tags.insert(0, ", ".join(tags))

                self.content_text.delete("1.0", "end")
                self.content_text.insert("1.0", note["content"])

                self.lbl_status.config(text=f"Loaded: {note['title'][:30]}")
                break

    def _save_current_note(self):
        """Save the current note — THE MOST IMPORTANT FUNCTION."""
        title = self.title_entry.get().strip()
        content = self.content_text.get("1.0", "end").strip()
        category = self.edit_category.get().strip() or "General"
        tags_str = self.edit_tags.get().strip()

        # Parse tags
        if tags_str == "tag1, tag2, tag3":
            tags = []
        else:
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]

        # Validation
        if not title and not content:
            messagebox.showwarning("Empty Note", "Please enter a title or content.")
            self.lbl_status.config(text="Cannot save empty note")
            return

        if not title:
            title = content[:30] + "..." if len(content) > 30 else content

        # Save or Update
        if self.current_note_id:
            # Update existing
            success = self.manager.update_note(
                self.current_note_id,
                title=title,
                content=content,
                category=category,
                tags=tags
            )
            if success:
                self.lbl_status.config(text=f"✅ Updated: {title[:25]}")
            else:
                self.lbl_status.config(text="❌ Update failed")
        else:
            # Create new
            note = self.manager.add_note(title, content, tags, category)
            self.current_note_id = note["id"]
            self.lbl_status.config(text=f"✅ Created: {title[:25]}")

        self._refresh_notes_list()

    def _clear_editor(self):
        """Clear the editor."""
        if messagebox.askyesno("Clear", "Clear current note? Unsaved changes will be lost."):
            self._new_note()

    def _pin_current(self):
        """Pin/unpin current note."""
        if self.current_note_id:
            self._pin_note(self.current_note_id)
        else:
            messagebox.showinfo("Pin", "Save the note first before pinning.")

    def _delete_current(self):
        """Delete current note."""
        if self.current_note_id:
            self._delete_note(self.current_note_id)
        else:
            messagebox.showinfo("Delete", "No note selected to delete.")

    def _pin_note(self, note_id: str):
        """Toggle pin status."""
        self.manager.pin_note(note_id)
        self._refresh_notes_list()

    def _archive_note(self, note_id: str):
        """Toggle archive status."""
        self.manager.archive_note(note_id)
        self._refresh_notes_list()

    def _delete_note(self, note_id: str):
        """Delete a note after confirmation."""
        if messagebox.askyesno("Delete", "Are you sure? This cannot be undone."):
            self.manager.delete_note(note_id)
            if self.current_note_id == note_id:
                self._new_note()
            self._refresh_notes_list()
            self.lbl_status.config(text="Note deleted")

    def _export_txt(self):
        """Export notes to text file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filepath:
            self.manager.export_to_txt(filepath)
            self.lbl_status.config(text=f"Exported to {filepath}")
            messagebox.showinfo("Exported", f"Notes exported to:\n{filepath}")

    def _setup_autosave(self):
        """Set up auto-save timer."""
        self._autosave()

    def _autosave(self):
        """Auto-save every 5 minutes if there's unsaved content."""
        if self.current_note_id:
            title = self.title_entry.get().strip()
            content = self.content_text.get("1.0", "end").strip()
            if title or content:
                self.manager.update_note(
                    self.current_note_id,
                    title=title,
                    content=content,
                    category=self.edit_category.get().strip() or "General",
                    tags=[t.strip() for t in self.edit_tags.get().split(",") if t.strip()]
                )
                self.lbl_status.config(text="💾 Auto-saved")
        self.root.after(300000, self._autosave)  # 5 minutes


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════
def main():
    root = Tk()

    # Try to set a nice default font
    try:
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=10)
        text_font = tkfont.nametofont("TkTextFont")
        text_font.configure(family="Segoe UI", size=10)
    except:
        pass

    app = KellysDairyApp(root)

    # Keyboard shortcuts
    root.bind("<Control-n>", lambda e: app._new_note())
    root.bind("<Control-s>", lambda e: app._save_current_note())
    root.bind("<Control-f>", lambda e: app.search_entry.focus())

    root.mainloop()


if __name__ == "__main__":
    main()
