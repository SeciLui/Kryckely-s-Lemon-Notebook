"""Tkinter user interface for the Kanban Ideas desktop application."""

from __future__ import annotations

import queue
import shutil
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import config
from .models import Idea
from .services import transcribe_audio
from .storage import load_all_ideas, read_text, write_text


class KanbanIdeasApp(tk.Tk):
    """Main Tkinter application."""

    def __init__(self) -> None:
        super().__init__()
        self.title(config.APP_TITLE)
        self.geometry("1200x720")
        self.minsize(1000, 600)

        self.search_var = tk.StringVar()
        self.columns: Dict[str, tk.Listbox] = {}
        self.listbox_to_status: Dict[tk.Listbox, str] = {}

        self.ideas: List[Idea] = []
        self.selected_idea: Optional[Idea] = None

        self.detail_title = tk.StringVar()
        self.detail_status = tk.StringVar(value=config.STATUSES[0])
        self.detail_category = tk.StringVar()
        self.detail_tags = tk.StringVar()

        self.queue: "queue.Queue[tuple[str, object]]" = queue.Queue()

        self._build_ui()
        self._load_data()
        self.after(100, self._process_queue)

    # ------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Recherche:").pack(side=tk.LEFT, padx=(0, 4))
        search_entry = ttk.Entry(top, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind("<KeyRelease>", lambda _event: self._refresh_lists())

        ttk.Button(top, text="➕ Nouvelle idée", command=self._create_idea_dialog).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(top, text="↻ Recharger", command=self._load_data).pack(side=tk.LEFT)

        self.status_label = ttk.Label(top, text="")
        self.status_label.pack(side=tk.RIGHT)

        main = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main)
        main.add(left, weight=3)

        board = ttk.Frame(left)
        board.pack(fill=tk.BOTH, expand=True)

        for index, status in enumerate(config.STATUSES):
            column = ttk.Frame(board, padding=6)
            column.grid(row=0, column=index, sticky="nsew")
            board.grid_columnconfigure(index, weight=1)

            ttk.Label(column, text=status, font=("TkDefaultFont", 10, "bold")).pack(
                anchor="w"
            )
            listbox = tk.Listbox(column, height=20, activestyle="none")
            listbox.pack(fill=tk.BOTH, expand=True, pady=(4, 4))
            listbox.bind("<<ListboxSelect>>", self._on_select)
            listbox.bind("<Double-Button-1>", self._on_open_details)
            self.columns[status] = listbox
            self.listbox_to_status[listbox] = status

        for idx in range(len(config.STATUSES)):
            board.grid_columnconfigure(idx, weight=1)

        right = ttk.Frame(main, padding=10)
        main.add(right, weight=2)

        ttk.Label(right, text="Détails", font=("TkDefaultFont", 12, "bold")).pack(
            anchor="w"
        )

        form = ttk.Frame(right)
        form.pack(fill=tk.X, pady=6)

        ttk.Label(form, text="Titre:").grid(row=0, column=0, sticky="e")
        ttk.Entry(form, textvariable=self.detail_title, width=40).grid(
            row=0, column=1, sticky="we", padx=4
        )

        ttk.Label(form, text="Statut:").grid(row=1, column=0, sticky="e")
        status_cb = ttk.Combobox(
            form,
            values=config.STATUSES,
            textvariable=self.detail_status,
            state="readonly",
            width=20,
        )
        status_cb.grid(row=1, column=1, sticky="w", padx=4)

        ttk.Label(form, text="Catégorie:").grid(row=2, column=0, sticky="e")
        ttk.Entry(form, textvariable=self.detail_category, width=40).grid(
            row=2, column=1, sticky="we", padx=4
        )

        ttk.Label(form, text="Tags (virgules):").grid(row=3, column=0, sticky="e")
        ttk.Entry(form, textvariable=self.detail_tags, width=40).grid(
            row=3, column=1, sticky="we", padx=4
        )

        form.grid_columnconfigure(1, weight=1)

        buttons = ttk.Frame(right)
        buttons.pack(fill=tk.X, pady=4)
        ttk.Button(buttons, text="💾 Sauver", command=self._save_current).pack(side=tk.LEFT)
        ttk.Button(
            buttons, text="➡ Déplacer au statut", command=self._move_to_status_dialog
        ).pack(side=tk.LEFT, padx=6)
        ttk.Button(buttons, text="🎧 Ajouter audio…", command=self._add_audio).pack(
            side=tk.LEFT
        )
        ttk.Button(buttons, text="📝 Transcrire", command=self._transcribe_audio).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(buttons, text="💡 Sauver analyse", command=self._save_analysis).pack(
            side=tk.LEFT
        )

        preview = ttk.Notebook(right)
        preview.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.transcript_text = tk.Text(preview, wrap="word", font=("TkDefaultFont", 9))
        preview.add(self.transcript_text, text="Transcription")

        self.analysis_text = tk.Text(preview, wrap="word", font=("TkDefaultFont", 9))
        preview.add(self.analysis_text, text="Analyse")

        ttk.Label(
            right,
            text="Astuce: double-clique une idée dans le Kanban pour l’ouvrir.",
        ).pack(anchor="w", pady=4)

    # ------------------------------------------------------------------
    # DATA MANAGEMENT
    # ------------------------------------------------------------------
    def _load_data(self) -> None:
        previous_id = self.selected_idea.id if self.selected_idea else None
        self.ideas = load_all_ideas()
        self._refresh_lists()
        if previous_id:
            for idea in self.ideas:
                if idea.id == previous_id:
                    self._open_idea(idea)
                    break

    def _refresh_lists(self) -> None:
        filtered = self._filter_ideas(self.ideas)

        for status, listbox in self.columns.items():
            listbox.delete(0, tk.END)
            for idea in filtered:
                if idea.status == status:
                    listbox.insert(tk.END, idea.title)

    def _filter_ideas(self, ideas: Iterable[Idea]) -> List[Idea]:
        query = self.search_var.get().strip().lower()
        if not query:
            return list(ideas)

        matched: List[Idea] = []
        for idea in ideas:
            haystack = " ".join(
                [
                    idea.title,
                    idea.category,
                    " ".join(idea.tags),
                    read_text(idea.transcript_path()),
                    read_text(idea.analysis_path()),
                ]
            ).lower()
            if query in haystack:
                matched.append(idea)
        return matched

    # ------------------------------------------------------------------
    # IDEA SELECTION & DETAILS
    # ------------------------------------------------------------------
    def _on_select(self, event: tk.Event) -> None:  # type: ignore[override]
        widget = event.widget
        if not isinstance(widget, tk.Listbox):
            return
        selection = widget.curselection()
        if not selection:
            return
        index = selection[0]
        title = widget.get(index)
        for idea in self.ideas:
            if idea.title == title and idea.status == self.listbox_to_status.get(widget):
                self._open_idea(idea)
                break

    def _on_open_details(self, event: tk.Event) -> None:  # type: ignore[override]
        self._on_select(event)

    def _open_idea(self, idea: Idea) -> None:
        self.selected_idea = idea
        self.detail_title.set(idea.title)
        self.detail_status.set(idea.status)
        self.detail_category.set(idea.category)
        self.detail_tags.set(", ".join(idea.tags))
        self.transcript_text.delete("1.0", tk.END)
        self.transcript_text.insert("1.0", read_text(idea.transcript_path()))
        self.analysis_text.delete("1.0", tk.END)
        self.analysis_text.insert("1.0", read_text(idea.analysis_path()))

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------
    def _save_current(self) -> None:
        if not self.selected_idea:
            self._set_status("Sélectionne une idée d’abord.")
            return

        idea = self.selected_idea
        idea.title = self.detail_title.get().strip() or idea.title
        idea.status = self.detail_status.get()
        idea.category = self.detail_category.get().strip()
        tags = [tag.strip() for tag in self.detail_tags.get().split(",") if tag.strip()]
        idea.tags = tags
        idea.save()
        write_text(idea.transcript_path(), self.transcript_text.get("1.0", tk.END))
        write_text(idea.analysis_path(), self.analysis_text.get("1.0", tk.END))
        self._set_status("Sauvegardé ✅")
        self._load_data()

    def _move_to_status_dialog(self) -> None:
        if not self.selected_idea:
            self._set_status("Sélectionne une idée d’abord.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Changer de statut")
        ttk.Label(dialog, text="Nouveau statut:").pack(padx=10, pady=10)
        status_var = tk.StringVar(value=self.selected_idea.status)
        ttk.Combobox(
            dialog, values=config.STATUSES, textvariable=status_var, state="readonly"
        ).pack(padx=10, pady=6)

        def apply() -> None:
            self.detail_status.set(status_var.get())
            self._save_current()
            dialog.destroy()

        ttk.Button(dialog, text="OK", command=apply).pack(pady=10)

    def _create_idea_dialog(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Nouvelle idée")
        ttk.Label(dialog, text="Titre de l’idée:").pack(padx=10, pady=(10, 2))
        title_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=title_var, width=40).pack(padx=10, pady=4)

        def create() -> None:
            idea = Idea.create(title_var.get().strip() or "Idée")
            self.ideas.append(idea)
            self._refresh_lists()
            self._open_idea(idea)
            dialog.destroy()

        ttk.Button(dialog, text="Créer", command=create).pack(pady=10)

    def _add_audio(self) -> None:
        if not self.selected_idea:
            self._set_status("Sélectionne une idée d’abord.")
            return

        paths = filedialog.askopenfilenames(
            title="Choisir un fichier audio",
            filetypes=[
                ("Audio", "*.wav *.mp3 *.m4a *.aac *.flac *.ogg"),
                ("Tous", "*.*"),
            ],
        )
        if not paths:
            return

        idea = self.selected_idea
        audio_dir = idea.audio_dir()
        audio_dir.mkdir(parents=True, exist_ok=True)

        imported = 0
        for path_str in paths:
            source = Path(path_str)
            destination = audio_dir / source.name
            try:
                shutil.copy(source, destination)
            except OSError as exc:
                messagebox.showerror("Erreur", f"Impossible de copier {source}: {exc}")
                continue
            idea.register_audio(destination)
            imported += 1

        idea.save()
        self._set_status(f"{imported} audio importé(s).")

    def _transcribe_audio(self) -> None:
        if not self.selected_idea:
            self._set_status("Sélectionne une idée d’abord.")
            return

        idea = self.selected_idea
        audio_files = idea.audio_files()
        if not audio_files:
            self._set_status("Ajoute d’abord un audio.")
            return

        latest_audio = audio_files[-1]
        transcript_path = idea.transcript_path()

        def worker() -> None:
            self.queue.put(("status", "Transcription en cours…"))
            success, message = transcribe_audio(latest_audio, transcript_path)
            if success:
                self.queue.put(("transcript", read_text(transcript_path)))
            self.queue.put(("status", message if success else f"Erreur transcription: {message}"))

        threading.Thread(target=worker, daemon=True).start()

    def _save_analysis(self) -> None:
        if not self.selected_idea:
            self._set_status("Sélectionne une idée d’abord.")
            return

        idea = self.selected_idea
        content = self.analysis_text.get("1.0", tk.END)
        write_text(idea.analysis_path(), content)
        self._set_status("Analyse sauvegardée ✅")

    # ------------------------------------------------------------------
    # BACKGROUND QUEUE
    # ------------------------------------------------------------------
    def _process_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "status":
                    self._set_status(str(payload))
                elif kind == "transcript":
                    self.transcript_text.delete("1.0", tk.END)
                    self.transcript_text.insert("1.0", str(payload))
                elif kind == "refresh":
                    self._load_data()
        except queue.Empty:
            pass
        finally:
            self.after(100, self._process_queue)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _set_status(self, message: str) -> None:
        self.status_label.config(text=message)
        self.after(3500, lambda: self.status_label.config(text=""))
