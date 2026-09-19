"""Bóveda cifrada para notas de Cuidado Pastoral."""
import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException


KEY_ENV = "PASTORAL_NOTES_ENCRYPTION_KEY"
KEY_VERSION = "v1"


def _key() -> bytes:
    encoded = os.environ.get(KEY_ENV)
    if not encoded:
        raise HTTPException(status_code=503, detail="La bóveda pastoral no está configurada")
    try:
        value = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="La bóveda pastoral no está configurada") from exc
    if len(value) != 32:
        raise HTTPException(status_code=503, detail="La bóveda pastoral no está configurada")
    return value


def vault_configured() -> bool:
    try:
        _key()
        return True
    except HTTPException:
        return False


def _aad(entity_id: str, item_id: str, visibility: str) -> bytes:
    return json.dumps(
        {"entity_id": entity_id, "item_id": item_id, "visibility": visibility, "key_version": KEY_VERSION},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def encrypt_text(content: str, entity_id: str, item_id: str, visibility: str) -> dict:
    import secrets

    nonce = secrets.token_bytes(12)
    encrypted = AESGCM(_key()).encrypt(nonce, content.encode("utf-8"), _aad(entity_id, item_id, visibility))
    return {
        "ciphertext": base64.urlsafe_b64encode(encrypted).decode("ascii"),
        "nonce": base64.urlsafe_b64encode(nonce).decode("ascii"),
        "key_version": KEY_VERSION,
    }


def decrypt_text(document: dict, entity_id: str, item_id: str, visibility: str) -> str:
    try:
        encrypted = base64.urlsafe_b64decode(document["ciphertext"].encode("ascii"))
        nonce = base64.urlsafe_b64decode(document["nonce"].encode("ascii"))
        plain = AESGCM(_key()).decrypt(nonce, encrypted, _aad(entity_id, item_id, visibility))
        return plain.decode("utf-8")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="No se pudo abrir la nota pastoral") from exc
