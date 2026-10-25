"""Formulario ÚNICO de visitantes (une los 3 papeles de la iglesia y el digital).

- Etiquetas de cada respuesta para el resumen legible de la ficha de seguimiento.
- ENRUTAMIENTO: cada respuesta crea su tarea de seguimiento con su área; «aceptar
  a Jesús», oración y reconciliación son URGENTES (aviso inmediato a la pastora y a
  quien asigna en Consolidación, y tarea «Llamar hoy»).
- La consejería y las necesidades siguen restringidas: su tarea no dice el tipo a
  quien no tiene el permiso."""
from typing import Optional

REQUEST_KEYS = ["prayer_me", "prayer_family", "call_prayer", "visit", "info", "counseling_personal", "counseling_marriage", "counseling_family", "support_child",
                "membership", "serve", "home_service", "other_help", "no_followup",
                "prayer"]  # «prayer» = versión anterior (se lee como «oración por mí»)
REQUEST_LABELS = {
    "prayer_me": "Quiero oración por mí", "prayer_family": "Quiero oración por mi familia", "call_prayer": "Llámenme para orar", "visit": "Me gustaría que me visiten",
    "info": "Quiero saber más de esta iglesia", "counseling_personal": "Consejería personal", "counseling_marriage": "Consejería matrimonial", "counseling_family": "Consejería familiar",
    "support_child": "Apoyo para un hijo o familiar", "membership": "Me gustaría pertenecer a la iglesia", "serve": "Quiero servir en la iglesia",
    "home_service": "Me gustaría un culto en mi casa", "other_help": "Otra ayuda", "no_followup": "Prefiero no recibir seguimiento por ahora", "prayer": "Quiero oración por mí",
}
RESTRICTED_REQUESTS = {"counseling_personal", "counseling_marriage", "counseling_family", "support_child", "other_help"}
PRAYER_REQUESTS = {"prayer_me", "prayer_family", "call_prayer", "prayer"}

VISIT_MODES = {"nearby": "Vive cerca de la iglesia", "other_city": "Viene de otra ciudad", "passing": "Está de paso", "new_in_area": "Es nuevo en el área"}
CHRISTIAN = {"yes": "Sí", "on_way": "Estoy en camino", "not_yet": "No todavía"}
ACCEPT_JESUS = {"today": "Hoy", "another_day": "Otro día"}
MARITAL = {"single": "Soltero o soltera", "married": "Casado o casada", "other": "Otro"}
SEX = {"female": "Femenino", "male": "Masculino"}
LANGUAGE = {"es": "Español", "en": "Inglés (English): contactarle en inglés"}
CONTACT = {"call": "Llamada", "text": "Mensaje de texto", "whatsapp": "WhatsApp", "email": "Correo electrónico"}

# Área → a quién le toca (se muestra en la tarea).
AREAS = {"consolidation": "Consolidación", "visits": "Visitas", "membership": "Membresía", "talents": "Talentos y ministerios", "children": "Ministerio de niños",
         "cells": "Sistema Celular", "finance": "Finanzas", "pastoral": "Pastoral (confidencial)", "welcome": "Bienvenida"}


def yes_no(value: Optional[bool]) -> Optional[str]:
    return None if value is None else ("Sí" if value else "No")


def phone_text(digits: Optional[str]) -> Optional[str]:
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}" if digits and len(digits) == 10 else digits


MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def birthday_text(value: Optional[str], day: Optional[int] = None, month: Optional[int] = None) -> Optional[str]:
    """«9 de julio de 1985», o «9 de julio» si no dio el año."""
    if not value and day and month and 1 <= month <= 12:
        return f"{day} de {MONTHS[month - 1]}"
    try:
        year, month, day = (int(part) for part in (value or "").split("-"))
        return f"{day} de {MONTHS[month - 1]} de {year}"
    except (ValueError, IndexError):
        return value


def build_tasks(doc: dict) -> list[dict]:
    """Una tarea por cada respuesta que pide acción (estado «abierta» hasta que el equipo la marque)."""
    requests = set(doc.get("requests") or [])
    faith = doc.get("faith") or {}
    household = doc.get("household") or {}
    tasks: list[dict] = []

    def add(key: str, label: str, area: str, urgent: bool = False, restricted: bool = False) -> None:
        tasks.append({"key": key, "label": label, "area": area, "area_label": AREAS[area], "urgent": urgent, "restricted": restricted, "done": False})

    urgent_reasons = []
    if faith.get("accept_jesus"):
        urgent_reasons.append(f"quiere aceptar a Jesús ({ACCEPT_JESUS[faith['accept_jesus']].lower()})")
    if faith.get("reconcile"):
        urgent_reasons.append("desea reconciliarse con Dios")
    if requests & PRAYER_REQUESTS:
        urgent_reasons.append("pidió oración")
    if urgent_reasons:
        add("call_today", "Llamar hoy: " + ", ".join(urgent_reasons), "consolidation", urgent=True)
    if faith.get("faith_info"):
        add("faith_info", "Explicarle cómo ser cristiano", "consolidation")
    if "visit" in requests:
        add("visit", "Visitarle", "visits")
    if "info" in requests:
        add("info", "Darle información de la iglesia", "welcome")
    if "membership" in requests:
        add("membership", "Iniciar el proceso de membresía", "membership")
    if "serve" in requests:
        add("serve", "Talentos y ministerios: quiere servir", "talents")
    if household.get("kids_ministry"):
        add("kids", "Ministerio de niños o Presentación: sus hijos quieren participar", "children")
    if "home_service" in requests:
        add("home_service", "Sistema Celular: culto en su casa", "cells")
    if (doc.get("giving") or {}).get("info"):
        add("giving", "Finanzas: información para ofrendar o donar mensualmente", "finance")
    if requests & RESTRICTED_REQUESTS:
        add("pastoral", "Atención pastoral confidencial", "pastoral", restricted=True)
    return tasks


def merge_followup(old: Optional[dict], new: dict) -> dict:
    """Al guardar otra vez (paso a paso o al terminar) se conserva lo que el equipo ya hizo."""
    old = old or {}
    done = {task["key"]: task for task in old.get("tasks") or []}
    tasks = [{**task, **({"done": done[task["key"]]["done"], "done_at": done[task["key"]].get("done_at"), "done_by": done[task["key"]].get("done_by")} if task["key"] in done else {})}
             for task in new.get("tasks") or []]
    kept = {key: old[key] for key in ("assigned_person_id", "assigned_at", "assigned_by", "results", "alert_sent", "alert_sent_at", "updated_at") if key in old}
    status = old.get("status") if old.get("status") in ("assigned", "in_progress", "done") else new.get("status")
    return {**new, **kept, "status": status, "tasks": tasks}


def answers(doc: dict, restricted_ok: bool) -> list[dict]:
    """Resumen legible de TODAS sus respuestas, por tema (lo confidencial solo con permiso)."""
    contact, visit = doc.get("contact") or {}, doc.get("visit") or {}
    faith, household = doc.get("faith") or {}, doc.get("household") or {}
    requests = doc.get("requests") or []
    shown_requests = [REQUEST_LABELS.get(item, item) for item in requests if restricted_ok or item not in RESTRICTED_REQUESTS]
    if not restricted_ok and any(item in RESTRICTED_REQUESTS for item in requests):
        shown_requests.append("Pedido confidencial (lo atiende el equipo pastoral)")
    address = ", ".join(part for part in [contact.get("address"), contact.get("city"), contact.get("zip_code")] if part)
    birth = birthday_text(contact.get("birth_date"), contact.get("birth_day"), contact.get("birth_month"))
    new_in_area = visit.get("new_in_area")
    children = household.get("children") or []
    legacy_family = [f"{item.get('name')}{' (' + item['relation'] + ')' if item.get('relation') else ''}" for item in doc.get("family") or [] if item.get("name")]
    sections = [
        ("Nombre", [("Nombre completo", f"{doc.get('first_name', '')} {doc.get('last_name', '')}".strip()), ("Le gusta que le llamen", (doc.get("welcome") or {}).get("preferred_name")),
                    ("Sexo", SEX.get((doc.get("profile") or {}).get("sex"))), ("Idioma preferido", LANGUAGE.get(doc.get("language") or "es"))]),
        ("Contacto", [("Teléfono", phone_text(contact.get("phone"))), ("Correo electrónico", contact.get("email")),
                      ("Cómo prefiere que le contacten", ", ".join(CONTACT.get(item, item) for item in contact.get("methods") or []) or None)]),
        ("Dónde vive", [("Dirección", address or None), ("Es nuevo en esta área", yes_no(new_in_area)),
                        ("Cómo nos visita hoy", VISIT_MODES.get(visit.get("visit_mode"))), ("Cumpleaños", birth)]),
        ("Su visita", [("Visita", None if visit.get("first_visit") is None else ("Primera vez" if visit.get("first_visit") else "Ya nos había visitado")),
                       ("Le invitó", (doc.get("welcome") or {}).get("invited_by_display") or (doc.get("welcome") or {}).get("invited_by") or visit.get("invited_by")), ("Cómo se enteró", visit.get("how_heard"))]),
        ("Su fe", [("¿Es cristiano o cristiana?", CHRISTIAN.get(faith.get("christian"))), ("Quiere aceptar a Jesús como su Salvador", ACCEPT_JESUS.get(faith.get("accept_jesus"))),
                   ("Desea reconciliarse con Dios", "Sí" if faith.get("reconcile") else None), ("Quiere informarse de cómo ser cristiano", "Sí" if faith.get("faith_info") else None),
                   ("Asiste a otra iglesia", yes_no(visit.get("other_church"))), ("Iglesia", visit.get("other_church_name")), ("Pastor de esa iglesia", visit.get("other_church_pastor"))]),
        ("Familia", [("Estado civil", MARITAL.get(household.get("marital_status"))), ("Cónyuge", household.get("spouse_name")), ("¿Tiene hijos?", yes_no(household.get("has_children"))),
                     ("Hijos", "; ".join(f"{item.get('name')}{', ' + str(item['age']) + ' años' if item.get('age') is not None else ''}" for item in children if item.get("name")) or None),
                     ("Le acompaña hoy", household.get("companions") or (", ".join(legacy_family) or None)),
                     ("Desea que sus hijos participen (ministerio de niños)", "Sí" if household.get("kids_ministry") else None)]),
        ("Cómo podemos servirle", [("Pidió", ", ".join(shown_requests) or None)]),
        ("Apoyo", [("Quiere información para ofrendar o donar mensualmente", "Sí" if (doc.get("giving") or {}).get("info") else None)]),
        ("Cierre", [("¿Podemos comunicarnos?", {True: "Sí", False: "No"}.get((doc.get("consents") or {}).get("followup"), "No respondió"))]),
    ]
    return [{"section": title, "items": [{"label": label, "value": value} for label, value in items if value]} for title, items in sections if any(value for _, value in items)]


async def alert_urgent(db, doc: dict) -> int:
    """Aviso inmediato (una sola vez por registro) a la pastora y a quien asigna en Consolidación."""
    urgent = [task for task in (doc.get("followup") or {}).get("tasks") or [] if task.get("urgent")]
    if not urgent or (doc.get("followup") or {}).get("alert_sent"):
        return 0
    from datetime import datetime, timezone
    claimed = await db.visitor_registrations.update_one({"registration_id": doc["registration_id"], "followup.alert_sent": {"$ne": True}},
                                                        {"$set": {"followup.alert_sent": True, "followup.alert_sent_at": datetime.now(timezone.utc)}})
    if not claimed.modified_count:
        return 0
    from access_control import CONSOLIDATION_ASSIGN, VISITORS_FOLLOWUP_MANAGE, has_capability, is_global_pastoral_authority
    from portal_notifications import notify_users
    recipients = [str(user["_id"]) async for user in db.users.find({"is_active": {"$ne": False}}, {"password": 0})
                  if is_global_pastoral_authority(user) or has_capability(user, CONSOLIDATION_ASSIGN) or has_capability(user, VISITORS_FOLLOWUP_MANAGE)]
    name = f"{doc.get('first_name', '')} {doc.get('last_name', '')}".strip()
    return await notify_users(recipients, "visitor_urgent", f"Visitante: llamar hoy · {name}", f"{doc.get('visitor_number')}: {urgent[0]['label'].replace('Llamar hoy: ', '')}.",
                              "/visitantes?tab=seguimiento", {"registration_id": doc["registration_id"]})
