export const careStatusLabel = {
  detected: 'Detectado', assigned: 'Asignado', contacted: 'Contactado',
  follow_up: 'En seguimiento', resolved: 'Resuelto', closed: 'Cerrado', escalated: 'Escalado',
};

export const caseTypeLabel = {
  first_conversion: 'Primera conversión', reconciliation: 'Reconciliación', restoration: 'Restauración',
  return: 'Regreso', crisis: 'Crisis', bereavement: 'Duelo', family: 'Familia', health: 'Salud',
  visitation: 'Visitación', pastoral_care: 'Cuidado pastoral', other: 'Otro',
};

export const alertLabel = {
  unassigned_24h: '24h sin asignar', uncontacted_72h: '72h sin contacto',
  next_step_due: 'Próximo paso vencido', urgent_case: 'Caso urgente',
};

export const priorityLabel = { low: 'Baja', medium: 'Media', high: 'Alta', urgent: 'Urgente' };

export const dateTime = (value) => value ? new Intl.DateTimeFormat('es-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'Sin fecha';

export const statusTone = (status) => ({
  detected: 'border-blue-200 bg-blue-50 text-blue-800', assigned: 'border-sky-200 bg-sky-50 text-sky-800',
  contacted: 'border-emerald-200 bg-emerald-50 text-emerald-800', follow_up: 'border-amber-200 bg-amber-50 text-amber-800',
  escalated: 'border-red-200 bg-red-50 text-red-800', resolved: 'border-slate-200 bg-slate-50 text-slate-700',
  closed: 'border-slate-200 bg-slate-100 text-slate-600',
}[status] || 'border-slate-200 bg-slate-50 text-slate-700');