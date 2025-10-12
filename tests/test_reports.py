import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from kanban_ideas.app import main
from kanban_ideas.models import (
    IDEA_DECISIONS,
    Idea,
    IdeaBestOf,
    IdeaContext,
    IdeaFiles,
    TestRun,
    TestSignals,
)
from kanban_ideas.reports import (
    build_spec_statistics,
    build_spec_summary,
    build_spec_summary_payload,
)


class SpecReportTest(unittest.TestCase):
    def _complete_idea(self, folder: Path) -> Idea:
        runs = [
            TestRun(
                date="2025-03-02T19:05:00",
                mode="live (IRL)",
                context_ref="date tranquille",
                partner_profile="Amie lectrice",
                version_used="A",
                outcome_score=4,
                signals=TestSignals(smile=1, laugh=1, relance=0, fluidite=4, awkward=1),
                notes="Premier essai",
                evidence=["captures/screen1.png"],
                micro_tweaks=["Insister sur la curiosité"],
                run_decision="keep",
            ),
            TestRun(
                date="2025-03-05T21:12:00",
                mode="live (IRL)",
                context_ref="ami·e en café",
                partner_profile="Ami curieux",
                version_used="B",
                outcome_score=2,
                signals=TestSignals(smile=0, laugh=0, relance=1, fluidite=2, awkward=3),
                notes="Besoin d'un hook plus court",
                micro_tweaks=["Commencer par une observation"],
                evidence=[],
                run_decision="tweak",
            ),
        ]

        idea = Idea(
            id="2025-03-01_183214_ab12cd34_biblio",
            title="Compliment utile – bibliothèque",
            one_liner="Ta tête est une vraie bibliothèque — et j’adore ça.",
            created_at="2025-03-01T18:32:14",
            updated_at="2025-03-01T18:32:14",
            status="Best-of",
            category="compliment utile",
            tags=["intellect", "valorisation", "humour léger"],
            purpose="Créer un lien en valorisant l'intelligence.",
            audience_hint="Personnes curieuses",
            success_criteria="Sourire + relance",
            risks=["Peut paraître condescendant"],
            contexts=[
                IdeaContext(label="ami·e en café", channel="irl", constraints="calme"),
                IdeaContext(label="date tranquille", channel="IRL", constraints="tête-à-tête"),
            ],
            test_instructions="Attendre qu’un livre soit mentionné, complimenter, relancer.",
            next_test_context="ami·e en café",
            priority="high",
            test_runs=runs,
            decision=IDEA_DECISIONS[0],
            rationale="Bon taux de relance ; ajouter un détail personnalisé.",
            next_actions=["Refaire en date tranquille", "Tester variante B"],
            best_of=IdeaBestOf(
                final_wording="Ta tête est une vraie bibliothèque — et j’adore ça.",
                delivery_tips=["Sourire doux", "Contact visuel"],
                do_use_when=["La personne parle lecture"],
                avoid_when=["La personne se dévalorise"],
                example_dialogues=[
                    "Toi: Ta tête est une vraie bibliothèque. Elle: Oh ?",
                    "Toi: Sérieux, j'ai envie d'y emprunter un chapitre.",
                ],
            ),
            files=IdeaFiles(audio=[], evidence=["captures/screen1.png"]),
            version=2,
            variant_of="2025-02-10_080000_esquisse",
            changelog=["Création de l'idée.", "Mise à jour."],
            folder=folder,
        )
        return idea

    def test_build_spec_summary_lists_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "idea"
            idea = self._complete_idea(folder)
            summary = build_spec_summary([idea])

        self.assertIn("✅ Compliment utile – bibliothèque", summary)
        self.assertIn("2 tests", summary)
        self.assertIn("score efficacité", summary)

    def test_build_spec_summary_lists_missing_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            idea = Idea(
                id="incomplete",
                title="Idée incomplète",
                created_at="2025-01-01T00:00:00",
                updated_at="2025-01-01T00:00:00",
                folder=Path(tmp) / "incomplete",
            )
            summary = build_spec_summary([idea])

        self.assertIn("⚠️ Idée incomplète", summary)
        self.assertIn("Identité & statut", summary)
        self.assertIn("Aucun test enregistré", summary)

    def test_build_spec_summary_payload_returns_machine_readable_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "idea"
            idea = self._complete_idea(folder)
            payload = build_spec_summary_payload([idea])

        self.assertEqual(len(payload), 1)
        entry = payload[0]
        self.assertTrue(entry["is_complete"])
        self.assertEqual(entry["tests_total"], 2)
        self.assertEqual(entry["signals"]["laugh"], 1)
        self.assertEqual(entry["missing_sections"], {})
        self.assertEqual(entry["version"], 2)
        self.assertEqual(entry["variant_of"], "2025-02-10_080000_esquisse")
        self.assertEqual(entry["changelog"], ["Création de l'idée.", "Mise à jour."])

    def test_build_spec_statistics_returns_dashboard_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "idea"
            idea_complete = self._complete_idea(folder)
            idea_incomplete = Idea(
                id="incomplete",
                title="À préparer",
                created_at="2025-01-01T00:00:00",
                updated_at="2025-01-01T00:00:00",
                status="Inbox",
                folder=Path(tmp) / "incomplete",
            )

            stats = build_spec_statistics([idea_complete, idea_incomplete])

        self.assertEqual(stats["total_ideas"], 2)
        self.assertEqual(stats["complete"], 1)
        self.assertEqual(stats["incomplete"], 1)
        self.assertEqual(stats["tests_total"], 2)
        self.assertEqual(stats["ideas_without_tests"], 1)
        self.assertGreater(stats["average_effectiveness"], 0)
        self.assertIn("Best-of", stats["statuses"])
        self.assertIn("ami·e en café", stats["tests_by_context"])

    def test_main_spec_report_prints_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "idea"
            idea = self._complete_idea(folder)
            idea.save()

            saved_stdout = sys.stdout
            try:
                sys.stdout = io.StringIO()
                main(["--spec-report", "--ideas-dir", tmp])
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = saved_stdout

        self.assertIn("Compliment utile – bibliothèque", output)

    def test_main_spec_report_json_prints_structured_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "idea"
            idea = self._complete_idea(folder)
            idea.save()

            saved_stdout = sys.stdout
            try:
                sys.stdout = io.StringIO()
                main([
                    "--spec-report",
                    "--spec-report-format",
                    "json",
                    "--ideas-dir",
                    tmp,
                ])
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = saved_stdout

        data = json.loads(output)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], idea.id)
        self.assertTrue(data[0]["is_complete"])

    def test_main_spec_report_stats_prints_dashboard_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "idea"
            idea = self._complete_idea(folder)
            idea.save()

            saved_stdout = sys.stdout
            try:
                sys.stdout = io.StringIO()
                main([
                    "--spec-report",
                    "--spec-report-format",
                    "stats",
                    "--ideas-dir",
                    tmp,
                ])
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = saved_stdout

        data = json.loads(output)
        self.assertIn("total_ideas", data)
        self.assertEqual(data["complete"], 1)


if __name__ == "__main__":
    unittest.main()
