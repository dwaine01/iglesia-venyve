import React, { useState } from 'react';
import axios from 'axios';
import { CalendarClock, Loader2, MapPin } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { errorDetailText } from '../../lib/errorText';

const STATUS_LABELS = { assigned: 'Asignado', confirmed: 'Confirmado', active: 'Con actividad' };
const STATUS_COLORS = {
  assigned: 'bg-slate-100 text-slate-700',
  confirmed: 'bg-blue-100 text-blue-800',
  active: 'bg-emerald-100 text-emerald-800',
};

export const ParticipateCampaignCard = ({ campaign, onUpdated }) => {
  const { API, getAuthHeaders } = useAuth();
  const [busy, setBusy] = useState(false);
  const status = campaign.my_participation_status;

  const participate = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/mentorship/outreach/campaigns/${campaign.campaign_id}/participate`, {}, getAuthHeaders());
      toast.success('Participación confirmada');
      if (onUpdated) onUpdated();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo confirmar la participación'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid={`outreach-participate-card-${campaign.campaign_id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-['Spectral'] font-semibold text-[#101D36]">{campaign.name}</p>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3" />{campaign.location}</span>
            {campaign.meeting_time && <span className="inline-flex items-center gap-1"><CalendarClock className="h-3 w-3" />{campaign.meeting_time}{campaign.meeting_place ? ` · ${campaign.meeting_place}` : ''}</span>}
          </p>
        </div>
        {status && <Badge className={STATUS_COLORS[status]} data-testid={`outreach-participate-status-${campaign.campaign_id}`}>{STATUS_LABELS[status] || status}</Badge>}
      </div>
      {campaign.sectors?.length > 0 && <p className="mt-2 text-xs text-slate-500">Sectores: {campaign.sectors.join(', ')}</p>}
      {campaign.instructions && <p className="mt-2 rounded-md border border-dashed border-[#D8D3C8] bg-[#FAF9F5] p-2 text-xs text-slate-600">{campaign.instructions}</p>}
      {status === 'assigned' && (
        <Button size="sm" className="mt-3 bg-[#132443]" disabled={busy} onClick={participate} data-testid={`outreach-participate-button-${campaign.campaign_id}`}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null} Participar en esta invasión
        </Button>
      )}
    </div>
  );
};
