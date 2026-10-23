import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Home, Loader2, MapPin, UploadCloud, UserCheck } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { errorDetailText } from '../../lib/errorText';
import { AssignHouseholdDialog } from './AssignHouseholdDialog';
import { ImportHouseholdsDialog } from './ImportHouseholdsDialog';

export const AvailableHouseholdsPanel = ({ campaign, isLeader, mentorOptions, onChanged }) => {
  const { API, getAuthHeaders } = useAuth();
  const [households, setHouseholds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [importOpen, setImportOpen] = useState(false);
  const [assignTarget, setAssignTarget] = useState(null);
  const [claimingId, setClaimingId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/api/mentorship/outreach/campaigns/${campaign.campaign_id}/households/available`, getAuthHeaders());
      setHouseholds(response.data.items || []);
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudieron cargar las casas disponibles'));
    } finally {
      setLoading(false);
    }
  }, [API, getAuthHeaders, campaign]);

  useEffect(() => { load(); }, [load]);

  const refresh = () => { load(); if (onChanged) onChanged(); };

  const claim = async (household) => {
    setClaimingId(household.household_id);
    try {
      await axios.post(`${API}/api/mentorship/outreach/households/${household.household_id}/claim`, {}, getAuthHeaders());
      toast.success('Casa tomada');
      refresh();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo tomar esta casa'));
    } finally {
      setClaimingId(null);
    }
  };

  const rosterMentors = (mentorOptions || []).filter((mentor) => (campaign.assigned_mentor_ids || []).includes(mentor.person_id));

  return (
    <div className="rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid={`outreach-available-panel-${campaign.campaign_id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-['Spectral'] text-base font-semibold text-[#101D36]">Casas disponibles — {campaign.name}</h4>
        {isLeader && (
          <Button size="sm" variant="outline" onClick={() => setImportOpen(true)} data-testid={`outreach-import-households-button-${campaign.campaign_id}`}>
            <UploadCloud className="h-4 w-4" /> Importar casas
          </Button>
        )}
      </div>

      {loading ? (
        <Loader2 className="mt-3 h-5 w-5 animate-spin text-slate-400" />
      ) : households.length === 0 ? (
        <p className="mt-3 text-sm text-slate-400" data-testid={`outreach-available-empty-${campaign.campaign_id}`}>Sin casas disponibles por ahora.</p>
      ) : (
        <div className="mt-3 space-y-2" data-testid={`outreach-available-list-${campaign.campaign_id}`}>
          {households.map((household) => {
            const address = [household.address_line1, household.sector].filter(Boolean).join(' · ') || 'Sin dirección';
            return (
              <div key={household.household_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#E8E5DE] p-2" data-testid={`outreach-available-row-${household.household_id}`}>
                <span className="flex items-center gap-2 text-sm text-[#101D36]"><Home className="h-4 w-4 text-slate-400" />{address}</span>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" className="h-11 bg-[#132443]" disabled={claimingId === household.household_id} onClick={() => claim(household)} data-testid={`outreach-claim-button-${household.household_id}`}>
                    {claimingId === household.household_id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Home className="h-4 w-4" />} Tomar esta casa
                  </Button>
                  {isLeader && (
                    <Button size="sm" variant="outline" className="h-11" onClick={() => setAssignTarget(household)} data-testid={`outreach-open-assign-button-${household.household_id}`}>
                      <UserCheck className="h-4 w-4" /> Asignar
                    </Button>
                  )}
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex h-11 items-center gap-1 rounded-md border border-[#E8E5DE] px-3 text-xs text-slate-500 hover:text-[#132443]"
                    data-testid={`outreach-available-map-link-${household.household_id}`}
                  >
                    <MapPin className="h-3.5 w-3.5" /> Mapa
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <ImportHouseholdsDialog open={importOpen} onOpenChange={setImportOpen} campaign={campaign} onImported={refresh} />
      <AssignHouseholdDialog open={Boolean(assignTarget)} onOpenChange={(value) => { if (!value) setAssignTarget(null); }} household={assignTarget} mentorOptions={rosterMentors} onAssigned={refresh} />
    </div>
  );
};
