import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate } from 'react-router-dom';
import { FileText, Presentation } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';

/** «Reporte para la pastora»: elegir invasión y día y abrir el Modo Presentar
 * desde la plataforma (sin pegar enlaces). Solo aparece si el usuario puede
 * ver el reporte completo de alguna invasión (el backend decide). */
export function PresentReportLauncher({ variant = 'card', campaignId = null }) {
  const { API, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState(null);
  const [chosen, setChosen] = useState('');
  const [day, setDay] = useState(1);
  useEffect(() => {
    axios.get(`${API}/api/invasions/report-settings/presentable`, getAuthHeaders()).then((response) => {
      const list = response.data.items || [];
      setItems(list);
      const first = list.find((item) => item.campaign_id === campaignId) || list[0];
      if (first) { setChosen(first.campaign_id); setDay(first.suggested_day || 1); }
    }).catch(() => setItems([]));
  }, [API, getAuthHeaders, campaignId]);
  if (!items || items.length === 0) {
    return variant === 'page' && items ? <p className="rounded-xl border border-dashed border-slate-300 bg-white p-5 text-base text-slate-600" data-testid="present-launcher-empty">Todavía no hay invasiones con reporte para presentar, o tu cuenta no tiene acceso al reporte completo.</p> : null;
  }
  const campaign = items.find((item) => item.campaign_id === chosen) || items[0];
  const pick = (value) => { const next = items.find((item) => item.campaign_id === value); setChosen(value); setDay(next?.suggested_day || 1); };
  const query = day ? `?dia=${day}` : '?dia=0';
  return (
    <section className="relative overflow-hidden rounded-2xl border-2 border-[#C8A951]/50 bg-gradient-to-r from-[#14213D] via-[#1B2A4A] to-[#0E5B5A] p-4 text-white shadow-xl sm:p-5" data-testid="present-launcher">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#C8A951] to-[#E2CF8A]"><Presentation className="h-7 w-7 text-[#1B2A4A]" /></div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold uppercase tracking-widest text-[#E7D28D]">Reporte para la pastora</p>
          <h3 className="text-xl font-bold leading-tight" style={{ fontFamily: 'Spectral, serif' }}>{variant === 'card' ? 'Reporte de la última invasión' : 'Presentar el reporte en pantalla grande'}</h3>
          <p className="text-sm text-white/75">Elige la invasión y el día; se abre el Modo Presentar con los datos en vivo.</p>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,2fr)_minmax(0,1.2fr)]">
        <label className="block"><span className="text-sm font-semibold text-white/85">Invasión</span>
          <select value={campaign.campaign_id} onChange={(event) => pick(event.target.value)} className="mt-1 h-12 w-full rounded-lg border border-white/30 bg-white px-3 text-base font-semibold text-[#101D36]" data-testid="present-launcher-campaign">
            {items.map((item) => <option key={item.campaign_id} value={item.campaign_id}>{item.name}{item.state === 'active' ? ' (en curso)' : ''}</option>)}
          </select></label>
        <label className="block"><span className="text-sm font-semibold text-white/85">Día</span>
          <select value={day} onChange={(event) => setDay(parseInt(event.target.value, 10))} className="mt-1 h-12 w-full rounded-lg border border-white/30 bg-white px-3 text-base font-semibold text-[#101D36]" data-testid="present-launcher-day">
            {campaign.days.map((item) => <option key={item.day} value={item.index}>Día {item.index} · {item.label}</option>)}
            <option value={0}>Toda la semana (acumulado)</option>
          </select></label>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <button type="button" onClick={() => navigate(`/invasiones/${campaign.campaign_id}/reporte/presentar${query}`)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-[#C8A951] px-4 text-base font-bold text-[#14213D] hover:bg-[#E2CF8A]" data-testid="present-launcher-open"><Presentation className="h-5 w-5" />Presentar reporte</button>
        <Link to={`/invasiones/${campaign.campaign_id}/reporte${query}`} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-white/40 px-4 text-base font-semibold text-white hover:bg-white/10" data-testid="present-launcher-report"><FileText className="h-5 w-5" />Ver reporte en una página</Link>
      </div>
    </section>
  );
}

export default function PresentReportLauncherPage() {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-4 p-4 sm:p-6" data-testid="present-launcher-page">
      <PresentReportLauncher variant="page" />
    </div>
  );
}
