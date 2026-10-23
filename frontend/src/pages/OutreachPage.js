import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Footprints, Home, Loader2, Map, Plus } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { canLeadOutreach } from '../lib/accessControl';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { AddHouseholdDialog } from '../components/outreach/AddHouseholdDialog';
import { AddVisitDialog } from '../components/outreach/AddVisitDialog';
import { AvailableHouseholdsPanel } from '../components/outreach/AvailableHouseholdsPanel';
import { HouseholdCard } from '../components/outreach/HouseholdCard';
import { HouseholdsMapView } from '../components/outreach/HouseholdsMapView';
import { LogVisitAttemptDialog } from '../components/outreach/LogVisitAttemptDialog';
import { MyLibraryHoldingsCard } from '../components/outreach/MyLibraryHoldingsCard';
import { OutreachLeaderPanel } from '../components/outreach/OutreachLeaderPanel';
import { ParticipateCampaignCard } from '../components/outreach/ParticipateCampaignCard';
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
  const [households, setHouseholds] = useState([]);
  const [mentorOptions, setMentorOptions] = useState([]);
  const [availableByCampaign, setAvailableByCampaign] = useState({});
  const [poolVersion, setPoolVersion] = useState(0);
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [addHouseholdOpen, setAddHouseholdOpen] = useState(false);
  const [attemptHousehold, setAttemptHousehold] = useState(null);
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

  const loadHouseholds = useCallback(async () => {
    if (!user?.person_id) { setHouseholds([]); return; }
    const response = await axios.get(`${API}/api/mentorship/outreach/households?mentor_person_id=${user.person_id}`, getAuthHeaders());
    setHouseholds(response.data.items || []);
  }, [API, getAuthHeaders, user]);

  const loadMentorOptions = useCallback(async () => {
    if (!isLeader) return;
    try {
      const response = await axios.get(`${API}/api/mentorship/mentors`, getAuthHeaders());
      setMentorOptions(response.data.items || []);
    } catch (error) {
      setMentorOptions([]);
    }
  }, [API, getAuthHeaders, isLeader]);

  useEffect(() => {
    setLoading(true);
    Promise.all([loadCampaigns(), loadMyVisits(), loadHouseholds(), loadMentorOptions()]).finally(() => setLoading(false));
  }, [loadCampaigns, loadMyVisits, loadHouseholds, loadMentorOptions]);

  const filteredVisits = statusFilter === 'all' ? myVisits : myVisits.filter((item) => item.status === statusFilter);
  const myCampaigns = campaigns.filter((item) => item.my_participation_status);

  const loadAvailableFor = useCallback(async (campaignId) => {
    try {
      const response = await axios.get(`${API}/api/mentorship/outreach/campaigns/${campaignId}/households/available`, getAuthHeaders());
      setAvailableByCampaign((prev) => ({ ...prev, [campaignId]: response.data.items || [] }));
      setPoolVersion((v) => v + 1);
    } catch (error) {
      setAvailableByCampaign((prev) => ({ ...prev, [campaignId]: [] }));
    }
  }, [API, getAuthHeaders]);

  useEffect(() => {
    myCampaigns.forEach((campaign) => loadAvailableFor(campaign.campaign_id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaigns.length]);

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
          <TabsTrigger value="hogares" data-testid="outreach-tab-households">Mis Hogares</TabsTrigger>
          {myCampaigns.length > 0 && <TabsTrigger value="mapa" data-testid="outreach-tab-map"><Map className="mr-1 h-3.5 w-3.5 inline" />Mapa</TabsTrigger>}
          {isLeader && <TabsTrigger value="panel" data-testid="outreach-tab-leader">Panel de líderes</TabsTrigger>}
        </TabsList>

        <TabsContent value="mis-visitas" className="mt-4 space-y-4">
          <MyLibraryHoldingsCard />

          {myCampaigns.length > 0 && (
            <div className="space-y-3" data-testid="outreach-my-campaigns">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Invasión activa</p>
              {myCampaigns.map((campaign) => <ParticipateCampaignCard key={campaign.campaign_id} campaign={campaign} onUpdated={loadCampaigns} />)}
            </div>
          )}

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

        <TabsContent value="hogares" className="mt-4 space-y-4">
          {myCampaigns.map((campaign) => (
            <AvailableHouseholdsPanel
              key={campaign.campaign_id}
              campaign={campaign}
              isLeader={isLeader}
              mentorOptions={mentorOptions}
              refreshKey={poolVersion}
              onChanged={() => { loadHouseholds(); loadAvailableFor(campaign.campaign_id); }}
            />
          ))}

          <div className="flex items-center justify-end">
            <Button onClick={() => setAddHouseholdOpen(true)} className="bg-[#132443]" data-testid="outreach-add-household-button"><Home className="h-4 w-4" /> Agregar hogar</Button>
          </div>
          {loading ? (
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          ) : households.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500" data-testid="outreach-households-empty-state">Sin hogares registrados todavía.</p>
          ) : (
            <div className="space-y-3">
              {households.map((household) => (
                <HouseholdCard
                  key={household.household_id}
                  household={household}
                  canRelease={household.status === 'assigned' && Boolean(household.campaign_id) && (household.mentor_person_id === user.person_id || isLeader)}
                  onLogAttempt={setAttemptHousehold}
                  onChanged={() => { loadHouseholds(); if (household.campaign_id) loadAvailableFor(household.campaign_id); }}
                />
              ))}
            </div>
          )}
        </TabsContent>

        {myCampaigns.length > 0 && (
          <TabsContent value="mapa" className="mt-4">
            <HouseholdsMapView myCampaigns={myCampaigns} myHouseholds={households} availableByCampaign={availableByCampaign} />
          </TabsContent>
        )}

        {isLeader && (
          <TabsContent value="panel" className="mt-4">
            <OutreachLeaderPanel campaigns={campaigns} onCampaignsChanged={loadCampaigns} />
          </TabsContent>
        )}
      </Tabs>

      <AddVisitDialog open={addOpen} onOpenChange={setAddOpen} campaigns={campaigns} forcedMentorId={user.person_id} onCreated={() => { loadMyVisits(); loadCampaigns(); }} />
      <AddHouseholdDialog open={addHouseholdOpen} onOpenChange={setAddHouseholdOpen} campaigns={campaigns} forcedMentorId={user.person_id} onCreated={() => { loadHouseholds(); loadCampaigns(); }} />
      <LogVisitAttemptDialog household={attemptHousehold} open={Boolean(attemptHousehold)} onOpenChange={(value) => { if (!value) setAttemptHousehold(null); }} onLogged={() => { loadHouseholds(); loadMyVisits(); loadCampaigns(); }} />
      <TransferVisitDialog visit={transferVisit} onClose={() => setTransferVisit(null)} onTransferred={loadMyVisits} />
    </div>
  );
}

