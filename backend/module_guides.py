"""Documentación contextual versionada, separada de los datos operativos."""
from copy import deepcopy
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from server import get_current_user

router = APIRouter(prefix="/api/guides", tags=["module-guides"])
GUIDES_PATH = Path(__file__).parent / "docs" / "module_guides.json"
ROLE_LABELS = {"pastor": "Pastor", "lider": "Líder", "persona": "Persona"}


def load_guides() -> dict:
    with GUIDES_PATH.open("r", encoding="utf-8") as source:
        return json.load(source)


def prepare_guide(guide: dict, current_user: dict) -> dict:
    prepared = deepcopy(guide)
    role = current_user.get("rol") or current_user.get("role") or "persona"
    role_guidance = prepared.pop("role_guidance", {})
    prepared["active_role"] = role
    prepared["active_role_label"] = ROLE_LABELS.get(role, role.replace("_", " ").title())
    matching_role = next((item for item in prepared.get("roles", []) if item.lower().startswith(ROLE_LABELS.get(role, role).lower())), None)
    prepared["role_focus"] = role_guidance.get(role) or role_guidance.get("default") or matching_role or "Consulta los pasos autorizados para tu alcance."
    prepared["result"] = prepared.get("result") or prepared.get("next")
    prepared["inputs"] = prepared.get("inputs") or ["Personas canónicas y registros autorizados del módulo", "Hechos operativos capturados en su fuente"]
    prepared["outputs"] = prepared.get("outputs") or [prepared["result"]]
    prepared["connections"] = prepared.get("connections") or [{"module": "Perfil 360 y módulos conectados", "impact": prepared.get("next")}]
    prepared["common_errors"] = prepared.get("common_errors") or ["Trabajar fuera del alcance autorizado", "Duplicar una Persona o registro existente", "Cerrar sin responsable, resultado o próximo paso"]
    prepared["example"] = prepared.get("example") or {
        "situation": prepared.get("purpose"),
        "action": "Sigue el flujo y registra únicamente hechos reales en cada paso.",
        "result": prepared.get("next"),
    }
    tour_steps = prepared.get("tour_steps", [])
    if not tour_steps and (module_key := prepared.get("module_key")):
        if module_key.startswith("cellular_"):
            tour_steps = [
                {"target": "cellular-page-title", "title": prepared.get("title"), "body": prepared.get("purpose")},
                {"target": "cellular-module-navigation", "title": "Flujo celular", "body": prepared.get("next")},
            ]
        elif module_key.startswith("door_") or module_key.startswith("doors_") or module_key.startswith("board_"):
            tour_steps = [
                {"target": "doors-page-title", "title": prepared.get("title"), "body": prepared.get("purpose")},
                {"target": "doors-module-navigation", "title": "Gobierno y respuesta", "body": prepared.get("next")},
            ]
    prepared["tour_steps"] = [
        step for step in tour_steps
        if not step.get("roles") or role in step["roles"]
    ]
    return prepared


@router.get("", response_model=dict)
async def list_module_guides(current_user: dict = Depends(get_current_user)):
    modules = load_guides().get("modules", {})
    return {
        "items": [
            {"module_key": key, "title": value.get("title"), "version": value.get("version")}
            for key, value in modules.items()
        ]
    }


@router.get("/{module_key}", response_model=dict)
async def get_module_guide(module_key: str, current_user: dict = Depends(get_current_user)):
    guide = load_guides().get("modules", {}).get(module_key)
    if not guide:
        raise HTTPException(status_code=404, detail="Manual contextual no encontrado")
    return prepare_guide({**guide, "module_key": module_key}, current_user)