"""Normalización conservadora de direcciones físicas para Mapa Territorial 360."""
import re
import unicodedata


STREET_SUFFIXES = {
    "ALLEY": "ALY", "AVENUE": "AVE", "BOULEVARD": "BLVD", "CIRCLE": "CIR",
    "COURT": "CT", "DRIVE": "DR", "EXPRESSWAY": "EXPY", "HIGHWAY": "HWY",
    "LANE": "LN", "PARKWAY": "PKWY", "PLACE": "PL", "ROAD": "RD",
    "SQUARE": "SQ", "STREET": "ST", "TERRACE": "TER", "TRAIL": "TRL",
}
UNIT_TYPES = {
    "APARTMENT": "APT", "APT": "APT", "UNIT": "UNIT", "SUITE": "STE",
    "STE": "STE", "FLOOR": "FL", "FL": "FL", "ROOM": "RM", "RM": "RM",
}


def _ascii(value: str | None) -> str:
    raw = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9#-]+", " ", raw.upper()).strip()


def _normalize_tokens(value: str | None, replacements: dict[str, str] | None = None) -> str:
    tokens = _ascii(value).replace(".", " ").split()
    replacements = replacements or {}
    return " ".join(replacements.get(token, token) for token in tokens)


def _street_and_unit(line1: str | None, line2: str | None) -> tuple[str, str]:
    street = _normalize_tokens(line1, STREET_SUFFIXES)
    unit = _normalize_tokens(line2, UNIT_TYPES)
    if not unit:
        match = re.search(r"(?:\s|^)(APT|APARTMENT|UNIT|STE|SUITE|FL|FLOOR|RM|ROOM|#)\s*([A-Z0-9-]+)$", street)
        if match:
            unit_type = UNIT_TYPES.get(match.group(1), "UNIT")
            unit = f"{unit_type} {match.group(2)}"
            street = street[:match.start()].strip()
    elif unit.startswith("#"):
        unit = f"UNIT {unit[1:].strip()}"
    return street, unit


def normalize_address_document(doc: dict) -> dict:
    """Devuelve una clave estable; las unidades nunca se colapsan entre sí."""
    line1 = doc.get("linea1") or doc.get("street") or doc.get("address")
    line2 = doc.get("linea2") or doc.get("unit")
    street, unit = _street_and_unit(line1, line2)
    city = _normalize_tokens(doc.get("ciudad") or doc.get("city"))
    state = _normalize_tokens(doc.get("provincia") or doc.get("state"))
    postal = re.sub(r"\D", "", str(doc.get("codigo_postal") or doc.get("zip") or ""))[:5]
    country = _normalize_tokens(doc.get("pais") or doc.get("country") or "US")
    complete = bool(street and city and state and len(postal) == 5)
    key = "|".join([street, unit, city, state, postal, country or "US"]) if complete else None
    return {
        "normalized_address_key": key,
        "normalized_street": street or None,
        "normalized_unit": unit or None,
        "normalized_city": city or None,
        "normalized_state": state or None,
        "normalized_zip": postal or None,
        "address_complete": complete,
    }


def address_completeness_reasons(address: dict) -> list[str]:
    normalized = normalize_address_document(address)
    reasons = []
    if not normalized["normalized_street"]: reasons.append("street_missing")
    if not normalized["normalized_city"]: reasons.append("city_missing")
    if not normalized["normalized_state"]: reasons.append("state_missing")
    if not normalized["normalized_zip"] or len(normalized["normalized_zip"]) != 5: reasons.append("zip_missing_or_invalid")
    return reasons