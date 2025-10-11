import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from kanban_ideas.models import (
    IDEA_DECISIONS,
    MAX_CONTEXTS,
    Idea,
    IdeaBestOf,
    IdeaContext,
    IdeaFiles,
    TestRun,
    TestSignals,
)


class IdeaModelSpecTest(unittest.TestCase):
    def _make_idea(self, folder: Path) -> Idea:
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
                micro_tweaks=["Insister sur la curiosité"],
                evidence=["captures/screen1.png"],
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
            status="À tester",
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
            decision=IDEA_DECISIONS[1],
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
            files=IdeaFiles(evidence=["captures/screen1.png"]),
            folder=folder,
        )
        return idea

    def test_effectiveness_and_signals_are_computed_from_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            idea = self._make_idea(Path(tmp))

            self.assertEqual(idea.tests_total, 2)
            self.assertEqual(
                idea.tests_by_context,
                {"ami·e en café": 1, "date tranquille": 1},
            )
            self.assertEqual(idea.effectiveness_score, 44)
            self.assertEqual(
                idea.signals,
                {
                    "smile": 1,
                    "laugh": 1,
                    "relance": 1,
                    "fluidite_avg": 3.0,
                    "awkward_avg": 2.0,
                },
            )

    def test_payload_contains_spec_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            idea = self._make_idea(Path(tmp))

            payload = idea.to_payload()
            for field in [
                "tests_total",
                "tests_by_context",
                "signals",
                "effectiveness_score",
                "files",
                "best_of",
            ]:
                with self.subTest(field=field):
                    self.assertIn(field, payload)

            self.assertEqual(payload["tests_total"], 2)
            self.assertEqual(payload["effectiveness_score"], 44)
            self.assertEqual(payload["signals"]["laugh"], 1)
            self.assertEqual(payload["files"]["audio"], [])
            self.assertIn("delivery_tips", payload["best_of"])

    def test_signal_values_are_clamped(self) -> None:
        signals = TestSignals(smile=5, laugh=-1, relance=2, fluidite=10, awkward="7")
        self.assertEqual(signals.smile, 1)
        self.assertEqual(signals.laugh, 0)
        self.assertEqual(signals.relance, 1)
        self.assertEqual(signals.fluidite, 5)
        self.assertEqual(signals.awkward, 5)

    def test_signals_from_dict_handles_messy_payloads(self) -> None:
        payload = {
            "smile": " 1 ",
            "laugh": "",
            "relance": "not a number",
            "fluidite": None,
            "awkward": "4",
        }

        signals = TestSignals.from_dict(payload)

        self.assertEqual(signals.smile, 1)
        self.assertEqual(signals.laugh, 0)
        self.assertEqual(signals.relance, 0)
        self.assertEqual(signals.fluidite, 0)
        self.assertEqual(signals.awkward, 4)

        list_payload = [("smile", "2"), ("awkward", 10)]
        signals_from_iterable = TestSignals.from_dict(list_payload)

        self.assertEqual(signals_from_iterable.smile, 1)
        self.assertEqual(signals_from_iterable.awkward, 5)

    def test_context_list_is_limited_to_spec(self) -> None:
        contexts = [IdeaContext(label=f"ctx {idx}") for idx in range(MAX_CONTEXTS + 2)]
        with tempfile.TemporaryDirectory() as tmp:
            idea = Idea(
                id="example",
                title="Example",
                created_at="2025-01-01T00:00:00",
                updated_at="2025-01-01T00:00:00",
                contexts=contexts,
                folder=Path(tmp),
            )

            self.assertEqual(len(idea.contexts), MAX_CONTEXTS)

    def test_context_channel_defaults_to_allowed_values(self) -> None:
        context = IdeaContext(label="Impro", channel="Zoom", constraints="rapide")

        self.assertEqual(context.channel, "IRL")

    def test_best_of_limits_example_dialogues(self) -> None:
        best_of = IdeaBestOf(
            example_dialogues=["A", "B", "C"],
        )
        self.assertEqual(len(best_of.example_dialogues), 2)

    def test_spec_report_detects_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            idea = Idea(
                id="incomplete",
                title="Idée incomplète",
                created_at="2025-01-01T00:00:00",
                updated_at="2025-01-01T00:00:00",
                folder=Path(tmp),
            )

            report = idea.spec_report()

            self.assertFalse(idea.is_spec_complete())
            self.assertIn("one_liner", report["identity"].missing_fields)
            self.assertIn("purpose", report["intention"].missing_fields)
            self.assertIn("Au moins un contexte", report["contexts"].missing_fields)
            self.assertIn("test_instructions", report["plan"].missing_fields)
            self.assertIn("audio ou preuves", report["attachments"].missing_fields)
            self.assertIn("Aucun test enregistré", report["tests"].missing_fields)
            self.assertIn("rationale", report["synthesis"].missing_fields)

    def test_spec_report_requires_context_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            idea = Idea(
                id="needs-constraints",
                title="Idée",
                created_at="2025-01-01T00:00:00",
                updated_at="2025-01-01T00:00:00",
                contexts=[
                    IdeaContext(label="date", channel="IRL", constraints=""),
                ],
                folder=Path(tmp),
            )

            report = idea.spec_report()

            self.assertIn("contexte #1: constraints", report["contexts"].missing_fields)

    def test_best_of_section_requires_all_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            idea = Idea(
                id="best-of-incomplete",
                title="Idée Best-of",
                created_at="2025-01-01T00:00:00",
                updated_at="2025-01-01T00:00:00",
                status="Best-of",
                best_of=IdeaBestOf(
                    final_wording="Version finale",
                    delivery_tips=["Sourire"],
                    example_dialogues=["A", "B"],
                ),
                folder=Path(tmp),
            )

            report = idea.spec_report()

            self.assertIn("best_of", report)
            self.assertIn("do_use_when", report["best_of"].missing_fields)
            self.assertIn("avoid_when", report["best_of"].missing_fields)

    def test_spec_report_is_complete_for_fully_defined_idea(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            idea = self._make_idea(Path(tmp))

            report = idea.spec_report()

            self.assertTrue(idea.is_spec_complete())
            for section in report.values():
                self.assertTrue(section.is_complete, section.name)


if __name__ == "__main__":
    unittest.main()
