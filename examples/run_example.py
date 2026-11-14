"""見本の定義（JSON）を読み、一時フォルダに作ったレジストリへ登録して、check_regression の結果を表示します。

使い方: python examples/run_example.py examples/sample_prompts.json

定義のキー:
  prompts  登録する版の一覧（name、version、template、eval_score）
  checks   比べる組の一覧（name、base、candidate）
レジストリのファイルは一時フォルダに作り、終了時に削除します。
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prompt_registry import PromptRegistry  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="プロンプトの版を登録し、評価スコアを比べた結果を表示します。")
    parser.add_argument("path", type=Path, help="見本の定義（JSON）のパス")
    args = parser.parse_args(argv)

    spec = json.loads(args.path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        reg = PromptRegistry(Path(tmp) / "prompts.json")
        for p in spec["prompts"]:
            v = reg.register(p["name"], p["version"], p["template"], p["eval_score"])
            print(f"register {v.name} {v.version} eval_score={v.eval_score} content_hash={v.content_hash}")
        for c in spec["checks"]:
            try:
                ok = reg.check_regression(c["name"], c["base"], c["candidate"])
            except KeyError as exc:
                parser.error(f"{c['name']} {c['base']} -> {c['candidate']}: {exc.args[0]}")
            print(f"check_regression {c['name']} {c['base']} -> {c['candidate']}: {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
