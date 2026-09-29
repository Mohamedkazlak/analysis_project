from pydantic import BaseModel
from typing import List, Optional


class ScoreTimelineRow(BaseModel):
    exam: str
    course: str = ""
    courseCode: str = ""
    chartLabel: str = ""
    date: str
    score: float
    classAverage: float


class TopicScore(BaseModel):
    topic: str
    score: float


class StudentDashboardReport(BaseModel):
    studentName: str
    college: str
    sector: str = ""
    termName: str = ""
    average: float
    gpa: Optional[float] = None
    classAverage: float
    bestTopic: str
    weakestTopic: str
    bestTopicScore: Optional[float] = None
    weakestTopicScore: Optional[float] = None
    topicsFrom: str = "questions"
    scoreTimeline: List[ScoreTimelineRow]
    topics: List[TopicScore]
    insight: str


class CourseScore(BaseModel):
    course: str
    code: Optional[str] = None
    credits: int
    average: float
    grade: str


class YearReport(BaseModel):
    year: str
    yearLabel: Optional[str] = None
    average: float
    gpa: float
    credits: int
    classAverage: float
    attendance: float
    standing: str
    examsTaken: int = 0
    passRate: float = 0
    courses: List[CourseScore]


class YearTrend(BaseModel):
    year: str
    student: float
    cohort: float


class CourseMatrix(BaseModel):
    course: str
    values: List[Optional[float]]


class RecentAttempt(BaseModel):
    exam: str
    course: str
    date: str
    score: float
    minutes: int
    status: str


class StudentProfileReport(BaseModel):
    studentId: str
    name: str
    program: str
    section: str
    cohortRank: int
    cohortSize: int
    overallAverage: float
    gpa: float
    classAverage: float
    attendance: float
    totalCredits: int
    standing: str
    years: List[YearReport]
    yearTrend: List[YearTrend]
    courseMatrix: List[CourseMatrix]
    recentAttempts: List[RecentAttempt]
    topics: List[TopicScore]
    insight: str
