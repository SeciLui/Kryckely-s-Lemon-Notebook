"""Utilities to inspect idea compliance with the cahier des charges."""

from __future__ import annotations

from collections import Counter
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
                "version": int(idea.version),
                "variant_of": idea.variant_of,
                "changelog": list(idea.changelog),
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


def build_spec_statistics(ideas: Iterable[Idea]) -> Dict[str, object]:
    """Return aggregate metrics describing spec completion.

    The resulting dictionary can be used to monitor overall progress toward a
    fully spec-compliant workspace. It contains counts of complete vs.
    incomplete fiches, testing volume, the distribution of contexts and
    statuses, plus aggregate behavioural signals captured during the tests.
    The averages ignore ideas without recorded tests so newly created fiches do
    not skew the learning indicators.
    """

    idea_list: List[Idea] = list(ideas)
    total = len(idea_list)
    complete = sum(1 for idea in idea_list if idea.is_spec_complete())
    incomplete = total - complete
    tests_total = sum(idea.tests_total for idea in idea_list)
    ideas_with_tests = sum(1 for idea in idea_list if idea.tests_total > 0)

    # Aggregate counts per context and status for quick dashboards.
    contexts_counter: Counter[str] = Counter()
    for idea in idea_list:
        contexts_counter.update(idea.tests_by_context)

    statuses_counter: Counter[str] = Counter(idea.status for idea in idea_list)

    effectiveness_scores = [
        idea.effectiveness_score for idea in idea_list if idea.tests_total > 0
    ]
    avg_effectiveness = (
        round(sum(effectiveness_scores) / len(effectiveness_scores), 2)
        if effectiveness_scores
        else 0.0
    )

    signals_totals: Counter[str] = Counter()
    fluidite_total = 0
    awkward_total = 0
    runs_count = 0
    for idea in idea_list:
        for run in idea.test_runs:
            signals_totals["smile"] += int(run.signals.smile)
            signals_totals["laugh"] += int(run.signals.laugh)
            signals_totals["relance"] += int(run.signals.relance)
            fluidite_total += int(run.signals.fluidite)
            awkward_total += int(run.signals.awkward)
            runs_count += 1

    signals_summary = {
        "smile": int(signals_totals.get("smile", 0)),
        "laugh": int(signals_totals.get("laugh", 0)),
        "relance": int(signals_totals.get("relance", 0)),
        "fluidite_avg": round(fluidite_total / runs_count, 2) if runs_count else 0.0,
        "awkward_avg": round(awkward_total / runs_count, 2) if runs_count else 0.0,
    }

    completion_rate = round((complete / total) * 100, 2) if total else 0.0

    return {
        "total_ideas": total,
        "complete": complete,
        "incomplete": incomplete,
        "completion_rate": completion_rate,
        "tests_total": tests_total,
        "ideas_with_tests": ideas_with_tests,
        "ideas_without_tests": total - ideas_with_tests,
        "average_effectiveness": avg_effectiveness,
        "signals_totals": signals_summary,
        "tests_by_context": dict(sorted(contexts_counter.items())),
        "statuses": dict(sorted(statuses_counter.items())),
    }
