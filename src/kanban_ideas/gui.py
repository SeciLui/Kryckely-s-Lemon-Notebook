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
from .models import Idea, IdeaContext, TestRun, TestSignals
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
        self.listbox_items: Dict[tk.Listbox, List[str]] = {}

        self.ideas: List[Idea] = []
        self.selected_idea: Optional[Idea] = None

        self.detail_title = tk.StringVar()
        self.detail_status = tk.StringVar(value=config.STATUSES[0])
        self.detail_category = tk.StringVar()
        self.detail_tags = tk.StringVar()
        self.detail_one_liner = tk.StringVar()
        self.detail_purpose = tk.StringVar()
        self.detail_audience = tk.StringVar()
        self.detail_success = tk.StringVar()
        self.detail_next_test_context = tk.StringVar()
        self.detail_priority = tk.StringVar(value="low")
        self.detail_decision = tk.StringVar(value="Keep")
        self.detail_final_wording = tk.StringVar()
        self.detail_version = tk.IntVar(value=1)
        self.detail_variant_of = tk.StringVar()

        self.text_risks: tk.Text | None = None
        self.text_contexts: tk.Text | None = None
        self.text_test_instructions: tk.Text | None = None
        self.text_rationale: tk.Text | None = None
        self.text_next_actions: tk.Text | None = None
        self.text_delivery_tips: tk.Text | None = None
        self.text_do_use_when: tk.Text | None = None
        self.text_avoid_when: tk.Text | None = None
        self.text_example_dialogues: tk.Text | None = None
        self.summary_tests_total = tk.StringVar(value="0 test")
        self.summary_tests_contexts = tk.StringVar(value="")
        self.summary_effectiveness = tk.StringVar(value="0")
        self.summary_decision = tk.StringVar(value="")
        self.summary_next_actions = tk.StringVar(value="")

        self.tests_tree: ttk.Treeview | None = None
        self.test_detail_partner = tk.StringVar(value="—")
        self.test_detail_version = tk.StringVar(value="—")
        self.test_detail_outcome = tk.StringVar(value="—")
        self.test_detail_signals = tk.StringVar(value="—")
        self.test_detail_run_decision = tk.StringVar(value="—")
        self.test_detail_notes: tk.Text | None = None
        self.test_detail_micro_tweaks: tk.Text | None = None
        self.test_detail_evidence: tk.Text | None = None

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

        ttk.Label(form, text="Version:").grid(row=4, column=0, sticky="e")
        tk.Spinbox(form, from_=1, to=999, textvariable=self.detail_version, width=6).grid(
            row=4, column=1, sticky="w", padx=4
        )

        ttk.Label(form, text="Variante de:").grid(row=5, column=0, sticky="e")
        ttk.Entry(form, textvariable=self.detail_variant_of, width=40).grid(
            row=5, column=1, sticky="we", padx=4
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

        detail_notebook = ttk.Notebook(right)
        detail_notebook.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        fiche_frame = ttk.Frame(detail_notebook, padding=6)
        detail_notebook.add(fiche_frame, text="Fiche")

        ttk.Label(fiche_frame, text="One-liner:").grid(row=0, column=0, sticky="e")
        ttk.Entry(fiche_frame, textvariable=self.detail_one_liner).grid(
            row=0, column=1, sticky="we", padx=4, pady=2
        )

        ttk.Label(fiche_frame, text="Intention / purpose:").grid(
            row=1, column=0, sticky="e"
        )
        ttk.Entry(fiche_frame, textvariable=self.detail_purpose).grid(
            row=1, column=1, sticky="we", padx=4, pady=2
        )

        ttk.Label(fiche_frame, text="Audience hint:").grid(row=2, column=0, sticky="e")
        ttk.Entry(fiche_frame, textvariable=self.detail_audience).grid(
            row=2, column=1, sticky="we", padx=4, pady=2
        )

        ttk.Label(fiche_frame, text="Critère succès:").grid(row=3, column=0, sticky="e")
        ttk.Entry(fiche_frame, textvariable=self.detail_success).grid(
            row=3, column=1, sticky="we", padx=4, pady=2
        )

        ttk.Label(fiche_frame, text="Risques (1/ligne):").grid(
            row=4, column=0, sticky="ne"
        )
        self.text_risks = tk.Text(fiche_frame, height=4, wrap="word")
        self.text_risks.grid(row=4, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(fiche_frame, text="Contexts (label | canal | contraintes):").grid(
            row=5, column=0, sticky="ne"
        )
        self.text_contexts = tk.Text(fiche_frame, height=5, wrap="word")
        self.text_contexts.grid(row=5, column=1, sticky="we", padx=4, pady=2)

        fiche_frame.grid_columnconfigure(1, weight=1)

        plan_frame = ttk.Frame(detail_notebook, padding=6)
        detail_notebook.add(plan_frame, text="Plan de test")

        ttk.Label(plan_frame, text="Instructions de test:").grid(
            row=0, column=0, sticky="ne"
        )
        self.text_test_instructions = tk.Text(plan_frame, height=6, wrap="word")
        self.text_test_instructions.grid(row=0, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(plan_frame, text="Prochain contexte:").grid(
            row=1, column=0, sticky="e"
        )
        ttk.Entry(plan_frame, textvariable=self.detail_next_test_context).grid(
            row=1, column=1, sticky="we", padx=4, pady=2
        )

        ttk.Label(plan_frame, text="Priorité:").grid(row=2, column=0, sticky="e")
        ttk.Combobox(
            plan_frame,
            values=["low", "med", "high"],
            textvariable=self.detail_priority,
            state="readonly",
        ).grid(row=2, column=1, sticky="w", padx=4, pady=2)

        plan_frame.grid_columnconfigure(1, weight=1)

        synthese_frame = ttk.Frame(detail_notebook, padding=6)
        detail_notebook.add(synthese_frame, text="Synthèse")

        ttk.Label(synthese_frame, text="Décision:").grid(row=0, column=0, sticky="e")
        ttk.Combobox(
            synthese_frame,
            values=["Keep", "Tweak", "Kill"],
            textvariable=self.detail_decision,
            state="readonly",
        ).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        ttk.Label(synthese_frame, text="Rationale:").grid(row=1, column=0, sticky="ne")
        self.text_rationale = tk.Text(synthese_frame, height=4, wrap="word")
        self.text_rationale.grid(row=1, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(synthese_frame, text="Next actions (1/ligne):").grid(
            row=2, column=0, sticky="ne"
        )
        self.text_next_actions = tk.Text(synthese_frame, height=4, wrap="word")
        self.text_next_actions.grid(row=2, column=1, sticky="we", padx=4, pady=2)

        synthese_frame.grid_columnconfigure(1, weight=1)

        best_frame = ttk.Frame(detail_notebook, padding=6)
        detail_notebook.add(best_frame, text="Best-of")

        ttk.Label(best_frame, text="Formulation finale:").grid(
            row=0, column=0, sticky="e"
        )
        ttk.Entry(best_frame, textvariable=self.detail_final_wording).grid(
            row=0, column=1, sticky="we", padx=4, pady=2
        )

        ttk.Label(best_frame, text="Delivery tips (1/ligne):").grid(
            row=1, column=0, sticky="ne"
        )
        self.text_delivery_tips = tk.Text(best_frame, height=4, wrap="word")
        self.text_delivery_tips.grid(row=1, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(best_frame, text="À utiliser quand (1/ligne):").grid(
            row=2, column=0, sticky="ne"
        )
        self.text_do_use_when = tk.Text(best_frame, height=4, wrap="word")
        self.text_do_use_when.grid(row=2, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(best_frame, text="À éviter quand (1/ligne):").grid(
            row=3, column=0, sticky="ne"
        )
        self.text_avoid_when = tk.Text(best_frame, height=4, wrap="word")
        self.text_avoid_when.grid(row=3, column=1, sticky="we", padx=4, pady=2)

        ttk.Label(best_frame, text="Dialogues exemple:").grid(
            row=4, column=0, sticky="ne"
        )
        self.text_example_dialogues = tk.Text(best_frame, height=5, wrap="word")
        self.text_example_dialogues.grid(row=4, column=1, sticky="we", padx=4, pady=2)

        best_frame.grid_columnconfigure(1, weight=1)

        tests_frame = ttk.Frame(detail_notebook, padding=6)
        detail_notebook.add(tests_frame, text="Tests")

        tests_table = ttk.Frame(tests_frame)
        tests_table.pack(fill=tk.BOTH, expand=True)

        columns = ("date", "mode", "context", "score", "signals", "decision")
        self.tests_tree = ttk.Treeview(
            tests_table,
            columns=columns,
            show="headings",
            height=6,
        )

        headings = {
            "date": "Date",
            "mode": "Mode",
            "context": "Contexte",
            "score": "Score",
            "signals": "Signaux",
            "decision": "Décision",
        }
        widths = {
            "date": 120,
            "mode": 120,
            "context": 140,
            "score": 60,
            "signals": 200,
            "decision": 90,
        }
        for key in columns:
            self.tests_tree.heading(key, text=headings[key])
            self.tests_tree.column(key, width=widths[key], anchor="w")

        vscroll = ttk.Scrollbar(tests_table, orient=tk.VERTICAL, command=self.tests_tree.yview)
        self.tests_tree.configure(yscrollcommand=vscroll.set)

        self.tests_tree.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        tests_table.grid_columnconfigure(0, weight=1)
        tests_table.grid_rowconfigure(0, weight=1)

        self.tests_tree.bind("<<TreeviewSelect>>", self._on_select_test)

        tests_details = ttk.LabelFrame(tests_frame, text="Détails du test", padding=6)
        tests_details.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        ttk.Label(tests_details, text="Partenaire:").grid(row=0, column=0, sticky="e")
        ttk.Label(tests_details, textvariable=self.test_detail_partner).grid(
            row=0, column=1, sticky="w"
        )

        ttk.Label(tests_details, text="Version utilisée:").grid(row=1, column=0, sticky="e")
        ttk.Label(tests_details, textvariable=self.test_detail_version).grid(
            row=1, column=1, sticky="w"
        )

        ttk.Label(tests_details, text="Score / décision:").grid(row=2, column=0, sticky="e")
        ttk.Label(tests_details, textvariable=self.test_detail_outcome).grid(
            row=2, column=1, sticky="w"
        )
        ttk.Label(tests_details, textvariable=self.test_detail_run_decision).grid(
            row=2, column=2, sticky="w", padx=(6, 0)
        )

        ttk.Label(tests_details, text="Signaux:").grid(row=3, column=0, sticky="ne")
        ttk.Label(tests_details, textvariable=self.test_detail_signals, wraplength=360).grid(
            row=3, column=1, columnspan=2, sticky="w"
        )

        ttk.Label(tests_details, text="Notes:").grid(row=4, column=0, sticky="ne")
        self.test_detail_notes = tk.Text(tests_details, height=4, wrap="word", state="disabled")
        self.test_detail_notes.grid(row=4, column=1, columnspan=2, sticky="we", pady=2)

        ttk.Label(tests_details, text="Micro-tweaks:").grid(row=5, column=0, sticky="ne")
        self.test_detail_micro_tweaks = tk.Text(
            tests_details, height=3, wrap="word", state="disabled"
        )
        self.test_detail_micro_tweaks.grid(row=5, column=1, columnspan=2, sticky="we", pady=2)

        ttk.Label(tests_details, text="Evidence:").grid(row=6, column=0, sticky="ne")
        self.test_detail_evidence = tk.Text(
            tests_details, height=3, wrap="word", state="disabled"
        )
        self.test_detail_evidence.grid(row=6, column=1, columnspan=2, sticky="we", pady=2)

        tests_details.grid_columnconfigure(1, weight=1)
        tests_details.grid_columnconfigure(2, weight=1)

        preview = ttk.Notebook(right)
        preview.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.transcript_text = tk.Text(preview, wrap="word", font=("TkDefaultFont", 9))
        preview.add(self.transcript_text, text="Transcription")

        self.analysis_text = tk.Text(preview, wrap="word", font=("TkDefaultFont", 9))
        preview.add(self.analysis_text, text="Analyse")

        summary = ttk.LabelFrame(right, text="Synthèse")
        summary.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(summary, text="Tests (total):", width=18).grid(row=0, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.summary_tests_total).grid(
            row=0, column=1, sticky="w"
        )

        ttk.Label(summary, text="Tests par contexte:", width=18).grid(
            row=1, column=0, sticky="nw"
        )
        ttk.Label(summary, textvariable=self.summary_tests_contexts, justify=tk.LEFT).grid(
            row=1, column=1, sticky="w"
        )

        ttk.Label(summary, text="Score efficacité:", width=18).grid(
            row=2, column=0, sticky="w"
        )
        ttk.Label(summary, textvariable=self.summary_effectiveness).grid(
            row=2, column=1, sticky="w"
        )

        ttk.Label(summary, text="Décision:", width=18).grid(row=3, column=0, sticky="w")
        ttk.Label(summary, textvariable=self.summary_decision).grid(
            row=3, column=1, sticky="w"
        )

        ttk.Label(summary, text="Next actions:", width=18).grid(row=4, column=0, sticky="nw")
        ttk.Label(summary, textvariable=self.summary_next_actions, justify=tk.LEFT).grid(
            row=4, column=1, sticky="w"
        )

        summary.grid_columnconfigure(1, weight=1)

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
            self.listbox_items[listbox] = []
            for idea in filtered:
                if idea.status == status:
                    listbox.insert(tk.END, idea.title)
                    self.listbox_items[listbox].append(idea.id)

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
        idea_ids = self.listbox_items.get(widget)
        if not idea_ids or index >= len(idea_ids):
            return

        target_id = idea_ids[index]
        for idea in self.ideas:
            if idea.id == target_id:
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
        self.detail_one_liner.set(idea.one_liner)
        self.detail_purpose.set(idea.purpose)
        self.detail_audience.set(idea.audience_hint)
        self.detail_success.set(idea.success_criteria)
        self.detail_next_test_context.set(idea.next_test_context)
        self.detail_priority.set(idea.priority or "low")
        self.detail_decision.set(idea.decision or "Keep")
        self.detail_final_wording.set(idea.best_of.final_wording)
        self.detail_version.set(max(1, int(idea.version or 1)))
        self.detail_variant_of.set(idea.variant_of)
        self.transcript_text.delete("1.0", tk.END)
        self.transcript_text.insert("1.0", read_text(idea.transcript_path()))
        self.analysis_text.delete("1.0", tk.END)
        self.analysis_text.insert("1.0", read_text(idea.analysis_path()))

        self._set_text_widget(self.text_risks, "\n".join(idea.risks))
        self._set_text_widget(self.text_contexts, self._contexts_to_text(idea.contexts))
        self._set_text_widget(self.text_test_instructions, idea.test_instructions)
        self._set_text_widget(self.text_rationale, idea.rationale)
        self._set_text_widget(self.text_next_actions, "\n".join(idea.next_actions))
        self._set_text_widget(self.text_delivery_tips, "\n".join(idea.best_of.delivery_tips))
        self._set_text_widget(self.text_do_use_when, "\n".join(idea.best_of.do_use_when))
        self._set_text_widget(self.text_avoid_when, "\n".join(idea.best_of.avoid_when))
        self._set_text_widget(
            self.text_example_dialogues, "\n".join(idea.best_of.example_dialogues)
        )

        self._populate_tests_tab(idea)
        self._update_summary_panel(idea)

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
        idea.one_liner = self.detail_one_liner.get().strip()
        idea.purpose = self.detail_purpose.get().strip()
        idea.audience_hint = self.detail_audience.get().strip()
        idea.success_criteria = self.detail_success.get().strip()
        idea.risks = self._text_to_list(self.text_risks)
        idea.contexts = self._text_to_contexts(self.text_contexts)
        idea.test_instructions = self._text_to_string(self.text_test_instructions)
        idea.next_test_context = self.detail_next_test_context.get().strip()
        idea.priority = self.detail_priority.get() or "low"
        idea.decision = self.detail_decision.get() or "Keep"
        idea.rationale = self._text_to_string(self.text_rationale)
        idea.next_actions = self._text_to_list(self.text_next_actions)
        idea.best_of.final_wording = self.detail_final_wording.get().strip()
        idea.best_of.delivery_tips = self._text_to_list(self.text_delivery_tips)
        idea.best_of.do_use_when = self._text_to_list(self.text_do_use_when)
        idea.best_of.avoid_when = self._text_to_list(self.text_avoid_when)
        idea.best_of.example_dialogues = self._text_to_list(self.text_example_dialogues)

        idea.version = max(1, int(self.detail_version.get() or 1))
        idea.variant_of = self.detail_variant_of.get().strip()
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

    def _update_summary_panel(self, idea: Idea) -> None:
        total = idea.tests_total
        tests_label = "1 test" if total == 1 else f"{total} tests"
        self.summary_tests_total.set(tests_label)

        if idea.tests_by_context:
            contexts = "\n".join(
                f"• {label}: {count}" for label, count in sorted(idea.tests_by_context.items())
            )
        else:
            contexts = "—"
        self.summary_tests_contexts.set(contexts)

        self.summary_effectiveness.set(f"{idea.effectiveness_score}/100")
        self.summary_decision.set(idea.decision or "—")

        if idea.next_actions:
            actions = "\n".join(f"• {action}" for action in idea.next_actions)
        else:
            actions = "—"
        self.summary_next_actions.set(actions)

    def _populate_tests_tab(self, idea: Idea) -> None:
        if not self.tests_tree:
            return

        tree = self.tests_tree
        tree.delete(*tree.get_children())

        for index, run in enumerate(idea.test_runs):
            tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    run.date or "—",
                    run.mode or "—",
                    run.context_ref or "—",
                    run.outcome_score,
                    self._format_signals(run.signals),
                    run.run_decision or "—",
                ),
            )

        if idea.test_runs:
            first = tree.get_children()[0]
            tree.selection_set(first)
            tree.focus(first)
            self._update_test_details(idea.test_runs[0])
        else:
            self._update_test_details(None)

    def _on_select_test(self, _event: tk.Event) -> None:  # type: ignore[override]
        if not self.selected_idea or not self.tests_tree:
            return
        selection = self.tests_tree.selection()
        if not selection:
            return
        try:
            index = int(selection[0])
        except (ValueError, IndexError):
            return
        if 0 <= index < len(self.selected_idea.test_runs):
            self._update_test_details(self.selected_idea.test_runs[index])

    def _update_test_details(self, run: TestRun | None) -> None:
        if run is None:
            self.test_detail_partner.set("—")
            self.test_detail_version.set("—")
            self.test_detail_outcome.set("—")
            self.test_detail_run_decision.set("—")
            self.test_detail_signals.set("—")
            self._set_readonly_text(self.test_detail_notes, "")
            self._set_readonly_text(self.test_detail_micro_tweaks, "")
            self._set_readonly_text(self.test_detail_evidence, "")
            return

        self.test_detail_partner.set(run.partner_profile or "—")
        self.test_detail_version.set(run.version_used or "—")
        self.test_detail_outcome.set(f"{run.outcome_score}/5")
        self.test_detail_run_decision.set(run.run_decision or "—")
        self.test_detail_signals.set(self._format_signals(run.signals))
        self._set_readonly_text(self.test_detail_notes, run.notes)

        micro = "\n".join(f"• {item}" for item in run.micro_tweaks) or "—"
        self._set_readonly_text(self.test_detail_micro_tweaks, micro)

        evidence = "\n".join(run.evidence) or "—"
        self._set_readonly_text(self.test_detail_evidence, evidence)

    def _format_signals(self, signals: "TestSignals") -> str:
        return (
            f"😊 {signals.smile}  "
            f"😂 {signals.laugh}  "
            f"↩️ {signals.relance}  "
            f"🎚️ {signals.fluidite}/5  "
            f"😬 {signals.awkward}/5"
        )

    # ------------------------------------------------------------------
    # TEXT UTILITIES
    # ------------------------------------------------------------------
    def _set_text_widget(self, widget: tk.Text | None, content: str) -> None:
        if widget is None:
            return
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content.strip())

    def _set_readonly_text(self, widget: tk.Text | None, content: str) -> None:
        if widget is None:
            return
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content.strip())
        widget.configure(state="disabled")

    def _text_to_list(self, widget: tk.Text | None) -> List[str]:
        if widget is None:
            return []
        raw = widget.get("1.0", tk.END)
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def _text_to_string(self, widget: tk.Text | None) -> str:
        if widget is None:
            return ""
        return widget.get("1.0", tk.END).strip()

    def _contexts_to_text(self, contexts: Iterable[IdeaContext]) -> str:
        lines: List[str] = []
        for context in contexts:
            parts = [context.label.strip(), context.channel.strip(), context.constraints.strip()]
            while parts and not parts[-1]:
                parts.pop()
            lines.append(" | ".join(parts))
        return "\n".join(lines)

    def _text_to_contexts(self, widget: tk.Text | None) -> List[IdeaContext]:
        contexts: List[IdeaContext] = []
        if widget is None:
            return contexts
        raw = widget.get("1.0", tk.END)
        for line in raw.splitlines():
            if not line.strip():
                continue
            parts = [part.strip() for part in line.split("|")]
            label = parts[0] if parts else ""
            channel = parts[1] if len(parts) > 1 else "IRL"
            constraints = parts[2] if len(parts) > 2 else ""
            contexts.append(
                IdeaContext(
                    label=label,
                    channel=channel or "IRL",
                    constraints=constraints,
                )
            )
        return contexts
