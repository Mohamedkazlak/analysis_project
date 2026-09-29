from pydantic import BaseModel, Field
from typing import List, Literal


class AverageByCourse(BaseModel):
    course: str
    courseCode: str = ""
    average: float
    quality: float


class SectionRow(BaseModel):
    section: str
    course: str
    courseCode: str = ""
    college: str = ""
    average: float
    passRate: float
    enrolled: int = 0


class AssignedCourseRow(BaseModel):
    id: str
    code: str
    name: str
    enrolled: int
    sections: List[str]


class CoursePerformanceReport(BaseModel):
    averageByCourse: List[AverageByCourse]
    sections: List[SectionRow]
    assignedCourses: List[AssignedCourseRow] = Field(default_factory=list)
    insight: str
