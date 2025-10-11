"""Utilities to inspect idea compliance with the cahier des charges."""

from __future__ import annotations

from typing import Iterable, List

from .models import Idea, SpecSectionReport


def build_spec_summary(ideas: Iterable[Idea]) -> str:
    """Return a human readable summary of spec completion for *ideas*.

    Each idea is listed on a separate line prefixed with an emoji indicating
    whether the fiche idea is complete (✅) or still missing mandatory fields
    (⚠️). When incomplete, the summary lists the sections and fields to fix.
    """

    idea_list: List[Idea] = list(ideas)
    if not idea_list:
        return "Aucune idée enregistrée."

    # Sort for stable output, newest ideas last to reflect kanban priorities.
    idea_list.sort(key=lambda idea: (idea.status, idea.created_at, idea.id))

    lines: List[str] = []
    for idea in idea_list:
        title = idea.title or idea.id
        header = f"{title} [{idea.status}]"
        report = idea.spec_report()
        missing_sections: List[SpecSectionReport] = [
            section for section in report.values() if not section.is_complete
        ]

        if missing_sections:
            lines.append(f"⚠️ {header}")
            for section in missing_sections:
                missing = ", ".join(section.missing_fields) or "Champs manquants"
                lines.append(f"   - {section.name}: {missing}")
            continue

        tests_total = idea.tests_total
        tests_label = "aucun test" if tests_total == 0 else (
            "1 test" if tests_total == 1 else f"{tests_total} tests"
        )
        effectiveness = idea.effectiveness_score
        lines.append(
            f"✅ {header} – {tests_label}, score efficacité {effectiveness}/100."
        )

    return "\n".join(lines)
