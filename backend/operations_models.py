"""Contratos Pydantic del Mega-Bloque E — Operaciones."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, model_validator


RecurrenceFrequency = Literal["none", "daily", "weekly", "monthly"]


class RecurrenceRule(BaseModel):
    frequency: RecurrenceFrequency = "none"
    interval: int = Field(default=1, ge=1, le=12)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    month_day: Optional[int] = Field(default=None, ge=1, le=31)
    end_mode: Literal["count", "until", "never"] = "count"
    count: Optional[int] = Field(default=1, ge=1, le=200)
    until: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_recurrence(self):
        if any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("Los días de semana deben estar entre 0 y 6")
        if self.frequency == "weekly" and not self.weekdays:
            raise ValueError("Seleccione al menos un día semanal")
        if self.end_mode == "until" and not self.until:
            raise ValueError("La recurrencia por fecha requiere fecha final")
        if self.end_mode == "count" and not self.count:
            raise ValueError("La recurrencia por cantidad requiere repeticiones")
        return self


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    event_type: Literal["service", "conference", "training", "outreach", "meeting", "other"] = "service"
    description: Optional[str] = Field(default=None, max_length=3000)
    location: str = Field(min_length=2, max_length=240)
    timezone: str = Field(default="America/New_York", min_length=3, max_length=80)
    starts_at: datetime
    ends_at: datetime
    capacity: Optional[int] = Field(default=None, ge=1, le=100000)
    registration_mode: Literal["open", "internal", "closed"] = "open"
    ministry_id: Optional[str] = None
    cell_id: Optional[str] = None
    recurrence: RecurrenceRule = Field(default_factory=RecurrenceRule)
    status: Literal["draft", "published"] = "published"

    @model_validator(mode="after")
    def valid_window(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("La hora final debe ser posterior al inicio")
        return self


class EventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=180)
    description: Optional[str] = Field(default=None, max_length=3000)
    location: Optional[str] = Field(default=None, min_length=2, max_length=240)
    capacity: Optional[int] = Field(default=None, ge=1, le=100000)
    registration_mode: Optional[Literal["open", "internal", "closed"]] = None
    status: Optional[Literal["draft", "published", "cancelled", "archived"]] = None


class ShiftTemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    role_name: str = Field(min_length=2, max_length=120)
    scope: Literal["all_occurrences", "single_occurrence"] = "all_occurrences"
    occurrence_id: Optional[str] = None
    start_offset_minutes: int = Field(default=0, ge=-720, le=1440)
    duration_minutes: int = Field(default=120, ge=15, le=1440)
    required_volunteers: int = Field(default=1, ge=1, le=500)
    ministry_id: Optional[str] = None
    cell_id: Optional[str] = None
    instructions: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def valid_scope(self):
        if self.scope == "single_occurrence" and not self.occurrence_id:
            raise ValueError("Un turno único requiere occurrence_id")
        return self


class VolunteerAssignmentCreate(BaseModel):
    person_id: str
    notes: Optional[str] = Field(default=None, max_length=500)


class VolunteerAssignmentAction(BaseModel):
    status: Literal["confirmed", "declined"]
    response_notes: Optional[str] = Field(default=None, max_length=500)


class RegistrationCreate(BaseModel):
    person_id: Optional[str] = None
    guest_name: Optional[str] = Field(default=None, max_length=180)
    guest_email: Optional[EmailStr] = None
    guest_phone: Optional[str] = Field(default=None, max_length=40)
    party_size: int = Field(default=1, ge=1, le=20)
    notes: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def person_or_guest(self):
        if not self.person_id and not (self.guest_name or "").strip():
            raise ValueError("Seleccione una Persona o escriba el nombre del invitado")
        if self.person_id and self.guest_name:
            raise ValueError("Use Persona canónica o invitado, no ambos")
        return self


class CheckInCreate(BaseModel):
    person_id: Optional[str] = None
    registration_id: Optional[str] = None
    code: Optional[str] = Field(default=None, max_length=500)
    kind: Literal["auto", "attendee", "volunteer"] = "auto"
    idempotency_key: str = Field(min_length=8, max_length=160)

    @model_validator(mode="after")
    def has_reference(self):
        if not self.person_id and not self.registration_id and not self.code:
            raise ValueError("Seleccione una Persona, inscripción o código")
        return self


class AttendanceClose(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=1000)