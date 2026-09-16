"""Documentación contextual versionada, separada de los datos operativos."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from server import get_current_user

router = APIRouter(prefix="/api/guides", tags=["module-guides"])
GUIDES_PATH = Path(__file__).parent / "docs" / "module_guides.json"


def load_guides() -> dict:
    with GUIDES_PATH.open("r", encoding="utf-8") as source:
        return json.load(source)


@router.get("/{module_key}", response_model=dict)
async def get_module_guide(module_key: str, current_user: dict = Depends(get_current_user)):
    guide = load_guides().get("modules", {}).get(module_key)
    if not guide:
        raise HTTPException(status_code=404, detail="Manual contextual no encontrado")
    return guide