from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ApprovalPolicy(BaseModel):
    method: Literal["attendance_only", "attendance_and_grade", "grade_only", "manual", "custom"] = "attendance_only"
    minimum_attendance_pct: float = Field(default=80, ge=0, le=100)
    minimum_grade_pct: float = Field(default=70, ge=0, le=100)
    late_weight: float = Field(default=0.5, ge=0, le=1)
    excused_policy: Literal["exclude", "valid", "absent"] = "exclude"
    manual_confirmation_required: bool = False
    custom_requirements: list[str] = Field(default_factory=list, max_length=20)


class ProgramInput(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=3000)
    purpose: Literal["general", "discipleship", "baptism_preparation", "leadership", "ministry"] = "general"
    active: bool = True
    certificate_enabled: bool = False
    certificate_scope: Literal["none", "program"] = "none"


class ModuleInput(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=3000)
    order: int = Field(ge=1, le=10000)
    active: bool = True
    approval_policy: ApprovalPolicy = Field(default_factory=ApprovalPolicy)
    certificate_enabled: bool = False


class PrerequisitesInput(BaseModel):
    prerequisite_module_ids: list[str] = Field(default_factory=list, max_length=100)
    mode: Literal["all", "any"] = "all"


class CohortInput(BaseModel):
    module_id: str
    name: str = Field(min_length=2, max_length=180)
    start_date: str
    end_date: Optional[str] = None
    schedule: Optional[str] = Field(default=None, max_length=500)
    modality: Literal["onsite", "online", "hybrid"] = "onsite"
    location: Optional[str] = Field(default=None, max_length=300)
    capacity: int = Field(default=30, ge=1, le=10000)
    status: Literal["planned", "open", "in_progress", "completed", "cancelled"] = "planned"


class CohortStaffInput(BaseModel):
    person_id: str
    role: Literal["teacher", "assistant"] = "teacher"


class SessionInput(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    session_date: str
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    teacher_person_id: Optional[str] = None
    required: bool = True
    notes: Optional[str] = Field(default=None, max_length=2000)


class EnrollmentInput(BaseModel):
    person_id: str
    override_eligibility: bool = False
    override_reason: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_override_reason(self):
        if self.override_eligibility and not self.override_reason:
            raise ValueError("Explique la excepción de elegibilidad")
        return self


class AttendanceItem(BaseModel):
    enrollment_id: str
    status: Literal["present", "absent", "late", "excused"]
    observation: Optional[str] = Field(default=None, max_length=1000)


class AttendanceBulkInput(BaseModel):
    items: list[AttendanceItem] = Field(min_length=1, max_length=500)


class AssessmentInput(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    weight: float = Field(gt=0, le=100)
    max_score: float = Field(default=100, gt=0, le=100000)
    due_date: Optional[str] = None
    required: bool = True


class GradeItem(BaseModel):
    enrollment_id: str
    score: float = Field(ge=0)
    observation: Optional[str] = Field(default=None, max_length=1000)


class GradeBulkInput(BaseModel):
    items: list[GradeItem] = Field(min_length=1, max_length=500)


class HistoricalCreditInput(BaseModel):
    module_id: str
    historical_completion_date: Optional[str] = None
    date_precision: Literal["exact", "month", "year", "unknown"] = "unknown"
    observation: str = Field(min_length=3, max_length=3000)
    evidence_document_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_date(self):
        if not self.historical_completion_date and self.date_precision != "unknown":
            raise ValueError("Sin fecha, la precisión debe ser desconocida")
        return self


class PromotionInput(BaseModel):
    target_cohort_id: str
    reason: Optional[str] = Field(default=None, max_length=1000)


class EnrollmentStatusInput(BaseModel):
    status: Literal["incomplete", "remediation_required", "withdrawn"]
    reason: str = Field(min_length=3, max_length=1000)


class ManualApprovalInput(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)