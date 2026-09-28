"""Almacenamiento seguro de archivos para Librería 360: portadas de catálogo y
adjuntos (facturas/recibos) de Órdenes de Compra. Usa Emergent Object Storage;
Mongo solo guarda referencia + metadatos, nunca el archivo en base64."""
import io
import os
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

import requests
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from PIL import Image

from access_control import has_capability, is_general_coordinator, is_global_pastoral_authority
from finance_engine import require_finance_manage
from server import db, get_current_user

router = APIRouter(prefix="/api/library/files", tags=["library-files"])

APP_NAME = "venyve360"
ALLOWED_CONTENT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}
MAX_FILE_BYTES = 10 * 1024 * 1024
_storage_key: Optional[str] = None


def storage_base() -> str:
    return (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"


def storage_url() -> str:
    return storage_base().rstrip("/") + "/objstore/api/v1/storage"


def init_storage(force: bool = False) -> str:
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{storage_url()}/init", json={"emergent_key": os.environ.get("EMERGENT_LLM_KEY")}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(f"{storage_url()}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.put(f"{storage_url()}/objects/{path}", headers={"X-Storage-Key": key, "Content-Type": content_type}, data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def get_object(path: str) -> tuple[bytes, str]:
    key = init_storage()
    resp = requests.get(f"{storage_url()}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.get(f"{storage_url()}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


async def ensure_indexes() -> None:
    await db.library_files.create_index("file_id", unique=True)
    await db.library_files.create_index([("owner_type", 1), ("owner_id", 1)])


def make_thumbnail(data: bytes, content_type: str) -> Optional[bytes]:
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        return None
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
        image.thumbnail((320, 320))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=82)
        return buffer.getvalue()
    except Exception:
        return None


async def store_upload(file: UploadFile, kind: Literal["cover", "po_attachment"], owner_type: str, owner_id: str, actor_user_id: str) -> dict:
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="Solo se permiten JPG, PNG, WebP o PDF")
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el tamaño máximo permitido (10MB)")
    ext = ALLOWED_CONTENT_TYPES[content_type]
    file_id = str(uuid4())
    path = f"{APP_NAME}/library/{kind}/{owner_id}/{file_id}.{ext}"
    result = put_object(path, data, content_type)
    thumbnail_path = None
    thumb_bytes = make_thumbnail(data, content_type)
    if thumb_bytes:
        thumbnail_path = f"{APP_NAME}/library/{kind}/{owner_id}/{file_id}_thumb.jpg"
        put_object(thumbnail_path, thumb_bytes, "image/jpeg")
    now = datetime.now(timezone.utc)
    doc = {
        "_id": file_id, "file_id": file_id, "storage_path": result["path"], "thumbnail_storage_path": thumbnail_path,
        "original_filename": file.filename, "content_type": content_type, "size": result.get("size", len(data)),
        "kind": kind, "owner_type": owner_type, "owner_id": owner_id, "uploaded_by_user_id": actor_user_id,
        "uploaded_at": now, "is_deleted": False, "is_voided": False,
    }
    await db.library_files.insert_one(doc)
    return doc


def can_view_po_attachment(current_user: dict) -> bool:
    return (
        is_global_pastoral_authority(current_user) or is_general_coordinator(current_user)
        or has_capability(current_user, "library.catalog.manage") or has_capability(current_user, "library.inventory.manage")
        or has_capability(current_user, "finance.manage") or has_capability(current_user, "finance.read")
    )


def can_upload_po_attachment(current_user: dict) -> bool:
    return (
        is_global_pastoral_authority(current_user) or is_general_coordinator(current_user)
        or has_capability(current_user, "library.catalog.manage") or has_capability(current_user, "library.inventory.manage")
        or has_capability(current_user, "finance.manage")
    )


@router.post("/cover/{book_id}", response_model=dict, status_code=201)
async def upload_cover(book_id: str, file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    if not (has_capability(current_user, "library.catalog.manage") or has_capability(current_user, "library.inventory.manage") or is_global_pastoral_authority(current_user) or is_general_coordinator(current_user)):
        raise HTTPException(status_code=403, detail="No tiene permiso para actualizar el catálogo")
    book = await db.library_books.find_one({"book_id": book_id})
    if not book:
        raise HTTPException(status_code=404, detail="Material no encontrado")
    doc = await store_upload(file, "cover", "book", book_id, current_user["user_id"])
    await db.library_books.update_one({"book_id": book_id}, {"$set": {"cover_file_id": doc["file_id"], "updated_at": datetime.now(timezone.utc)}})
    return {"file_id": doc["file_id"]}


@router.post("/po-attachment/{po_id}", response_model=dict, status_code=201)
async def upload_po_attachment(po_id: str, file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    if not can_upload_po_attachment(current_user):
        raise HTTPException(status_code=403, detail="No tiene permiso para adjuntar documentos financieros")
    po = await db.library_purchase_orders.find_one({"po_id": po_id})
    if not po:
        raise HTTPException(status_code=404, detail="Orden de compra no encontrada")
    doc = await store_upload(file, "po_attachment", "purchase_order", po_id, current_user["user_id"])
    return {"file_id": doc["file_id"]}


@router.get("/{file_id}/download")
async def download_file(file_id: str, thumbnail: bool = False, current_user: dict = Depends(get_current_user)):
    record = await db.library_files.find_one({"file_id": file_id, "is_deleted": False})
    if not record:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    if record["kind"] == "po_attachment" and not can_view_po_attachment(current_user):
        raise HTTPException(status_code=403, detail="No tiene permiso para ver este documento")
    path = record["thumbnail_storage_path"] if (thumbnail and record.get("thumbnail_storage_path")) else record["storage_path"]
    data, content_type = get_object(path)
    return Response(content=data, media_type=record.get("content_type", content_type))


@router.get("/by-owner/{owner_type}/{owner_id}", response_model=dict)
async def list_owner_files(owner_type: str, owner_id: str, current_user: dict = Depends(get_current_user)):
    files = await db.library_files.find({"owner_type": owner_type, "owner_id": owner_id, "is_deleted": False}, {"_id": 0}).sort("uploaded_at", -1).to_list(200)
    if any(item["kind"] == "po_attachment" for item in files) and not can_view_po_attachment(current_user):
        raise HTTPException(status_code=403, detail="No tiene permiso para ver estos documentos")
    for item in files:
        item["uploaded_at"] = item["uploaded_at"].isoformat()
    return {"items": files}


@router.delete("/{file_id}", response_model=dict)
async def delete_file(file_id: str, current_user: dict = Depends(get_current_user)):
    record = await db.library_files.find_one({"file_id": file_id})
    if not record:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    if record["kind"] == "po_attachment" and not can_upload_po_attachment(current_user):
        raise HTTPException(status_code=403, detail="No tiene permiso para eliminar este documento")
    if record["kind"] == "cover" and not (has_capability(current_user, "library.catalog.manage") or has_capability(current_user, "library.inventory.manage") or is_global_pastoral_authority(current_user) or is_general_coordinator(current_user)):
        raise HTTPException(status_code=403, detail="No tiene permiso para eliminar la portada")
    po_closed = False
    if record["kind"] == "po_attachment":
        po = await db.library_purchase_orders.find_one({"po_id": record["owner_id"]}, {"status": 1})
        po_closed = bool(po and po.get("status") == "closed")
    if po_closed:
        await db.library_files.update_one({"file_id": file_id}, {"$set": {"is_voided": True}})
    else:
        await db.library_files.update_one({"file_id": file_id}, {"$set": {"is_deleted": True}})
        if record["kind"] == "cover":
            await db.library_books.update_one({"book_id": record["owner_id"], "cover_file_id": file_id}, {"$unset": {"cover_file_id": ""}})
    return {"deleted": True, "voided": po_closed}
