import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Loader2, Users } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';
import { mentorAccountBlocked, mentorAccessHint, mentorNeedsAccountCreation } from '../../lib/accessControl';
import { errorDetailText } from '../../lib/errorText';

export const CreateCampaignDialog = ({ open, onOpenChange, mentorOptions, onCreated }) => {
  const { API, getAuthHeaders } = useAuth();
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [zoneNotes, setZoneNotes] = useState('');
  const [meetingTime, setMeetingTime] = useState('');
  const [meetingPlace, setMeetingPlace] = useState('');
  const [sectorsText, setSectorsText] = useState('');
  const [instructions, setInstructions] = useState('');
  const [selectedMentors, setSelectedMentors] = useState([]);
  const [extraMentors, setExtraMentors] = useState([]);
  const [credentials, setCredentials] = useState({});
  const [saving, setSaving] = useState(false);
  const [groups, setGroups] = useState([]);
  const [groupId, setGroupId] = useState('');
  const [loadingGroup, setLoadingGroup] = useState(false);

  useEffect(() => {
    if (!open) return;
    axios.get(`${API}/api/front-groups`, getAuthHeaders())
      .then((response) => setGroups(response.data.items || []))
      .catch(() => setGroups([]));
  }, [open, API, getAuthHeaders]);

  const combinedOptions = useMemo(() => {
    const map = new Map();
    [...(mentorOptions || []), ...extraMentors].forEach((item) => map.set(item.person_id, item));
    return Array.from(map.values());
  }, [mentorOptions, extraMentors]);

  const reset = () => {
    setName(''); setLocation(''); setStartDate(''); setEndDate(''); setZoneNotes('');
    setMeetingTime(''); setMeetingPlace(''); setSectorsText(''); setInstructions('');
    setSelectedMentors([]); setExtraMentors([]); setCredentials({}); setGroupId('');
  };

  const toggleMentor = (personId) => {
    setSelectedMentors((prev) => (prev.includes(personId) ? prev.filter((id) => id !== personId) : [...prev, personId]));
    setCredentials((prev) => {
      if (!prev[personId]) return prev;
      const next = { ...prev };
      delete next[personId];
      return next;
    });
  };

  const setCredentialField = (personId, field, value) => {
    setCredentials((prev) => ({ ...prev, [personId]: { ...prev[personId], [field]: value } }));
  };

  const addGroupMentors = async () => {
    if (!groupId) { toast.error('Seleccione un Grupo Frontal'); return; }
    setLoadingGroup(true);
    try {
      const response = await axios.get(`${API}/api/mentorship/outreach/mentors-by-group/${groupId}`, getAuthHeaders());
      const found = response.data.items || [];
      if (found.length === 0) {
        toast.message('Ese grupo no tiene mentores con insignia activa todavía');
        return;
      }
      setExtraMentors((prev) => {
        const map = new Map(prev.map((item) => [item.person_id, item]));
        found.forEach((item) => map.set(item.person_id, item));
        return Array.from(map.values());
      });
      const addableIds = found.filter((item) => !mentorAccountBlocked(item)).map((item) => item.person_id);
      setSelectedMentors((prev) => Array.from(new Set([...prev, ...addableIds])));
      toast.success(`${found.length} mentor(es) del grupo agregados al roster`);
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo cargar los mentores de ese grupo'));
    } finally {
      setLoadingGroup(false);
    }
  };

  const submit = async () => {
    if (!name.trim() || !location.trim() || !startDate || !endDate) {
      toast.error('Completa el lugar, el nombre, la fecha de inicio y la fecha de fin de la invasión');
      return;
    }
    const assignedMentors = [];
    for (const personId of selectedMentors) {
      const mentor = combinedOptions.find((item) => item.person_id === personId);
      if (mentorNeedsAccountCreation(mentor)) {
        const cred = credentials[personId] || {};
        if (!cred.email || !cred.password || cred.password.length < 10) {
          toast.error(`Indique correo y una contraseña temporal de al menos 10 caracteres para ${mentor.name}`);
          return;
        }
        if (cred.password !== cred.confirm) {
          toast.error(`Las contraseñas no coinciden para ${mentor.name}`);
          return;
        }
        assignedMentors.push({ person_id: personId, email: cred.email.trim(), temporary_password: cred.password });
      } else {
        assignedMentors.push({ person_id: personId });
      }
    }
    const sectors = sectorsText.split(/\n|,/).map((item) => item.trim()).filter(Boolean);
    setSaving(true);
    try {
      const response = await axios.post(
        `${API}/api/mentorship/outreach/campaigns`,
        {
          name: name.trim(), location: location.trim(), start_date: startDate, end_date: endDate, zone_notes: zoneNotes || null,
          meeting_time: meetingTime || null, meeting_place: meetingPlace || null, sectors, instructions: instructions || null,
          assigned_mentors: assignedMentors,
        },
        getAuthHeaders(),
      );
      const created = response.data.accounts_created || [];
      toast.success(created.length ? `Invasión creada · se crearon ${created.length} cuenta(s) de mentor nuevas` : 'Invasión creada');
      reset();
      onOpenChange(false);
      if (onCreated) onCreated();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo crear la invasión'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => { onOpenChange(next); if (!next) reset(); }}>
      <DialogContent className="max-h-[85vh] overflow-y-auto bg-white" data-testid="create-campaign-dialog">
        <DialogHeader>
          <DialogTitle>Crear invasión</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Nombre de la invasión</Label>
            <Input value={name} onChange={(event) => setName(event.target.value)} placeholder="Invasión Sector Norte" data-testid="create-campaign-name-input" />
          </div>
          <div className="space-y-1.5">
            <Label>Lugar</Label>
            <Input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Barrio, sector o dirección general" data-testid="create-campaign-location-input" />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Fecha de inicio</Label>
              <Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} data-testid="create-campaign-date-input" />
            </div>
            <div className="space-y-1.5">
              <Label>Fecha de fin</Label>
              <Input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} data-testid="create-campaign-end-date-input" />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Hora de encuentro</Label>
              <Input type="time" value={meetingTime} onChange={(event) => setMeetingTime(event.target.value)} data-testid="create-campaign-meeting-time-input" />
            </div>
            <div className="space-y-1.5">
              <Label>Lugar de encuentro</Label>
              <Input value={meetingPlace} onChange={(event) => setMeetingPlace(event.target.value)} placeholder="Dónde se reúne el equipo" data-testid="create-campaign-meeting-place-input" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Sectores / lugares a cubrir (uno por línea)</Label>
            <Textarea value={sectorsText} onChange={(event) => setSectorsText(event.target.value)} placeholder={'Sector A\nSector B'} data-testid="create-campaign-sectors-input" />
          </div>
          <div className="space-y-1.5">
            <Label>Instrucciones para los mentores (opcional)</Label>
            <Textarea value={instructions} onChange={(event) => setInstructions(event.target.value)} placeholder="Qué llevar, cómo presentarse, seguridad, etc." data-testid="create-campaign-instructions-input" />
          </div>
          <div className="space-y-1.5">
            <Label>Notas de zona (opcional)</Label>
            <Textarea value={zoneNotes} onChange={(event) => setZoneNotes(event.target.value)} placeholder="Observaciones generales de la semana" data-testid="create-campaign-notes-input" />
          </div>

          {groups.length > 0 && (
            <div className="space-y-1.5 rounded-md border border-dashed border-[#D8D3C8] bg-[#FAF9F5] p-2">
              <Label>Agregar mentores de un Grupo Frontal completo</Label>
              <div className="flex gap-2">
                <Select value={groupId} onValueChange={setGroupId}>
                  <SelectTrigger data-testid="create-campaign-group-select"><SelectValue placeholder="Seleccione una rama" /></SelectTrigger>
                  <SelectContent className="bg-white">
                    {groups.map((group) => <SelectItem key={group.front_group_id} value={group.front_group_id}>{group.display_name || group.name}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Button type="button" variant="outline" disabled={loadingGroup} onClick={addGroupMentors} data-testid="create-campaign-add-group-button">
                  {loadingGroup ? <Loader2 className="h-4 w-4 animate-spin" /> : <Users className="h-4 w-4" />} Agregar grupo
                </Button>
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <Label>Mentores asignados a esta invasión</Label>
            <div className="max-h-72 space-y-2 overflow-y-auto rounded-md border border-[#E8E5DE] p-2" data-testid="create-campaign-mentor-list">
              {combinedOptions.map((mentor) => {
                const blocked = mentorAccountBlocked(mentor);
                const needsAccount = mentorNeedsAccountCreation(mentor);
                const checked = selectedMentors.includes(mentor.person_id);
                return (
                  <div key={mentor.person_id} className="rounded px-1 py-1">
                    <label className={`flex items-center gap-2 text-sm ${blocked ? 'cursor-not-allowed text-slate-400' : 'cursor-pointer text-[#101D36] hover:bg-[#F6F4EF]'}`}>
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={blocked}
                        onChange={() => toggleMentor(mentor.person_id)}
                        data-testid={`create-campaign-mentor-checkbox-${mentor.person_id}`}
                      />
                      {mentor.name}
                      {blocked ? ' (sin acceso)' : ''}
                      {needsAccount ? ' (sin cuenta · se creará ahora)' : ''}
                    </label>
                    {checked && needsAccount && (
                      <div className="ml-6 mt-2 grid gap-2 rounded-md border border-dashed border-[#D8D3C8] bg-[#FAF9F5] p-2 sm:grid-cols-3" data-testid={`create-campaign-mentor-credentials-${mentor.person_id}`}>
                        <Input placeholder="Correo" type="email" value={credentials[mentor.person_id]?.email || ''} onChange={(event) => setCredentialField(mentor.person_id, 'email', event.target.value)} data-testid={`create-campaign-mentor-email-${mentor.person_id}`} />
                        <Input placeholder="Clave temporal" type="password" value={credentials[mentor.person_id]?.password || ''} onChange={(event) => setCredentialField(mentor.person_id, 'password', event.target.value)} data-testid={`create-campaign-mentor-password-${mentor.person_id}`} />
                        <Input placeholder="Confirmar clave" type="password" value={credentials[mentor.person_id]?.confirm || ''} onChange={(event) => setCredentialField(mentor.person_id, 'confirm', event.target.value)} data-testid={`create-campaign-mentor-confirm-${mentor.person_id}`} />
                      </div>
                    )}
                  </div>
                );
              })}
              {combinedOptions.length === 0 && <p className="text-xs text-slate-400">Sin mentores con insignia activa todavía.</p>}
            </div>
            {combinedOptions.some(mentorAccountBlocked) && <p className="text-xs text-slate-500" data-testid="create-campaign-mentor-access-hint">{mentorAccessHint}</p>}
          </div>
          <Button disabled={saving} onClick={submit} className="w-full bg-[#132443]" data-testid="create-campaign-submit-button">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Crear invasión'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
