import React, { useState } from 'react';
import { Loader2, TicketCheck } from 'lucide-react';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { OperationsPersonPicker } from './OperationsPersonPicker';

export const RegistrationDialog = ({ open, onOpenChange, occurrenceId, selfPersonId, privileged, onRegister, saving, error }) => {
  const [mode, setMode] = useState(selfPersonId && !privileged ? 'self' : 'person'); const [person, setPerson] = useState(null); const [guestName, setGuestName] = useState(''); const [partySize, setPartySize] = useState(1);
  const submit = () => onRegister(mode === 'guest' ? { guest_name: guestName, party_size: Number(partySize) } : { person_id: mode === 'self' ? selfPersonId : person?.person_id, party_size: Number(partySize) });
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="bg-white" data-testid="registration-dialog"><DialogHeader><DialogTitle className="flex items-center gap-2 font-['Spectral'] text-2xl"><TicketCheck className="h-5 w-5 text-blue-700" />Registrar asistencia esperada</DialogTitle><DialogDescription>La inscripción genera un código operativo y evita registros duplicados para Personas 360.</DialogDescription></DialogHeader>
    {error && <p className="border border-red-200 bg-red-50 p-3 text-sm text-red-700" data-testid="registration-error">{error}</p>}
    {privileged && <div className="flex gap-2"><Button type="button" size="sm" variant={mode === 'person' ? 'default' : 'outline'} onClick={() => setMode('person')} data-testid="registration-mode-person">Persona 360</Button><Button type="button" size="sm" variant={mode === 'guest' ? 'default' : 'outline'} onClick={() => setMode('guest')} data-testid="registration-mode-guest">Invitado</Button></div>}
    {mode === 'person' && <OperationsPersonPicker occurrenceId={occurrenceId} selectedId={person?.person_id} onSelect={setPerson} testIdPrefix="registration-person" />}
    {mode === 'self' && <p className="border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900" data-testid="registration-self-message">La inscripción quedará vinculada a su Persona 360.</p>}
    {mode === 'guest' && <div><Label htmlFor="registration-guest-name">Nombre del invitado</Label><Input id="registration-guest-name" value={guestName} onChange={(event) => setGuestName(event.target.value)} data-testid="registration-guest-name-input" /></div>}
    <div><Label htmlFor="registration-party-size">Cantidad de personas</Label><Input id="registration-party-size" type="number" min="1" max="20" value={partySize} onChange={(event) => setPartySize(event.target.value)} data-testid="registration-party-size-input" /></div>
    <DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)} data-testid="registration-cancel-button">Cancelar</Button><Button onClick={submit} disabled={saving || (mode === 'person' && !person) || (mode === 'guest' && !guestName.trim()) || (mode === 'self' && !selfPersonId)} className="bg-blue-700 hover:bg-blue-800" data-testid="registration-submit-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Registrar</Button></DialogFooter>
  </DialogContent></Dialog>;
};