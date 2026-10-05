from pydantic import BaseModel
from typing import List, Literal, Optional


class InsightEvidence(BaseModel):
    label: str
    detail: str
    weight: int


class RiskCase(BaseModel):
    id: str
    subject: str
    exam: str
    level: Literal["Low", "Medium", "High"]
    score: int
    evidence: List[InsightEvidence]


class InsightWarning(BaseModel):
    id: str
    text: str
    tone: Literal["amber", "rose"]


class InsightAction(BaseModel):
    label: str
    to: str


class Insight(BaseModel):
    headline: str
    body: str
    action: Optional[InsightAction] = None
    cases: Optional[List[RiskCase]] = None
    warnings: Optional[List[InsightWarning]] = None


class PredictionRow(BaseModel):
    label: str
    value: str
    tone: Literal["mint", "amber", "rose", "iris"]


class PredictionAction(BaseModel):
    label: str
    to: str


class Prediction(BaseModel):
    title: str
    direction: Literal["rising", "stable", "falling"]
    summary: str
    rows: List[PredictionRow]
    action: Optional[PredictionAction] = None
    kind: Literal["current_standing", "forecast"] = "current_standing"
    method: Optional[str] = None
    observations: Optional[int] = None
    forecastValue: Optional[float] = None
    intervalLow: Optional[float] = None
    intervalHigh: Optional[float] = None


class EvidenceComparison(BaseModel):
    name: str
    scopeAverage: Optional[float] = None


class EvidenceMetric(BaseModel):
    id: str
    name: str
    entity: Optional[str] = None
    value: float
    unit: str = "percent"
    source: Literal["deterministic_sql"] = "deterministic_sql"
    dataset: str = ""
    comparison: Optional[EvidenceComparison] = None


class AiWarning(BaseModel):
    id: str
    rule: str
    severity: Literal["low", "medium", "high"]
    tone: Literal["amber", "rose"]
    metric: str
    entity: Optional[str] = None
    value: float
    threshold: float
    text: str


class DecisionMetadata(BaseModel):
    role: str
    scopeId: Optional[str] = None
    generatedAt: str
    dataVersion: Optional[str] = None
    filters: dict = {}


class ValidationMeta(BaseModel):
    status: Literal["not_run", "passed", "fallback"] = "not_run"
    failures: int = 0


class RecommendationEvidence(BaseModel):
    label: str
    detail: str


class RecommendationBasedOn(BaseModel):
    source: str
    evidence: List[RecommendationEvidence]


class RecommendationAction(BaseModel):
    label: str
    to: Optional[str] = None
    confirmTitle: str
    confirmBody: str
    confirmLabel: str
    exports: Optional[bool] = None


class Recommendation(BaseModel):
    id: str
    kind: Literal["action", "guidance"]
    text: str
    basedOn: RecommendationBasedOn
    action: Optional[RecommendationAction] = None
    metric: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    rule: Optional[str] = None
    confirmationRequired: bool = False


class RecommendationSet(BaseModel):
    insightId: str
    items: List[Recommendation]


class AiDecision(BaseModel):
    insight: Optional[Insight] = None
    prediction: Optional[Prediction] = None
    recommendations: Optional[RecommendationSet] = None
    warnings: Optional[List[AiWarning]] = None
    evidence: Optional[List[EvidenceMetric]] = None
    metadata: Optional[DecisionMetadata] = None
    validation: ValidationMeta = ValidationMeta()
    dataStatus: Literal["ready", "insufficient"] = "insufficient"
    status: Literal["ok", "timeout", "unavailable"] = "ok"
    message: Optional[str] = None
    # "pending" while an LLM reword runs in the background; "done" once it
    # lands or gives up; "skipped" when narration is off or there is nothing
    # to reword.
    narrationStatus: Literal["pending", "done", "skipped"] = "skipped"
    # Deterministic fact packet + narrative overlays (Path 2 card upgrades).
    factPacket: Optional[dict] = None
    narrative: Optional[dict] = None
    ruleAlerts: Optional[List[dict]] = None
    anomalies: Optional[List[dict]] = None
    impactItems: Optional[List[dict]] = None
    provenance: Optional[dict] = None
    forecastStatus: Optional[dict] = None
    evidenceQuality: Optional[dict] = None
    page: Optional[str] = None
    pageLabel: Optional[str] = None


class ChatRequest(BaseModel):
    question: str
    # Handoff ids only — server re-derives facts and re-checks scope.
    cardId: Optional[str] = None
    slice: Optional[dict] = None
    itemId: Optional[str] = None
    language: Optional[str] = None


class ChatActivityStep(BaseModel):
    id: str
    label: str
    done: bool = True


class ChatAnalyticalObject(BaseModel):
    type: Literal[
        "metric",
        "comparison",
        "warning",
        "pattern",
        "what_if",
        "recommendation",
        "evidence",
        "policy",
        "prediction",
    ]
    title: str
    data: dict = {}


class ChatResponse(BaseModel):
    text: str
    blocked: bool
    openIssues: Optional[List[str]] = None
    activities: Optional[List[ChatActivityStep]] = None
    objects: Optional[List[ChatAnalyticalObject]] = None
    evidenceQuality: Optional[dict] = None
    sources: Optional[List[dict]] = None
