import React from 'react';
import { ArrowRight, Clock3, UserRoundCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { Button } from '../ui/button';

const entryLabels = { complete_cycle: 'Ciclo completo', direct_church: 'Iglesia', cell: 'Célula', visitor_followup: 'Seguimiento' };

export const ConsolidationJourneyCard = ({ item }) => {
  const navigate = useNavigate();
  return <article className="border border-slate-200 bg-white p-4 shadow-sm" data-testid={`consolidation-card-${item.enrollment_id}`}>
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-mono text-[10px] font-semibold uppercase text-amber-700">{entryLabels[item.entry_mode] || 'Histórico'}</p><h3 className="font-['Spectral'] text-xl font-semibold text-slate-950">{item.person?.name}</h3><p className="text-xs text-slate-500">{item.person?.person_number}</p></div><span className={`border px-2 py-1 text-xs font-semibold ${item.status === 'completed' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-blue-200 bg-blue-50 text-blue-800'}`}>{item.status === 'completed' ? 'Completado' : item.consolidation_status === 'followup_pending' ? 'Seguimiento' : 'En progreso'}</span></div>
    <div className="mt-4 grid grid-cols-2 gap-3 border-y border-slate-100 py-3 text-xs"><div><Clock3 className="mb-1 h-4 w-4 text-slate-400" /><span className="text-slate-500">Etapa actual</span><b className="block text-slate-800">{item.current_stage?.stage_name || item.current_stage_key}</b></div><div><UserRoundCheck className="mb-1 h-4 w-4 text-slate-400" /><span className="text-slate-500">Mentor</span><b className="block text-slate-800">{item.responsible?.name || 'Pendiente'}</b></div></div>
    <div className="mt-3 flex items-center justify-between gap-3"><div className="h-1.5 flex-1 bg-slate-100"><div className="h-full bg-amber-500" style={{ width: `${item.progress_pct || 0}%` }} /></div><span className="text-xs font-semibold text-slate-600">{item.progress_pct || 0}%</span><Button size="sm" variant="ghost" onClick={() => navigate(`/procesos/consolidacion/${item.enrollment_id}`)} data-testid={`open-consolidation-${item.enrollment_id}`}><ArrowRight className="h-4 w-4" /><span className="sr-only">Abrir expediente</span></Button></div>
  </article>;
};