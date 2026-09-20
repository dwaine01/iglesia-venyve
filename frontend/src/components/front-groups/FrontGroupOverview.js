import React from 'react';
import { Activity, GitBranch, Home, Route, UsersRound } from 'lucide-react';

const Metric = ({ icon: Icon, label, value, testId }) => <article className="border-r border-slate-200 px-4 py-5 last:border-r-0" data-testid={testId}><Icon className="h-4 w-4 text-amber-700" /><strong className="mt-4 block font-['Spectral'] text-3xl text-slate-950">{value || 0}</strong><span className="text-xs text-slate-500">{label}</span></article>;

export const FrontGroupOverview = ({ detail, report }) => {
  const metrics = report?.metrics;
  return <div className="space-y-6" data-testid="front-group-overview">
    <section className="grid border border-slate-200 bg-white sm:grid-cols-2 xl:grid-cols-5">
      <Metric icon={UsersRound} label="Personas en la rama" value={metrics?.people ?? detail.stats?.people_reached} testId="front-group-metric-people" />
      <Metric icon={Route} label="Consolidaciones activas" value={metrics?.consolidation?.active ?? detail.stats?.active_processes} testId="front-group-metric-consolidation" />
      <Metric icon={Activity} label="Operaciones 72" value={metrics?.op72?.active} testId="front-group-metric-op72" />
      <Metric icon={Home} label="Casas en invasión" value={metrics?.invasions?.targets} testId="front-group-metric-invasions" />
      <Metric icon={GitBranch} label="Grupos en subárbol" value={metrics?.groups ?? 1} testId="front-group-metric-branches" />
    </section>
    <section className="border border-slate-200 bg-white" data-testid="front-group-branch-report"><header className="border-b border-slate-200 px-5 py-4"><h3 className="font-['Spectral'] text-xl font-semibold">Resultados por rama directa</h3></header>{report?.branches?.length ? <div className="divide-y divide-slate-200">{report.branches.map((branch) => <div key={branch.front_group_id} className="grid gap-3 px-5 py-4 sm:grid-cols-[1fr_repeat(3,minmax(90px,auto))]" data-testid={`front-group-branch-metric-${branch.front_group_id}`}><div><b>{branch.name}</b><span className="block text-xs text-slate-500">{branch.metrics.groups} grupo(s)</span></div><span className="text-sm"><b className="block text-lg">{branch.metrics.people}</b>Personas</span><span className="text-sm"><b className="block text-lg">{branch.metrics.consolidation.active}</b>Consolidación</span><span className="text-sm"><b className="block text-lg">{branch.metrics.work.active}</b>Trabajo activo</span></div>)}</div> : <p className="p-8 text-center text-sm text-slate-500" data-testid="front-group-branch-report-empty">Esta rama todavía no tiene subramas activas.</p>}</section>
  </div>;
};