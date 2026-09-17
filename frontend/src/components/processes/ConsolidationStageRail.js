import React from 'react';
import { Check, Circle, LockKeyhole, Minus } from 'lucide-react';

const statusIcon = {
  completed: Check,
  skipped: Minus,
  locked: LockKeyhole,
  open: Circle,
  in_progress: Circle,
};

export const ConsolidationStageRail = ({ stages, currentStageKey }) => (
  <section className="border border-slate-200 bg-white p-4 sm:overflow-x-auto" data-testid="consolidation-stage-rail">
    <div className="grid grid-cols-2 items-start gap-2 sm:flex sm:min-w-max">{stages.map((stage, index) => {
      const Icon = statusIcon[stage.status] || Circle;
      const current = stage.stage_key === currentStageKey;
      return <React.Fragment key={stage.stage_key}><div className={`text-center sm:w-28 ${current ? 'text-slate-950' : 'text-slate-500'}`} data-testid={`stage-rail-${stage.stage_key}`}><div className={`mx-auto flex h-9 w-9 items-center justify-center border ${stage.status === 'completed' ? 'border-emerald-600 bg-emerald-600 text-white' : current ? 'border-amber-500 bg-amber-50 text-amber-700' : 'border-slate-200 bg-white'}`}><Icon className="h-4 w-4" /></div><b className="mt-2 block text-xs">{stage.stage_name}</b><span className="text-[10px] uppercase">{stage.status === 'skipped' ? 'No aplica' : stage.status === 'completed' ? 'Completada' : current ? 'Actual' : 'Pendiente'}</span></div>{index < stages.length - 1 && <div className={`mt-4 hidden h-px w-6 sm:block ${stage.status === 'completed' || stage.status === 'skipped' ? 'bg-emerald-400' : 'bg-slate-200'}`} />}</React.Fragment>;
    })}</div>
  </section>
);