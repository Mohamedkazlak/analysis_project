"""Deterministic fact packet for AI decision cards."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Driver:
    label: str
    contribution_points: float
    evidence_refs: list[str] = field(default_factory=list)
    kind: str = "course"  # course|section|topic|yoy


@dataclass
class RuleAlert:
    id: str
    rule: str
    severity: str
    text: str
    entity: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    evidence: list[str] = field(default_factory=list)


@dataclass
class Anomaly:
    id: str
    detector: str
    severity: str
    confidence: float
    text: str
    evidence: list[str] = field(default_factory=list)
    entity: Optional[str] = None


@dataclass
class ImpactItem:
    id: str
    issue: str
    students_affected: int
    gap_to_threshold: float
    uplift_program: float
    uplift_university: float
    source: str  # rule|anomaly|driver
    rank: int = 0


@dataclass
class ForecastStatus:
    kind: str  # forecast|current_standing|insufficient
    message: str
    value: Optional[float] = None
    low: Optional[float] = None
    high: Optional[float] = None
    observations: int = 0
    needs_years: int = 0


@dataclass
class Provenance:
    tables: list[str]
    row_counts: dict[str, int]
    updated_at: str


@dataclass
class FactPacket:
    card_id: str
    role: str
    scope_id: Optional[str]
    slice: dict[str, Any]
    data_version: str
    headline_metrics: dict[str, Any]
    drivers: list[Driver] = field(default_factory=list)
    rule_alerts: list[RuleAlert] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)
    impact_items: list[ImpactItem] = field(default_factory=list)
    forecast: Optional[ForecastStatus] = None
    provenance: Optional[Provenance] = None
    story_template: str = ""
    no_structural_cause: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def all_numbers(self) -> set[str]:
        """String forms of numbers that narration may cite."""
        found: set[str] = set()

        def add(v: Any) -> None:
            if isinstance(v, bool) or v is None:
                return
            if isinstance(v, (int, float)):
                found.add(f"{v:g}")
                found.add(str(int(v)) if float(v).is_integer() else f"{float(v):.1f}")
            elif isinstance(v, dict):
                for x in v.values():
                    add(x)
            elif isinstance(v, list):
                for x in v:
                    add(x)

        add(self.to_dict())
        return found


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
