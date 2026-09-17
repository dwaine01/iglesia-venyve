import React, { useState } from 'react';
import axios from 'axios';
import { AlertTriangle, Check, ShieldCheck, X } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { hasCapability } from '../../lib/accessControl';

const stateMeta = { met: [Check, 'Cumplido', 'text-emerald-700 bg-emerald-50 border-emerald-200'], pending: [AlertTriangle, 'Pendiente', 'text-amber-700 bg-amber-50 border-amber-200'], not_met: [X, 'No cumplido', 'text-red-700 bg-red-50 border-red-200'] };

export const EligibilityPanel = ({ eligibility, frontGroupId, onUpdated }) => {
  const { API, getAuthHeaders, user } = useAuth();
  const [observations, setObservations] = useState('');
  const [busy, setBusy] = useState('');
  const canPromote = hasCapability(user, 'leadership.promote');
  const act = async (key, request) => { setBusy(key); try { await request(); toast.success('Evaluación actualizada'); await onUpdated(); } catch (error) { toast.error(typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : error?.response?.data?.detail?.message || 'No se pudo completar la acción'); } finally { setBusy(''); } };
  if (!eligibility) return <div className="border border-dashed p-8 text-center text-sm text-slate-500">Seleccione una Persona y Grupo Frontal para evaluar.</div>;
  return <section className="space-y-4" data-testid="leadership-eligibility-panel"><div className={`border p-4 ${eligibility.eligible ? 'border-emerald-300 bg-emerald-50' : 'border-amber-300 bg-amber-50'}`}><b className="flex items-center gap-2"><ShieldCheck className="h-5 w-5" />{eligibility.eligible ? 'Elegible para liderazgo' : `${eligibility.blocking_count} requisito(s) pendiente(s)`}</b><p className="mt-1 text-xs">La elegibilidad nunca promueve automáticamente.</p></div><div className="space-y-2">{eligibility.requirements.map((item) => { const [Icon, label, classes] = stateMeta[item.status]; return <article key={item.requirement_id} className={`border p-3 ${classes}`} data-testid={`leadership-requirement-status-${item.requirement_id}`}><div className="flex items-start justify-between gap-3"><div><b className="flex items-center gap-2 text-sm"><Icon className="h-4 w-4" />{item.name}</b><p className="mt-1 text-xs opacity-80">{item.description}</p></div><span className="text-xs font-semibold">{label}</span></div>{item.source_type === 'manual' && canPromote && <Select value={item.status} onValueChange={(status) => act(`manual-${item.requirement_id}`, () => axios.put(`${API}/api/leadership/candidates/${eligibility.person.person_id}/requirements/${item.requirement_id}`, { front_group_id: frontGroupId || null, status, notes: 'Evaluación registrada desde ficha de liderazgo' }, getAuthHeaders()))}><SelectTrigger className="mt-3 bg-white" data-testid={`manual-requirement-${item.requirement_id}`}><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="met">Cumplido</SelectItem><SelectItem value="pending">Pendiente</SelectItem><SelectItem value="not_met">No cumplido</SelectItem></SelectContent></Select>}</article>; })}</div>{canPromote && <div className="space-y-3 border-t pt-4"><Input value={observations} onChange={(event) => setObservations(event.target.value)} placeholder="Observaciones obligatorias de la autoridad" data-testid="leadership-promotion-observations-input" /><Button disabled={!eligibility.eligible || observations.trim().length < 2 || Boolean(busy)} onClick={() => act('promote', () => axios.post(`${API}/api/leadership/candidates/${eligibility.person.person_id}/promote`, { front_group_id: frontGroupId || null, observations }, getAuthHeaders()))} className="w-full bg-emerald-700 text-white hover:bg-emerald-800" data-testid="leadership-promote-button"><ShieldCheck className="h-4 w-4" />Aprobar promoción a Líder</Button></div>}</section>;
};