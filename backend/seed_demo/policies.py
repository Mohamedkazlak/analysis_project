"""Load bilingual policy markdown files from data/policies/."""

from __future__ import annotations

import re
from pathlib import Path

from seed_demo.constants import OWNED_PREFIX

ROOT = Path(__file__).resolve().parents[2]
POLICIES_DIR = ROOT / "data" / "policies"

FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)


def load_policies() -> list[dict]:
    rows: list[dict] = []
    if not POLICIES_DIR.exists():
        return rows
    for path in sorted(POLICIES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = FRONT_MATTER.match(text)
        if not match:
            continue
        meta: dict[str, str] = {}
        for line in match.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"').strip("'")
        doc_id = meta.get("id") or f"{OWNED_PREFIX}policy-{path.stem}"
        if not doc_id.startswith(OWNED_PREFIX):
            doc_id = f"{OWNED_PREFIX}{doc_id}"
        rows.append(
            {
                "id": doc_id,
                "title": meta.get("title") or path.stem,
                "language": meta.get("language") or "en",
                "body": match.group(2).strip(),
                "effective_date": meta.get("effective_date") or "2025-09-01",
                "is_synthetic": True,
            }
        )
    return rows
