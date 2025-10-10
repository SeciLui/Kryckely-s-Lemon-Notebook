"""Allow ``python -m kanban_ideas`` to run the desktop application."""

from __future__ import annotations

from .app import main


if __name__ == "__main__":  # pragma: no cover - module entry point
    main()
