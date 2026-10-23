import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, ShieldAlert, Trash2, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { errorDetailText } from '../../lib/errorText';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { AddCampaignMentorsDialog } from './AddCampaignMentorsDialog';

const RosterRow = ({ campaignId, mentor, onRemoved }) => {
  const { API, getAuthHeaders } = useAuth();
  const [confirming, setConfirming] = useState(false);
  const [preview, setPreview] = useState(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);

  const openConfirm = async () => {
    setConfirming(true);
    try {
      const { data } = await axios.get(`${API}/api/mentorship/outreach/campaigns/${campaignId}/mentors/${mentor.person_id}/remove-preview`, getAuthHeaders());
      setPreview(data);
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo calcular si se puede quitar'));
      setConfirming(false);
    }
  };

  const confirmRemove = async () => {
    if (!reason.trim()) { toast.error('Indique el motivo'); return; }
    setBusy(true);
    try {
      await axios.delete(`${API}/api/mentorship/outreach/campaigns/${campaignId}/mentors/${mentor.person_id}`, { ...getAuthHeaders(), data: { reason: reason.trim() } });
      toast.success(`${mentor.name} fue quitado de la invasión`);
      setConfirming(false); setReason('');
      if (onRemoved) onRemoved();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo quitar al mentor'));
    } finally { setBusy(false); }
  };

  return (
    <div className="rounded-lg border border-[#E8E5DE] p-3" data-testid={`campaign-roster-row-${mentor.person_id}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-[#101D36]">{mentor.name}</span>
        {!confirming && (
          <Button size="sm" variant="outline" onClick={openConfirm} className="border-red-300 text-red-700 hover:bg-red-50" data-testid={`campaign-roster-remove-button-${mentor.person_id}`}>
            <Trash2 className="h-4 w-4" />Quitar
          </Button>
        )}
      </div>
      {confirming && (
        <div className="mt-2 space-y-2 rounded-md border border-amber-200 bg-amber-50 p-2" data-testid={`campaign-roster-confirm-${mentor.person_id}`}>
          {!preview && <Loader2 className="h-4 w-4 animate-spin text-amber-600" />}
          {preview && (
            <>
              {preview.blocked ? (
                <>
                  <p className="flex items-start gap-1.5 text-xs text-amber-800" data-testid={`campaign-roster-blocked-${mentor.person_id}`}>
                    <ShieldAlert className="h-4 w-4 shrink-0" />
                    No se puede quitar: tiene {preview.households} hogar(es), {preview.visits} visita(s) y {preview.books_in_custody} libro(s) en custodia de esta invasión. Transfiera los contactos y devuelva los libros primero.
                  </p>
                  <Button size="sm" variant="ghost" onClick={() => { setConfirming(false); setPreview(null); }} data-testid={`campaign-roster-cancel-blocked-${mentor.person_id}`}>Cerrar</Button>
                </>
              ) : (
                <>
                  <Input placeholder="Motivo" value={reason} onChange={(event) => setReason(event.target.value)} data-testid={`campaign-roster-remove-reason-${mentor.person_id}`} />
                  <div className="flex gap-2">
                    <Button size="sm" disabled={busy} onClick={confirmRemove} className="bg-red-700 text-white hover:bg-red-800" data-testid={`campaign-roster-confirm-remove-${mentor.person_id}`}>
                      {busy && <Loader2 className="h-4 w-4 animate-spin" />}Confirmar
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => { setConfirming(false); setPreview(null); setReason(''); }} data-testid={`campaign-roster-cancel-remove-${mentor.person_id}`}>Cancelar</Button>
                  </div>
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export const CampaignRosterDialog = ({ open, onOpenChange, campaign, mentorOptions, onChanged }) => {
  const [addOpen, setAddOpen] = useState(false);

  const roster = (campaign?.assigned_mentor_ids || []).map((personId) => mentorOptions.find((item) => item.person_id === personId) || { person_id: personId, name: 'Mentor' });

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[85vh] overflow-y-auto bg-white" data-testid="campaign-roster-dialog">
          <DialogHeader><DialogTitle>Mentores de "{campaign?.name}"</DialogTitle></DialogHeader>
          <Button onClick={() => setAddOpen(true)} className="bg-[#132443]" data-testid="campaign-roster-open-add-button"><UserPlus className="h-4 w-4" />Agregar mentores</Button>
          <div className="space-y-2" data-testid="campaign-roster-list">
            {roster.map((mentor) => <RosterRow key={mentor.person_id} campaignId={campaign.campaign_id} mentor={mentor} onRemoved={onChanged} />)}
            {roster.length === 0 && <p className="text-sm text-slate-400">Sin mentores asignados todavía.</p>}
          </div>
        </DialogContent>
      </Dialog>
      <AddCampaignMentorsDialog open={addOpen} onOpenChange={setAddOpen} campaign={campaign} mentorOptions={mentorOptions} onAdded={onChanged} />
    </>
  );
};
