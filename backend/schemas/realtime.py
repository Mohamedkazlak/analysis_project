from pydantic import BaseModel
from typing import List, Literal


class StrugglingStudent(BaseModel):
    studentId: str
    name: str
    college: str = ""
    course: str
    lastScore: float
    average: float
    trend: int
    lastActivity: str


class LiveExamSitting(BaseModel):
    examId: str
    exam: str
    program: str
    sector: str
    activeNow: int
    submitted: int
    expected: int
    flagged: int
    status: Literal["In progress", "Closing"]


class RealTimeReport(BaseModel):
    students: List[StrugglingStudent]
    liveExams: List[LiveExamSitting]
    updatedAt: str
    activeNow: int
    insight: str
