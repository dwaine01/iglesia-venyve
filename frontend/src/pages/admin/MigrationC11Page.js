import React, { useState } from 'react';
import axios from 'axios';
import { DatabaseBackup, Loader2, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { errorDetailText } from '../../lib/errorText';
import { Button } from '../../components/ui/button';

const SUMMARY_LABEL = {
  persons_with_multiple_accounts: 'Personas con más de una cuenta',
  accounts_without_person: 'Cuentas sin Persona',
  groups_leader_without_account: 'Grupos con líder sin cuenta',
  groups_multiple_active_leaders: 'Grupos con más de un líder activo',
  enrollments_missing_front_group: 'Expedientes de invasión sin Grupo Frontal',
  enrollments_auto_fixable: 'De esos, se pueden corregir automáticamente',
};

export default function MigrationC11Page() {
  const { API, getAuthHeaders } = useAuth();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);

  const diagnose = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/api/admin/migrations/c11?mode=diagnose`, getAuthHeaders());
      setReport(data);
    } catch (error) { toast.error(errorDetailText(error, 'No se pudo ejecutar el diagnóstico')); }
    finally { setLoading(false); }
  };

  const apply = async () => {
    if (!window.confirm('Esto corrige SOLO los expedientes donde el mentor tiene una única rama de supervisión activa. Es seguro e idempotente. ¿Continuar?')) return;
    setApplying(true);
    try {
      const { data } = await axios.get(`${API}/api/admin/migrations/c11?mode=apply`, getAuthHeaders());
      toast.success(`${data.enrollments_fixed} expediente(s) corregido(s)`);
      await diagnose();
    } catch (error) { toast.error(errorDetailText(error, 'No se pudo aplicar la corrección')); }
    finally { setApplying(false); }
  };

  return (
    <div className="space-y-6 p-4 sm:p-6" data-testid="migration-c11-page">
      <header className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#132443]/10 text-[#132443]"><DatabaseBackup className="h-5 w-5" /></div>
        <div>
          <h1 className="font-['Spectral'] text-2xl font-semibold text-[#101D36] sm:text-3xl">Migración de Datos (C11)</h1>
          <p className="text-sm text-slate-500">Diagnóstico no destructivo. Nunca ejecute "Aplicar" contra producción sin revisar antes el diagnóstico.</p>
        </div>
      </header>

      <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800" data-testid="migration-c11-warning">
        <ShieldAlert className="h-4 w-4" /> "Aplicar" solo corrige el caso seguro: expedientes de invasión sin Grupo Frontal cuando el mentor tiene una única rama activa. El resto de hallazgos requiere revisión pastoral manual.
      </div>

      <div className="flex gap-2">
        <Button onClick={diagnose} disabled={loading} data-testid="migration-c11-diagnose-button">{loading && <Loader2 className="h-4 w-4 animate-spin" />}Ejecutar diagnóstico</Button>
        {report && report.summary.enrollments_auto_fixable > 0 && (
          <Button variant="outline" onClick={apply} disabled={applying} className="border-emerald-300 text-emerald-700 hover:bg-emerald-50" data-testid="migration-c11-apply-button">
            {applying && <Loader2 className="h-4 w-4 animate-spin" />}Aplicar corrección segura ({report.summary.enrollments_auto_fixable})
          </Button>
        )}
      </div>

      {report && (
        <div className="space-y-4" data-testid="migration-c11-report">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {Object.entries(report.summary).map(([key, value]) => (
              <div key={key} className="rounded-xl border border-[#E8E5DE] bg-white p-3" data-testid={`migration-c11-summary-${key}`}>
                <div className="text-2xl font-semibold text-[#101D36]">{value}</div>
                <div className="text-xs text-slate-500">{SUMMARY_LABEL[key] || key}</div>
              </div>
            ))}
          </div>

          {report.enrollments_missing_front_group.length > 0 && (
            <div>
              <h3 className="mb-2 font-['Spectral'] text-lg font-semibold text-[#101D36]">Expedientes sin Grupo Frontal</h3>
              <div className="space-y-2" data-testid="migration-c11-missing-front-group-list">
                {report.enrollments_missing_front_group.map((item) => (
                  <div key={item.enrollment_id} className="rounded-lg border border-[#E8E5DE] p-3 text-sm" data-testid={`migration-c11-row-${item.enrollment_id}`}>
                    <p className="text-slate-600">Mentor: {item.mentor_person_id || 'sin mentor'}</p>
                    <p className="text-xs text-slate-500">{item.proposed_front_group_id ? `Propuesta: asignar al grupo ${item.proposed_front_group_id}` : 'Sin propuesta automática (el mentor tiene más de una rama o ninguna)'}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
