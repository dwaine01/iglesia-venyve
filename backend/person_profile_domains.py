"""Person Profile 360 modular domains.

Household, family, arrival, attendance, notes, activity and photo data remain
outside the persons collection. The profile read-model aggregates them.
"""
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import uuid4

from bson import ObjectId
from bson.binary import Binary
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator

from access_control import (
    PERSON_ARRIVAL_READ,
    PERSON_ARRIVAL_WRITE,
    PERSON_ATTENDANCE_READ,
    PERSON_ATTENDANCE_WRITE,
    PERSON_FAMILY_READ,
    PERSON_FAMILY_WRITE,
    PERSON_HISTORY_READ,
    PERSON_HOUSEHOLD_READ,
    PERSON_HOUSEHOLD_WRITE,
    PERSON_NOTES_READ,
    PERSON_NOTES_WRITE,
    PERSON_MINISTRIES_READ,
    PERSON_MINISTRIES_WRITE,
    PERSON_PASTORAL_NOTES_READ,
    PERSON_TALENTS_READ,
    PERSON_TALENTS_WRITE,
    PERSON_PROFILE_SENSITIVE_READ,
    PERSON_PROFILE_WRITE,
    PROCESSES_READ,
    PROCESSES_WRITE,
    authorize_person,
    has_capability,
)
from core_person import _age_category, db, now_utc, require_person_profile_user
from person_core_expansion import age_info, household_snapshot, relationship_items, talent_snapshot
from ministries import assignment_items
from process_engine import create_enrollment, evaluate_alerts

router = APIRouter(prefix="/api/core/persons", tags=["person-profile-domains"])
MAX_PHOTO_BYTES = 5 * 1024 * 1024
PHOTO_CHUNK_BYTES = 512 * 1024
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}

def iso_z(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


async def load_person(person_id: str) -> dict:
    try:
        oid = ObjectId(person_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="person_id invalido")
    person = await db.persons.find_one({"_id": oid})
    if not person:
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    person["person_id"] = person_id
    return person


async def authorize_domain(person_id: str, current_user: dict, capability: str) -> dict:
    person = await load_person(person_id)
    authorize_person(current_user, person, capability)
    return person


async def record_activity(
    person_id: str,
    current_user: dict,
    domain: str,
    action: str,
    summary: str,
) -> None:
    await db.person_activity.insert_one({
        "_id": str(uuid4()),
        "person_id": person_id,
        "domain": domain,
        "action": action,
        "summary": summary,
        "actor_user_id": current_user.get("user_id"),
        "created_at": now_utc(),
    })


class BasicsUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    apellido: Optional[str] = Field(default=None, min_length=2, max_length=100)
    fecha_nacimiento: Optional[str] = None
    genero: Optional[Literal["masculino", "femenino", "no_especificado"]] = None
    estado_civil: Optional[
        Literal[
            "soltero", "casado", "divorciado", "viudo",
            "separado", "otro", "no_especificado",
        ]
    ] = None

    @field_validator("nombre", "apellido")
    @classmethod
    def clean_text(cls, value: Optional[str]) -> Optional[str]:
        return clean_optional(value)

    @field_validator("fecha_nacimiento")
    @classmethod
    def valid_date(cls, value: Optional[str]) -> Optional[str]:
        value = clean_optional(value)
        if value:
            try:
                datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("fecha_nacimiento invalida") from exc
        return value

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_dump(exclude_none=True):
            raise ValueError("Incluya al menos un campo")
        return self


class HouseholdPayload(BaseModel):
    nombre_hogar: str = Field(..., min_length=2, max_length=140)
    rol_en_hogar: Optional[str] = Field(default=None, max_length=80)
    tipo_vivienda: Optional[str] = Field(default=None, max_length=80)
    miembros_estimados: Optional[int] = Field(default=None, ge=1, le=50)
    notas: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("nombre_hogar")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("rol_en_hogar", "tipo_vivienda", "notas")
    @classmethod
    def clean_fields(cls, value: Optional[str]) -> Optional[str]:
        return clean_optional(value)


class FamilyPayload(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=140)
    relacion: str = Field(..., min_length=2, max_length=80)
    alcance: Literal["inmediata", "extendida"] = "inmediata"
    related_person_id: Optional[str] = None
    telefono: Optional[str] = Field(default=None, max_length=80)
    notas: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("nombre", "relacion")
    @classmethod
    def clean_required(cls, value: str) -> str:
        return value.strip()

    @field_validator("related_person_id", "telefono", "notas")
    @classmethod
    def clean_fields(cls, value: Optional[str]) -> Optional[str]:
        return clean_optional(value)


class ArrivalPayload(BaseModel):
    fecha_llegada: str
    tipo: Literal["visitante", "transferencia", "nacimiento", "otro"] = "visitante"
    lugar_origen: Optional[str] = Field(default=None, max_length=180)
    invitado_por: Optional[str] = Field(default=None, max_length=140)
    motivo: Optional[str] = Field(default=None, max_length=300)
    notas: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("fecha_llegada")
    @classmethod
    def valid_date(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("fecha_llegada invalida") from exc
        return value

    @field_validator("lugar_origen", "invitado_por", "motivo", "notas")
    @classmethod
    def clean_fields(cls, value: Optional[str]) -> Optional[str]:
        return clean_optional(value)


class AttendancePayload(BaseModel):
    fecha: str
    actividad: str = Field(..., min_length=2, max_length=180)
    estado: Literal["presente", "ausente", "justificado"] = "presente"
    notas: Optional[str] = Field(default=None, max_length=500)

    @field_validator("fecha")
    @classmethod
    def valid_date(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("fecha invalida") from exc
        return value

    @field_validator("actividad")
    @classmethod
    def clean_activity(cls, value: str) -> str:
        return value.strip()

    @field_validator("notas")
    @classmethod
    def clean_notes(cls, value: Optional[str]) -> Optional[str]:
        return clean_optional(value)


class NotePayload(BaseModel):
    contenido: str = Field(..., min_length=2, max_length=4000)
    categoria: Literal["general", "pastoral", "seguimiento"] = "general"

    @field_validator("contenido")
    @classmethod
    def clean_content(cls, value: str) -> str:
        return value.strip()


class PhotoUploadInit(BaseModel):
    content_type: str
    total_size: int = Field(..., ge=1, le=MAX_PHOTO_BYTES)
    total_chunks: int = Field(..., ge=1, le=20)

    @field_validator("content_type")
    @classmethod
    def allowed_type(cls, value: str) -> str:
        if value not in ALLOWED_PHOTO_TYPES:
            raise ValueError("Formato de imagen no permitido")
        return value



def serialize_household(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return None
    return {
        "household_id": doc["_id"],
        "person_id": doc["person_id"],
        "nombre_hogar": doc["nombre_hogar"],
        "rol_en_hogar": doc.get("rol_en_hogar"),
        "tipo_vivienda": doc.get("tipo_vivienda"),
        "miembros_estimados": doc.get("miembros_estimados"),
        "notas": doc.get("notas"),
        "updated_at": iso_z(doc.get("updated_at")),
    }


def serialize_family(doc: dict) -> dict:
    return {
        "relation_id": doc["_id"],
        "person_id": doc["person_id"],
        "nombre": doc["nombre"],
        "relacion": doc["relacion"],
        "alcance": doc["alcance"],
        "related_person_id": doc.get("related_person_id"),
        "related_profile_path": (
            f"/personas/{doc['related_person_id']}" if doc.get("related_person_id") else None
        ),
        "telefono": doc.get("telefono"),
        "notas": doc.get("notas"),
        "created_at": iso_z(doc.get("created_at")),
        "updated_at": iso_z(doc.get("updated_at")),
    }


def serialize_arrival(doc: Optional[dict]) -> Optional[dict]:
    if not doc:
        return None
    return {
        "arrival_id": doc["_id"],
        "person_id": doc["person_id"],
        "fecha_llegada": doc["fecha_llegada"],
        "tipo": doc["tipo"],
        "lugar_origen": doc.get("lugar_origen"),
        "invitado_por": doc.get("invitado_por"),
        "motivo": doc.get("motivo"),
        "notas": doc.get("notas"),
        "updated_at": iso_z(doc.get("updated_at")),
    }


def serialize_attendance(doc: dict) -> dict:
    return {
        "attendance_id": doc["_id"],
        "person_id": doc["person_id"],
        "fecha": doc["fecha"],
        "actividad": doc["actividad"],
        "estado": doc["estado"],
        "notas": doc.get("notas"),
        "created_at": iso_z(doc.get("created_at")),
        "updated_at": iso_z(doc.get("updated_at")),
    }


def serialize_note(doc: dict) -> dict:
    return {
        "note_id": doc["_id"],
        "person_id": doc["person_id"],
        "contenido": doc["contenido"],
        "categoria": doc["categoria"],
        "created_at": iso_z(doc.get("created_at")),
        "updated_at": iso_z(doc.get("updated_at")),
    }


def serialize_activity(doc: dict) -> dict:
    return {
        "activity_id": doc["_id"],
        "domain": doc["domain"],
        "action": doc["action"],
        "summary": doc["summary"],
        "created_at": iso_z(doc.get("created_at")),
    }


async def profile_domain_snapshot(person_id: str, current_user: dict) -> dict:
    permissions = {
        "household": {
            "read": has_capability(current_user, PERSON_HOUSEHOLD_READ),
            "write": has_capability(current_user, PERSON_HOUSEHOLD_WRITE),
        },
        "familia": {
            "read": has_capability(current_user, PERSON_FAMILY_READ),
            "write": has_capability(current_user, PERSON_FAMILY_WRITE),
        },
        "procesos": {
            "read": has_capability(current_user, PROCESSES_READ),
            "write": has_capability(current_user, PROCESSES_WRITE),
        },
        "asistencia": {
            "read": has_capability(current_user, PERSON_ATTENDANCE_READ),
            "write": has_capability(current_user, PERSON_ATTENDANCE_WRITE),
        },
        "notas": {
            "read": has_capability(current_user, PERSON_NOTES_READ),
            "write": has_capability(current_user, PERSON_NOTES_WRITE),
            "pastoral": has_capability(current_user, PERSON_PASTORAL_NOTES_READ),
        },
        "historial": {
            "read": has_capability(current_user, PERSON_HISTORY_READ),
            "write": False,
        },
        "talentos": {
            "read": has_capability(current_user, PERSON_TALENTS_READ),
            "write": has_capability(current_user, PERSON_TALENTS_WRITE),
        },
        "ministerios": {
            "read": has_capability(current_user, PERSON_MINISTRIES_READ),
            "write": has_capability(current_user, PERSON_MINISTRIES_WRITE),
        },
    }
    household = (
        await household_snapshot(person_id)
        if permissions["household"]["read"]
        else None
    )
    arrival_doc = (
        await db.person_arrivals.find_one({"person_id": person_id})
        if permissions["procesos"]["read"]
        else None
    )
    family = (
        await relationship_items(person_id)
        if permissions["familia"]["read"]
        else []
    )
    attendance_docs = (
        await db.person_attendance.find({"person_id": person_id}).sort("fecha", -1).to_list(100)
        if permissions["asistencia"]["read"]
        else []
    )
    note_filter = {"person_id": person_id}
    if not permissions["notas"]["pastoral"]:
        note_filter["categoria"] = {"$ne": "pastoral"}
    note_docs = (
        await db.person_notes.find(note_filter).sort("created_at", -1).to_list(100)
        if permissions["notas"]["read"]
        else []
    )
    activity_docs = (
        await db.person_activity.find({"person_id": person_id}).sort("created_at", -1).to_list(100)
        if permissions["historial"]["read"]
        else []
    )
    photo = (
        await db.person_photos.find_one({"person_id": person_id}, {"_id": 1})
        if has_capability(current_user, PERSON_PROFILE_SENSITIVE_READ)
        else None
    )
    process_docs = (
        await db.process_enrollments.find(
            {"person_id": person_id},
            {"_id": 0, "enrollment_id": 1, "process_key": 1, "status": 1, "current_stage_key": 1, "progress_pct": 1, "next_action": 1, "next_action_at": 1, "responsible_person_id": 1, "ready_for_cellular": 1},
        ).sort("updated_at", -1).to_list(100)
        if permissions["procesos"]["read"]
        else []
    )
    process_names = {
        "seven_weeks": "Ley de las 7 Semanas",
        "consolidation": "Consolidación",
        "mentorship": "Mentoría",
        "cap": "CAP",
    }
    process_status_labels = {
        "planned": "Planificado",
        "active": "Activo",
        "paused": "Pausado",
        "completed": "Completado",
        "cancelled": "Cancelado",
    }
    return {
        "permissions": permissions,
        "photo_available": bool(photo),
        "household": household,
        "familia": family,
        "talentos": await talent_snapshot(person_id),
        "ministerios": (
            await assignment_items(person_id) if permissions["ministerios"]["read"] else []
        ),
        "llegada_origen": serialize_arrival(arrival_doc),
        "asistencia": [serialize_attendance(item) for item in attendance_docs],
        "notas": [serialize_note(item) for item in note_docs],
        "historial": [serialize_activity(item) for item in activity_docs],
        "procesos": [
            {
                **item,
                "key": item["process_key"],
                "label": process_names.get(item["process_key"], item["process_key"]),
                "status_code": item.get("status"),
                "status_label": process_status_labels.get(item.get("status"), item.get("status", "")),
                "route": f"/procesos/{'7-semanas' if item['process_key'] == 'seven_weeks' else item['process_key']}",
            }
            for item in process_docs
        ],
    }


@router.put("/{person_id}/profile-basics")
async def update_profile_basics(
    person_id: str,
    payload: BasicsUpdate,
    current_user: dict = Depends(require_person_profile_user),
):
    person = await authorize_domain(person_id, current_user, PERSON_PROFILE_WRITE)
    update = payload.model_dump(exclude_none=True)
    if "fecha_nacimiento" in update:
        update["age_category"] = _age_category(update["fecha_nacimiento"])
    update["updated_at"] = now_utc()
    await db.persons.update_one({"_id": person["_id"]}, {"$set": update})
    await record_activity(person_id, current_user, "core", "updated", "Datos básicos actualizados")
    return {"message": "Perfil actualizado"}


@router.post("/{person_id}/photo/uploads", status_code=status.HTTP_201_CREATED)
async def init_photo_upload(
    person_id: str,
    payload: PhotoUploadInit,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_PROFILE_WRITE)
    expected_chunks = (payload.total_size + PHOTO_CHUNK_BYTES - 1) // PHOTO_CHUNK_BYTES
    if payload.total_chunks != expected_chunks:
        raise HTTPException(status_code=400, detail="Cantidad de fragmentos invalida")
    upload_id = str(uuid4())
    await db.person_photo_uploads.insert_one({
        "_id": upload_id,
        "person_id": person_id,
        "content_type": payload.content_type,
        "total_size": payload.total_size,
        "total_chunks": payload.total_chunks,
        "created_by": current_user["user_id"],
        "created_at": now_utc(),
    })
    return {"upload_id": upload_id, "chunk_size": PHOTO_CHUNK_BYTES}


@router.put("/{person_id}/photo/uploads/{upload_id}/chunks/{chunk_index}")
async def upload_photo_chunk(
    person_id: str,
    upload_id: str,
    chunk_index: int,
    request: Request,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_PROFILE_WRITE)
    upload = await db.person_photo_uploads.find_one({"_id": upload_id, "person_id": person_id})
    if not upload:
        raise HTTPException(status_code=404, detail="Carga no encontrada")
    if chunk_index < 0 or chunk_index >= upload["total_chunks"]:
        raise HTTPException(status_code=400, detail="Fragmento invalido")
    chunk = await request.body()
    if not chunk or len(chunk) > PHOTO_CHUNK_BYTES:
        raise HTTPException(status_code=400, detail="Tamaño de fragmento invalido")
    await db.person_photo_chunks.update_one(
        {"_id": f"{upload_id}:{chunk_index}"},
        {"$set": {"upload_id": upload_id, "index": chunk_index, "data": Binary(chunk)}},
        upsert=True,
    )
    return {"chunk_index": chunk_index, "received": len(chunk)}


def valid_image_signature(data: bytes, content_type: str) -> bool:
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    return False


@router.post("/{person_id}/photo/uploads/{upload_id}/complete")
async def complete_photo_upload(
    person_id: str,
    upload_id: str,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_PROFILE_WRITE)
    upload = await db.person_photo_uploads.find_one({"_id": upload_id, "person_id": person_id})
    if not upload:
        raise HTTPException(status_code=404, detail="Carga no encontrada")
    chunks = await db.person_photo_chunks.find({"upload_id": upload_id}).sort("index", 1).to_list(20)
    if len(chunks) != upload["total_chunks"]:
        raise HTTPException(status_code=400, detail="Faltan fragmentos de imagen")
    data = b"".join(bytes(item["data"]) for item in chunks)
    if len(data) != upload["total_size"] or not valid_image_signature(data, upload["content_type"]):
        raise HTTPException(status_code=400, detail="Imagen invalida")
    photo_id = str(uuid4())
    await db.person_photos.delete_many({"person_id": person_id})
    await db.person_photos.insert_one({
        "_id": photo_id,
        "person_id": person_id,
        "content_type": upload["content_type"],
        "data": Binary(data),
        "size": len(data),
        "created_by": current_user["user_id"],
        "created_at": now_utc(),
    })
    await db.person_photo_chunks.delete_many({"upload_id": upload_id})
    await db.person_photo_uploads.delete_one({"_id": upload_id})
    await record_activity(person_id, current_user, "photo", "updated", "Fotografía actualizada")
    return {"photo_id": photo_id, "photo_available": True}


@router.get("/{person_id}/photo")
async def get_person_photo(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    await authorize_domain(person_id, current_user, PERSON_PROFILE_SENSITIVE_READ)
    photo = await db.person_photos.find_one({"person_id": person_id})
    if not photo:
        raise HTTPException(status_code=404, detail="Fotografía no encontrada")
    return Response(
        content=bytes(photo["data"]),
        media_type=photo["content_type"],
        headers={"Cache-Control": "private, max-age=300", "ETag": photo["_id"]},
    )


@router.delete("/{person_id}/photo")
async def delete_person_photo(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    await authorize_domain(person_id, current_user, PERSON_PROFILE_WRITE)
    result = await db.person_photos.delete_many({"person_id": person_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Fotografía no encontrada")
    await record_activity(person_id, current_user, "photo", "deleted", "Fotografía eliminada")
    return {"message": "Fotografía eliminada"}


@router.get("/{person_id}/household")
async def get_household(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    await authorize_domain(person_id, current_user, PERSON_HOUSEHOLD_READ)
    return {"record": serialize_household(await db.person_households.find_one({"person_id": person_id}))}


@router.put("/{person_id}/household")
async def upsert_household(
    person_id: str,
    payload: HouseholdPayload,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_HOUSEHOLD_WRITE)
    now = now_utc()
    doc = {"person_id": person_id, **payload.model_dump(), "updated_at": now}
    await db.person_households.update_one(
        {"_id": person_id},
        {"$set": doc, "$setOnInsert": {"created_at": now, "created_by": current_user["user_id"]}},
        upsert=True,
    )
    await record_activity(person_id, current_user, "household", "updated", "Household actualizado")
    return serialize_household(await db.person_households.find_one({"_id": person_id}))


@router.delete("/{person_id}/household")
async def delete_household(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    await authorize_domain(person_id, current_user, PERSON_HOUSEHOLD_WRITE)
    result = await db.person_households.delete_one({"_id": person_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Household no encontrado")
    await record_activity(person_id, current_user, "household", "deleted", "Household eliminado")
    return {"message": "Household eliminado"}


@router.get("/{person_id}/family")
async def list_family(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    await authorize_domain(person_id, current_user, PERSON_FAMILY_READ)
    raise HTTPException(
        status_code=410,
        detail="Familia usa relaciones canónicas; consulte /relationships",
    )


@router.post("/{person_id}/family", status_code=status.HTTP_201_CREATED)
async def create_family(
    person_id: str,
    payload: FamilyPayload,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_FAMILY_WRITE)
    raise HTTPException(
        status_code=410,
        detail="No se permiten familiares como texto; use /relationships",
    )


@router.put("/{person_id}/family/{relation_id}")
async def update_family(
    person_id: str,
    relation_id: str,
    payload: FamilyPayload,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_FAMILY_WRITE)
    raise HTTPException(
        status_code=410,
        detail="No se permiten familiares como texto; use /relationships",
    )


@router.delete("/{person_id}/family/{relation_id}")
async def delete_family(
    person_id: str,
    relation_id: str,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_FAMILY_WRITE)
    result = await db.person_family.delete_one({"_id": relation_id, "person_id": person_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Relación heredada no encontrada")
    return {"message": "Relación heredada eliminada"}


@router.get("/{person_id}/arrival")
async def get_arrival(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    await authorize_domain(person_id, current_user, PERSON_ARRIVAL_READ)
    return {"record": serialize_arrival(await db.person_arrivals.find_one({"person_id": person_id}))}


@router.put("/{person_id}/arrival")
async def upsert_arrival(
    person_id: str,
    payload: ArrivalPayload,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_ARRIVAL_WRITE)
    now = now_utc()
    doc = {"person_id": person_id, **payload.model_dump(), "updated_at": now}
    await db.person_arrivals.update_one(
        {"_id": person_id},
        {"$set": doc, "$setOnInsert": {"created_at": now, "created_by": current_user["user_id"]}},
        upsert=True,
    )
    await record_activity(person_id, current_user, "llegada_origen", "updated", "Llegada y origen actualizados")
    enrollment, created = await create_enrollment(
        db,
        "consolidation",
        person_id,
        current_user.get("person_id") if current_user.get("rol") in {"pastor", "lider"} else None,
        current_user["user_id"],
        status="active",
        next_action="Realizar primer contacto",
        next_action_at=now + timedelta(hours=24),
        source="arrival_automation",
        source_id=person_id,
    )
    if created:
        await record_activity(person_id, current_user, "procesos", "created", f"Seguimiento de Consolidación creado: {enrollment['enrollment_id']}")
    await evaluate_alerts(db)
    return serialize_arrival(await db.person_arrivals.find_one({"_id": person_id}))


@router.delete("/{person_id}/arrival")
async def delete_arrival(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    await authorize_domain(person_id, current_user, PERSON_ARRIVAL_WRITE)
    result = await db.person_arrivals.delete_one({"_id": person_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Llegada y origen no encontrados")
    await record_activity(person_id, current_user, "llegada_origen", "deleted", "Llegada y origen eliminados")
    return {"message": "Llegada y origen eliminados"}


@router.get("/{person_id}/attendance")
async def list_attendance(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    await authorize_domain(person_id, current_user, PERSON_ATTENDANCE_READ)
    docs = await db.person_attendance.find({"person_id": person_id}).sort("fecha", -1).to_list(300)
    return {"items": [serialize_attendance(doc) for doc in docs]}


@router.post("/{person_id}/attendance", status_code=status.HTTP_201_CREATED)
async def create_attendance(
    person_id: str,
    payload: AttendancePayload,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_ATTENDANCE_WRITE)
    now = now_utc()
    doc = {
        "_id": str(uuid4()),
        "person_id": person_id,
        **payload.model_dump(),
        "created_by": current_user["user_id"],
        "created_at": now,
        "updated_at": now,
    }
    await db.person_attendance.insert_one(doc)
    await record_activity(person_id, current_user, "asistencia", "created", f"Asistencia: {doc['actividad']}")
    return serialize_attendance(doc)


@router.put("/{person_id}/attendance/{attendance_id}")
async def update_attendance(
    person_id: str,
    attendance_id: str,
    payload: AttendancePayload,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_ATTENDANCE_WRITE)
    result = await db.person_attendance.update_one(
        {"_id": attendance_id, "person_id": person_id},
        {"$set": {**payload.model_dump(), "updated_at": now_utc()}},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Asistencia no encontrada")
    await record_activity(person_id, current_user, "asistencia", "updated", "Asistencia actualizada")
    return serialize_attendance(await db.person_attendance.find_one({"_id": attendance_id}))


@router.delete("/{person_id}/attendance/{attendance_id}")
async def delete_attendance(
    person_id: str,
    attendance_id: str,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_ATTENDANCE_WRITE)
    result = await db.person_attendance.delete_one({"_id": attendance_id, "person_id": person_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Asistencia no encontrada")
    await record_activity(person_id, current_user, "asistencia", "deleted", "Asistencia eliminada")
    return {"message": "Asistencia eliminada"}


@router.get("/{person_id}/notes")
async def list_notes(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    await authorize_domain(person_id, current_user, PERSON_NOTES_READ)
    note_filter = {"person_id": person_id}
    if not has_capability(current_user, PERSON_PASTORAL_NOTES_READ):
        note_filter["categoria"] = {"$ne": "pastoral"}
    docs = await db.person_notes.find(note_filter).sort("created_at", -1).to_list(300)
    return {"items": [serialize_note(doc) for doc in docs]}


@router.post("/{person_id}/notes", status_code=status.HTTP_201_CREATED)
async def create_note(
    person_id: str,
    payload: NotePayload,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_NOTES_WRITE)
    if payload.categoria == "pastoral" and not has_capability(
        current_user, PERSON_PASTORAL_NOTES_READ
    ):
        raise HTTPException(status_code=403, detail="Nota pastoral restringida")
    now = now_utc()
    doc = {
        "_id": str(uuid4()),
        "person_id": person_id,
        **payload.model_dump(),
        "created_by": current_user["user_id"],
        "created_at": now,
        "updated_at": now,
    }
    await db.person_notes.insert_one(doc)
    await record_activity(person_id, current_user, "notas", "created", "Nota agregada")
    return serialize_note(doc)


@router.put("/{person_id}/notes/{note_id}")
async def update_note(
    person_id: str,
    note_id: str,
    payload: NotePayload,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_NOTES_WRITE)
    if payload.categoria == "pastoral" and not has_capability(
        current_user, PERSON_PASTORAL_NOTES_READ
    ):
        raise HTTPException(status_code=403, detail="Nota pastoral restringida")
    result = await db.person_notes.update_one(
        {"_id": note_id, "person_id": person_id},
        {"$set": {**payload.model_dump(), "updated_at": now_utc()}},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    await record_activity(person_id, current_user, "notas", "updated", "Nota actualizada")
    return serialize_note(await db.person_notes.find_one({"_id": note_id}))


@router.delete("/{person_id}/notes/{note_id}")
async def delete_note(
    person_id: str,
    note_id: str,
    current_user: dict = Depends(require_person_profile_user),
):
    await authorize_domain(person_id, current_user, PERSON_NOTES_WRITE)
    result = await db.person_notes.delete_one({"_id": note_id, "person_id": person_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    await record_activity(person_id, current_user, "notas", "deleted", "Nota eliminada")
    return {"message": "Nota eliminada"}


@router.get("/{person_id}/history")
async def list_history(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    await authorize_domain(person_id, current_user, PERSON_HISTORY_READ)
    docs = await db.person_activity.find({"person_id": person_id}).sort("created_at", -1).to_list(500)
    return {"items": [serialize_activity(doc) for doc in docs]}


@router.get("/{person_id}/processes")
async def list_process_connectors(person_id: str, current_user: dict = Depends(require_person_profile_user)):
    await authorize_domain(person_id, current_user, PROCESSES_READ)
    docs = await db.process_enrollments.find(
        {"person_id": person_id},
        {"_id": 0, "enrollment_id": 1, "process_key": 1, "status": 1, "current_stage_key": 1, "progress_pct": 1, "next_action": 1, "next_action_at": 1, "ready_for_cellular": 1},
    ).sort("updated_at", -1).to_list(100)
    return {"items": [{**doc, "canonical_profile_path": f"/personas/{person_id}"} for doc in docs]}


async def ensure_indexes() -> None:
    await db.person_households.create_index("person_id", unique=True)
    await db.person_family.create_index([("person_id", 1), ("created_at", 1)])
    await db.person_arrivals.create_index("person_id", unique=True)
    await db.person_attendance.create_index([("person_id", 1), ("fecha", -1)])
    await db.person_notes.create_index([("person_id", 1), ("created_at", -1)])
    await db.person_activity.create_index([("person_id", 1), ("created_at", -1)])
    await db.person_photos.create_index("person_id", unique=True)
    await db.person_photo_uploads.create_index("created_at", expireAfterSeconds=3600)
    await db.person_photo_chunks.create_index("upload_id")
