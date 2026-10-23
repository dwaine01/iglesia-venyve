import React, { useEffect, useState } from 'react';
import axios from 'axios';

import { useAuth } from '../../context/AuthContext';

const PERIODS = [
  { key: 'week', label: 'Semanal' }, { key: 'month', label: 'Mensual' },
  { key: 'invasion', label: 'Por invasión' }, { key: 'all', label: 'Todo' },
];

// Selector del período evaluado (mismo para panel, estadísticas y actividad).
export function PeriodSelector({ period, campaignId, onChange }) {
  const { API, getAuthHeaders } = useAuth();
  const [campaigns, setCampaigns] = useState([]);
  useEffect(() => {
    axios.get(`${API}/api/front-group-structure/campaigns`, getAuthHeaders()).then((response) => setCampaigns(response.data.items || [])).catch(() => setCampaigns([]));
  }, [API, getAuthHeaders]);
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-4 gap-1 rounded-xl bg-[#EEECE6] p-1" role="tablist" aria-label="Período evaluado">
        {PERIODS.map((item) => <button key={item.key} type="button" role="tab" aria-selected={period === item.key} onClick={() => onChange(item.key, campaignId)} className={`min-h-11 rounded-lg px-1 text-xs font-semibold ${period === item.key ? 'bg-white text-[#101D36] shadow-sm' : 'text-slate-600'}`} data-testid={`period-${item.key}`}>{item.label}</button>)}
      </div>
      {period === 'invasion' && (
        <select value={campaignId} onChange={(event) => onChange('invasion', event.target.value)} className="h-11 w-full rounded-md border border-[#E8E5DE] bg-white px-3 text-sm" aria-label="Invasión" data-testid="period-campaign-select">
          <option value="">Última invasión</option>
          {campaigns.map((campaign) => <option key={campaign.campaign_id} value={campaign.campaign_id}>{campaign.name}</option>)}
        </select>
      )}
    </div>
  );
}

export const periodParams = (period, campaignId) => ({ period, ...(period === 'invasion' && campaignId ? { campaign_id: campaignId } : {}) });
