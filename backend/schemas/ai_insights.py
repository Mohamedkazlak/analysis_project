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


class RecommendationSet(BaseModel):
    insightId: str
    items: List[Recommendation]


class AiDecision(BaseModel):
    insight: Optional[Insight] = None
    prediction: Optional[Prediction] = None
    recommendations: Optional[RecommendationSet] = None
    status: Literal["ok", "timeout", "unavailable"] = "ok"
    message: Optional[str] = None
    # "pending" while an LLM reword runs in the background; "done" once it
    # lands or gives up; "skipped" when narration is off or there is nothing
    # to reword.
    narrationStatus: Literal["pending", "done", "skipped"] = "skipped"


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    text: str
    blocked: bool
