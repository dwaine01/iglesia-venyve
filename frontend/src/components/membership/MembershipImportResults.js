import React from 'react';
import { AlertTriangle, CheckCircle2, Home, XCircle } from 'lucide-react';

const statusMeta = {
  ready: { label: 'Listo', icon: CheckCircle2, className: 'border-emerald-300 bg-emerald-50 text-emerald-900' },
  review: { label: 'Revisar', icon: AlertTriangle, className: 'border-amber-300 bg-amber-50 text-amber-950' },
  error: { label: 'Error', icon: XCircle, className: 'border-red-300 bg-red-50 text-red-900' },
};

const reasonLabel = (value) => value.replaceAll('_', ' ');

export const MembershipImportResults = ({ report }) => {
  if (!report) return null;
  const { summary, rows, households } = report;
  return <section className="space-y-5" data-testid="membership-import-results">
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {[['total', 'Filas'], ['ready', 'Listo'], ['review', 'Revisar'], ['error', 'Error'], ['households', 'Hogares sugeridos']].map(([key, label]) => <div key={key} className="border bg-white p-4"><span className="text-xs font-bold uppercase text-slate-500">{label}</span><strong className="mt-1 block text-3xl text-slate-950" data-testid={`membership-import-summary-${key}`}>{summary[key] || 0}</strong></div>)}
    </div>
    {households.length > 0 && <div className="border border-blue-200 bg-blue-50 p-4" data-testid="membership-import-households"><h3 className="flex items-center gap-2 font-semibold text-blue-950"><Home className="h-4 w-4" />Agrupaciones sugeridas, no fusionadas</h3><div className="mt-3 flex flex-wrap gap-2">{households.map((item) => <span key={item.group_id} className="border border-blue-300 bg-white px-2 py-1 text-xs text-blue-900" data-testid={`membership-import-household-${item.group_id}`}>{item.group_id} · {item.member_count} personas</span>)}</div></div>}
    <div className="overflow-hidden border bg-white"><div className="border-b px-4 py-3"><h3 className="font-['Spectral'] text-xl font-semibold">Detalle del análisis</h3></div><div className="max-h-[560px] overflow-auto"><table className="w-full min-w-[920px] text-left text-sm" data-testid="membership-import-results-table"><thead className="sticky top-0 bg-slate-950 text-white"><tr><th className="p-3">Fila</th><th className="p-3">Estado</th><th className="p-3">Persona</th><th className="p-3">Contacto</th><th className="p-3">Dirección</th><th className="p-3">Hallazgos</th></tr></thead><tbody className="divide-y">{rows.map((row) => { const meta = statusMeta[row.status]; const Icon = meta.icon; const findings = [...row.errors, ...row.review_reasons, ...row.duplicate_matches]; return <tr key={row.row_number} data-testid={`membership-import-row-${row.row_number}`}><td className="p-3 font-mono">{row.row_number}</td><td className="p-3"><span className={`inline-flex items-center gap-1 border px-2 py-1 text-xs font-semibold ${meta.className}`}><Icon className="h-3.5 w-3.5" />{meta.label}</span></td><td className="p-3"><b>{row.first_name} {row.last_name}</b><small className="block text-slate-500">{row.member_number || 'Número nuevo automático'}{row.household_group ? ` · ${row.household_group}` : ''}</small></td><td className="p-3">{row.email || '—'}<small className="block text-slate-500">{row.phone || '—'}</small></td><td className="max-w-xs p-3">{row.address?.linea1 || 'Sin dirección'}<small className="block text-slate-500">{[row.address?.city, row.address?.state, row.address?.codigo_postal].filter(Boolean).join(', ')}</small></td><td className="max-w-sm p-3 text-xs">{findings.length ? findings.map(reasonLabel).join(' · ') : 'Sin observaciones'}</td></tr>; })}</tbody></table></div></div>
  </section>;
};