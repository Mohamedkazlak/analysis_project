from pydantic import BaseModel
from typing import List, Literal


class AttemptsPerExam(BaseModel):
    exam: str
    attempts: int
    expected: int


class AttendanceByCurriculum(BaseModel):
    course: str
    attendance: float
    absentees: int
    students: int = 0
    participated: int = 0


class AvgTimePerExam(BaseModel):
    exam: str
    minutes: int


class AbsenteeRow(BaseModel):
    student: str
    exam: str
    reason: Literal["No attempt", "Late start"]
    minutesLate: int
    college: str = ""


class ParticipationReport(BaseModel):
    grain: Literal["college", "curriculum", "exam"] = "exam"
    attemptsPerExam: List[AttemptsPerExam]
    completionRate: float
    attendanceRate: float
    attendanceByCurriculum: List[AttendanceByCurriculum]
    avgTimePerExam: List[AvgTimePerExam]
    absentees: List[AbsenteeRow]
    insight: str
