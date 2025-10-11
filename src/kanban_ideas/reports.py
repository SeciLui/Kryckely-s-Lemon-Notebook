"""Utilities to inspect idea compliance with the cahier des charges."""

from __future__ import annotations

from typing import Dict, Iterable, List

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


def build_spec_summary_payload(ideas: Iterable[Idea]) -> List[Dict[str, object]]:
    """Return a machine-readable overview of spec completion for *ideas*.

    The resulting list is sorted for deterministic output. Each entry contains
    the identifying information, derived metrics and the missing fields grouped
    by cahier-des-charges section when the fiche idée is incomplete. This makes
    it easy to plug the data into automation or dashboards without having to
    parse the human oriented text summary produced by :func:`build_spec_summary`.
    """

    payload: List[Dict[str, object]] = []
    idea_list = list(ideas)
    idea_list.sort(key=lambda idea: (idea.status, idea.created_at, idea.id))

    for idea in idea_list:
        report = idea.spec_report()
        missing_sections: Dict[str, List[str]] = {}
        for section in report.values():
            if not section.is_complete:
                missing_sections[section.name] = list(section.missing_fields)

        payload.append(
            {
                "id": idea.id,
                "title": idea.title,
                "status": idea.status,
                "category": idea.category,
                "created_at": idea.created_at,
                "updated_at": idea.updated_at,
                "priority": idea.priority,
                "decision": idea.decision,
                "tests_total": idea.tests_total,
                "tests_by_context": idea.tests_by_context,
                "effectiveness_score": idea.effectiveness_score,
                "signals": idea.signals,
                "next_actions": list(idea.next_actions),
                "missing_sections": missing_sections,
                "is_complete": not missing_sections,
            }
        )

    return payload
