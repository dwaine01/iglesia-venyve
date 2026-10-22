import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, Plus, UserRoundSearch } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { AddVisitDialog } from './AddVisitDialog';
import { TransferVisitDialog } from './TransferVisitDialog';
import { VisitCard } from './VisitCard';

const TOTAL_CARDS = [
  ['assigned', 'Asignados'],
  ['visited', 'Visitados'],
  ['wants_followup', 'Quiere seguimiento'],
  ['seven_weeks_started', '7 Semanas iniciadas'],
];

export const OutreachLeaderPanel = ({ campaigns, onCampaignsChanged }) => {
  const { API, getAuthHeaders } = useAuth();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [campaignName, setCampaignName] = useState('');
  const [zoneNotes, setZoneNotes] = useState('');
  const [creatingCampaign, setCreatingCampaign] = useState(false);
  const [mentors, setMentors] = useState([]);
  const [drillMentorId, setDrillMentorId] = useState(null);
  const [drillVisits, setDrillVisits] = useState([]);
  const [addOpen, setAddOpen] = useState(false);
  const [transferVisit, setTransferVisit] = useState(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/api/mentorship/outreach/dashboard`, getAuthHeaders());
      setDashboard(response.data);
    } finally {
      setLoading(false);
    }
  }, [API, getAuthHeaders]);

  const loadMentors = useCallback(async () => {
    const response = await axios.get(`${API}/api/mentorship/mentors`, getAuthHeaders());
    setMentors(response.data.items || []);
  }, [API, getAuthHeaders]);

  useEffect(() => { loadDashboard(); loadMentors(); }, [loadDashboard, loadMentors]);

  const loadDrill = async (mentorId) => {
    setDrillMentorId(mentorId);
    const response = await axios.get(`${API}/api/mentorship/outreach/visits?mentor_person_id=${mentorId}`, getAuthHeaders());
    setDrillVisits(response.data.items || []);
  };

  const createCampaign = async () => {
    if (!campaignName.trim()) { toast.error('Escriba el nombre de la campaña'); return; }
    setCreatingCampaign(true);
    try {
      await axios.post(`${API}/api/mentorship/outreach/campaigns`, { name: campaignName.trim(), zone_notes: zoneNotes || null }, getAuthHeaders());
      toast.success('Campaña creada');
      setCampaignName(''); setZoneNotes('');
      if (onCampaignsChanged) onCampaignsChanged();
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'No se pudo crear la campaña');
    } finally {
      setCreatingCampaign(false);
    }
  };

  const refreshDrill = () => { if (drillMentorId) loadDrill(drillMentorId); loadDashboard(); };

  if (loading) return <Loader2 className="h-6 w-6 animate-spin text-slate-400" data-testid="outreach-leader-loading" />;

  return (
    <div className="space-y-6" data-testid="outreach-leader-panel">
      <div className="rounded-xl border border-[#E8E5DE] bg-white p-4">
        <h3 className="font-['Spectral'] text-lg font-semibold text-[#101D36]">Nueva campaña de invasión</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-[2fr_3fr_auto]">
          <Input value={campaignName} onChange={(event) => setCampaignName(event.target.value)} placeholder="Nombre" data-testid="outreach-campaign-name-input" />
          <Input value={zoneNotes} onChange={(event) => setZoneNotes(event.target.value)} placeholder="Zona / notas" data-testid="outreach-campaign-zone-input" />
          <Button disabled={creatingCampaign} onClick={createCampaign} className="bg-[#132443]" data-testid="outreach-campaign-create-button"><Plus className="h-4 w-4" /> Crear</Button>
        </div>
        {campaigns?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {campaigns.map((campaign) => (
              <Badge key={campaign.campaign_id} variant="outline" data-testid={`outreach-campaign-badge-${campaign.campaign_id}`}>
                {campaign.name} · {campaign.status === 'active' ? 'Activa' : 'Cerrada'}
              </Badge>
            ))}
          </div>
        )}
      </div>

      {dashboard && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {TOTAL_CARDS.map(([key, label]) => (
            <div key={key} className="rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid={`outreach-total-${key}`}>
              <p className="text-2xl font-semibold text-[#101D36]">{dashboard.totals[key]}</p>
              <p className="text-xs text-slate-500">{label}</p>
            </div>
          ))}
        </div>
      )}

      <div className="rounded-xl border border-[#E8E5DE] bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-['Spectral'] text-lg font-semibold text-[#101D36]">Totales por mentor</h3>
          <Button size="sm" variant="outline" onClick={() => setAddOpen(true)} data-testid="outreach-leader-assign-button"><UserRoundSearch className="h-4 w-4" /> Asignar visita</Button>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm" data-testid="outreach-mentor-table">
            <thead>
              <tr className="text-left text-xs text-slate-500">
                <th className="py-2">Mentor</th><th>Total</th><th>Pendientes</th><th>Visitados</th><th>Quiere seguimiento</th><th>Mi conexión</th><th>Nací p. triunfar</th><th>LBS pendiente</th><th>7 Semanas</th><th />
              </tr>
            </thead>
            <tbody>
              {(dashboard?.by_mentor || []).map((row) => (
                <tr key={row.mentor_person_id} className="border-t border-slate-100" data-testid={`outreach-mentor-row-${row.mentor_person_id}`}>
                  <td className="py-2 font-medium">{row.mentor_name}</td>
                  <td>{row.total}</td><td>{row.assigned}</td><td>{row.visited}</td><td>{row.wants_followup}</td><td>{row.received_mcd}</td><td>{row.received_npt}</td><td>{row.lbs_pending}</td><td>{row.seven_weeks_started}</td>
                  <td><Button size="sm" variant="ghost" onClick={() => loadDrill(row.mentor_person_id)} data-testid={`outreach-mentor-drill-button-${row.mentor_person_id}`}>Ver lista</Button></td>
                </tr>
              ))}
              {(dashboard?.by_mentor || []).length === 0 && (
                <tr><td colSpan={10} className="py-4 text-center text-slate-400">Sin mentores con visitas todavía.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {drillMentorId && (
        <div className="space-y-3" data-testid="outreach-drill-list">
          <h3 className="font-['Spectral'] text-lg font-semibold text-[#101D36]">
            Visitas de {dashboard?.by_mentor?.find((item) => item.mentor_person_id === drillMentorId)?.mentor_name}
          </h3>
          {drillVisits.map((visit) => <VisitCard key={`${visit.visit_id}-${visit.updated_at}`} visit={visit} canManage onUpdated={refreshDrill} onTransfer={setTransferVisit} />)}
          {drillVisits.length === 0 && <p className="text-sm text-slate-500">Sin visitas registradas.</p>}
        </div>
      )}

      <AddVisitDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        campaigns={campaigns}
        mentorOptions={mentors}
        onCreated={() => { loadDashboard(); if (drillMentorId) loadDrill(drillMentorId); }}
      />
      <TransferVisitDialog visit={transferVisit} onClose={() => setTransferVisit(null)} onTransferred={refreshDrill} />
    </div>
  );
};
