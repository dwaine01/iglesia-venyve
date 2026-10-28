import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Archive, ArchiveRestore, FlaskConical, Loader2, Undo2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';

/** Datos de prueba (auditoría 8/10): inventario de solo lectura, marca reversible y archivo de invasiones. Nada se borra. */
export default function TestDataPage() {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState('');
  const [legacy, setLegacy] = useState(null);
  useEffect(() => { axios.get(`${API}/api/processes/legacy-auto/report`, getAuthHeaders()).then((response) => setLegacy(response.data)).catch(() => setLegacy(null)); }, [API, getAuthHeaders]);
  const load = useCallback(() => axios.get(`${API}/api/test-data/inventory`, getAuthHeaders()).then((response) => setData(response.data))
    .catch((error) => toast.error(apiErrorMessage(error, 'No se pudo cargar el inventario'))), [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);

  const mark = async (kind, id, isTest) => {
    setBusy(`${kind}:${id}`);
    try {
      const response = await axios.post(`${API}/api/test-data/mark`, { kind, ids: [id], is_test: isTest, reason: isTest ? 'Marcado como prueba desde Datos de prueba' : 'Marca de prueba quitada' }, getAuthHeaders());
      setData(response.data.inventory);
      toast.success(isTest ? 'Marcado como prueba: ya no cuenta en las cifras' : 'Marca quitada: vuelve a contar');
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo cambiar la marca')); } finally { setBusy(''); }
  };
  const archive = async (id, archived) => {
    setBusy(`archive:${id}`);
    try {
      await axios.post(`${API}/api/test-data/campaigns/${id}/archive`, { archived, reason: archived ? 'Invasión de prueba archivada' : 'Invasión desarchivada' }, getAuthHeaders());
      toast.success(archived ? 'Invasión archivada (se puede deshacer)' : 'Invasión desarchivada');
      load();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo archivar')); } finally { setBusy(''); }
  };

  if (!data) return <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
  const button = 'inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-lg border px-3 text-sm font-semibold disabled:opacity-50';
  return (
    <div className="mx-auto max-w-5xl space-y-5 p-4 sm:p-6" data-testid="test-data-page">
      {legacy && (
        <section className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950" data-testid="legacy-auto-report">
          <h2 className="font-semibold">Expedientes que el sistema creaba solo desde el Manual viejo</h2>
          <p>Creación automática: <b>{legacy.auto_migration_enabled ? 'ENCENDIDA' : 'apagada'}</b>{legacy.disabled_at ? ` desde ${legacy.disabled_at.slice(0, 16).replace('T', ' ')} (UTC)` : ''}. Solo lectura; lo ya creado no se borra.</p>
          <ul className="grid gap-1 sm:grid-cols-2">
            <li>Creados solos en total: <b>{legacy.total_auto_created}</b></li>
            <li>Personas distintas: <b>{legacy.distinct_people}</b> · recreadas: <b>{legacy.people_recreated}</b> (copias de más: {legacy.extra_copies})</li>
            <li>«Personas sin líder» hoy: <b>{legacy.people_without_leader_total}</b> · solo por un expediente del Manual viejo: <b>{legacy.people_without_leader_only_legacy}</b></li>
            {legacy.library && <li data-testid="legacy-library-unlinked">Libros entregados a personas: <b>{legacy.library.deliveries_to_people}</b> · todavía sin expediente unido (historial): <b>{legacy.library.without_enrollment}</b></li>}
            {legacy.graduation && <li data-testid="legacy-graduation-pending">Cerraron el Retiro con la regla anterior (sin graduación registrada): <b>{legacy.graduation.legacy_retreat_closed}</b></li>}
            <li>Creados después del apagado: <b>{legacy.created_after_disabled ?? '—'}</b> (debe quedar en 0)</li>
          </ul>
        </section>
      )}
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 font-['Spectral'] text-2xl font-semibold text-[#101D36]"><FlaskConical className="h-6 w-6 text-[#9A7A2F]" />Datos de prueba</h1>
        <p className="text-sm text-slate-600">{data.note} Las marcas y los archivos quedan en el historial.</p>
      </header>

      <section className="space-y-2 rounded-xl border border-[#E8E5DE] bg-white p-4">
        <h2 className="text-lg font-semibold text-[#101D36]">Invasiones ({data.counts.campaigns})</h2>
        {data.campaigns.length === 0 && <p className="text-sm text-slate-500">No hay invasiones con nombre de prueba.</p>}
        <ul className="divide-y">{data.campaigns.map((item) => (
          <li key={item.campaign_id} className="flex flex-wrap items-center justify-between gap-2 py-3" data-testid={`test-data-campaign-${item.campaign_id}`}>
            <span className="min-w-0"><span className="block font-semibold text-[#101D36]">{item.name}</span>
              <span className="block text-xs text-slate-500">{item.start_date || 'Sin fecha'} · {item.is_test ? 'Marcada como prueba' : item.reasons.join(', ')}{item.archived ? ' · Archivada' : ''}</span></span>
            <span className="flex flex-wrap gap-2">
              <button type="button" className={button} disabled={Boolean(busy)} onClick={() => mark('campaign', item.campaign_id, !item.is_test)}>{item.is_test ? <Undo2 className="h-4 w-4" /> : <FlaskConical className="h-4 w-4" />}{item.is_test ? 'Quitar marca' : 'Es de prueba'}</button>
              <button type="button" className={button} disabled={Boolean(busy)} onClick={() => archive(item.campaign_id, !item.archived)} data-testid="test-data-campaign-archive">{item.archived ? <ArchiveRestore className="h-4 w-4" /> : <Archive className="h-4 w-4" />}{item.archived ? 'Desarchivar' : 'Archivar'}</button>
            </span>
          </li>
        ))}</ul>
      </section>

      <section className="space-y-2 rounded-xl border border-[#E8E5DE] bg-white p-4">
        <h2 className="text-lg font-semibold text-[#101D36]">Personas ({data.counts.people} · {data.counts.people_marked} marcadas)</h2>
        <p className="text-xs text-slate-500">Candidatas por correo o nombre de prueba, o por venir de la demostración antigua. Revise cada una: marcar no borra ni desactiva la cuenta.</p>
        {data.people.length === 0 && <p className="text-sm text-slate-500">No hay personas candidatas.</p>}
        <ul className="divide-y">{data.people.map((item) => (
          <li key={item.person_id} className="flex flex-wrap items-center justify-between gap-2 py-3" data-testid={`test-data-person-${item.person_id}`}>
            <span className="min-w-0"><a href={`/personas/${item.person_id}`} className="block font-semibold text-[#101D36] underline-offset-2 hover:underline">{item.name}</a>
              <span className="block text-xs text-slate-500">{[item.person_number, ...item.reasons].filter(Boolean).join(' · ')}{item.is_archived ? ' · Archivada' : ''}</span></span>
            <button type="button" className={button} disabled={Boolean(busy)} onClick={() => mark('person', item.person_id, !item.is_test)} data-testid="test-data-person-mark">{item.is_test ? <Undo2 className="h-4 w-4" /> : <FlaskConical className="h-4 w-4" />}{item.is_test ? 'Quitar marca' : 'Es de prueba'}</button>
          </li>
        ))}</ul>
      </section>
      <p className="text-xs text-slate-500">Registros de visitantes marcados «Es una prueba» en la tableta: {data.visitor_registrations_marked}.</p>
      {data.finance_contributions && <p className="text-xs text-slate-500" data-testid="test-data-finance">Contribuciones de Finanzas a nombre de estas personas: {data.finance_contributions.count} (total ${((data.finance_contributions.amount_cents || 0) / 100).toFixed(2)}). Se revisan y corrigen desde Finanzas; aquí no se cambia nada.</p>}
    </div>
  );
}
