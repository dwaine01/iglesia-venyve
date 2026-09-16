import React from 'react';
import { CheckCircle2, Database, Link2, ShieldCheck, TriangleAlert } from 'lucide-react';
import { Card, CardContent } from '../ui/card';

const Metric = ({ testId, label, value, detail, icon: Icon, tone }) => (
  <Card className="border-[#E5E1D7] shadow-sm">
    <CardContent className="p-4 sm:p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase text-gray-500">{label}</p>
          <p className="mt-2 text-3xl font-bold text-[#101D36]" data-testid={testId}>{value}</p>
          <p className="mt-1 text-xs text-gray-500">{detail}</p>
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-md ${tone}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </CardContent>
  </Card>
);

export const CoreHealthCards = ({ integrity }) => {
  const issues = integrity?.issues || {};
  const openIssues = Object.values(issues).reduce((sum, value) => sum + (Number(value) || 0), 0);
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="core-health-metrics">
      <Metric testId="core-integrity-score" label="Integridad" value={`${integrity?.score ?? 0}%`} detail={integrity?.status === 'healthy' ? 'Núcleo consistente' : 'Revisión requerida'} icon={integrity?.status === 'healthy' ? CheckCircle2 : TriangleAlert} tone={integrity?.status === 'healthy' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'} />
      <Metric testId="core-person-count" label="Personas canónicas" value={integrity?.counts?.persons ?? 0} detail="Fuente humana única" icon={Database} tone="bg-[#F4EEDB] text-[#8A6D2F]" />
      <Metric testId="core-user-count" label="Cuentas enlazadas" value={integrity?.counts?.users ?? 0} detail={`${issues.users_without_person || 0} sin Perfil 360`} icon={Link2} tone="bg-cyan-50 text-cyan-700" />
      <Metric testId="core-open-issues-count" label="Alertas abiertas" value={openIssues} detail="Duplicados, huérfanos y acceso" icon={ShieldCheck} tone="bg-slate-100 text-slate-700" />
    </div>
  );
};