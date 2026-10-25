"""Radio propio (R1, opción C aprobada): «mantener para hablar» por invasión,
sobre WebSocket en este mismo backend (sin servicios ni dependencias nuevas).

- Canal = invasión. Entran sus participantes (con la invasión activa: desde
  el día anterior hasta el último día) y sus responsables (autoridad,
  coordinadores, organizador, encargado general) mientras no esté cerrada.
- Audio en vivo: PCM 16 kHz mono 16 bits en fragmentos binarios; solo puede
  hablar uno a la vez (turno del canal) y como máximo 60 s seguidos.
- NO se guarda el audio en vivo (privacidad); solo un registro de quién habló
  y cuándo (`radio_talk_log`).
- «Mensaje de voz» explícito: se guarda en GridFS (bucket `radio_messages`)
  y se borra solo a los 30 días.
- Limitación conocida (explicada en la pantalla): con la pantalla bloqueada o
  la app en segundo plano el navegador corta el audio; eso queda para R2.
- Las salas viven en memoria: Railway corre un solo proceso de uvicorn. Si se
  escala a varios, hará falta un canal compartido (p. ej. Redis)."""
import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from invasion_alerts import is_participant
from invasion_participants import can_edit_participants
from server import db, get_authenticated_user, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/radio", tags=["radio"])

MAX_TALK_SECONDS = 60
VOICE_RETENTION_DAYS = 30
MAX_VOICE_BYTES = 3 * 1024 * 1024
MAX_VOICE_SECONDS = 90
QUEUE_LIMIT = 64  # fragmentos pendientes por oyente antes de descartar (red lenta)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def bucket() -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(db, bucket_name="radio_messages")


async def person_name(person_id: Optional[str], fallback: str = "Participante") -> str:
    from mentorship_outreach import person_display_name
    return (await person_display_name(person_id) if person_id else None) or fallback


async def radio_access(campaign_id: str, user: dict) -> dict:
    """Devuelve la invasión si la persona puede usar su canal; si no, 403/404/409."""
    campaign = await db.outreach_campaigns.find_one({"campaign_id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Invasión no encontrada")
    if campaign.get("status") == "closed":
        raise HTTPException(status_code=409, detail="La invasión está cerrada")
    if can_edit_participants(user, campaign):
        return campaign
    if not await is_participant(campaign, user.get("person_id")):
        raise HTTPException(status_code=403, detail="El canal de radio es solo para los participantes de esta invasión")
    today = date.today()
    start = date.fromisoformat(campaign["start_date"]) - timedelta(days=1)
    end = date.fromisoformat(campaign.get("end_date") or campaign["start_date"])
    if not (start <= today <= end):
        raise HTTPException(status_code=409, detail="El canal de radio se abre el día antes de la invasión y se cierra al terminar")
    return campaign


# ------------------------------------------------------------------ salas en memoria
class Member:
    def __init__(self, websocket: WebSocket, user: dict, name: str):
        self.websocket = websocket
        self.user_id = user["user_id"]
        self.person_id = user.get("person_id")
        self.name = name
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_LIMIT)
        self.sender: Optional[asyncio.Task] = None

    def offer(self, item) -> None:
        try:
            self.queue.put_nowait(item)
        except asyncio.QueueFull:  # oyente con red lenta: se descarta audio viejo, nunca se bloquea el canal
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(item)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                pass

    async def pump(self) -> None:
        while True:
            item = await self.queue.get()
            if isinstance(item, (bytes, bytearray)):
                await self.websocket.send_bytes(item)
            else:
                await self.websocket.send_json(item)


class Room:
    def __init__(self, campaign_id: str):
        self.campaign_id = campaign_id
        self.members: dict[int, Member] = {}
        self.speaker: Optional[Member] = None
        self.speaker_since: Optional[datetime] = None
        self.timer: Optional[asyncio.Task] = None

    def presence(self) -> dict:
        names = sorted({member.name for member in self.members.values()})
        return {"type": "presence", "count": len(self.members), "names": names[:50],
                "speaker": self.speaker.name if self.speaker else None}

    def broadcast(self, message, exclude: Optional[Member] = None) -> None:
        for member in list(self.members.values()):
            if member is not exclude:
                member.offer(message)

    async def start_talk(self, member: Member) -> bool:
        if self.speaker and self.speaker is not member:
            member.offer({"type": "busy", "speaker": self.speaker.name})
            return False
        self.speaker, self.speaker_since = member, now_utc()
        self.timer = asyncio.create_task(self._limit(member))
        member.offer({"type": "talk_granted", "max_seconds": MAX_TALK_SECONDS})
        self.broadcast({"type": "speaking", "name": member.name, "person_id": member.person_id}, exclude=member)
        return True

    async def _limit(self, member: Member) -> None:
        await asyncio.sleep(MAX_TALK_SECONDS)
        if self.speaker is member:
            member.offer({"type": "talk_limit"})
            await self.end_talk(member)

    async def end_talk(self, member: Member) -> None:
        if self.speaker is not member:
            return
        started = self.speaker_since or now_utc()
        self.speaker, self.speaker_since = None, None
        if self.timer and self.timer is not asyncio.current_task():
            self.timer.cancel()
        self.timer = None
        ended = now_utc()
        self.broadcast({"type": "stopped", "name": member.name})
        # Solo el registro (quién y cuándo); el audio en vivo no se guarda.
        await db.radio_talk_log.insert_one({"_id": str(uuid4()), "campaign_id": self.campaign_id, "person_id": member.person_id, "user_id": member.user_id,
                                            "name": member.name, "started_at": started, "ended_at": ended, "seconds": round((ended - started).total_seconds(), 1)})


ROOMS: dict[str, Room] = {}


def room_for(campaign_id: str) -> Room:
    if campaign_id not in ROOMS:
        ROOMS[campaign_id] = Room(campaign_id)
    return ROOMS[campaign_id]


@router.websocket("/ws/{campaign_id}")
async def radio_socket(websocket: WebSocket, campaign_id: str, token: Optional[str] = None):
    """El navegador no puede mandar cabeceras en un WebSocket: el token va en la URL (wss)."""
    try:
        user = await get_authenticated_user(f"Bearer {token or ''}")
        if user.get("must_change_password") or (user.get("onboarding_required") and not user.get("onboarding_completed_at")):
            raise HTTPException(status_code=403, detail="Complete el ingreso antes de usar la radio")
        await radio_access(campaign_id, user)
    except HTTPException as exc:
        await websocket.accept()
        await websocket.send_json({"type": "error", "status": exc.status_code, "detail": exc.detail})
        await websocket.close(code=4000 + exc.status_code if 400 <= exc.status_code < 1000 else 4400)
        return
    await websocket.accept()
    room = room_for(campaign_id)
    member = Member(websocket, user, await person_name(user.get("person_id"), user.get("nombre") or "Participante"))
    room.members[id(member)] = member
    member.sender = asyncio.create_task(member.pump())
    member.offer({"type": "welcome", "name": member.name, "sample_rate": 16000, "max_seconds": MAX_TALK_SECONDS})
    room.broadcast(room.presence())
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                if room.speaker is member:  # solo el que tiene el turno transmite
                    room.broadcast(message["bytes"], exclude=member)
                continue
            try:
                kind = json.loads(message.get("text") or "{}").get("type")
            except ValueError:
                continue
            if kind == "ptt_start":
                await room.start_talk(member)
            elif kind == "ptt_end":
                await room.end_talk(member)
            elif kind == "ping":
                member.offer({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 — una conexión rota nunca tumba el canal
        logger.warning("radio: conexión cerrada con error", exc_info=True)
    finally:
        await room.end_talk(member)
        room.members.pop(id(member), None)
        if member.sender:
            member.sender.cancel()
        if room.members:
            room.broadcast(room.presence())
        else:
            ROOMS.pop(campaign_id, None)


# ------------------------------------------------------------------ mensajes de voz y registro
def voice_view(doc: dict) -> dict:
    return {key: (value.isoformat() if isinstance(value, datetime) else value) for key, value in doc.items() if key not in {"_id", "gridfs_id"}}


@router.get("/{campaign_id}", response_model=dict)
async def radio_state(campaign_id: str, current_user: dict = Depends(get_current_user)):
    campaign = await radio_access(campaign_id, current_user)
    room = ROOMS.get(campaign_id)
    log = await db.radio_talk_log.find({"campaign_id": campaign_id}, {"_id": 0, "name": 1, "started_at": 1, "seconds": 1}).sort("started_at", -1).limit(30).to_list(30)
    messages = await db.radio_voice_messages.find({"campaign_id": campaign_id, "expires_at": {"$gt": now_utc()}}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    return {"campaign_id": campaign_id, "name": campaign.get("name"), "online": room.presence() if room else {"count": 0, "names": [], "speaker": None},
            "talk_log": [voice_view(item) for item in log], "voice_messages": [voice_view(item) for item in messages],
            "retention_days": VOICE_RETENTION_DAYS, "max_talk_seconds": MAX_TALK_SECONDS, "max_voice_seconds": MAX_VOICE_SECONDS}


@router.post("/{campaign_id}/messages", response_model=dict, status_code=201)
async def post_voice_message(campaign_id: str, audio: UploadFile = File(...), duration_seconds: float = Form(0), client_request_id: str = Form(...),
                             current_user: dict = Depends(get_current_user)):
    """Mensaje de voz explícito (queda en el canal 30 días). Idempotente por clave."""
    await radio_access(campaign_id, current_user)
    existing = await db.radio_voice_messages.find_one({"client_request_id": client_request_id}, {"_id": 0})
    if existing:
        return {**voice_view(existing), "duplicate": True}
    content_type = (audio.content_type or "").split(";")[0].strip().lower()
    if not content_type.startswith("audio/"):
        raise HTTPException(status_code=415, detail="Solo se aceptan grabaciones de audio")
    data = await audio.read(MAX_VOICE_BYTES + 1)
    if len(data) > MAX_VOICE_BYTES:
        raise HTTPException(status_code=413, detail="El mensaje de voz es demasiado largo")
    if not data:
        raise HTTPException(status_code=422, detail="La grabación está vacía")
    name = await person_name(current_user.get("person_id"), current_user.get("nombre") or "Participante")
    created = now_utc()
    gridfs_id = await bucket().upload_from_stream(f"radio-{campaign_id}-{created.timestamp()}", data, metadata={"campaign_id": campaign_id, "content_type": content_type})
    message_id = str(uuid4())
    doc = {"_id": message_id, "message_id": message_id, "campaign_id": campaign_id, "client_request_id": client_request_id, "gridfs_id": gridfs_id,
           "person_id": current_user.get("person_id"), "name": name, "content_type": content_type, "bytes": len(data),
           "duration_seconds": round(min(max(duration_seconds, 0), MAX_VOICE_SECONDS), 1), "created_at": created, "expires_at": created + timedelta(days=VOICE_RETENTION_DAYS)}
    await db.radio_voice_messages.insert_one(doc)
    room = ROOMS.get(campaign_id)
    if room:
        room.broadcast({"type": "voice_message", **voice_view(doc)})
    return {**voice_view(doc), "duplicate": False}


@router.get("/{campaign_id}/messages/{message_id}/audio")
async def get_voice_audio(campaign_id: str, message_id: str, current_user: dict = Depends(get_current_user)):
    await radio_access(campaign_id, current_user)
    doc = await db.radio_voice_messages.find_one({"campaign_id": campaign_id, "message_id": message_id, "expires_at": {"$gt": now_utc()}}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado o vencido")
    stream = await bucket().open_download_stream(ObjectId(doc["gridfs_id"]) if not isinstance(doc["gridfs_id"], ObjectId) else doc["gridfs_id"])
    data = await stream.read()
    return StreamingResponse(iter([data]), media_type=doc["content_type"], headers={"Cache-Control": "private, max-age=3600"})


async def purge_expired_voice_messages() -> int:
    """Borra los mensajes de voz con más de 30 días (documento y archivo)."""
    removed = 0
    async for doc in db.radio_voice_messages.find({"expires_at": {"$lte": now_utc()}}, {"_id": 1, "gridfs_id": 1}):
        try:
            await bucket().delete(doc["gridfs_id"])
        except Exception:  # noqa: BLE001 — el archivo ya no estaba
            pass
        await db.radio_voice_messages.delete_one({"_id": doc["_id"]})
        removed += 1
    return removed


async def _purge_loop() -> None:
    while True:
        try:
            await purge_expired_voice_messages()
        except Exception:  # noqa: BLE001
            logger.warning("radio: limpieza de mensajes vencidos falló", exc_info=True)
        await asyncio.sleep(6 * 3600)


_purge_task: Optional[asyncio.Task] = None


async def ensure_indexes() -> None:
    global _purge_task
    await db.radio_voice_messages.create_index("client_request_id", unique=True)
    await db.radio_voice_messages.create_index([("campaign_id", 1), ("created_at", -1)])
    await db.radio_voice_messages.create_index("expires_at")
    await db.radio_talk_log.create_index([("campaign_id", 1), ("started_at", -1)])
    if _purge_task is None:
        _purge_task = asyncio.create_task(_purge_loop())
