import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from prompt_registry import PromptRegistry, PromptVersion


def _sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


class TestPromptRegistry(unittest.TestCase):
    def test_register_and_regression_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reg = PromptRegistry(Path(tmp) / "prompts.json")
            reg.register("triage", "v1", "分類して", 0.85)
            reg.register("triage", "v2", "JSONで分類して", 0.92)
            reg.register("triage", "v3", "曖昧に答えて", 0.60)
            self.assertTrue(reg.check_regression("triage", "v1", "v2"))
            self.assertFalse(reg.check_regression("triage", "v2", "v3"))


class TestInit(unittest.TestCase):
    def test_normal_creates_parent_dirs_but_not_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "a" / "b" / "prompts.json"
            PromptRegistry(store)
            self.assertTrue(store.parent.is_dir())
            self.assertFalse(store.exists())

    def test_normal_reloads_saved_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "prompts.json"
            PromptRegistry(str(store)).register("triage", "v1", "分類して", 0.85)
            again = PromptRegistry(store).get("triage", "v1")
        self.assertEqual(again, PromptVersion("triage", "v1", "分類して", 0.85, _sha12("分類して")))

    def test_error_invalid_json_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "prompts.json"
            store.write_text("{not json", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                PromptRegistry(store)

    def test_error_empty_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "prompts.json"
            store.write_text("", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                PromptRegistry(store)

    def test_error_parent_is_a_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "not_a_dir").write_text("x", encoding="utf-8")
            with self.assertRaises(OSError):
                PromptRegistry(Path(tmp) / "not_a_dir" / "prompts.json")


class TestRegister(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Path(self._tmp.name) / "prompts.json"
        self.reg = PromptRegistry(self.store)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_normal_returns_version_with_short_sha256(self) -> None:
        v = self.reg.register("triage", "v1", "分類して", 0.85)
        self.assertEqual(v, PromptVersion("triage", "v1", "分類して", 0.85, _sha12("分類して")))
        self.assertEqual(len(v.content_hash), 12)

    def test_normal_saves_utf8_json_by_name_and_version(self) -> None:
        self.reg.register("triage", "v1", "分類して", 0.85)
        self.reg.register("summary", "v1", "要約して", 0.7)
        raw = self.store.read_text(encoding="utf-8")
        self.assertIn("分類して", raw)  # 日本語はエスケープせずに保存する
        data = json.loads(raw)
        self.assertEqual(sorted(data), ["summary", "triage"])
        self.assertEqual(data["triage"]["v1"]["content_hash"], _sha12("分類して"))

    def test_boundary_empty_template(self) -> None:
        self.assertEqual(self.reg.register("t", "v1", "", 0.0).content_hash, "e3b0c44298fc")

    def test_boundary_same_template_gives_same_hash(self) -> None:
        a = self.reg.register("triage", "v1", "分類して", 0.85)
        b = self.reg.register("other", "v9", "分類して", 0.10)
        c = self.reg.register("triage", "v2", "分類して。", 0.85)
        self.assertEqual(a.content_hash, b.content_hash)
        self.assertNotEqual(a.content_hash, c.content_hash)

    def test_boundary_same_version_is_overwritten(self) -> None:
        self.reg.register("triage", "v1", "分類して", 0.85)
        self.reg.register("triage", "v1", "上書き", 0.50)
        self.assertEqual(self.reg.get("triage", "v1"), PromptVersion("triage", "v1", "上書き", 0.50, _sha12("上書き")))
        self.assertEqual(list(json.loads(self.store.read_text(encoding="utf-8"))["triage"]), ["v1"])

    def test_boundary_score_is_not_validated(self) -> None:
        # 範囲や型は検査しない（1を超える値も、文字列も登録できる）
        self.assertEqual(self.reg.register("t", "v1", "a", 1.5).eval_score, 1.5)
        self.assertEqual(self.reg.register("t", "v2", "b", "high").eval_score, "high")


class TestGetAndCheckRegression(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.reg = PromptRegistry(Path(self._tmp.name) / "prompts.json")
        self.reg.register("triage", "v1", "分類して", 0.80)
        self.reg.register("triage", "v2", "JSONで分類して", 0.90)
        self.reg.register("triage", "v3", "短く分類して", 0.80)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_normal_get_returns_registered_version(self) -> None:
        self.assertEqual(self.reg.get("triage", "v2").template, "JSONで分類して")

    def test_boundary_get_unknown_returns_none(self) -> None:
        self.assertIsNone(self.reg.get("triage", "v9"))
        self.assertIsNone(self.reg.get("unknown", "v1"))

    def test_normal_higher_score_passes(self) -> None:
        self.assertTrue(self.reg.check_regression("triage", "v1", "v2"))

    def test_normal_lower_score_fails(self) -> None:
        self.assertFalse(self.reg.check_regression("triage", "v2", "v1"))

    def test_boundary_equal_score_passes(self) -> None:
        self.assertTrue(self.reg.check_regression("triage", "v1", "v3"))

    def test_boundary_same_version_passes(self) -> None:
        self.assertTrue(self.reg.check_regression("triage", "v2", "v2"))

    def test_error_unknown_candidate_raises_key_error(self) -> None:
        with self.assertRaisesRegex(KeyError, "Specified version not found"):
            self.reg.check_regression("triage", "v1", "v9")

    def test_error_unknown_base_or_name_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.reg.check_regression("triage", "v0", "v1")
        with self.assertRaises(KeyError):
            self.reg.check_regression("unknown", "v1", "v2")

    def test_error_non_numeric_score_raises_type_error_on_compare(self) -> None:
        self.reg.register("triage", "v4", "文字列のスコア", "high")
        with self.assertRaises(TypeError):
            self.reg.check_regression("triage", "v1", "v4")

    def test_error_prompt_version_is_immutable(self) -> None:
        with self.assertRaises(dataclasses.FrozenInstanceError):
            self.reg.get("triage", "v1").eval_score = 1.0  # type: ignore[misc]


class TestExampleScript(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        return subprocess.run(
            [sys.executable, str(ROOT / "examples" / "run_example.py"), *args],
            capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT,
        )

    def test_normal_sample_output(self) -> None:
        proc = self._run("examples/sample_prompts.json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertEqual(len(lines), 5)
        self.assertTrue(lines[0].startswith("register inquiry_triage v1 eval_score=0.82 content_hash="))
        self.assertEqual(lines[3:], [
            "check_regression inquiry_triage v1 -> v2: True",
            "check_regression inquiry_triage v2 -> v3: False",
        ])

    def test_error_unknown_version_in_checks_exits_with_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "spec.json"
            spec.write_text(json.dumps({
                "prompts": [{"name": "t", "version": "v1", "template": "a", "eval_score": 0.5}],
                "checks": [{"name": "t", "base": "v1", "candidate": "v2"}],
            }), encoding="utf-8")
            proc = self._run(str(spec))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Specified version not found", proc.stderr)


if __name__ == "__main__":
    unittest.main()
