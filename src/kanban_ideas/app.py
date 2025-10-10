"""High-level application entry point."""

from __future__ import annotations

from .gui import KanbanIdeasApp


def main() -> None:
    """Launch the Kanban Ideas desktop application."""

    app = KanbanIdeasApp()
    app.mainloop()
