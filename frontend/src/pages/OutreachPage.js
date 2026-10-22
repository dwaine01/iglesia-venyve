import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Footprints, Loader2, Plus } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { canLeadOutreach } from '../lib/accessControl';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { AddVisitDialog } from '../components/outreach/AddVisitDialog';
import { OutreachLeaderPanel } from '../components/outreach/OutreachLeaderPanel';
import { TransferVisitDialog } from '../components/outreach/TransferVisitDialog';
import { VisitCard } from '../components/outreach/VisitCard';

const STATUS_FILTERS = [
  ['all', 'Todas'],
  ['assigned', 'Asignadas'],
  ['visited', 'Visitadas'],
  ['wants_followup', 'Quiere seguimiento'],
  ['not_found', 'No encontradas'],
  ['rejected', 'Rechazó'],
];

export default function OutreachPage() {
  const { user, API, getAuthHeaders } = useAuth();
  const isLeader = canLeadOutreach(user);
  const [activeTab, setActiveTab] = useState(isLeader ? 'panel' : 'mis-visitas');
  const [campaigns, setCampaigns] = useState([]);
  const [myVisits, setMyVisits] = useState([]);
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [transferVisit, setTransferVisit] = useState(null);

  const loadCampaigns = useCallback(async () => {
    const response = await axios.get(`${API}/api/mentorship/outreach/campaigns`, getAuthHeaders());
    setCampaigns(response.data.items || []);
  }, [API, getAuthHeaders]);

  const loadMyVisits = useCallback(async () => {
    if (!user?.person_id) { setMyVisits([]); return; }
    const response = await axios.get(`${API}/api/mentorship/outreach/visits?mentor_person_id=${user.person_id}`, getAuthHeaders());
    setMyVisits(response.data.items || []);
  }, [API, getAuthHeaders, user]);

  useEffect(() => {
    setLoading(true);
    Promise.all([loadCampaigns(), loadMyVisits()]).finally(() => setLoading(false));
  }, [loadCampaigns, loadMyVisits]);

  const filteredVisits = statusFilter === 'all' ? myVisits : myVisits.filter((item) => item.status === statusFilter);

  return (
    <div className="space-y-6 p-4 sm:p-6" data-testid="outreach-page">
      <header className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#132443]/10 text-[#132443]"><Footprints className="h-5 w-5" /></div>
        <div>
          <h1 className="font-['Spectral'] text-2xl font-semibold text-[#101D36] sm:text-3xl">{isLeader ? 'Visitas e Invasiones' : 'Mis Visitas'}</h1>
          <p className="text-sm text-slate-500">Ley de las 7 Semanas — seguimiento puerta a puerta</p>
        </div>
      </header>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList data-testid="outreach-tabs">
          <TabsTrigger value="mis-visitas" data-testid="outreach-tab-my-visits">Mis Visitas</TabsTrigger>
          {isLeader && <TabsTrigger value="panel" data-testid="outreach-tab-leader">Panel de líderes</TabsTrigger>}
        </TabsList>

        <TabsContent value="mis-visitas" className="mt-4 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {STATUS_FILTERS.map(([key, label]) => (
                <Button
                  key={key}
                  size="sm"
                  variant={statusFilter === key ? 'default' : 'outline'}
                  onClick={() => setStatusFilter(key)}
                  className={statusFilter === key ? 'bg-[#132443]' : ''}
                  data-testid={`outreach-filter-${key}`}
                >
                  {label}
                </Button>
              ))}
            </div>
            <Button onClick={() => setAddOpen(true)} className="bg-[#132443]" data-testid="outreach-add-visit-button"><Plus className="h-4 w-4" /> Agregar visita</Button>
          </div>

          {loading ? (
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          ) : filteredVisits.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500" data-testid="outreach-empty-state">Sin visitas en esta vista todavía.</p>
          ) : (
            <div className="space-y-3">
              {filteredVisits.map((visit) => (
                <VisitCard key={`${visit.visit_id}-${visit.updated_at}`} visit={visit} canManage={false} onUpdated={loadMyVisits} onTransfer={setTransferVisit} />
              ))}
            </div>
          )}
        </TabsContent>

        {isLeader && (
          <TabsContent value="panel" className="mt-4">
            <OutreachLeaderPanel campaigns={campaigns} onCampaignsChanged={loadCampaigns} />
          </TabsContent>
        )}
      </Tabs>

      <AddVisitDialog open={addOpen} onOpenChange={setAddOpen} campaigns={campaigns} forcedMentorId={user.person_id} onCreated={loadMyVisits} />
      <TransferVisitDialog visit={transferVisit} onClose={() => setTransferVisit(null)} onTransferred={loadMyVisits} />
    </div>
  );
}
