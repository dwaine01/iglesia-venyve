const COMMON_LABELS = Object.freeze({
  active: 'Activo', inactive: 'Inactivo', planned: 'Planificado', paused: 'En pausa', completed: 'Completado', cancelled: 'Cancelado', withdrawn: 'Retirado',
  ready: 'Listo', processing: 'En procesamiento', uploading: 'Cargando audio', complete: 'Completado', blocked: 'Pendiente de configuración', failed: 'No se pudo completar', uploaded: 'Audio recibido',
  open: 'Abierto', closed: 'Cerrado', assigned: 'Asignado', in_progress: 'En proceso', resolved: 'Resuelto', waiting: 'En espera', pending: 'Pendiente', locked: 'Bloqueado',
  scheduled: 'Programada', draft: 'Borrador', review: 'En revisión', official: 'Oficial', rejected: 'Rechazada', ai_draft: 'Borrador asistido por IA',
  presented: 'Presentada', ready_for_vote: 'Lista para votación', approved: 'Aprobada', denied: 'No aprobada',
  present: 'Presente', presente: 'Presente', absent: 'Ausente', ausente: 'Ausente', excused: 'Ausencia justificada', justificado: 'Ausencia justificada', remote: 'Participación en línea', late: 'Llegó tarde', left_early: 'Se retiró antes',
  low: 'Baja', medium: 'Media', high: 'Alta', urgent: 'Urgente', info: 'Informativa', warning: 'Atención', critical: 'Crítica',
  online: 'En línea', onsite: 'Presencial', hybrid: 'Híbrida', percentage: 'Porcentaje', simple_majority: 'Mayoría simple', supermajority: 'Mayoría calificada',
  candidate: 'Candidata', under_review: 'En revisión', postponed: 'Pospuesta', multiplied: 'Multiplicada',
  follow_up_required: 'Requiere seguimiento', overdue: 'Seguimiento vencido', due_soon: 'Próximo a vencer', on_sla: 'Seguimiento a tiempo', stalled: 'Detenido',
  ready_for_cellular: 'Listo para integrarse a una célula', ready_for_activation: 'Listo para servir',
  door_suggested: 'Puerta recomendada', door_selected: 'Puerta confirmada', activated: 'Activo en servicio', continuous_training: 'En desarrollo continuo', evaluated: 'Dones identificados',
  new_visitor: 'Nuevo visitante', contacted: 'Contactado', first_visit: 'Primera visita', follow_up: 'Seguimiento', formation: 'Formación',
  pastor: 'Pastor', lider: 'Líder', leader: 'Líder', persona: 'Persona', disciple: 'Discípulo',
  general_coordinator: 'Coordinador general', network_director: 'Director de red', supervisor: 'Supervisor', cell_leader: 'Líder de célula', assistant_leader: 'Líder asistente', assistant: 'Asistente', host: 'Anfitrión', intercessor: 'Intercesor', collaborator: 'Colaborador', server: 'Servidor', door_leader: 'Líder de Puerta', member: 'Miembro', visitor: 'Visitante',
  primary: 'Membresía principal', service: 'Servicio adicional',
  illness: 'Enfermedad', urgent_prayer: 'Oración urgente', crisis: 'Crisis', new_believer: 'Nuevo creyente', family_need: 'Necesidad familiar', ready_for_discipleship: 'Listo para discipulado', special_event: 'Evento especial', other: 'Otro', pastoral_care: 'Cuidado pastoral', family_support: 'Apoyo familiar', material_support: 'Apoyo material', health_support: 'Apoyo de salud', spiritual_guidance: 'Orientación espiritual',
  consolidation: 'Consolidación', seven_weeks: '7 Semanas', mentorship: 'Mentoría', cap: 'Encuentra tu lugar para servir',
  secretary_notes: 'Notas de secretaría', human_draft: 'Borrador humano', manual: 'Minuta manual', transcript: 'Transcripción', executive_summary: 'Resumen ejecutivo', minute_draft: 'Borrador de minuta', pastoral_risks: 'Asuntos que requieren atención pastoral', decisions: 'Decisiones', actions: 'Acuerdos y tareas', agreements: 'Acuerdos', tasks: 'Tareas', participation: 'Participación',
  yes: 'Sí', no: 'No', abstain: 'Abstención',
  call: 'Llamada', message: 'Mensaje', visit: 'Visita', meeting: 'Reunión', other: 'Otro',
  triage: 'Clasificación inicial', virtual: 'En línea', in_person: 'Presencial', task: 'Tarea', agreement: 'Acuerdo',
  core: 'Perfil 360', processes: 'Procesos', cellular: 'Sistema Celular', doors: '9 Puertas', board: 'Junta Directiva', ministries: 'Ministerios',
  speaker_mapping_corrected: 'Identificación de participante corregida', transcript_text_corrected: 'Transcripción corregida', manual: 'Registro manual',
  healthy: 'Íntegro', attention_required: 'Requiere revisión',
  contactado: 'Contactado', visitado: 'Visitado', en_proceso: 'En proceso', graduado: 'Graduado', inactivo: 'Inactivo',
  familiar: 'Familiar', amigo: 'Amigo', conocido: 'Conocido', vecino: 'Vecino',
  assessment: 'Identificación de dones',
  excelente: 'Meta alcanzada', bien: 'En ritmo', recien_iniciado: 'Recién iniciado', meta_baja: 'Requiere acompañamiento', sin_personas: 'Sin personas asignadas',
  created_by: 'Creado por', created_at: 'Fecha de creación', updated_at: 'Última actualización', processed_at: 'Fecha de procesamiento',
  cash: 'Efectivo', modified_cash: 'Efectivo modificado', accrual: 'Devengado', asset: 'Activo', liability: 'Pasivo', net_assets: 'Activos netos', revenue: 'Ingreso', expense: 'Gasto',
  unrestricted: 'Sin restricción', donor_restricted: 'Restricción del donante', board_designated: 'Designado por Junta', posted: 'Contabilizado', submitted: 'Enviado a revisión', reviewed: 'Revisado', payment_pending_posting: 'Pago pendiente de contabilizar', pending_reconciliation: 'Pendiente de conciliación', reconciled: 'Conciliado', balanced: 'Cuadrado', needs_review: 'Requiere revisión',
  person_id: 'Perfil 360', responsible_person_id: 'Responsable', meeting_id: 'Reunión', source_id: 'Registro de origen', source_type: 'Tipo de origen',
  external_processing_acknowledged: 'Procesamiento externo confirmado', transcription_status: 'Estado de transcripción',
  active_members: 'Miembros activos', average_attendance: 'Promedio de asistencia', has_leader_in_training: 'Líder en formación', has_host: 'Anfitrión asignado', open_followups: 'Seguimientos abiertos', open_needs: 'Necesidades abiertas',
});

const WEEK_LABELS = Object.freeze(Object.fromEntries(Array.from({ length: 7 }, (_, index) => [`week_${index + 1}`, `Semana ${index + 1}`])));
const LABELS = Object.freeze({ ...COMMON_LABELS, ...WEEK_LABELS });
const DEFAULT_FALLBACK = 'Sin información';

const titleCase = (value) => value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();

export const displayLabel = (value, fallback = DEFAULT_FALLBACK) => {
  if (value === null || value === undefined || value === '') return fallback;
  const raw = String(value).trim();
  const key = raw.toLowerCase().replaceAll(' ', '_').replaceAll('-', '_');
  if (LABELS[key]) return LABELS[key];
  const doorMatch = key.match(/^door_(\d+)$/);
  if (doorMatch) return `Puerta ${doorMatch[1]}`;
  const speakerMatch = key.match(/^speaker_?(\d+)$/);
  if (speakerMatch) return `Participante ${Number(speakerMatch[1]) + 1}`;
  if (!raw.includes('_') && !raw.includes('-')) return fallback !== DEFAULT_FALLBACK ? fallback : raw;
  if (fallback !== DEFAULT_FALLBACK) return fallback;
  return raw.split(/[_-]+/).filter(Boolean).map(titleCase).join(' ');
};

export const processLabel = (processKey) => displayLabel(processKey, 'Proceso');
export const stageLabel = (stageKey) => displayLabel(stageKey, 'Etapa sin definir');

export const processStageLabel = (value) => {
  if (!value) return 'Etapa sin definir';
  const [processKey, stageKey] = String(value).split(':');
  if (!stageKey) return stageLabel(processKey);
  return `${processLabel(processKey)} · ${stageLabel(stageKey)}`;
};

export const translateTechnicalText = (value) => {
  if (Array.isArray(value)) {
    const messages = value.map((item) => translateTechnicalText(item?.msg || item?.message || item?.detail || item)).filter(Boolean);
    return messages.join(' · ') || 'No se pudo completar la solicitud.';
  }
  if (value && typeof value === 'object') {
    return translateTechnicalText(value.message || value.msg || value.detail || 'No se pudo completar la solicitud.');
  }
  if (!value || typeof value !== 'string') return value;
  const exact = displayLabel(value, value);
  if (exact !== value) return exact;
  return value
    .replace(/\bSLA\b/gi, 'tiempo de seguimiento')
    .replace(/\bDashboard\b/gi, 'Panel')
    .replace(/\bHousehold\b/gi, 'Hogar')
    .replace(/\bPipeline\b/gi, 'recorrido de acompañamiento')
    .replace(/\bCAP\b/g, 'Encuentra tu lugar para servir')
    .replace(/\bperson_id\b/gi, 'Perfil 360')
    .replace(/\btranscript\b/gi, 'transcripción')
    .replace(/\bstatus\b/gi, 'estado')
    .replace(/\brole\b/gi, 'función')
    .replace(/\bmeeting\b/gi, 'reunión')
    .replace(/\bworkflow\b/gi, 'flujo de acompañamiento')
    .replace(/[a-z]+(?:_[a-z0-9]+)+/gi, (token) => displayLabel(token));
};

export const roleLabel = (value) => displayLabel(value, 'Función ministerial');

export const meetingModalityLabel = (value) => displayLabel(value, 'Modalidad por confirmar');
export const priorityLabel = (value) => displayLabel(value, 'Prioridad normal');
export const statusLabel = (value) => displayLabel(value, 'Sin estado');
export const minuteTypeLabel = (value) => value === 'manual' ? 'Minuta manual' : displayLabel(value, 'Minuta');
export const speakerLabel = (value) => displayLabel(value, 'Participante');