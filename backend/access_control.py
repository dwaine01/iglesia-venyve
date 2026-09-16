"""ACCESS-01 minimal capability + person scope policy.

Capabilities are stored explicitly on users and resolved from Mongo on every
request by BASE-01. Roles are used only by the idempotent rollout backfill and
new-user defaults; authorization checks consume capabilities + access_scope.
"""
from copy import deepcopy

from fastapi import HTTPException

PERSON_PROFILE_SENSITIVE_READ = "person.profile.sensitive.read"
PERSON_PROFILE_WRITE = "person.profile.write"
PERSON_HOUSEHOLD_READ = "person.household.read"
PERSON_HOUSEHOLD_WRITE = "person.household.write"
PERSON_FAMILY_READ = "person.family.read"
PERSON_FAMILY_WRITE = "person.family.write"
PERSON_ARRIVAL_READ = "person.arrival.read"
PERSON_ARRIVAL_WRITE = "person.arrival.write"
PERSON_ATTENDANCE_READ = "person.attendance.read"
PERSON_ATTENDANCE_WRITE = "person.attendance.write"
PERSON_NOTES_READ = "person.notes.read"
PERSON_NOTES_WRITE = "person.notes.write"
PERSON_HISTORY_READ = "person.history.read"
PERSON_CONTACTS_READ = "person.contacts.read"
PERSON_CONTACTS_WRITE = "person.contacts.write"
PERSON_ADDRESSES_READ = "person.addresses.read"
PERSON_ADDRESSES_WRITE = "person.addresses.write"
PERSON_PASTORAL_NOTES_READ = "person.notes.pastoral.read"

PERSON_DOMAIN_CAPABILITIES = [
    PERSON_PROFILE_SENSITIVE_READ,
    PERSON_PROFILE_WRITE,
    PERSON_HOUSEHOLD_READ,
    PERSON_HOUSEHOLD_WRITE,
    PERSON_FAMILY_READ,
    PERSON_FAMILY_WRITE,
    PERSON_ARRIVAL_READ,
    PERSON_ARRIVAL_WRITE,
    PERSON_ATTENDANCE_READ,
    PERSON_ATTENDANCE_WRITE,
    PERSON_NOTES_READ,
    PERSON_NOTES_WRITE,
    PERSON_HISTORY_READ,
    PERSON_CONTACTS_READ,
    PERSON_CONTACTS_WRITE,
    PERSON_ADDRESSES_READ,
    PERSON_ADDRESSES_WRITE,
]

_ROLE_ACCESS_DEFAULTS = {
    "pastor": {
        "capabilities": [*PERSON_DOMAIN_CAPABILITIES, PERSON_PASTORAL_NOTES_READ],
        "access_scope": {"persons": "all"},
    },
    "lider": {
        "capabilities": PERSON_DOMAIN_CAPABILITIES,
        "access_scope": {"persons": "created_by"},
    },
    "persona": {
        "capabilities": [],
        "access_scope": {"persons": "none"},
    },
}


def access_defaults_for_role(role: str) -> dict:
    """Return explicit fields for a newly created user."""
    defaults = deepcopy(
        _ROLE_ACCESS_DEFAULTS.get(
            (role or "").strip().lower(),
            {"capabilities": [], "access_scope": {"persons": "none"}},
        )
    )
    defaults["access_policy_version"] = 3
    return defaults


def normalized_capabilities(user: dict) -> list[str]:
    value = user.get("capabilities", [])
    if not isinstance(value, list):
        return []
    return sorted({item for item in value if isinstance(item, str) and item})


def normalized_access_scope(user: dict) -> dict:
    value = user.get("access_scope", {})
    return value if isinstance(value, dict) else {}


def has_capability(user: dict, capability: str) -> bool:
    return capability in normalized_capabilities(user)


def can_access_person(user: dict, person: dict) -> bool:
    person_scope = normalized_access_scope(user).get("persons", "none")
    if person_scope == "all":
        return True
    if person_scope == "created_by":
        return bool(user.get("user_id")) and person.get("created_by") == user.get("user_id")
    if person_scope == "assigned":
        person_ids = normalized_access_scope(user).get("person_ids", [])
        return isinstance(person_ids, list) and person.get("person_id") in person_ids
    return False


def authorize_person(user: dict, person: dict, capability: str) -> None:
    if not has_capability(user, capability) or not can_access_person(user, person):
        raise HTTPException(status_code=403, detail="Acceso no autorizado para esta persona")


async def ensure_access_defaults(db) -> None:
    """Idempotently materialize and version additive grants for rollout."""
    for role, defaults in _ROLE_ACCESS_DEFAULTS.items():
        await db.users.update_many(
            {"rol": role, "capabilities": {"$exists": False}},
            {"$set": {"capabilities": defaults["capabilities"]}},
        )
        await db.users.update_many(
            {"rol": role, "access_scope": {"$exists": False}},
            {"$set": {"access_scope": defaults["access_scope"]}},
        )
        await db.users.update_many(
            {"rol": role, "access_policy_version": {"$ne": 3}},
            {
                "$addToSet": {"capabilities": {"$each": defaults["capabilities"]}},
                "$set": {"access_policy_version": 3},
            },
        )
