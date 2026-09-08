from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import re


# ---------------------------------------------------------------------------
# Institution schemas
# ---------------------------------------------------------------------------

class InstitutionCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    domain: Optional[str] = Field(None, description="e.g. 'stanford.edu'")
    max_seats: int = Field(100, ge=1)


class InstitutionResponse(BaseModel):
    id: str
    name: str
    domain: Optional[str]
    institution_code: str
    max_seats: int
    used_seats: int = 0
    created_at: str


# ---------------------------------------------------------------------------
# User / Auth schemas
# ---------------------------------------------------------------------------

class UserRegister(BaseModel):
    email: str = Field(..., description="Must be an institutional (.edu) email or use an institution code")
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2, max_length=100)
    institution_code: Optional[str] = Field(None, description="8-char code for non-.edu domains")

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email address")
        return v.lower().strip()


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserProfile"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    institution_id: Optional[str]
    institution_name: Optional[str]
    email_verified: bool
    created_at: str


class EmailVerifyRequest(BaseModel):
    token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


# ---------------------------------------------------------------------------
# Admin / Seat management schemas
# ---------------------------------------------------------------------------

class InviteRequest(BaseModel):
    emails: list[str] = Field(..., min_length=1)
    role: str = Field("student", pattern="^(instructor|student)$")


class InviteResponse(BaseModel):
    invited: list[str]
    already_registered: list[str]
    failed: list[str]


class RoleUpdateRequest(BaseModel):
    role: str = Field(..., pattern="^(super_admin|institution_admin|instructor|student)$")


class SeatAllocation(BaseModel):
    institution_id: str
    institution_name: str
    max_seats: int
    used_seats: int
    available_seats: int
    members: list[UserProfile]


class IntegrityMetrics(BaseModel):
    institution_id: str
    total_submissions: int
    avg_plagiarism_score: float
    avg_ai_score: float
    flagged_high: int      # plagiarism_score >= 0.6
    flagged_medium: int    # 0.3 <= plagiarism_score < 0.6
    clean: int             # plagiarism_score < 0.3


class AdminOverviewStats(BaseModel):
    total_users: int = 0
    total_institutions: int = 0
    total_submissions: int = 0
    avg_plagiarism_score: float = 0.0
    avg_ai_score: float = 0.0
    flagged_high: int = 0
    flagged_medium: int = 0
    clean: int = 0
    total_seats_allocated: int = 0
    total_seats_used: int = 0
    active_instructors: int = 0
    active_students: int = 0


class SubmissionAuditItem(BaseModel):
    id: str
    assignment_title: Optional[str] = "Research Paper Submission"
    student_name: Optional[str] = "Anonymous Scholar"
    student_email: Optional[str] = "scholar@university.edu"
    institution_name: Optional[str] = "Institutional Repository"
    plagiarism_score: float = 0.0
    ai_score: float = 0.0
    status: str = "completed"
    submitted_at: str


class AdminUserItem(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    institution_id: Optional[str] = None
    institution_name: Optional[str] = None
    email_verified: bool = False
    submissions_count: int = 0
    created_at: str


class ApiKeyCreate(BaseModel):
    label: str = Field(..., min_length=2, max_length=100)
    expires_in_days: Optional[int] = 90


class ApiKeyResponse(BaseModel):
    id: str
    label: str
    raw_key: Optional[str] = None
    key_prefix: str
    created_at: str
    expires_at: Optional[str] = None
