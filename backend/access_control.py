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
PERSON_DIRECTORY_SEARCH = "person.directory.search"
PERSON_TALENTS_READ = "person.talents.read"
PERSON_TALENTS_WRITE = "person.talents.write"
PERSON_MINISTRIES_READ = "person.ministries.read"
PERSON_MINISTRIES_WRITE = "person.ministries.write"
MINISTRIES_CATALOG_MANAGE = "ministries.catalog.manage"
PERSON_CONTACTS_READ = "person.contacts.read"
PERSON_CONTACTS_WRITE = "person.contacts.write"
PERSON_ADDRESSES_READ = "person.addresses.read"
PERSON_ADDRESSES_WRITE = "person.addresses.write"
PERSON_PASTORAL_NOTES_READ = "person.notes.pastoral.read"
CORE_GOVERNANCE_MANAGE = "core.governance.manage"
CORE_ACCESS_MANAGE = "core.access.manage"
BOARD_CONFIDENTIAL_ACCESS = "board.confidential.access"
FINANCE_READ = "finance.read"
FINANCE_MANAGE = "finance.manage"
FINANCE_CAPABILITIES = [FINANCE_READ, FINANCE_MANAGE]
MEMBERSHIP_DOCUMENTS_MANAGE = "membership.documents.manage"
PROCESSES_READ = "processes.read"
PROCESSES_WRITE = "processes.write"
PROCESSES_PARTICIPATE = "processes.participate"
PROCESSES_MANAGE = "processes.manage"
PROCESS_ALERTS_MANAGE = "processes.alerts.manage"
CELLULAR_READ = "cellular.read"
CELLULAR_WRITE = "cellular.write"
CELLULAR_MANAGE = "cellular.manage"
CELLULAR_ATTENDANCE = "cellular.attendance.write"
CELLULAR_NEEDS = "cellular.needs.write"
CELLULAR_SENSITIVE_READ = "cellular.sensitive.read"
CELLULAR_MULTIPLY = "cellular.multiplication.manage"
DOORS_READ = "doors.read"
DOORS_WRITE = "doors.write"
DOORS_MANAGE = "doors.manage"
BOARD_AUDIO = "board.audio.manage"
BOARD_AI = "board.ai.generate"

CELLULAR_CAPABILITIES = [
    CELLULAR_READ,
    CELLULAR_WRITE,
    CELLULAR_MANAGE,
    CELLULAR_ATTENDANCE,
    CELLULAR_NEEDS,
    CELLULAR_SENSITIVE_READ,
    CELLULAR_MULTIPLY,
]
DOOR_BOARD_CAPABILITIES = [DOORS_READ, DOORS_WRITE, DOORS_MANAGE, BOARD_AUDIO, BOARD_AI]

PROCESS_CAPABILITIES = [
    PROCESSES_READ,
    PROCESSES_WRITE,
    PROCESSES_PARTICIPATE,
    PROCESSES_MANAGE,
    PROCESS_ALERTS_MANAGE,
]

PERSON_SELF_CAPABILITIES = [
    PERSON_PROFILE_SENSITIVE_READ,
    PERSON_PROFILE_WRITE,
    PERSON_HOUSEHOLD_READ,
    PERSON_FAMILY_READ,
    PERSON_ARRIVAL_READ,
    PERSON_ATTENDANCE_READ,
    PERSON_NOTES_READ,
    PERSON_HISTORY_READ,
    PERSON_TALENTS_READ,
    PERSON_TALENTS_WRITE,
    PERSON_MINISTRIES_READ,
    PERSON_CONTACTS_READ,
    PERSON_CONTACTS_WRITE,
    PERSON_ADDRESSES_READ,
    PERSON_ADDRESSES_WRITE,
    PROCESSES_READ,
    PROCESSES_PARTICIPATE,
    CELLULAR_READ,
]

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
    PERSON_DIRECTORY_SEARCH,
    PERSON_TALENTS_READ,
    PERSON_TALENTS_WRITE,
    PERSON_MINISTRIES_READ,
    PERSON_MINISTRIES_WRITE,
    MINISTRIES_CATALOG_MANAGE,
    PERSON_CONTACTS_READ,
    PERSON_CONTACTS_WRITE,
    PERSON_ADDRESSES_READ,
    PERSON_ADDRESSES_WRITE,
]

_ROLE_ACCESS_DEFAULTS = {
    "pastor": {
        "capabilities": [*PERSON_DOMAIN_CAPABILITIES, *PROCESS_CAPABILITIES, *CELLULAR_CAPABILITIES, *DOOR_BOARD_CAPABILITIES, *FINANCE_CAPABILITIES, MEMBERSHIP_DOCUMENTS_MANAGE, PERSON_PASTORAL_NOTES_READ, CORE_GOVERNANCE_MANAGE, CORE_ACCESS_MANAGE],
        "access_scope": {"persons": "all"},
    },
    "lider": {
        "capabilities": [*PERSON_DOMAIN_CAPABILITIES, PROCESSES_READ, PROCESSES_WRITE, PROCESSES_PARTICIPATE, CELLULAR_READ, CELLULAR_WRITE, CELLULAR_ATTENDANCE, CELLULAR_NEEDS, CELLULAR_SENSITIVE_READ, DOORS_READ],
        "access_scope": {"persons": "created_by"},
    },
    "persona": {
        "capabilities": PERSON_SELF_CAPABILITIES,
        "access_scope": {"persons": "self"},
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
    defaults["access_policy_version"] = 13
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
    user_id = user.get("user_id")
    user_person_id = user.get("person_id")
    target_person_id = person.get("person_id")
    target_auth_user_id = person.get("auth_user_id")
    if person_scope == "all":
        return True
    if person_scope == "created_by":
        return bool(user_id) and (
            person.get("created_by") == user_id
            or (bool(target_auth_user_id) and target_auth_user_id == user_id)
            or (bool(user_person_id) and bool(target_person_id) and target_person_id == user_person_id)
        )
    if person_scope == "assigned":
        person_ids = normalized_access_scope(user).get("person_ids", [])
        return isinstance(person_ids, list) and person.get("person_id") in person_ids
    if person_scope == "self":
        return (
            (bool(user_id) and bool(target_auth_user_id) and target_auth_user_id == user_id)
            or (bool(user_person_id) and bool(target_person_id) and target_person_id == user_person_id)
        )
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
            {"rol": role, "$or": [{"parent_user_id": {"$exists": False}}, {"access_policy_version": {"$lt": 13}}, {"access_policy_version": {"$exists": False}}]},
            {
                "$addToSet": {"capabilities": {"$each": defaults["capabilities"]}},
                "$set": {"access_policy_version": 13},
            },
        )
