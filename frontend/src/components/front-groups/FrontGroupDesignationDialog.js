import React, { useState } from 'react';
import axios from 'axios';
import { Loader2, Users } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { PersonQuickPicker } from './PersonQuickPicker';

const SelectedPersonChip = ({ person, onClear }) => <div className="flex items-center justify-between border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm" data-testid={`front-group-selected-person-${person.person_id}`}><span>{person.nombre} {person.apellido}</span><button type="button" onClick={onClear} className="text-xs text-emerald-700 underline">Cambiar</button></div>;

// A3/A4: la pastora (o un líder real sobre esta rama) designa Líder+Colíder;
// el grupo dependiente se crea de inmediato como "pendiente de conformación".
export const FrontGroupDesignationDialog = ({ parentGroupId, onCreated }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false); const [saving, setSaving] = useState(false);
  const [leader, setLeader] = useState(null); const [coLeader, setCoLeader] = useState(null);
  const [reason, setReason] = useState('Designación de pareja de liderazgo');

  const submit = async () => {
    if (!leader) { toast.error('Seleccione a la persona líder'); return; }
    setSaving(true);
    try {
      const response = await axios.post(`${API}/api/front-groups/${parentGroupId}/designations`, {
        leader_person_id: leader.person_id, co_leader_person_id: coLeader?.person_id || null, reason,
      }, getAuthHeaders());
      toast.success('Pareja designada: el nuevo grupo queda pendiente de conformación');
      setOpen(false); setLeader(null); setCoLeader(null);
      await onCreated(response.data);
    } catch (error) {
      toast.error(apiErrorMessage(error, 'No se pudo designar la pareja'));
    } finally { setSaving(false); }
  };

  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button variant="outline" data-testid="front-group-designate-pair-button"><Users className="h-4 w-4" />Designar pareja de liderazgo</Button></DialogTrigger>
    <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto bg-white" data-testid="front-group-designation-dialog">
      <DialogHeader><DialogTitle>Designar pareja de liderazgo</DialogTitle><DialogDescription>Se crea de inmediato el grupo dependiente (pendiente de conformación); el líder designado lo conformará desde su propio portal.</DialogDescription></DialogHeader>
      <div className="space-y-4">
        <div><Label>Líder</Label>{leader ? <SelectedPersonChip person={leader} onClear={() => setLeader(null)} /> : <PersonQuickPicker groupId={parentGroupId} onPicked={setLeader} placeholder="Buscar al líder…" />}</div>
        <div><Label>Colíder (opcional)</Label>{coLeader ? <SelectedPersonChip person={coLeader} onClear={() => setCoLeader(null)} /> : <PersonQuickPicker groupId={parentGroupId} onPicked={setCoLeader} placeholder="Buscar al colíder…" />}</div>
        <div><Label htmlFor="fg-designation-reason">Motivo (opcional)</Label><Input id="fg-designation-reason" value={reason} onChange={(event) => setReason(event.target.value)} data-testid="front-group-designation-reason-input" /></div>
        <Button onClick={submit} disabled={saving || !leader} className="w-full bg-amber-700 text-white hover:bg-amber-800" data-testid="front-group-designation-submit-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Designar pareja</Button>
      </div>
    </DialogContent>
  </Dialog>;
};
