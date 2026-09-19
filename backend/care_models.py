"""Contratos del Mega-Bloque F — Cuidado Pastoral."""
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


CareStatus = Literal["detected", "assigned", "contacted", "follow_up", "resolved", "closed", "escalated"]
CarePriority = Literal["low", "medium", "high", "urgent"]
CaseType = Literal[
    "first_conversion", "reconciliation", "restoration", "return", "crisis",
    "bereavement", "family", "health", "visitation", "pastoral_care", "other",
]


class CareCaseCreate(BaseModel):
    person_id: str
    case_type: CaseType = "pastoral_care"
    priority: CarePriority = "medium"
    source_type: str = Field(default="manual", min_length=2, max_length=80)
    source_id: Optional[str] = Field(default=None, max_length=160)
    household_id: Optional[str] = None
    operational_summary: Optional[str] = Field(default=None, max_length=500)
    next_step: Optional[str] = Field(default=None, max_length=500)
    next_step_at: Optional[datetime] = None


class CareCaseUpdate(BaseModel):
    priority: Optional[CarePriority] = None
    operational_summary: Optional[str] = Field(default=None, max_length=500)
    next_step: Optional[str] = Field(default=None, max_length=500)
    next_step_at: Optional[datetime] = None


class CareTransition(BaseModel):
    status: CareStatus
    reason: str = Field(min_length=3, max_length=1200)


class CareAssignmentCreate(BaseModel):
    assignee_person_id: str
    assignment_role: Literal["primary", "support", "supervisor"] = "primary"
    reason: Optional[str] = Field(default=None, max_length=600)


class CareContactCreate(BaseModel):
    method: Literal["call", "message", "visit", "in_person", "other"]
    outcome: Literal["successful", "no_answer", "wrong_number", "rescheduled", "refused", "no_access"]
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    next_step: Optional[str] = Field(default=None, max_length=500)
    next_step_at: Optional[datetime] = None


class CareEscalation(BaseModel):
    authority_person_id: str
    reason: str = Field(min_length=5, max_length=1500)


class CareNoteCreate(BaseModel):
    content: str = Field(min_length=2, max_length=20000)
    visibility: Literal["pastoral_core", "assigned_team"] = "pastoral_core"


class CareNoteAddendum(BaseModel):
    content: str = Field(min_length=2, max_length=20000)


class Op72Create(BaseModel):
    person_id: str
    decision_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_type: Literal["cell_meeting", "operation_occurrence", "evangelism_target", "manual"] = "manual"
    source_id: Optional[str] = Field(default=None, max_length=160)


class Op72LifecycleAction(BaseModel):
    reason: str = Field(min_length=3, max_length=1200)


class VisitParticipantCreate(BaseModel):
    person_id: str
    case_id: Optional[str] = None


class VisitCreate(BaseModel):
    household_id: Optional[str] = None
    participants: list[VisitParticipantCreate] = Field(min_length=1, max_length=30)
    scheduled_at: datetime
    lead_visitor_person_id: str
    visitor_person_ids: list[str] = Field(default_factory=list, max_length=12)
    purpose: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def validate_grouping(self):
        ids = [item.person_id for item in self.participants]
        if len(ids) != len(set(ids)):
            raise ValueError("No repita una Persona en la misma visita")
        if not self.household_id and len(ids) > 1:
            raise ValueError("Una visita con varias Personas requiere un Hogar canónico")
        return self


class VisitParticipantResult(BaseModel):
    person_id: str
    outcome: Literal["successful", "no_access", "absent", "rescheduled", "refused"]
    next_step: Optional[str] = Field(default=None, max_length=500)
    next_step_at: Optional[datetime] = None


class VisitComplete(BaseModel):
    participant_results: list[VisitParticipantResult] = Field(min_length=1, max_length=30)
    confidential_summary: Optional[str] = Field(default=None, max_length=20000)


class CareAlertAction(BaseModel):
    status: Literal["acknowledged", "resolved"]
    resolution: Optional[str] = Field(default=None, max_length=800)


class CareEntityResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


class CareCaseResponse(CareEntityResponse):
    case_id: str
    person_id: str
    case_type: str
    status: str
    priority: str


class Op72Response(CareEntityResponse):
    op72_id: str
    person_id: str
    case_id: str
    first_conversion_at: datetime | str


class VisitResponse(CareEntityResponse):
    visit_id: str
    status: str


class CareListResponse(BaseModel):
    items: list[dict]
    total: int
