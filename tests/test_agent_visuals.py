import unittest
from unittest.mock import patch

from src.agent import _build_viral_poster_structure, _extract_visual_title_for_type


class AgentVisualTests(unittest.TestCase):
    def test_visual_title_ignores_bare_numbers_and_scaffold_labels(self):
        post_text = "\n".join([
            "5",
            "Best Practices",
            "Common Mistakes",
            "GPT in Production needs observability before optimization.",
        ])

        title = _extract_visual_title_for_type(post_text, "GPT in Production", "Flow Chart")
        self.assertEqual(title, "GPT in Production needs observability before optimizat")

    def test_viral_structure_filters_scaffold_labels(self):
        post_text = "\n".join([
            "Best Practices",
            "Common Mistakes",
            "1. Measure token latency by stage",
            "2. Track cache hit rate before tuning prompts",
            "3. Add evals before model swaps",
            "4. Validate production traces before prompt tuning",
        ])

        with patch(
            "src.agent.call_ai",
            return_value="\n".join([
                "Best Practices",
                "Measure token latency by stage",
                "Track cache hit rate before tuning prompts",
                "Add evals before model swaps",
            ]),
        ):
            structure = _build_viral_poster_structure(post_text, "GPT in Production", "topic")
        labels = [section["label"].lower() for section in structure["sections"]]

        self.assertNotIn("best practices", labels)
        self.assertNotIn("common mistakes", labels)
        self.assertIn("measure token latency by stage", labels)


if __name__ == "__main__":
    unittest.main()
