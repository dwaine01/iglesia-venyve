import React from 'react';
import { Award, BadgeCheck, BookHeart, Route, UserRoundCheck } from 'lucide-react';
import { processStageLabel } from '../lib/displayLabels';

// «Mentor actual» = asignación de Consolidación; quien la contactó va aparte.
const mentorValue = (status, contact) => {
  if (status?.mentor_assignment?.mentor_person_id) return contact?.current_mentor?.name || 'Asignado';
  const by = contact?.first_contact?.mentor_name;
  return by ? `Pendiente de asignar · Contactado por ${by}` : 'Pendiente';
};

const blocks = (status, contact) => [
  [BadgeCheck, 'Membresía', status?.membership?.status === 'active' ? `Miembro · ${status.membership.member_number}` : 'No activa', 'text-emerald-700'],
  [Route, 'Consolidación', status?.consolidation ? `${status.consolidation.consolidation_status === 'completed' ? 'Completada' : status.consolidation.consolidation_status === 'graduation_pending' ? 'Pendiente de graduación' : 'En progreso'} · ${processStageLabel(status.consolidation.current_stage_key)}` : 'Sin proceso', 'text-amber-700'],
  [UserRoundCheck, 'Mentor actual', mentorValue(status, contact), 'text-blue-700'],
  [BookHeart, 'Discipulado', status?.discipleship ? `${status.discipleship.status === 'completed' ? 'Completado' : 'En progreso'} · ${processStageLabel(status.discipleship.current_stage_key)}` : 'Pendiente', 'text-teal-700'],
  [Award, 'Liderazgo', status?.leadership?.status === 'leader' ? 'Líder ministerial' : 'No promovido', 'text-rose-700'],
];

export const PersonJourneyStatusStrip = ({ status, contact }) => {
  if (!status) return null;
  return <section className="grid gap-2 border border-slate-200 bg-white p-3 sm:grid-cols-2 xl:grid-cols-5" data-testid="person-journey-status-strip">{blocks(status, contact).map(([Icon, label, value, color]) => <article key={label} className="border border-slate-100 p-3"><Icon className={`h-4 w-4 ${color}`} /><span className="mt-3 block text-[10px] font-semibold uppercase text-slate-500">{label}</span><b className="mt-1 block text-xs text-slate-900" data-testid={`journey-status-${label.toLowerCase().replace(' ', '-')}`}>{value}</b></article>)}</section>;
};