from pydantic import BaseModel
from typing import List, Literal, Optional


class Kpi(BaseModel):
    label: str
    value: str
    # No prior-term data exists yet to compute a real trend (course_offerings
    # only has current-term rows), so these are omitted rather than faked.
    # Populate once a prior period is available to compare against.
    delta: Optional[str] = None
    direction: Optional[Literal["up", "down"]] = None


class PassRateByCourse(BaseModel):
    course: str
    passRate: float
    participants: int


class PassRateByCollege(BaseModel):
    college: str
    passRate: float
    participants: int
    students: int = 0
    courses: int
    attendance: float = 0
    participation: float = 0
    expected: int = 0
    onTime: int = 0
    late: int = 0
    absent: int = 0
    passed: int = 0
    failed: int = 0


class ActivityTrendRow(BaseModel):
    month: str
    exams: int
    participants: int
    year: Optional[int] = None
    monthNum: Optional[int] = None
    termId: Optional[str] = None
    termName: Optional[str] = None


class ExamSummaryRow(BaseModel):
    examId: str
    title: str
    course: str
    college: str
    termId: Optional[str] = None
    termName: Optional[str] = None
    month: Optional[str] = None
    year: Optional[int] = None
    monthNum: Optional[int] = None
    sittings: int
    passed: int
    failed: int
    absent: int
    late: int
    avgScore: float


class ManagementOverview(BaseModel):
    kpis: List[Kpi]
    passRateByCourse: List[PassRateByCourse]
    passRateByCollege: List[PassRateByCollege]
    activityTrend: List[ActivityTrendRow]
    examSummaries: List[ExamSummaryRow] = []
    insight: str
    containsSynthetic: bool = False
