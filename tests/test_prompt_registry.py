import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from prompt_registry import PromptRegistry


class TestPromptRegistry(unittest.TestCase):
    def test_register_and_regression_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = PromptRegistry(Path(tmp) / "prompts.json")
            reg.register("triage", "v1", "分類して", 0.85)
            reg.register("triage", "v2", "JSONで分類して", 0.92)
            reg.register("triage", "v3", "曖昧に答えて", 0.60)
            self.assertTrue(reg.check_regression("triage", "v1", "v2"))
            self.assertFalse(reg.check_regression("triage", "v2", "v3"))


if __name__ == "__main__":
    unittest.main()
