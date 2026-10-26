import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Bus, ExternalLink } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { CampaignDonationForm } from '../../components/campaign/CampaignDonationForm';
import { CampaignDonationHistory } from '../../components/campaign/CampaignDonationHistory';
import { CampaignSettingsPanel } from '../../components/campaign/CampaignSettingsPanel';
import { CampaignPresentationLinks } from '../../components/campaign/CampaignPresentationLinks';
import { CampaignMessagingPanel } from '../../components/campaign/CampaignMessagingPanel';
import { formatUsdCents } from '../../lib/campaignFormat';

export default function CampaignControlPage() {
  const { API, getAuthHeaders } = useAuth();
  const base = `${API}/api/campaigns/venycome`;
  const [settings, setSettings] = useState(null);
  const [summary, setSummary] = useState(null);
  const [donations, setDonations] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadAll = useCallback(async () => {
    try {
      const [s, sum, d] = await Promise.all([
        axios.get(`${base}/settings`, getAuthHeaders()),
        axios.get(`${base}/summary`, getAuthHeaders()),
        axios.get(`${base}/donations`, getAuthHeaders()),
      ]);
      setSettings(s.data); setSummary(sum.data); setDonations(d.data.items || []);
    } catch (err) {
      toast.error('No se pudo cargar el panel de la campaña');
    } finally {
      setLoading(false);
    }
  }, [base]);

  useEffect(() => {
    loadAll();
    const id = setInterval(loadAll, 4000);
    return () => clearInterval(id);
  }, [loadAll]);

  if (loading || !settings) {
    return <div className="flex min-h-[50vh] items-center justify-center" data-testid="campaign-control-loading">Cargando panel de campaña…</div>;
  }

  // «Ver pantalla»: enlace de presentación temporal (12 h); nunca la sesión del usuario en la dirección.
  const openScreen = async () => {
    const screen = window.open('', '_blank');
    try {
      const { data } = await axios.post(`${base}/screen-link`, {}, getAuthHeaders());
      const url = `${window.location.origin}/campanas/ven-y-come/pantalla?token=${encodeURIComponent(data.token)}`;
      if (screen) screen.location.href = url; else window.location.assign(url);
    } catch (error) {
      if (screen) screen.close();
      toast.error('No se pudo abrir la pantalla');
    }
  };

  return (
    <div className="space-y-6" data-testid="campaign-control-page">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 font-serif text-2xl font-bold text-[#132443]"><Bus className="h-6 w-6 text-[#B5953F]" />Ven y Come — Panel de Control</h1>
          <p className="text-sm text-slate-500">Meta {formatUsdCents(settings.goal_cents)} USD</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge data-testid="campaign-mode-badge" className={settings.mode === 'production' ? 'bg-emerald-600' : 'bg-amber-500'}>
            {settings.mode === 'production' ? 'PRODUCCIÓN' : 'ENSAYO'}
          </Badge>
          <Button variant="outline" size="sm" onClick={openScreen} data-testid="campaign-open-screen-button">
            <ExternalLink className="h-4 w-4" />Ver pantalla
          </Button>
        </div>
      </header>

      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="campaign-summary-cards">
          <SummaryCard label="Comprometido" value={summary.committed_cents} />
          <SummaryCard label="Recibido" value={summary.received_cents} />
          <SummaryCard label="Pendiente" value={summary.pending_cents} />
          <SummaryCard label="Progreso" value={null} percent={summary.percent} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <CampaignDonationForm base={base} getAuthHeaders={getAuthHeaders} onCreated={loadAll} />
          <CampaignDonationHistory base={base} getAuthHeaders={getAuthHeaders} donations={donations} onChanged={loadAll} />
          <CampaignMessagingPanel base={base} getAuthHeaders={getAuthHeaders} />
        </div>
        <div className="space-y-6">
          <CampaignSettingsPanel base={base} getAuthHeaders={getAuthHeaders} settings={settings} onChanged={loadAll} />
          <CampaignPresentationLinks base={base} getAuthHeaders={getAuthHeaders} />
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, percent }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid={`campaign-summary-${label.toLowerCase()}`}>
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="text-xl font-bold text-[#132443]">{percent !== undefined && percent !== null ? `${Math.round(percent * 100)}%` : formatUsdCents(value)}</p>
    </div>
  );
}
