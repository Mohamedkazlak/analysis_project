from typing import List, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    id: str
    password: str


class SessionProfile(BaseModel):
    """Display fields for the client. Later requests reload role and scope."""

    user_id: str
    role: str
    display_role: Optional[str] = None
    name: Optional[str] = None
    scope_level: Optional[str] = None
    scope_label: Optional[str] = None
    sector_id: Optional[str] = None
    college_id: Optional[str] = None
    student_id: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: SessionProfile


class AssignedCourse(BaseModel):
    id: str
    code: str
    name: str
    enrolled: int
    sections: List[str]


class UserContext(BaseModel):
    user_id: str
    role: str
    scope_id: Optional[str]
    person_id: str
    student_id: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    display_role: Optional[str] = None
    scope_level: Optional[str] = None
    sector_id: Optional[str] = None
    college_id: Optional[str] = None
    sector_name: Optional[str] = None
    college_name: Optional[str] = None
    university_name: Optional[str] = None
    scope_label: Optional[str] = None
    course_ids: List[str] = Field(default_factory=list)
    courses: List[AssignedCourse] = Field(default_factory=list)
    initials: Optional[str] = None
