import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';
import { CheckCircle2, Hand, Loader2, MapPin, Navigation, Siren } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { directionsUrl } from '../lib/geolocation';

const STATUS = {
  open: { label: 'Sin atender', className: 'border-[#b91c1c] bg-[#fef2f2] text-[#7f1d1d]' },
  acknowledged: { label: 'Atendiendo', className: 'border-amber-300 bg-amber-50 text-amber-900' },
  resolved: { label: 'Resuelto', className: 'border-[#bcd8c4] bg-[#eef5f0] text-[#2f6e47]' },
};
const time = (iso) => (iso ? new Date(iso).toLocaleTimeString('es', { hour: 'numeric', minute: '2-digit' }) : '');

/** Alertas de ayuda de una invasión: solo responsables (el backend responde 403 al resto). */
export default function InvasionHelpPage() {
  const { campaignId } = useParams();
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const load = useCallback(() => {
    axios.get(`${API}/api/invasions/${campaignId}/help`, getAuthHeaders()).then((response) => { setData(response.data); setError(''); })
      .catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudieron cargar las alertas')));
  }, [API, getAuthHeaders, campaignId]);
  useEffect(() => { load(); const timer = setInterval(load, 15000); return () => clearInterval(timer); }, [load]);
  const update = async (alert, status) => {
    setBusy(`${alert.alert_id}-${status}`);
    try { await axios.put(`${API}/api/invasions/${campaignId}/help/${alert.alert_id}`, { status }, getAuthHeaders()); toast.success(status === 'resolved' ? 'Marcada como resuelta' : 'Avisamos que la estás atendiendo'); load(); }
    catch (requestError) { toast.error(apiErrorMessage(requestError, 'No se pudo actualizar')); } finally { setBusy(''); }
  };
  if (error) return <div className="p-4 sm:p-6"><p className="rounded-xl border border-red-200 bg-red-50 p-4 text-base text-red-800" data-testid="help-error">{error}</p></div>;
  if (!data) return <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
  return (
    <div className="mx-auto w-full max-w-3xl space-y-4 p-4 sm:p-6" data-testid="help-page">
      <header>
        <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.2em] text-[#b91c1c]"><Siren className="h-4 w-4" />Alertas de ayuda</p>
        <h1 className="font-['Spectral'] text-2xl font-semibold text-[#101D36]">{data.name}</h1>
        <p className="text-sm text-slate-600">{data.open ? `${data.open} sin resolver` : 'Todas resueltas'} · se actualiza cada 15 s</p>
      </header>
      {data.items.length === 0 ? <p className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center text-base text-slate-500">Aún no hay alertas en esta invasión.</p> : (
        <ul className="space-y-3">
          {data.items.map((alert) => {
            const status = STATUS[alert.status] || STATUS.open;
            return (
              <li key={alert.alert_id} className={`rounded-2xl border-2 bg-white p-4 ${alert.status === 'open' ? 'border-[#b91c1c]' : 'border-[#E8E5DE]'}`} data-testid={`help-alert-${alert.alert_id}`}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0"><p className="text-lg font-semibold text-[#101D36]">{alert.reason_label}</p><p className="text-[15px] text-slate-700">{alert.person_name} · {time(alert.created_at)}</p></div>
                  <span className={`shrink-0 rounded-full border px-3 py-1 text-xs font-semibold ${status.className}`}>{status.label}</span>
                </div>
                {alert.note && <p className="mt-2 rounded-lg bg-[#FBFAF7] p-2 text-[15px] text-[#101D36]">{alert.note}</p>}
                <p className="mt-2 flex items-center gap-1 text-sm text-slate-600"><MapPin className="h-4 w-4" />{alert.latitude != null ? `Ubicación compartida${alert.accuracy_m ? ` (±${Math.round(alert.accuracy_m)} m)` : ''}` : 'Sin ubicación'}</p>
                {(alert.acknowledged_by_name || alert.resolved_by_name) && <p className="text-xs text-slate-500">{alert.acknowledged_by_name ? `Atendió: ${alert.acknowledged_by_name}` : ''}{alert.response_minutes != null ? ` · respuesta en ${alert.response_minutes} min` : ''}{alert.resolved_by_name ? ` · resolvió: ${alert.resolved_by_name}` : ''}</p>}
                <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
                  {alert.latitude != null && <a href={directionsUrl(alert.latitude, alert.longitude)} target="_blank" rel="noreferrer" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-[#D9D4C7] px-3 text-[15px] font-semibold text-[#101D36]" data-testid={`help-directions-${alert.alert_id}`}><Navigation className="h-5 w-5" />Cómo llegar</a>}
                  {alert.status === 'open' && <button type="button" onClick={() => update(alert, 'acknowledged')} disabled={Boolean(busy)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-amber-600 px-3 text-[15px] font-semibold text-white" data-testid={`help-ack-${alert.alert_id}`}>{busy === `${alert.alert_id}-acknowledged` ? <Loader2 className="h-5 w-5 animate-spin" /> : <Hand className="h-5 w-5" />}Ya atendí</button>}
                  {alert.status !== 'resolved' && <button type="button" onClick={() => update(alert, 'resolved')} disabled={Boolean(busy)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-[#2f6e47] px-3 text-[15px] font-semibold text-white" data-testid={`help-resolve-${alert.alert_id}`}>{busy === `${alert.alert_id}-resolved` ? <Loader2 className="h-5 w-5 animate-spin" /> : <CheckCircle2 className="h-5 w-5" />}Resuelto</button>}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
