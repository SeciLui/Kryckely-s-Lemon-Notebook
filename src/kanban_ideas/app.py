# kanban_ideas.py
# Proto GUI fichiers/dossiers – Kanban d'idées (impro/punchlines)
# Dépendances: Python 3.9+, Tkinter (builtin), json, subprocess
# Optionnel: openai (pip install openai) si tu veux l'analyse automatique
# Optionnel: une CLI de transcription (ex: "vibe" ou "whisper") accessible dans le PATH

import os
import sys
import json
import uuid
import shutil
import queue
import time
import threading
import datetime as dt
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# =========================
# ======= CONFIG ==========
# =========================

APP_TITLE = "CITRON LAB – Kanban d'idées (proto fichiers)"
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
IDEAS_ROOT = os.path.join(ROOT_DIR, "ideas")
os.makedirs(IDEAS_ROOT, exist_ok=True)

# Colonnes Kanban (statuts)
STATUSES = [
    "Inbox",        # nouvelle idée / capture
    "À tester",     # prête à tester
    "En test",      # en cours d'essais
    "À analyser",   # à relire / synthétiser
    "Best-of",      # validée, robuste (ton style)
    "Kill"          # on jette (ou archive)
]

# Commande CLI de transcription – à ADAPTER à ta CLI
# Exemple générique pour "vibe":
#   vibe --input "audio_path" --output "transcript_path"
# Exemple pour "whisper":
#   whisper "audio_path" --model small --language fr --output_format txt --output_dir "dest_dir"
TRANSCRIBE_COMMAND_TEMPLATE = [
    "vibe",               # remplace par "whisper" si tu utilises whisper
    "--input", "{input}",
    "--output", "{output}"
]

# Modèle OpenAI pour l'analyse JSON
OPENAI_MODEL = "gpt-4o-mini"  # change si besoin

# =========================
# ======= MODELS ==========
# =========================

def now_iso():
    return dt.datetime.now().isoformat(timespec="seconds")

def slugify(text: str) -> str:
    s = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in text)
    s = "_".join(s.strip().split())
    return s[:64] if s else "idee"

@dataclass
class Idea:
    id: str
    title: str
    created_at: str
    status: str = "Inbox"
    category: str = ""
    tags: List[str] = field(default_factory=list)
    folder: str = ""
    files: Dict[str, List[str]] = field(default_factory=lambda: {"audio": []})

    @staticmethod
    def create(title: str) -> "Idea":
        uid = uuid.uuid4().hex[:8]
        ts = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        slug = slugify(title)
        folder_name = f"{ts}_{uid}_{slug}"
        folder_path = os.path.join(IDEAS_ROOT, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        os.makedirs(os.path.join(folder_path, "audio"), exist_ok=True)
        idea = Idea(
            id=uid,
            title=title or f"idée_{uid}",
            created_at=now_iso(),
            status="Inbox",
            folder=folder_path
        )
        idea.save()
        return idea

    @staticmethod
    def load(folder_path: str) -> Optional["Idea"]:
        idea_json = os.path.join(folder_path, "idea.json")
        if not os.path.isfile(idea_json):
            return None
        with open(idea_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Idea(
            id=data.get("id", ""),
            title=data.get("title", ""),
            created_at=data.get("created_at", ""),
            status=data.get("status", "Inbox"),
            category=data.get("category", ""),
            tags=data.get("tags", []),
            folder=folder_path,
            files=data.get("files", {"audio": []})
        )

    def save(self):
        idea_json = os.path.join(self.folder, "idea.json")
        data = {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "status": self.status,
            "category": self.category,
            "tags": self.tags,
            "files": self.files,
        }
        with open(idea_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def transcript_path(self) -> str:
        return os.path.join(self.folder, "transcript.txt")

    def analysis_path(self) -> str:
        return os.path.join(self.folder, "analysis.json")

    def audio_dir(self) -> str:
        return os.path.join(self.folder, "audio")

def load_all_ideas() -> List[Idea]:
    ideas = []
    for name in sorted(os.listdir(IDEAS_ROOT)):
        path = os.path.join(IDEAS_ROOT, name)
        if os.path.isdir(path):
            idea = Idea.load(path)
            if idea:
                ideas.append(idea)
    return ideas

# =========================
# ======= UTILS ===========
# =========================

def run_subprocess(command: List[str]) -> (int, str, str):
    try:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        out, err = proc.communicate()
        return proc.returncode, out, err
    except FileNotFoundError:
        return 127, "", f"Commande introuvable: {command[0]}"
    except Exception as e:
        return 1, "", str(e)

def threaded(fn):
    def wrapper(*args, **kwargs):
        t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
        t.start()
        return t
    return wrapper

def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return ""

def write_text(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# =========================
# ======= OPENAI ==========
# =========================

def try_import_openai():
    try:
        import openai  # legacy import name may still exist
        # new SDK (openai>=1.0) style
        from openai import OpenAI  # if fails, we fallback to legacy
        return "new"
    except Exception:
        try:
            import openai
            return "legacy"
        except Exception:
            return None

def analyze_with_openai(transcript_text: str) -> Dict:
    """
    Appelle OpenAI pour renvoyer un JSON structuré d'analyse.
    Nécessite OPENAI_API_KEY dans l'environnement.
    """
    mode = try_import_openai()
    if not mode:
        raise RuntimeError("Le package 'openai' n'est pas installé. Fais: pip install openai")

    system_prompt = (
        "Tu es un analyste d'idées pour impro/punchlines/conversation. "
        "Retourne STRICTEMENT un JSON qui respecte le schéma suivant."
    )
    user_prompt = f"""
TRANSCRIPTION (français):
\"\"\"{transcript_text}\"\"\"

Ta tâche:
1) Résume l'idée en une phrase claire.
2) Catégorise (ex: compliment utile, micro-histoire, opener, punchline, hook, statut, non-verbal, etc.).
3) But de l'idée (impact recherché).
4) Contextes conseillés pour tester (3 contextes concrets).
5) Instructions de test (simple, mesurable).
6) Punch-up (3 améliorations possibles).
7) Risques/éthiques à surveiller.
8) Tags (mots-clés).
9) Recommandation de statut: 'À tester' | 'Best-of' | 'Kill' | 'À analyser'.

Réponds UNIQUEMENT en JSON:
{{
  "title": "...",
  "category": "...",
  "one_liner": "...",
  "purpose": "...",
  "contexts": ["...", "...", "..."],
  "test_instructions": "...",
  "punch_up": ["...", "...", "..."],
  "risks": ["...", "..."],
  "tags": ["...", "..."],
  "status_recommendation": "À tester"
}}
"""

    # nouvelle API
    if mode == "new":
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = resp.choices[0].message.content
    else:
        # legacy (openai.ChatCompletion)
        import openai
        content = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.4
        )["choices"][0]["message"]["content"]

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {"error": "Réponse non-JSON", "raw": content}
    return data

# =========================
# ======= TRANSCRIBE ======
# =========================

def transcribe_with_cli(audio_path: str, transcript_out: str) -> (bool, str):
    cmd = [arg.format(input=audio_path, output=transcript_out) for arg in TRANSCRIBE_COMMAND_TEMPLATE]
    code, out, err = run_subprocess(cmd)
    if code == 0:
        # Certaines CLI écrivent dans un dossier ; si transcript_out n'existe pas, on tente de retrouver un .txt
        if not os.path.isfile(transcript_out):
            # fallback: si la CLI a écrit un .txt à côté de l'audio
            base_dir = os.path.dirname(audio_path)
            candidates = [p for p in os.listdir(base_dir) if p.lower().endswith(".txt")]
            if candidates:
                shutil.copyfile(os.path.join(base_dir, candidates[0]), transcript_out)
        ok = os.path.isfile(transcript_out)
        return ok, (out or "Transcription terminée." if ok else f"Impossible de trouver {transcript_out}")
    else:
        return False, err or out or "Erreur de transcription."

# =========================
# ======= GUI =============
# =========================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1200x720")
        self.minsize(1000, 600)

        self.search_var = tk.StringVar()
        self.status_vars: Dict[str, tk.Variable] = {}
        self.columns: Dict[str, tk.Listbox] = {}
        self.listbox_to_status: Dict[tk.Listbox, str] = {}
        self.ideas: List[Idea] = []
        self.filtered_ids: set = set()
        self.selected_idea: Optional[Idea] = None

        self.queue = queue.Queue()

        self.build_ui()
        self.load_data()

        self.after(100, self.process_queue)

    def build_ui(self):
        # Top bar
        top = ttk.Frame(self, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Recherche:").pack(side=tk.LEFT, padx=(0,4))
        search_entry = ttk.Entry(top, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind("<KeyRelease>", lambda e: self.refresh_lists())

        ttk.Button(top, text="➕ Nouvelle idée", command=self.create_idea_dialog).pack(side=tk.LEFT, padx=8)
        ttk.Button(top, text="↻ Recharger", command=self.load_data).pack(side=tk.LEFT)

        self.status_label = ttk.Label(top, text="")
        self.status_label.pack(side=tk.RIGHT)

        # Main split
        main = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        # Left: Kanban
        left = ttk.Frame(main)
        main.add(left, weight=3)

        board = ttk.Frame(left)
        board.pack(fill=tk.BOTH, expand=True)

        # create columns
        for idx, status in enumerate(STATUSES):
            col = ttk.Frame(board, padding=6)
            col.grid(row=0, column=idx, sticky="nsew")
            board.grid_columnconfigure(idx, weight=1)
            ttk.Label(col, text=status, font=("TkDefaultFont", 10, "bold")).pack(anchor="w")
            lb = tk.Listbox(col, height=20, activestyle="none")
            lb.pack(fill=tk.BOTH, expand=True, pady=(4,4))
            lb.bind("<<ListboxSelect>>", self.on_select)
            lb.bind("<Double-Button-1>", self.on_open_details)
            self.columns[status] = lb
            self.listbox_to_status[lb] = status

        for c in range(len(STATUSES)):
            board.grid_columnconfigure(c, weight=1)

        # Right: details
        right = ttk.Frame(main, padding=10)
        main.add(right, weight=2)

        self.detail_title = tk.StringVar()
        self.detail_status = tk.StringVar(value=STATUSES[0])
        self.detail_category = tk.StringVar()
        self.detail_tags = tk.StringVar()

        ttk.Label(right, text="Détails", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")

        form = ttk.Frame(right)
        form.pack(fill=tk.X, pady=6)

        ttk.Label(form, text="Titre:").grid(row=0, column=0, sticky="e")
        ttk.Entry(form, textvariable=self.detail_title, width=40).grid(row=0, column=1, sticky="we", padx=4)

        ttk.Label(form, text="Statut:").grid(row=1, column=0, sticky="e")
        status_cb = ttk.Combobox(form, values=STATUSES, textvariable=self.detail_status, state="readonly", width=20)
        status_cb.grid(row=1, column=1, sticky="w", padx=4)

        ttk.Label(form, text="Catégorie:").grid(row=2, column=0, sticky="e")
        ttk.Entry(form, textvariable=self.detail_category, width=40).grid(row=2, column=1, sticky="we", padx=4)

        ttk.Label(form, text="Tags (virgules):").grid(row=3, column=0, sticky="e")
        ttk.Entry(form, textvariable=self.detail_tags, width=40).grid(row=3, column=1, sticky="we", padx=4)

        form.grid_columnconfigure(1, weight=1)

        # Buttons
        btns = ttk.Frame(right)
        btns.pack(fill=tk.X, pady=4)
        ttk.Button(btns, text="💾 Sauver", command=self.save_current).pack(side=tk.LEFT)
        ttk.Button(btns, text="➡ Déplacer au statut", command=self.move_to_status_dialog).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="🎧 Ajouter audio…", command=self.add_audio).pack(side=tk.LEFT)
        ttk.Button(btns, text="📝 Transcrire", command=self.do_transcribe).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="🧠 Analyser (OpenAI)", command=self.do_analyze).pack(side=tk.LEFT)

        # Preview areas
        preview = ttk.Notebook(right)
        preview.pack(fill=tk.BOTH, expand=True, pady=(8,0))

        # Transcript tab
        self.transcript_text = tk.Text(preview, wrap="word")
        self.transcript_text.config(font=("TkDefaultFont", 9))
        preview.add(self.transcript_text, text="Transcription")

        # Analysis tab
        self.analysis_text = tk.Text(preview, wrap="word")
        self.analysis_text.config(font=("TkDefaultFont", 9))
        preview.add(self.analysis_text, text="Analyse JSON")

        # Footer
        ttk.Label(right, text="Astuce: double-clique une idée dans le Kanban pour l’ouvrir.").pack(anchor="w", pady=4)

    def set_status(self, msg: str):
        self.status_label.config(text=msg)
        self.after(3500, lambda: self.status_label.config(text=""))

    def load_data(self):
        self.ideas = load_all_ideas()
        self.refresh_lists()

    def filter_ideas(self, ideas: List[Idea]) -> List[Idea]:
        q = self.search_var.get().strip().lower()
        if not q:
            return ideas
        out = []
        for idea in ideas:
            text = f"{idea.title} {idea.category} {' '.join(idea.tags)}"
            # transcript and analysis snippets
            tr = read_text(idea.transcript_path())
            an = read_text(idea.analysis_path())
            hay = f"{text} {tr} {an}".lower()
            if q in hay:
                out.append(idea)
        return out

    def refresh_lists(self):
        for status, lb in self.columns.items():
            lb.delete(0, tk.END)
        ideas_sorted = sorted(self.filter_ideas(self.ideas), key=lambda i: i.created_at, reverse=True)
        for idea in ideas_sorted:
            lb = self.columns.get(idea.status, None)
            if not lb:
                continue
            display = f"{idea.title}  ·  {idea.created_at.split('T')[0]}"
            lb.insert(tk.END, display)
            # attach idea object reference via a parallel map
            # We store the index mapping on the listbox widget itself
            if not hasattr(lb, "_items"):
                lb._items = []
            lb._items.append(idea)

        # clean _items lengths to match list contents
        for status, lb in self.columns.items():
            items = getattr(lb, "_items", [])
            if len(items) != lb.size():
                # rebuild accurate length
                selected = items[:lb.size()]
                lb._items = selected

    def get_selected_from_listbox(self, lb: tk.Listbox) -> Optional[Idea]:
        if lb.curselection():
            idx = lb.curselection()[0]
            if hasattr(lb, "_items") and 0 <= idx < len(lb._items):
                return lb._items[idx]
        return None

    def on_select(self, event):
        lb = event.widget
        idea = self.get_selected_from_listbox(lb)
        if idea:
            self.open_idea(idea)

    def on_open_details(self, event):
        lb = event.widget
        idea = self.get_selected_from_listbox(lb)
        if idea:
            self.open_idea(idea)

    def open_idea(self, idea: Idea):
        self.selected_idea = idea
        self.detail_title.set(idea.title)
        self.detail_status.set(idea.status)
        self.detail_category.set(idea.category)
        self.detail_tags.set(", ".join(idea.tags))
        # load transcript & analysis
        self.transcript_text.delete("1.0", tk.END)
        self.transcript_text.insert("1.0", read_text(idea.transcript_path()))
        self.analysis_text.delete("1.0", tk.END)
        self.analysis_text.insert("1.0", read_text(idea.analysis_path()))

    def save_current(self):
        if not self.selected_idea:
            self.set_status("Aucune idée sélectionnée.")
            return
        idea = self.selected_idea
        idea.title = self.detail_title.get().strip() or idea.title
        idea.status = self.detail_status.get()
        idea.category = self.detail_category.get().strip()
        idea.tags = [t.strip() for t in self.detail_tags.get().split(",") if t.strip()]
        idea.save()
        # save transcript/analysis if edited
        tr = self.transcript_text.get("1.0", tk.END).strip()
        write_text(idea.transcript_path(), tr)
        an = self.analysis_text.get("1.0", tk.END).strip()
        if an:
            write_text(idea.analysis_path(), an)
        self.refresh_lists()
        self.set_status("Sauvegardé ✅")

    def move_to_status_dialog(self):
        if not self.selected_idea:
            self.set_status("Sélectionne une idée d’abord.")
            return
        win = tk.Toplevel(self)
        win.title("Changer de statut")
        ttk.Label(win, text="Nouveau statut:").pack(padx=10, pady=10)
        var = tk.StringVar(value=self.selected_idea.status)
        cb = ttk.Combobox(win, values=STATUSES, textvariable=var, state="readonly")
        cb.pack(padx=10, pady=6)
        def apply():
            self.detail_status.set(var.get())
            self.save_current()
            win.destroy()
        ttk.Button(win, text="OK", command=apply).pack(pady=10)

    def create_idea_dialog(self):
        win = tk.Toplevel(self)
        win.title("Nouvelle idée")
        ttk.Label(win, text="Titre de l’idée:").pack(padx=10, pady=(10,2))
        var = tk.StringVar()
        ttk.Entry(win, textvariable=var, width=40).pack(padx=10, pady=4)
        def create():
            title = var.get().strip() or "Idée"
            idea = Idea.create(title)
            self.ideas.append(idea)
            self.refresh_lists()
            self.open_idea(idea)
            win.destroy()
        ttk.Button(win, text="Créer", command=create).pack(pady=10)

    def add_audio(self):
        if not self.selected_idea:
            self.set_status("Sélectionne une idée d’abord.")
            return
        paths = filedialog.askopenfilenames(
            title="Choisir un fichier audio",
            filetypes=[("Audio", "*.wav *.mp3 *.m4a *.aac *.flac *.ogg"), ("Tous", "*.*")]
        )
        if not paths:
            return
        idea = self.selected_idea
        audio_dir = idea.audio_dir()
        os.makedirs(audio_dir, exist_ok=True)
        for p in paths:
            dest = os.path.join(audio_dir, os.path.basename(p))
            shutil.copyfile(p, dest)
            idea.files.setdefault("audio", [])
            if dest not in idea.files["audio"]:
                idea.files["audio"].append(dest)
        idea.save()
        self.set_status(f"{len(paths)} audio importé(s).")

    @threaded
    def do_transcribe(self):
        if not self.selected_idea:
            self.set_status("Sélectionne une idée d’abord.")
            return
        idea = self.selected_idea
        audios = idea.files.get("audio", [])
        if not audios:
            self.set_status("Ajoute d’abord un audio.")
            return
        audio_path = audios[-1]   # dernier ajouté
        transcript_path = idea.transcript_path()
        self.queue.put(("status", "Transcription en cours…"))
        ok, msg = transcribe_with_cli(audio_path, transcript_path)
        if ok:
            text = read_text(transcript_path)
            self.queue.put(("transcript", text))
            self.queue.put(("status", "Transcription OK ✅"))
        else:
            self.queue.put(("status", f"Erreur transcription: {msg}"))

    @threaded
    def do_analyze(self):
        if not self.selected_idea:
            self.set_status("Sélectionne une idée d’abord.")
            return
        idea = self.selected_idea
        transcript = self.transcript_text.get("1.0", tk.END).strip()
        if not transcript:
            self.set_status("Pas de transcription. Transcris d’abord.")
            return
        self.queue.put(("status", "Analyse OpenAI en cours…"))
        try:
            data = analyze_with_openai(transcript)
            write_text(idea.analysis_path(), json.dumps(data, ensure_ascii=False, indent=2))
            self.queue.put(("analysis", json.dumps(data, ensure_ascii=False, indent=2)))
            # si le modèle recommande un statut, on le propose
            if isinstance(data, dict) and "status_recommendation" in data:
                rec = data["status_recommendation"]
                if rec in STATUSES:
                    idea.status = rec
                    idea.save()
                    self.queue.put(("refresh", None))
            self.queue.put(("status", "Analyse OK ✅"))
        except Exception as e:
            self.queue.put(("status", f"Analyse échouée: {e}"))

    def process_queue(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "status":
                    self.set_status(str(payload))
                elif kind == "transcript":
                    self.transcript_text.delete("1.0", tk.END)
                    self.transcript_text.insert("1.0", payload)
                elif kind == "analysis":
                    self.analysis_text.delete("1.0", tk.END)
                    self.analysis_text.insert("1.0", payload)
                elif kind == "refresh":
                    self.refresh_lists()
        except queue.Empty:
            pass
        self.after(100, self.process_queue)

if __name__ == "__main__":
    App().mainloop()

