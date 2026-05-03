"""
Backend principal — Casa de Oracion Ven y Ve

Tras la migración a sistema jerárquico de 5 niveles (Phase 6), este archivo
mantiene SOLO endpoints de infraestructura y de presentación/manual.
Todo lo relacionado con auth, usuarios y permisos vive en `hierarchy.py`.

Endpoints aquí:
  - /api/health                  Diagnóstico
  - /api/proxy/image             Proxy de imágenes externas (CORS)
  - /api/manual/pdf              Generación PDF del manual (Playwright)
  - /api/upload/photo            Subida de foto base64
  - /api/presentation/notes      Notas custom por slide del presentador
  - /api/presentation/session    Sesión sincronizada (presentador↔audiencia)

Auth/usuarios/jerarquía: ver `hierarchy.py`.
"""

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from typing import Optional
from datetime import datetime, timedelta, timezone
import os
import secrets
import jwt
from motor.motor_asyncio import AsyncIOMotorClient

from hierarchy import router as hierarchy_router

# ==============================================================================
# Setup
# ==============================================================================

app = FastAPI(title="Manual Ley 7 Semanas API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "ley7semanas_db")
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

SECRET_KEY = os.environ.get("JWT_SECRET", "ley7semanas_secret_key_2026")
ALGORITHM = "HS256"

# Roles permitidos para presentar / descargar manual / acceder a contenido pastoral.
# Todos excepto Discípulo (que solo consume contenido).
PRESENTER_ROLES = {"maestro", "supervisor", "lider", "obrero"}


# ==============================================================================
# Helpers de autenticación (compatibles con tokens emitidos por hierarchy.py)
# ==============================================================================

def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sesión expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


async def _current_user_payload(authorization: Optional[str]) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="No autorizado")
    token = authorization.replace("Bearer ", "").strip()
    return _decode_token(token)


# ==============================================================================
# Startup
# ==============================================================================

@app.on_event("startup")
async def startup():
    # Solo crear indexes que no estén ya en hierarchy.py
    try:
        await db.presentation_sessions.create_index("code")
        await db.presentation_notes.create_index([("user_id", 1), ("slide_id", 1)], unique=True)
    except Exception as e:
        print(f"[startup] Index warning: {e}")
    print("[startup] Backend ready (modo jerarquía 5 niveles)")


# ==============================================================================
# Montar router de jerarquía (auth + users + invitaciones + dashboard)
# ==============================================================================

app.include_router(hierarchy_router)


# ==============================================================================
# Health
# ==============================================================================

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Manual Ley 7 Semanas", "mode": "hierarchy-v2"}


# ==============================================================================
# Image Proxy (mismo origen para html2canvas / PDF)
# ==============================================================================

_ALLOWED_IMAGE_HOSTS = {
    "customer-assets.emergentagent.com",
    "images.unsplash.com",
    "images.pexels.com",
}


@app.get("/api/proxy/image")
async def proxy_image(url: str):
    """Proxy para imágenes externas (evita CORS al generar PDFs)."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise HTTPException(status_code=400, detail="Esquema no soportado")
        if parsed.hostname not in _ALLOWED_IMAGE_HOSTS:
            raise HTTPException(status_code=403, detail=f"Dominio no permitido: {parsed.hostname}")

        import httpx
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as cli:
            resp = await cli.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/png")
            return Response(
                content=resp.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo obtener la imagen: {e}")


# ==============================================================================
# Manual PDF (server-side via Playwright)
# ==============================================================================

_PLAYWRIGHT_CHROMIUM_PATH = os.environ.get(
    "PLAYWRIGHT_CHROMIUM_PATH",
    "/pw-browsers/chromium_headless_shell-1208/chrome-linux/headless_shell",
)


def _frontend_base_url() -> str:
    if os.environ.get("FRONTEND_PUBLIC_URL"):
        return os.environ["FRONTEND_PUBLIC_URL"]
    return "http://localhost:3000"


@app.get("/api/manual/pdf")
async def generate_manual_pdf(request: Request, authorization: Optional[str] = Header(None)):
    """Genera el PDF del manual. Solo roles con privilegios pastorales."""
    payload = await _current_user_payload(authorization)
    if payload.get("rol") not in PRESENTER_ROLES:
        raise HTTPException(status_code=403, detail="Sin permiso para descargar el manual")

    base_url = _frontend_base_url()
    target_url = f"{base_url}/presentacion/imprimir?pdf=1"

    ephemeral_token = jwt.encode(
        {
            "user_id": payload["user_id"],
            "rol": payload.get("rol"),
            "nombre": payload.get("nombre", ""),
            "email": payload.get("email", ""),
            "exp": datetime.utcnow() + timedelta(minutes=3),
            "purpose": "pdf-render",
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise HTTPException(status_code=500, detail="Playwright no disponible")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                executable_path=_PLAYWRIGHT_CHROMIUM_PATH if os.path.exists(_PLAYWRIGHT_CHROMIUM_PATH) else None,
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            context = await browser.new_context(
                viewport={"width": 1200, "height": 900},
                device_scale_factor=2,
            )
            page = await context.new_page()

            await context.add_init_script(
                f"""
                try {{
                    const token = {repr(ephemeral_token)};
                    const user = {{
                        id: {repr(payload['user_id'])},
                        rol: {repr(payload.get('rol', ''))},
                        nombre: {repr(payload.get('nombre', ''))},
                        email: {repr(payload.get('email', ''))},
                    }};
                    localStorage.setItem('token', token);
                    localStorage.setItem('user', JSON.stringify(user));
                }} catch(e) {{}}
                """
            )

            await page.goto(target_url, wait_until="networkidle", timeout=60000)
            await page.evaluate(
                """
                () => Promise.all(
                    Array.from(document.images).map(img => {
                        if (img.complete && img.naturalWidth > 0) return Promise.resolve();
                        return new Promise((resolve) => {
                            const done = () => { img.onload = null; img.onerror = null; resolve(); };
                            img.onload = done;
                            img.onerror = done;
                            setTimeout(done, 8000);
                        });
                    })
                )
                """
            )
            await page.evaluate(
                """
                () => {
                    document.querySelectorAll('#emergent-badge, a[href*="emergent.sh"]').forEach(el => el.remove());
                }
                """
            )
            try:
                await page.evaluate("document.fonts && document.fonts.ready")
            except Exception:
                pass
            await page.wait_for_timeout(1500)

            pdf_bytes = await page.pdf(
                format="Letter",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
                display_header_footer=False,
            )
            await browser.close()

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="Manual-La-Ley-de-las-7-Semanas.pdf"',
                "Cache-Control": "no-store",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {e}")


# ==============================================================================
# Upload de fotos (base64 → URL)
# ==============================================================================

@app.post("/api/upload/photo")
async def upload_photo(photo_data: dict, authorization: Optional[str] = Header(None)):
    await _current_user_payload(authorization)
    base64_data = photo_data.get("base64")
    if not base64_data:
        raise HTTPException(status_code=400, detail="No photo data")
    return {"url": base64_data}


# ==============================================================================
# Notas de presentación (editables por slide, por usuario)
# ==============================================================================

@app.post("/api/presentation/notes")
async def save_presentation_note(data: dict, authorization: Optional[str] = Header(None)):
    payload = await _current_user_payload(authorization)
    slide_id = data.get("slide_id")
    note_text = data.get("note_text", "")
    if not slide_id:
        raise HTTPException(status_code=400, detail="slide_id requerido")
    await db.presentation_notes.update_one(
        {"user_id": payload["user_id"], "slide_id": slide_id},
        {"$set": {
            "user_id": payload["user_id"],
            "slide_id": slide_id,
            "note_text": note_text,
            "updated_at": datetime.utcnow(),
        }},
        upsert=True,
    )
    return {"message": "Nota guardada"}


@app.get("/api/presentation/notes")
async def get_presentation_notes(authorization: Optional[str] = Header(None)):
    payload = await _current_user_payload(authorization)
    cursor = db.presentation_notes.find({"user_id": payload["user_id"]})
    items = await cursor.to_list(length=200)
    return {n["slide_id"]: n.get("note_text", "") for n in items}


# ==============================================================================
# Sesiones de presentación (presentador ↔ audiencia ↔ teleprompter)
# ==============================================================================

@app.post("/api/presentation/session")
async def create_presentation_session(authorization: Optional[str] = Header(None)):
    """Crea una sesión sincronizada con código de 4 dígitos."""
    payload = await _current_user_payload(authorization)
    if payload.get("rol") not in PRESENTER_ROLES:
        raise HTTPException(status_code=403, detail="Sin permiso para presentar")

    code = ""
    for _ in range(10):
        code = "".join(secrets.choice("0123456789") for _ in range(4))
        existing = await db.presentation_sessions.find_one({"code": code, "active": True})
        if not existing:
            break

    doc = {
        "code": code,
        "owner_id": payload["user_id"],
        "owner_name": payload.get("nombre", ""),
        "current_slide": 0,
        "active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    await db.presentation_sessions.insert_one(doc)
    return {"code": code, "current_slide": 0}


@app.put("/api/presentation/session/{code}")
async def update_presentation_session(code: str, data: dict, authorization: Optional[str] = Header(None)):
    payload = await _current_user_payload(authorization)
    session = await db.presentation_sessions.find_one({"code": code, "active": True})
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    if session["owner_id"] != payload["user_id"]:
        raise HTTPException(status_code=403, detail="Solo el presentador controla")
    current_slide = int(data.get("current_slide", 0))
    await db.presentation_sessions.update_one(
        {"code": code},
        {"$set": {"current_slide": current_slide, "updated_at": datetime.utcnow()}},
    )
    return {"code": code, "current_slide": current_slide}


@app.get("/api/presentation/session/{code}")
async def get_presentation_session(code: str):
    """Pública: la audiencia y el teleprompter consultan sin autenticación."""
    session = await db.presentation_sessions.find_one({"code": code, "active": True})
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    return {
        "code": session["code"],
        "current_slide": session.get("current_slide", 0),
        "owner_name": session.get("owner_name", ""),
        "updated_at": session.get("updated_at").isoformat() if session.get("updated_at") else None,
    }


@app.delete("/api/presentation/session/{code}")
async def close_presentation_session(code: str, authorization: Optional[str] = Header(None)):
    payload = await _current_user_payload(authorization)
    session = await db.presentation_sessions.find_one({"code": code})
    if not session:
        return {"success": True}
    if session["owner_id"] != payload["user_id"]:
        raise HTTPException(status_code=403, detail="Solo el presentador puede cerrar")
    await db.presentation_sessions.update_one({"code": code}, {"$set": {"active": False}})
    return {"success": True}
