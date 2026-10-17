"""Read/write ground truth drift events as JSON (PRD 5.3 criterion 5)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from telltale.data.injector import DriftEvent


def save_events(path: str | Path, events: list[DriftEvent]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump([asdict(e) for e in events], f, indent=2)


def load_events(path: str | Path) -> list[DriftEvent]:
    with open(path) as f:
        rows = json.load(f)
    return [DriftEvent(**row) for row in rows]
