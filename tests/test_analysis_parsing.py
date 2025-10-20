import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from kanban_ideas.models import Idea
from kanban_ideas.services import apply_analysis_payload


class ApplyAnalysisPayloadTest(unittest.TestCase):
    def _make_idea(self, tmp: Path) -> Idea:
        return Idea(
            id="demo",
            title="Prototype",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            folder=tmp,
        )

    def test_gpt_like_payload_populates_idea_and_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            idea = self._make_idea(Path(tmp_dir))
            payload = {
                "idea": {
                    "title": "Compliment cosmique",
                    "one_liner": "Une phrase d'accroche intergalactique.",
                    "tags": ["astro", "humour"],
                    "contexts": [
                        {
                            "label": "Rooftop",
                            "channel": "scène",
                            "constraints": "Nuit claire",
                        }
                    ],
                    "decision": "Tweak",
                    "next_actions": ["Tester version B"],
                    "best_of": {
                        "final_wording": "Tu es mon étoile polaire.",
                        "delivery_tips": ["Sourire", "Tempo lent"],
                    },
                },
                "tests": [
                    {
                        "date": "2024-05-02",
                        "mode": "live (IRL)",
                        "context": "Rooftop",
                        "partner": "Ami astronome",
                        "version": "B",
                        "score": 4,
                        "signals": {"smile": 1, "fluidite": 4},
                        "notes": "Bonne vibe cosmique.",
                        "decision": "keep",
                    }
                ],
            }

            warnings = apply_analysis_payload(idea, payload)

            self.assertFalse(warnings)
            self.assertEqual(idea.title, "Compliment cosmique")
            self.assertEqual(
                idea.one_liner, "Une phrase d'accroche intergalactique."
            )
            self.assertEqual(idea.tags, ["astro", "humour"])
            self.assertEqual(len(idea.contexts), 1)
            self.assertEqual(idea.contexts[0].label, "Rooftop")
            self.assertEqual(idea.decision, "Tweak")
            self.assertEqual(idea.next_actions, ["Tester version B"])
            self.assertEqual(idea.best_of.final_wording, "Tu es mon étoile polaire.")
            self.assertEqual(
                idea.best_of.delivery_tips, ["Sourire", "Tempo lent"]
            )
            self.assertEqual(len(idea.test_runs), 1)
            run = idea.test_runs[0]
            self.assertEqual(run.context_ref, "Rooftop")
            self.assertEqual(run.partner_profile, "Ami astronome")
            self.assertEqual(run.outcome_score, 4)
            self.assertEqual(run.run_decision, "keep")
            self.assertEqual(run.notes, "Bonne vibe cosmique.")
            self.assertEqual(run.signals.smile, 1)

    def test_invalid_sections_generate_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            idea = self._make_idea(Path(tmp_dir))
            payload = {
                "idea": {
                    "contexts": "pas une liste",
                    "next_actions": 42,
                }
            }

            warnings = apply_analysis_payload(idea, payload)

            self.assertTrue(any("contexts" in msg for msg in warnings))
            self.assertTrue(any("next_actions" in msg for msg in warnings))
            self.assertEqual(idea.contexts, [])
            self.assertEqual(idea.next_actions, [])


if __name__ == "__main__":  # pragma: no cover - convenience
    unittest.main()
