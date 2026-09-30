from typing import List, Optional

from pydantic import BaseModel, Field


class AnalyticsFilters(BaseModel):
    """Shared analytics scope. `college_id` is an org_units program-level id."""

    sector_id: Optional[str] = None
    college_id: Optional[str] = None
    curriculum_id: Optional[str] = None
    student_id: Optional[str] = None
    professor_id: Optional[str] = None

    @classmethod
    def from_query(
        cls,
        sector_id: Optional[str] = None,
        college_id: Optional[str] = None,
        curriculum_id: Optional[str] = None,
        student_id: Optional[str] = None,
        professor_id: Optional[str] = None,
    ) -> "AnalyticsFilters":
        def clean(value: Optional[str]) -> Optional[str]:
            if value is None:
                return None
            stripped = value.strip()
            return stripped or None

        return cls(
            sector_id=clean(sector_id),
            college_id=clean(college_id),
            curriculum_id=clean(curriculum_id),
            student_id=clean(student_id),
            professor_id=clean(professor_id),
        )


class FilterOption(BaseModel):
    id: str
    name: str
    parentId: Optional[str] = None


class CurriculumOption(BaseModel):
    id: str
    code: str
    name: str
    collegeId: str


class StudentOption(BaseModel):
    id: str
    name: str
    collegeId: Optional[str] = None


class FilterOptionsResponse(BaseModel):
    role: str
    scopeLevel: Optional[str] = None
    scopeLabel: str
    visible: List[str]
    required: List[str]
    sectors: List[FilterOption]
    colleges: List[FilterOption]
    curricula: List[CurriculumOption]
    professors: List[FilterOption] = Field(default_factory=list)
    students: List[StudentOption]
    hasMoreStudents: bool = False
    studentPageSize: int = 150
    containsSynthetic: bool = False


class AiDecisionRequest(BaseModel):
    sectorId: Optional[str] = None
    collegeId: Optional[str] = None
    curriculumId: Optional[str] = None
    studentId: Optional[str] = None
    professorId: Optional[str] = None
    language: Optional[str] = "en"

    def to_filters(self) -> AnalyticsFilters:
        return AnalyticsFilters.from_query(
            self.sectorId,
            self.collegeId,
            self.curriculumId,
            self.studentId,
            self.professorId,
        )
