import React from 'react';
import { Badge } from '../ui/badge';
import { statusLabel } from '../../lib/displayLabels';

const styles = { active: 'border-emerald-200 bg-emerald-50 text-emerald-800', completed: 'border-blue-200 bg-blue-50 text-blue-800', planned: 'border-slate-200 bg-slate-50 text-slate-700', paused: 'border-amber-200 bg-amber-50 text-amber-800', cancelled: 'border-rose-200 bg-rose-50 text-rose-800', open: 'border-cyan-200 bg-cyan-50 text-cyan-800', in_progress: 'border-amber-200 bg-amber-50 text-amber-800', locked: 'border-slate-200 bg-slate-50 text-slate-500' };

export const ProcessStatus = ({ value, testId }) => <Badge variant="outline" className={styles[value] || 'border-slate-200 bg-white text-slate-700'} data-testid={testId}>{statusLabel(value)}</Badge>;

export const SlaPill = ({ dueAt }) => {
  if (!dueAt) return <Badge variant="outline" className="border-slate-200 text-slate-500">Sin vencimiento</Badge>;
  const hours = (new Date(dueAt).getTime() - Date.now()) / 3600000;
  const tone = hours < 0 ? 'border-rose-200 bg-rose-50 text-rose-800' : hours <= 48 ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800';
  const label = hours < 0 ? `Seguimiento vencido · ${Math.ceil(Math.abs(hours) / 24)} días` : hours <= 48 ? `Próximo a vencer · ${Math.max(1, Math.ceil(hours))} h` : `A tiempo · ${Math.ceil(hours / 24)} días`;
  return <Badge variant="outline" className={tone}>{label}</Badge>;
};