"""Deterministic prompt version registry with SHA-256 content hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class PromptVersion:
    name: str
    version: str
    template: str
    eval_score: float
    content_hash: str


class PromptRegistry:
    """Stores versioned prompts and prevents unverified regressions."""

    def __init__(self, store_path: Path | str) -> None:
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Dict[str, dict]] = {}
        if self.store_path.exists():
            self._data = json.loads(self.store_path.read_text(encoding="utf-8"))

    @staticmethod
    def _hash(template: str) -> str:
        return hashlib.sha256(template.encode("utf-8")).hexdigest()[:12]

    def register(self, name: str, version: str, template: str, eval_score: float) -> PromptVersion:
        h = self._hash(template)
        rec = {
            "name": name,
            "version": version,
            "template": template,
            "eval_score": eval_score,
            "content_hash": h,
        }
        self._data.setdefault(name, {})[version] = rec
        self.store_path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        return PromptVersion(**rec)

    def get(self, name: str, version: str) -> Optional[PromptVersion]:
        rec = self._data.get(name, {}).get(version)
        return PromptVersion(**rec) if rec else None

    def check_regression(self, name: str, base_ver: str, cand_ver: str) -> bool:
        base = self.get(name, base_ver)
        cand = self.get(name, cand_ver)
        if not base or not cand:
            raise KeyError("Specified version not found")
        return cand.eval_score >= base.eval_score
