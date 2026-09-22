"""ACCESS-01 minimal capability + person scope policy.

Capabilities are stored explicitly on users and resolved from Mongo on every
request by BASE-01. Roles are used only by the idempotent rollout backfill and
new-user defaults; authorization checks consume capabilities + access_scope.
"""
from copy import deepcopy

from fastapi import HTTPException

ACCESS_POLICY_VERSION = 21

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
BOARD_ACCESS = "board.access"
BOARD_CONFIDENTIAL_ACCESS = "board.confidential.access"
FINANCE_READ = "finance.read"
FINANCE_MANAGE = "finance.manage"
FINANCE_CAPABILITIES = [FINANCE_READ, FINANCE_MANAGE]
FINANCE_PRIVILEGE_GROUP = "finance"
BOARD_PRIVILEGE_GROUP = "board"
MEMBERSHIP_DOCUMENTS_MANAGE = "membership.documents.manage"
MEMBERSHIP_DIRECT_IMPORT = "membership.direct_import"
MEMBERSHIP_ACCEPTANCE_MANAGE = "membership.acceptance.manage"
CONSOLIDATION_MENTOR_TRANSFER = "consolidation.mentor.transfer"
CONSOLIDATION_RETREAT_CLOSE = "consolidation.retreat.close"
CONSOLIDATION_ASSIGN = "consolidation.assign"
FRONT_GROUPS_MANAGE = "front_groups.manage"
FRONT_GROUPS_VIEW = "front_groups.view"
FRONT_GROUP_WORK_ASSIGN = "front_groups.work.assign"
FRONT_GROUP_ROTATION_MANAGE = "front_groups.rotation.manage"
MENTOR_QUALIFICATIONS_MANAGE = "mentor.qualifications.manage"
LEADERSHIP_REQUIREMENTS_MANAGE = "leadership.requirements.manage"
LEADERSHIP_PROMOTE = "leadership.promote"
LEADERSHIP_VIEW = "leadership.view"
GEO_VIEW_AGGREGATE = "geo.view_aggregate"
GEO_VIEW_PRECISE = "geo.view_precise"
GEO_MANAGE_LOCATIONS = "geo.manage_locations"
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
OPERATIONS_VIEW = "operations.view"
OPERATIONS_MANAGE = "operations.manage"
OPERATIONS_CHECKIN = "operations.checkin"
OPERATIONS_VOLUNTEER = "operations.volunteer"
OPERATIONS_REPORTS = "operations.reports"
OPERATIONS_CAPABILITIES = [OPERATIONS_VIEW, OPERATIONS_MANAGE, OPERATIONS_CHECKIN, OPERATIONS_VOLUNTEER, OPERATIONS_REPORTS]
CARE_ASSIGNED_READ = "care.assigned.read"
CARE_ASSIGNED_WRITE = "care.assigned.write"
CARE_MANAGE = "care.manage"
CARE_CONFIDENTIAL_READ = "care.confidential.read"
CARE_CONFIDENTIAL_WRITE = "care.confidential.write"
CARE_AUDIT_READ = "care.audit.read"
CARE_CAPABILITIES = [CARE_ASSIGNED_READ, CARE_ASSIGNED_WRITE, CARE_MANAGE, CARE_CONFIDENTIAL_READ, CARE_CONFIDENTIAL_WRITE, CARE_AUDIT_READ]


def resolved_access_level(user: dict) -> str:
    """Normalize current and legacy coordinator account shapes."""
    role = str(user.get("rol") or user.get("role") or "").strip().lower()
    explicit = str(user.get("access_level") or "").strip().lower()
    coordinator_aliases = {"coordinador_general", "general_coordinator"}
    if explicit in coordinator_aliases or role in coordinator_aliases:
        return "coordinador_general"
    if role == "lider" and CORE_ACCESS_MANAGE in (user.get("capabilities") or []) and explicit in {"", "lider"}:
        return "coordinador_general"
    return explicit or role or "persona"


def is_general_coordinator(user: dict) -> bool:
    return resolved_access_level(user) == "coordinador_general"

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

JOURNEY_GOVERNANCE_CAPABILITIES = [
    MEMBERSHIP_ACCEPTANCE_MANAGE,
    CONSOLIDATION_MENTOR_TRANSFER,
    CONSOLIDATION_RETREAT_CLOSE,
    CONSOLIDATION_ASSIGN,
    FRONT_GROUPS_VIEW,
    FRONT_GROUPS_MANAGE,
    FRONT_GROUP_WORK_ASSIGN,
    FRONT_GROUP_ROTATION_MANAGE,
    MENTOR_QUALIFICATIONS_MANAGE,
    LEADERSHIP_VIEW,
    LEADERSHIP_REQUIREMENTS_MANAGE,
    LEADERSHIP_PROMOTE,
    GEO_VIEW_AGGREGATE,
    GEO_VIEW_PRECISE,
    GEO_MANAGE_LOCATIONS,
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
        "capabilities": [*PERSON_DOMAIN_CAPABILITIES, *PROCESS_CAPABILITIES, *CELLULAR_CAPABILITIES, *DOOR_BOARD_CAPABILITIES, *FINANCE_CAPABILITIES, *JOURNEY_GOVERNANCE_CAPABILITIES, *OPERATIONS_CAPABILITIES, *CARE_CAPABILITIES, MEMBERSHIP_DOCUMENTS_MANAGE, MEMBERSHIP_DIRECT_IMPORT, PERSON_PASTORAL_NOTES_READ, CORE_GOVERNANCE_MANAGE, CORE_ACCESS_MANAGE],
        "access_scope": {"persons": "all"},
    },
    "lider": {
        "capabilities": [*PERSON_DOMAIN_CAPABILITIES, PROCESSES_READ, PROCESSES_WRITE, PROCESSES_PARTICIPATE, FRONT_GROUPS_VIEW, FRONT_GROUP_WORK_ASSIGN, LEADERSHIP_VIEW, CELLULAR_READ, CELLULAR_WRITE, CELLULAR_ATTENDANCE, CELLULAR_NEEDS, CELLULAR_SENSITIVE_READ, DOORS_READ, OPERATIONS_VIEW, OPERATIONS_CHECKIN, OPERATIONS_VOLUNTEER, CARE_ASSIGNED_READ, CARE_ASSIGNED_WRITE],
        "access_scope": {"persons": "created_by"},
    },
    "persona": {
        "capabilities": [*PERSON_SELF_CAPABILITIES, OPERATIONS_VIEW, OPERATIONS_VOLUNTEER],
        "access_scope": {"persons": "self"},
    },
}
_ROLE_ACCESS_DEFAULTS["pastora"] = deepcopy(_ROLE_ACCESS_DEFAULTS["pastor"])


def access_defaults_for_role(role: str) -> dict:
    """Return explicit fields for a newly created user."""
    defaults = deepcopy(
        _ROLE_ACCESS_DEFAULTS.get(
            (role or "").strip().lower(),
            {"capabilities": [], "access_scope": {"persons": "none"}},
        )
    )
    defaults["access_policy_version"] = ACCESS_POLICY_VERSION
    return defaults


def normalized_capabilities(user: dict) -> list[str]:
    value = user.get("capabilities", [])
    if not isinstance(value, list):
        return []
    capabilities = {item for item in value if isinstance(item, str) and item}
    if not is_global_pastoral_authority(user):
        groups = set(normalized_privilege_groups(user))
        if FINANCE_PRIVILEGE_GROUP not in groups:
            capabilities.difference_update(FINANCE_CAPABILITIES)
        if BOARD_PRIVILEGE_GROUP not in groups:
            capabilities.discard(BOARD_ACCESS)
        capabilities.discard(BOARD_CONFIDENTIAL_ACCESS)
    return sorted(capabilities)


def normalized_privilege_groups(user: dict) -> list[str]:
    value = user.get("privilege_groups", [])
    if not isinstance(value, list):
        return []
    return sorted({item for item in value if isinstance(item, str) and item})


def normalized_access_scope(user: dict) -> dict:
    value = user.get("access_scope", {})
    return value if isinstance(value, dict) else {}


def is_global_pastoral_authority(user: dict) -> bool:
    """Autoridad global reservada a cuentas pastorales, incluidas variantes legadas."""
    roles = {
        str(user.get("rol") or "").strip().lower(),
        str(user.get("role") or "").strip().lower(),
    }
    access_level = str(user.get("access_level") or "").strip().lower()
    return bool(roles & {"pastor", "pastora", "admin", "superadmin"}) or access_level == "pastor"


def has_capability(user: dict, capability: str) -> bool:
    """Las lecturas sensibles siempre requieren una concesión explícita."""
    return capability in normalized_capabilities(user)


def can_access_person(user: dict, person: dict) -> bool:
    if is_global_pastoral_authority(user):
        return True
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
            {"rol": role, "$or": [{"parent_user_id": {"$exists": False}}, {"access_policy_version": {"$lt": ACCESS_POLICY_VERSION}}, {"access_policy_version": {"$exists": False}}]},
            {
                "$addToSet": {"capabilities": {"$each": defaults["capabilities"]}},
                "$set": {"access_policy_version": ACCESS_POLICY_VERSION},
            },
        )
    await db.users.update_many({"rol": "persona"}, {"$addToSet": {"capabilities": {"$each": [OPERATIONS_VIEW, OPERATIONS_VOLUNTEER]}}})
    await db.users.update_many({"rol": "lider"}, {"$addToSet": {"capabilities": {"$each": [OPERATIONS_VIEW, OPERATIONS_CHECKIN, OPERATIONS_VOLUNTEER]}}})
    await db.users.update_many(
        {"$or": [{"access_level": "coordinador_general"}, {"rol": "lider", "capabilities": CORE_ACCESS_MANAGE}]},
        {"$addToSet": {"capabilities": {"$each": [*CARE_CAPABILITIES, MEMBERSHIP_DIRECT_IMPORT]}, "privilege_groups": "care"}, "$set": {"access_scope.persons": "all", "access_policy_version": ACCESS_POLICY_VERSION}},
    )
