import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Loader2, UserPlus, Users } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { errorDetailText } from '../../lib/errorText';
import { mentorAccountBlocked, mentorAccessHint, mentorNeedsAccountCreation } from '../../lib/accessControl';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

export const AddCampaignMentorsDialog = ({ open, onOpenChange, campaign, mentorOptions, onAdded }) => {
  const { API, getAuthHeaders } = useAuth();
  const [selected, setSelected] = useState([]);
  const [emails, setEmails] = useState({});
  const [groups, setGroups] = useState([]);
  const [groupId, setGroupId] = useState('');
  const [loadingGroup, setLoadingGroup] = useState(false);
  const [groupMentors, setGroupMentors] = useState([]);
  const [saving, setSaving] = useState(false);

  const alreadyIds = useMemo(() => new Set(campaign?.assigned_mentor_ids || []), [campaign]);
  const candidates = useMemo(() => {
    const map = new Map();
    [...(mentorOptions || []), ...groupMentors].forEach((item) => { if (!alreadyIds.has(item.person_id)) map.set(item.person_id, item); });
    return Array.from(map.values());
  }, [mentorOptions, groupMentors, alreadyIds]);

  useEffect(() => {
    if (!open) return;
    axios.get(`${API}/api/front-groups`, getAuthHeaders()).then((response) => setGroups(response.data.items || [])).catch(() => setGroups([]));
  }, [open, API, getAuthHeaders]);

  const reset = () => { setSelected([]); setEmails({}); setGroupId(''); setGroupMentors([]); };

  const toggle = (personId) => setSelected((prev) => (prev.includes(personId) ? prev.filter((id) => id !== personId) : [...prev, personId]));

  const loadGroup = async () => {
    if (!groupId) { toast.error('Seleccione un Grupo Frontal'); return; }
    setLoadingGroup(true);
    try {
      const { data } = await axios.get(`${API}/api/mentorship/outreach/mentors-by-group/${groupId}`, getAuthHeaders());
      const found = (data.items || []).filter((item) => !alreadyIds.has(item.person_id));
      if (found.length === 0) { toast.message('Esa rama no tiene mentores nuevos con insignia activa'); return; }
      setGroupMentors((prev) => { const map = new Map(prev.map((item) => [item.person_id, item])); found.forEach((item) => map.set(item.person_id, item)); return Array.from(map.values()); });
      setSelected((prev) => Array.from(new Set([...prev, ...found.filter((item) => !mentorAccountBlocked(item)).map((item) => item.person_id)])));
      toast.success(`${found.length} mentor(es) de la rama agregados a la selección`);
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo cargar los mentores de esa rama'));
    } finally { setLoadingGroup(false); }
  };

  const submit = async () => {
    if (selected.length === 0) { toast.error('Seleccione al menos un mentor'); return; }
    const emailPayload = {};
    for (const personId of selected) {
      const mentor = candidates.find((item) => item.person_id === personId);
      if (mentor && mentorNeedsAccountCreation(mentor)) {
        if (!emails[personId]) { toast.error(`Indique el correo de ${mentor.name} para invitarlo`); return; }
        emailPayload[personId] = emails[personId].trim();
      }
    }
    setSaving(true);
    try {
      const { data } = await axios.post(`${API}/api/mentorship/outreach/campaigns/${campaign.campaign_id}/mentors`, { person_ids: selected, emails: emailPayload }, getAuthHeaders());
      const parts = [];
      if (data.added?.length) parts.push(`${data.added.length} mentor(es) agregado(s)`);
      if (data.accounts_created?.length) parts.push(`${data.accounts_created.length} cuenta(s) invitada(s)`);
      if (data.already_assigned?.length) parts.push(`${data.already_assigned.length} ya estaban`);
      toast.success(parts.join(' · ') || 'Sin cambios');
      if (data.rejected?.length) data.rejected.forEach((item) => toast.error(`${item.name}: ${item.reason}`));
      reset();
      onOpenChange(false);
      if (onAdded) onAdded();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo agregar mentores'));
    } finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => { onOpenChange(next); if (!next) reset(); }}>
      <DialogContent className="max-h-[85vh] overflow-y-auto bg-white" data-testid="add-campaign-mentors-dialog">
        <DialogHeader><DialogTitle>Agregar mentores a "{campaign?.name}"</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <p className="text-xs text-slate-500" data-testid="add-campaign-mentors-already">Ya participan {alreadyIds.size} mentor(es); no se duplicarán.</p>

          {groups.length > 0 && (
            <div className="space-y-1.5 rounded-md border border-dashed border-[#D8D3C8] bg-[#FAF9F5] p-2">
              <Label>Agregar mentores de un Grupo Frontal y su rama</Label>
              <div className="flex gap-2">
                <Select value={groupId} onValueChange={setGroupId}>
                  <SelectTrigger data-testid="add-campaign-mentors-group-select"><SelectValue placeholder="Seleccione una rama" /></SelectTrigger>
                  <SelectContent className="bg-white">
                    {groups.map((group) => <SelectItem key={group.front_group_id} value={group.front_group_id}>{group.display_name || group.name}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Button type="button" variant="outline" disabled={loadingGroup} onClick={loadGroup} data-testid="add-campaign-mentors-group-button">
                  {loadingGroup ? <Loader2 className="h-4 w-4 animate-spin" /> : <Users className="h-4 w-4" />} Agregar rama
                </Button>
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <Label>Mentores disponibles (Persona 360, insignia vigente)</Label>
            <div className="max-h-72 space-y-2 overflow-y-auto rounded-md border border-[#E8E5DE] p-2" data-testid="add-campaign-mentors-list">
              {candidates.map((mentor) => {
                const blocked = mentorAccountBlocked(mentor);
                const needsAccount = mentorNeedsAccountCreation(mentor);
                const checked = selected.includes(mentor.person_id);
                return (
                  <div key={mentor.person_id} className="rounded px-1 py-1">
                    <label className={`flex items-start gap-2 text-sm ${blocked ? 'cursor-not-allowed text-slate-400' : 'cursor-pointer text-[#101D36] hover:bg-[#F6F4EF]'}`}>
                      <input type="checkbox" checked={checked} disabled={blocked} onChange={() => toggle(mentor.person_id)} className="mt-0.5 shrink-0" data-testid={`add-campaign-mentor-checkbox-${mentor.person_id}`} />
                      <span className="break-words">{mentor.name}{blocked ? ' (sin acceso)' : ''}{needsAccount ? ' (sin cuenta · se invitará)' : ''}</span>
                    </label>
                    {checked && needsAccount && (
                      <div className="ml-6 mt-2" data-testid={`add-campaign-mentor-email-wrap-${mentor.person_id}`}>
                        <Input placeholder="Correo para invitarlo" type="email" value={emails[mentor.person_id] || ''} onChange={(event) => setEmails((prev) => ({ ...prev, [mentor.person_id]: event.target.value }))} data-testid={`add-campaign-mentor-email-${mentor.person_id}`} />
                      </div>
                    )}
                  </div>
                );
              })}
              {candidates.length === 0 && <p className="text-xs text-slate-400">No hay mentores nuevos disponibles para agregar.</p>}
            </div>
            {candidates.some(mentorAccountBlocked) && <p className="text-xs text-slate-500" data-testid="add-campaign-mentors-access-hint">{mentorAccessHint}</p>}
          </div>

          <Button disabled={saving} onClick={submit} className="w-full bg-[#132443]" data-testid="add-campaign-mentors-submit-button">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <><UserPlus className="h-4 w-4" />Agregar seleccionados</>}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
