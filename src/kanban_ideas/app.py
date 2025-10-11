"""High-level application entry point."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from . import config
from .reports import build_spec_summary
from .storage import load_all_ideas


def main(argv: Sequence[str] | None = None) -> None:
    """Launch the Kanban Ideas desktop application or report spec status."""

    parser = argparse.ArgumentParser(description="Kanban Ideas helper")
    parser.add_argument(
        "--spec-report",
        action="store_true",
        help="affiche un résumé de conformité au cahier des charges puis quitte",
    )
    parser.add_argument(
        "--ideas-dir",
        type=Path,
        default=config.IDEAS_ROOT,
        help="chemin du dossier des idées (par défaut: %(default)s)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.spec_report:
        ideas = load_all_ideas(args.ideas_dir)
        print(build_spec_summary(ideas))
        return

    from .gui import KanbanIdeasApp  # Imported lazily to avoid Tk on report runs.

    app = KanbanIdeasApp()
    app.mainloop()
