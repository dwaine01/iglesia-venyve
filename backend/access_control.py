"""ACCESS-01 minimal capability + person scope policy.

Capabilities are stored explicitly on users and resolved from Mongo on every
request by BASE-01. Roles are used only by the idempotent rollout backfill and
new-user defaults; authorization checks consume capabilities + access_scope.
"""
from copy import deepcopy

from fastapi import HTTPException

ACCESS_POLICY_VERSION = 24

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
# Nuevo flujo de la colecta (decisión del dueño): roles independientes, cada uno asignado a mano.
FINANCE_COLLECTION_RECORD = "finance.collection.record"   # Finanzas: abre la colecta y registra aportes
FINANCE_COLLECTION_VERIFY = "finance.collection.verify"   # segunda persona: valida el cuadre
FINANCE_TREASURY = "finance.treasury"                     # Tesorería: recibe el efectivo y deposita
FINANCE_DONORS_READ = "finance.donors.read"               # ver aportes por persona (además de la pastora)
FINANCE_FLOW_CAPABILITIES = [FINANCE_COLLECTION_RECORD, FINANCE_COLLECTION_VERIFY, FINANCE_TREASURY, FINANCE_DONORS_READ]
FINANCE_DEFAULT_CAPABILITIES = [FINANCE_READ, FINANCE_MANAGE]  # lo que recibe el grupo Finanzas por defecto (como antes)
FINANCE_CAPABILITIES = [FINANCE_READ, FINANCE_MANAGE, *FINANCE_FLOW_CAPABILITIES]
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
# Registro digital de visitantes (tabletas de bienvenida).
VISITORS_DEVICES_MANAGE = "visitors.devices.manage"
VISITORS_READ = "visitors.read"
VISITORS_FOLLOWUP_MANAGE = "visitors.followup.manage"
VISITORS_RESTRICTED_READ = "visitors.restricted.read"
VISITORS_WELCOME_OPERATE = "visitors.welcome.operate"
VISITORS_TEXTS_MANAGE = "visitors.texts.manage"
OPERATIONS_CAPABILITIES = [OPERATIONS_VIEW, OPERATIONS_MANAGE, OPERATIONS_CHECKIN, OPERATIONS_VOLUNTEER, OPERATIONS_REPORTS]
CARE_ASSIGNED_READ = "care.assigned.read"
CARE_ASSIGNED_WRITE = "care.assigned.write"
CARE_MANAGE = "care.manage"
CARE_CONFIDENTIAL_READ = "care.confidential.read"
CARE_CONFIDENTIAL_WRITE = "care.confidential.write"
CARE_AUDIT_READ = "care.audit.read"
CARE_CAPABILITIES = [CARE_ASSIGNED_READ, CARE_ASSIGNED_WRITE, CARE_MANAGE, CARE_CONFIDENTIAL_READ, CARE_CONFIDENTIAL_WRITE, CARE_AUDIT_READ]
FORMATION_READ = "formation.read"
FORMATION_PROGRAMS_MANAGE = "formation.programs.manage"
FORMATION_COHORTS_MANAGE = "formation.cohorts.manage"
FORMATION_ENROLL = "formation.enroll"
FORMATION_ATTENDANCE_WRITE = "formation.attendance.write"
FORMATION_GRADES_READ = "formation.grades.read"
FORMATION_GRADES_WRITE = "formation.grades.write"
FORMATION_PROGRESS_MANAGE = "formation.progress.manage"
FORMATION_HISTORICAL_CREDIT_MANAGE = "formation.historical_credit.manage"
FORMATION_PROMOTE = "formation.promote"
FORMATION_CERTIFICATES_ISSUE = "formation.certificates.issue"
BAPTISM_READ = "baptism.read"
BAPTISM_WRITE = "baptism.write"
BAPTISM_CERTIFICATES_ISSUE = "baptism.certificates.issue"
BAPTISM_EVENTS_MANAGE = "baptism.events.manage"
DEDICATION_READ = "dedication.read"
DEDICATION_EVENTS_MANAGE = "dedication.events.manage"
DEDICATION_CERTIFICATES_ISSUE = "dedication.certificates.issue"
LIBRARY_CATALOG_MANAGE = "library.catalog.manage"
LIBRARY_INVENTORY_MANAGE = "library.inventory.manage"
LIBRARY_DELIVER = "library.deliver"
LIBRARY_REPORTS_READ = "library.reports.read"
LIBRARY_CAPABILITIES = [LIBRARY_CATALOG_MANAGE, LIBRARY_INVENTORY_MANAGE, LIBRARY_DELIVER, LIBRARY_REPORTS_READ]
CAMPAIGN_VENYCOME_MANAGE = "campaign.venycome.manage"
CAMPAIGN_CAPABILITIES = [CAMPAIGN_VENYCOME_MANAGE]
MENTORSHIP_BADGE_MANAGE = "mentorship.badge.manage"
MENTORSHIP_OUTREACH_ASSIGN = "mentorship.outreach.assign"
MENTORSHIP_OUTREACH_REPORT = "mentorship.outreach.report"
MENTORSHIP_CAPABILITIES = [MENTORSHIP_BADGE_MANAGE, MENTORSHIP_OUTREACH_ASSIGN, MENTORSHIP_OUTREACH_REPORT]
FORMATION_CAPABILITIES = [
    FORMATION_READ, FORMATION_PROGRAMS_MANAGE, FORMATION_COHORTS_MANAGE,
    FORMATION_ENROLL, FORMATION_ATTENDANCE_WRITE, FORMATION_GRADES_READ,
    FORMATION_GRADES_WRITE, FORMATION_PROGRESS_MANAGE,
    FORMATION_HISTORICAL_CREDIT_MANAGE, FORMATION_PROMOTE,
    FORMATION_CERTIFICATES_ISSUE, BAPTISM_READ, BAPTISM_WRITE,
    BAPTISM_CERTIFICATES_ISSUE, BAPTISM_EVENTS_MANAGE,
    DEDICATION_READ, DEDICATION_EVENTS_MANAGE, DEDICATION_CERTIFICATES_ISSUE,
]

# ETAPA 5A: estas tres herramientas de staff (códigos, bitácora, manual) eran
# accesibles por cualquier "lider" solo por el cargo; ahora son módulos como
# cualquier otro, con su propia capability.
INVITATION_CODES_MANAGE = "invitations.codes.manage"
EVANGELISM_LOG_WRITE = "evangelism.log.write"
PRESENTATION_MANUAL_VIEW = "presentation.manual.view"
STAFF_TOOLS_CAPABILITIES = [INVITATION_CODES_MANAGE, EVANGELISM_LOG_WRITE, PRESENTATION_MANUAL_VIEW]


# ETAPA 5A: matriz módulo × acción para altas/ediciones de cuentas. Única
# fuente de verdad consumida por el backend (validación) y el frontend
# (matriz de permisos). Cada cuenta nueva nace en modo "manual": solo recibe
# lo que el administrador marque aquí explícitamente (más el paquete de
# mentor si corresponde); no hereda el paquete amplio por cargo.
CAPABILITY_CATALOG = [
    {"module_key": "persons", "label": "Personas y Directorio 360", "items": [
        {"capability": PERSON_DIRECTORY_SEARCH, "action": "consultar", "label": "Consultar: buscar personas en el directorio"},
        {"capability": PERSON_PROFILE_SENSITIVE_READ, "action": "consultar", "label": "Consultar: datos sensibles del perfil (nacimiento, género, estado civil)"},
        {"capability": PERSON_PROFILE_WRITE, "action": "editar", "label": "Editar: datos del perfil de una persona"},
        {"capability": PERSON_CONTACTS_READ, "action": "consultar", "label": "Consultar: teléfonos y correos"},
        {"capability": PERSON_CONTACTS_WRITE, "action": "editar", "label": "Editar: teléfonos y correos"},
        {"capability": PERSON_ADDRESSES_READ, "action": "consultar", "label": "Consultar: direcciones"},
        {"capability": PERSON_ADDRESSES_WRITE, "action": "editar", "label": "Editar: direcciones"},
        {"capability": PERSON_HOUSEHOLD_READ, "action": "consultar", "label": "Consultar: hogar/household"},
        {"capability": PERSON_HOUSEHOLD_WRITE, "action": "editar", "label": "Editar: hogar/household"},
        {"capability": PERSON_FAMILY_READ, "action": "consultar", "label": "Consultar: relaciones familiares"},
        {"capability": PERSON_FAMILY_WRITE, "action": "editar", "label": "Editar: relaciones familiares"},
        {"capability": PERSON_ARRIVAL_READ, "action": "consultar", "label": "Consultar: llegada y origen"},
        {"capability": PERSON_ARRIVAL_WRITE, "action": "editar", "label": "Editar: llegada y origen"},
        {"capability": PERSON_ATTENDANCE_READ, "action": "consultar", "label": "Consultar: asistencia"},
        {"capability": PERSON_ATTENDANCE_WRITE, "action": "agregar", "label": "Agregar/editar: registros de asistencia"},
        {"capability": PERSON_NOTES_READ, "action": "consultar", "label": "Consultar: notas"},
        {"capability": PERSON_NOTES_WRITE, "action": "agregar", "label": "Agregar/editar: notas"},
        {"capability": PERSON_PASTORAL_NOTES_READ, "action": "consultar", "label": "Consultar: notas pastorales"},
        {"capability": PERSON_HISTORY_READ, "action": "consultar", "label": "Consultar: historial"},
        {"capability": PERSON_TALENTS_READ, "action": "consultar", "label": "Consultar: talentos y dones"},
        {"capability": PERSON_TALENTS_WRITE, "action": "editar", "label": "Editar: talentos y dones"},
        {"capability": PERSON_MINISTRIES_READ, "action": "consultar", "label": "Consultar: ministerios asignados"},
        {"capability": PERSON_MINISTRIES_WRITE, "action": "editar", "label": "Editar: ministerios asignados"},
        {"capability": MINISTRIES_CATALOG_MANAGE, "action": "administrar", "label": "Administrar: catálogo de ministerios"},
    ]},
    {"module_key": "processes", "label": "Procesos (Consolidación, 7 Semanas, Discipulado)", "items": [
        {"capability": PROCESSES_READ, "action": "consultar", "label": "Consultar: procesos de otras personas"},
        {"capability": PROCESSES_WRITE, "action": "editar", "label": "Editar: avance de procesos"},
        {"capability": PROCESSES_PARTICIPATE, "action": "agregar", "label": "Participar en un proceso propio"},
        {"capability": PROCESSES_MANAGE, "action": "administrar", "label": "Administrar: configuración de procesos"},
        {"capability": PROCESS_ALERTS_MANAGE, "action": "administrar", "label": "Administrar: alertas de procesos"},
    ]},
    {"module_key": "front_groups", "label": "Grupos Frontales y Liderazgo", "items": [
        {"capability": FRONT_GROUPS_VIEW, "action": "consultar", "label": "Consultar: Grupos Frontales"},
        {"capability": FRONT_GROUPS_MANAGE, "action": "administrar", "label": "Administrar: Grupos Frontales"},
        {"capability": FRONT_GROUP_WORK_ASSIGN, "action": "agregar", "label": "Agregar: asignar trabajo a integrantes"},
        {"capability": FRONT_GROUP_ROTATION_MANAGE, "action": "administrar", "label": "Administrar: rotación de Grupos Frontales"},
        {"capability": LEADERSHIP_VIEW, "action": "consultar", "label": "Consultar: Liderazgo"},
        {"capability": LEADERSHIP_REQUIREMENTS_MANAGE, "action": "administrar", "label": "Administrar: requisitos de liderazgo"},
        {"capability": LEADERSHIP_PROMOTE, "action": "administrar", "label": "Administrar: promover liderazgo"},
        {"capability": MENTOR_QUALIFICATIONS_MANAGE, "action": "administrar", "label": "Administrar: calificación de mentores LBS"},
    ]},
    {"module_key": "mentorship_outreach", "label": "Mentoría e Invasiones", "items": [
        {"capability": MENTORSHIP_BADGE_MANAGE, "action": "administrar", "label": "Administrar: insignia de Mentor"},
        {"capability": MENTORSHIP_OUTREACH_ASSIGN, "action": "administrar", "label": "Administrar: asignar visitas e invasiones"},
        {"capability": MENTORSHIP_OUTREACH_REPORT, "action": "agregar", "label": "Agregar: rendir informe de visitas propias"},
        {"capability": CONSOLIDATION_MENTOR_TRANSFER, "action": "administrar", "label": "Administrar: transferir mentor"},
        {"capability": CONSOLIDATION_RETREAT_CLOSE, "action": "administrar", "label": "Administrar: cerrar Retiro"},
        {"capability": CONSOLIDATION_ASSIGN, "action": "administrar", "label": "Administrar: asignación de Consolidación"},
        {"capability": CAMPAIGN_VENYCOME_MANAGE, "action": "administrar", "label": "Administrar: Campaña Ven y Come"},
    ]},
    {"module_key": "library", "label": "Librería 360", "items": [
        {"capability": LIBRARY_DELIVER, "action": "agregar", "label": "Agregar: recibir/entregar libros"},
        {"capability": LIBRARY_CATALOG_MANAGE, "action": "administrar", "label": "Administrar: catálogo de Librería"},
        {"capability": LIBRARY_INVENTORY_MANAGE, "action": "administrar", "label": "Administrar: inventario de Librería"},
        {"capability": LIBRARY_REPORTS_READ, "action": "consultar", "label": "Consultar: reportes de Librería"},
    ]},
    {"module_key": "cellular", "label": "Sistema Celular", "items": [
        {"capability": CELLULAR_READ, "action": "consultar", "label": "Consultar: células"},
        {"capability": CELLULAR_WRITE, "action": "editar", "label": "Editar: datos de células"},
        {"capability": CELLULAR_MANAGE, "action": "administrar", "label": "Administrar: Sistema Celular"},
        {"capability": CELLULAR_ATTENDANCE, "action": "agregar", "label": "Agregar: asistencia celular"},
        {"capability": CELLULAR_NEEDS, "action": "agregar", "label": "Agregar: necesidades celulares"},
        {"capability": CELLULAR_SENSITIVE_READ, "action": "consultar", "label": "Consultar: información celular sensible"},
        {"capability": CELLULAR_MULTIPLY, "action": "administrar", "label": "Administrar: multiplicación celular"},
    ]},
    {"module_key": "doors_media", "label": "9 Puertas y recursos de Junta", "items": [
        {"capability": DOORS_READ, "action": "consultar", "label": "Consultar: 9 Puertas"},
        {"capability": DOORS_WRITE, "action": "editar", "label": "Editar: casos de 9 Puertas"},
        {"capability": DOORS_MANAGE, "action": "administrar", "label": "Administrar: 9 Puertas"},
        {"capability": BOARD_AUDIO, "action": "administrar", "label": "Administrar: grabación de audio de Junta"},
        {"capability": BOARD_AI, "action": "administrar", "label": "Administrar: generación por IA en Junta"},
    ]},
    {"module_key": "visitors", "label": "Registro de visitantes", "items": [
        {"capability": VISITORS_DEVICES_MANAGE, "action": "administrar", "label": "Administrar: tabletas de registro (emparejar y desactivar)"},
        {"capability": VISITORS_READ, "action": "consultar", "label": "Consultar: registros de visitantes y sus datos de contacto"},
        {"capability": VISITORS_FOLLOWUP_MANAGE, "action": "editar", "label": "Editar: seguimiento de visitantes (asignar y registrar resultado)"},
        {"capability": VISITORS_RESTRICTED_READ, "action": "consultar", "label": "Consultar: oración, consejería y necesidades personales (restringido)"},
        {"capability": VISITORS_WELCOME_OPERATE, "action": "administrar", "label": "Administrar: panel y pantalla de bienvenida"},
        {"capability": VISITORS_TEXTS_MANAGE, "action": "editar", "label": "Editar: textos de bienvenida, privacidad y confirmación"},
    ]},
    {"module_key": "operations", "label": "Operaciones y Eventos", "items": [
        {"capability": OPERATIONS_VIEW, "action": "consultar", "label": "Consultar: Operaciones y eventos"},
        {"capability": OPERATIONS_MANAGE, "action": "administrar", "label": "Administrar: Operaciones"},
        {"capability": OPERATIONS_CHECKIN, "action": "agregar", "label": "Agregar: check-in de eventos"},
        {"capability": OPERATIONS_VOLUNTEER, "action": "agregar", "label": "Agregar: voluntariado en turnos"},
        {"capability": OPERATIONS_REPORTS, "action": "consultar", "label": "Consultar: reportes de Operaciones"},
    ]},
    {"module_key": "care", "label": "Cuidado Pastoral", "items": [
        {"capability": CARE_ASSIGNED_READ, "action": "consultar", "label": "Consultar: casos pastorales asignados"},
        {"capability": CARE_ASSIGNED_WRITE, "action": "editar", "label": "Editar: casos pastorales asignados"},
        {"capability": CARE_MANAGE, "action": "administrar", "label": "Administrar: Cuidado Pastoral"},
        {"capability": CARE_CONFIDENTIAL_READ, "action": "consultar", "label": "Consultar: expediente confidencial"},
        {"capability": CARE_CONFIDENTIAL_WRITE, "action": "editar", "label": "Editar: expediente confidencial"},
        {"capability": CARE_AUDIT_READ, "action": "consultar", "label": "Consultar: auditoría de Cuidado Pastoral"},
    ]},
    {"module_key": "formation", "label": "Formación, Bautismo y Presentación de Niños", "items": [
        {"capability": FORMATION_READ, "action": "consultar", "label": "Consultar: Formación"},
        {"capability": FORMATION_PROGRAMS_MANAGE, "action": "administrar", "label": "Administrar: programas de Formación"},
        {"capability": FORMATION_COHORTS_MANAGE, "action": "administrar", "label": "Administrar: promociones de Formación"},
        {"capability": FORMATION_ENROLL, "action": "agregar", "label": "Agregar: inscribir estudiantes"},
        {"capability": FORMATION_ATTENDANCE_WRITE, "action": "agregar", "label": "Agregar: tomar asistencia"},
        {"capability": FORMATION_GRADES_READ, "action": "consultar", "label": "Consultar: notas"},
        {"capability": FORMATION_GRADES_WRITE, "action": "editar", "label": "Editar: notas"},
        {"capability": FORMATION_PROGRESS_MANAGE, "action": "administrar", "label": "Administrar: progreso de Formación"},
        {"capability": FORMATION_HISTORICAL_CREDIT_MANAGE, "action": "administrar", "label": "Administrar: acreditar formación histórica"},
        {"capability": FORMATION_PROMOTE, "action": "administrar", "label": "Administrar: promover estudiantes"},
        {"capability": FORMATION_CERTIFICATES_ISSUE, "action": "administrar", "label": "Administrar: certificados de Formación"},
        {"capability": BAPTISM_READ, "action": "consultar", "label": "Consultar: Bautismo"},
        {"capability": BAPTISM_WRITE, "action": "editar", "label": "Editar: registros de Bautismo"},
        {"capability": BAPTISM_CERTIFICATES_ISSUE, "action": "administrar", "label": "Administrar: certificados de Bautismo"},
        {"capability": BAPTISM_EVENTS_MANAGE, "action": "administrar", "label": "Administrar: eventos de Bautismo"},
        {"capability": DEDICATION_READ, "action": "consultar", "label": "Consultar: Presentación de Niños"},
        {"capability": DEDICATION_EVENTS_MANAGE, "action": "administrar", "label": "Administrar: eventos de Presentación"},
        {"capability": DEDICATION_CERTIFICATES_ISSUE, "action": "administrar", "label": "Administrar: certificados de Presentación"},
    ]},
    {"module_key": "geo", "label": "Mapa 360", "items": [
        {"capability": GEO_VIEW_AGGREGATE, "action": "consultar", "label": "Consultar: mapa agregado (sin direcciones exactas)"},
        {"capability": GEO_VIEW_PRECISE, "action": "consultar", "label": "Consultar: mapa con direcciones exactas"},
        {"capability": GEO_MANAGE_LOCATIONS, "action": "administrar", "label": "Administrar: corregir ubicaciones"},
    ]},
    {"module_key": "membership", "label": "Membresía", "items": [
        {"capability": MEMBERSHIP_DOCUMENTS_MANAGE, "action": "administrar", "label": "Administrar: emitir carnet/certificado"},
        {"capability": MEMBERSHIP_DIRECT_IMPORT, "action": "administrar", "label": "Administrar: regularizar membresía existente"},
        {"capability": MEMBERSHIP_ACCEPTANCE_MANAGE, "action": "administrar", "label": "Administrar: registrar firma de membresía"},
    ]},
    {"module_key": "finance", "label": "Finanzas (requiere grupo de privilegio Finanzas)", "items": [
        {"capability": FINANCE_READ, "action": "consultar", "label": "Consultar: Finanzas"},
        {"capability": FINANCE_MANAGE, "action": "administrar", "label": "Administrar: Finanzas"},
        {"capability": FINANCE_COLLECTION_RECORD, "action": "agregar", "label": "Colecta: registrar aportes (Finanzas)"},
        {"capability": FINANCE_COLLECTION_VERIFY, "action": "administrar", "label": "Colecta: validar el cuadre (segunda persona)"},
        {"capability": FINANCE_TREASURY, "action": "administrar", "label": "Tesorería: recibir efectivo y depositar"},
        {"capability": FINANCE_DONORS_READ, "action": "consultar", "label": "Ver aportes por persona (cada consulta queda registrada)"},
    ]},
    {"module_key": "board", "label": "Junta Directiva (requiere grupo de privilegio Junta)", "items": [
        {"capability": BOARD_ACCESS, "action": "consultar", "label": "Consultar: Junta Directiva"},
    ]},
    {"module_key": "staff_tools", "label": "Herramientas de Evangelismo y Comunicación", "items": [
        {"capability": INVITATION_CODES_MANAGE, "action": "administrar", "label": "Administrar: generar Códigos de Invitación"},
        {"capability": EVANGELISM_LOG_WRITE, "action": "agregar", "label": "Agregar: registrar Bitácora Evangelística"},
        {"capability": PRESENTATION_MANUAL_VIEW, "action": "consultar", "label": "Consultar: Manual de las 7 Semanas"},
    ]},
]


def capability_catalog_keys() -> set[str]:
    return {item["capability"] for module in CAPABILITY_CATALOG for item in module["items"]}


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
        "capabilities": [*PERSON_DOMAIN_CAPABILITIES, *PROCESS_CAPABILITIES, *CELLULAR_CAPABILITIES, *DOOR_BOARD_CAPABILITIES, *FINANCE_DEFAULT_CAPABILITIES, FINANCE_DONORS_READ, *JOURNEY_GOVERNANCE_CAPABILITIES, *OPERATIONS_CAPABILITIES, *CARE_CAPABILITIES, *FORMATION_CAPABILITIES, *LIBRARY_CAPABILITIES, *STAFF_TOOLS_CAPABILITIES, MEMBERSHIP_DOCUMENTS_MANAGE, MEMBERSHIP_DIRECT_IMPORT, PERSON_PASTORAL_NOTES_READ, CORE_GOVERNANCE_MANAGE, CORE_ACCESS_MANAGE],
        "access_scope": {"persons": "all"},
    },
    "lider": {
        "capabilities": [*PERSON_DOMAIN_CAPABILITIES, PROCESSES_READ, PROCESSES_WRITE, PROCESSES_PARTICIPATE, FRONT_GROUPS_VIEW, FRONT_GROUP_WORK_ASSIGN, LEADERSHIP_VIEW, CELLULAR_READ, CELLULAR_WRITE, CELLULAR_ATTENDANCE, CELLULAR_NEEDS, CELLULAR_SENSITIVE_READ, DOORS_READ, OPERATIONS_VIEW, OPERATIONS_CHECKIN, OPERATIONS_VOLUNTEER, CARE_ASSIGNED_READ, CARE_ASSIGNED_WRITE, LIBRARY_DELIVER, *STAFF_TOOLS_CAPABILITIES],
        "access_scope": {"persons": "created_by"},
    },
    "persona": {
        "capabilities": [*PERSON_SELF_CAPABILITIES, FORMATION_READ, BAPTISM_READ, DEDICATION_READ, OPERATIONS_VIEW, OPERATIONS_VOLUNTEER],
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


def has_church_wide_reach(user: dict) -> bool:
    """Ve listados de toda la iglesia: autoridad pastoral, Coordinación General o alcance «todas las Personas».
    Una cuenta de Miembro (alcance propio) solo ve lo suyo aunque tenga el permiso de consulta."""
    return is_global_pastoral_authority(user) or is_general_coordinator(user) or normalized_access_scope(user).get("persons") == "all"


def is_own_person(user: dict, person_id: str | None) -> bool:
    """La Persona vinculada a la propia cuenta."""
    own = user.get("person_id")
    return bool(own) and bool(person_id) and own == person_id


# Lectura de la propia ficha: toda cuenta puede ver su Perfil 360 completo
# sin permiso de directorio. Solo lecturas; las escrituras siguen dependiendo
# de lo que la cuenta tenga concedido.
SELF_PROFILE_READ_CAPABILITIES = [item for item in PERSON_SELF_CAPABILITIES if item.endswith(".read")]


def self_view_user(user: dict) -> dict:
    """Usuario efectivo para leer la PROPIA ficha. Añade las lecturas de uno
    mismo y, si el alcance original no cubría a la propia Persona, lo limita
    a 'self' sin conceder escrituras que antes no podía ejercer."""
    effective = dict(user)
    original_caps = list(user.get("capabilities") or []) if isinstance(user.get("capabilities"), list) else []
    own_person = {"person_id": user.get("person_id")}
    if not can_access_person(user, own_person):
        original_caps = [item for item in original_caps if item.endswith(".read") or not item.startswith(("person.", "processes."))]
        effective["access_scope"] = {"persons": "self"}
    effective["capabilities"] = sorted(set(original_caps) | set(SELF_PROFILE_READ_CAPABILITIES))
    return effective


def authorize_person(user: dict, person: dict, capability: str) -> None:
    if not has_capability(user, capability) or not can_access_person(user, person):
        raise HTTPException(status_code=403, detail="Acceso no autorizado para esta persona")


async def ensure_access_defaults(db) -> None:
    """Idempotently materialize and version additive grants for rollout.
    ETAPA 5A: nunca toca cuentas en permissions_mode="manual" (nacidas desde
    la matriz módulo×acción); solo retro-completa cuentas heredadas del
    modelo por cargo, para no quitarles nada de lo que ya tenían."""
    manual_excluded = {"permissions_mode": {"$ne": "manual"}}
    for role, defaults in _ROLE_ACCESS_DEFAULTS.items():
        await db.users.update_many(
            {"rol": role, "capabilities": {"$exists": False}, **manual_excluded},
            {"$set": {"capabilities": defaults["capabilities"]}},
        )
        await db.users.update_many(
            {"rol": role, "access_scope": {"$exists": False}, **manual_excluded},
            {"$set": {"access_scope": defaults["access_scope"]}},
        )
        await db.users.update_many(
            {"rol": role, "$or": [{"parent_user_id": {"$exists": False}}, {"access_policy_version": {"$lt": ACCESS_POLICY_VERSION}}, {"access_policy_version": {"$exists": False}}], **manual_excluded},
            {
                "$addToSet": {"capabilities": {"$each": defaults["capabilities"]}},
                "$set": {"access_policy_version": ACCESS_POLICY_VERSION},
            },
        )
    await db.users.update_many({"rol": "persona", **manual_excluded}, {"$addToSet": {"capabilities": {"$each": [OPERATIONS_VIEW, OPERATIONS_VOLUNTEER]}}})
    await db.users.update_many({"rol": "lider", **manual_excluded}, {"$addToSet": {"capabilities": {"$each": [OPERATIONS_VIEW, OPERATIONS_CHECKIN, OPERATIONS_VOLUNTEER, LIBRARY_DELIVER, *STAFF_TOOLS_CAPABILITIES]}}})
    await db.users.update_many(
        {"$or": [{"access_level": "coordinador_general"}, {"rol": "lider", "capabilities": CORE_ACCESS_MANAGE}], **manual_excluded},
        {"$addToSet": {"capabilities": {"$each": [*CARE_CAPABILITIES, MEMBERSHIP_DIRECT_IMPORT, FORMATION_READ, FORMATION_COHORTS_MANAGE, FORMATION_ENROLL, FORMATION_ATTENDANCE_WRITE, FORMATION_GRADES_READ, FORMATION_GRADES_WRITE, FORMATION_PROGRESS_MANAGE, FORMATION_HISTORICAL_CREDIT_MANAGE, FORMATION_PROMOTE, BAPTISM_READ, BAPTISM_WRITE, BAPTISM_CERTIFICATES_ISSUE, BAPTISM_EVENTS_MANAGE, DEDICATION_READ, DEDICATION_EVENTS_MANAGE, DEDICATION_CERTIFICATES_ISSUE, *LIBRARY_CAPABILITIES, MENTORSHIP_BADGE_MANAGE, MENTORSHIP_OUTREACH_ASSIGN, CONSOLIDATION_MENTOR_TRANSFER]}, "privilege_groups": "care"}, "$set": {"access_scope.persons": "all", "access_policy_version": ACCESS_POLICY_VERSION}},
    )
    await db.users.update_many(
        {"capabilities": MENTORSHIP_OUTREACH_REPORT, **manual_excluded},
        {"$addToSet": {"capabilities": {"$each": [*PERSON_SELF_CAPABILITIES, PROCESSES_PARTICIPATE, LIBRARY_DELIVER]}}},
    )
