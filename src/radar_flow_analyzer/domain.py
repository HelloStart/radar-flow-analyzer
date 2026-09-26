from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class Chapter:
    chapter_id: str
    title: str
    summary: str


@dataclass(slots=True)
class FlowStep:
    name: str
    title: str
    description: str


@dataclass(slots=True)
class Scenario:
    key: str
    title: str
    summary: str
    focus: str


@dataclass(slots=True)
class Catalog:
    title: str
    subtitle: str
    overview: dict[str, str]
    chapters: list[Chapter]
    flow_steps: list[FlowStep]
    scenarios: list[Scenario]


def load_catalog(path: Path) -> Catalog:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    chapters = [
        Chapter(
            chapter_id=str(item["id"]),
            title=str(item["title"]),
            summary=str(item.get("summary", "")),
        )
        for item in data.get("foundation", {}).get("chapters", [])
    ]

    flow_steps = [
        FlowStep(
            name=str(item["name"]),
            title=str(item["title"]),
            description=str(item.get("description", "")),
        )
        for item in data.get("flow", {}).get("steps", [])
    ]

    scenarios = [
        Scenario(
            key=str(item["key"]),
            title=str(item["title"]),
            summary=str(item.get("summary", "")),
            focus=str(item.get("focus", "")),
        )
        for item in data.get("scenarios", [])
    ]

    return Catalog(
        title=str(data.get("title", "Radar Flow Analyzer")),
        subtitle=str(data.get("subtitle", "")),
        overview={
            "what": str(data.get("overview", {}).get("what", "")),
            "modules": str(data.get("overview", {}).get("modules", "")),
            "how": str(data.get("overview", {}).get("how", "")),
        },
        chapters=chapters,
        flow_steps=flow_steps,
        scenarios=scenarios,
    )
