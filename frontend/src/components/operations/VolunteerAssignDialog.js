import React, { useState } from 'react';
import { Loader2, UserPlus } from 'lucide-react';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../ui/dialog';
import { OperationsPersonPicker } from './OperationsPersonPicker';

export const VolunteerAssignDialog = ({ open, onOpenChange, occurrenceId, shift, onAssign, saving, error }) => {
  const [person, setPerson] = useState(null);
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="bg-white" data-testid="volunteer-assign-dialog"><DialogHeader><DialogTitle className="flex items-center gap-2 font-['Spectral'] text-2xl"><UserPlus className="h-5 w-5 text-emerald-700" />Asignar voluntario</DialogTitle><DialogDescription>{shift ? `${shift.name} · ${shift.role_name}` : 'Seleccione un turno y una Persona.'}</DialogDescription></DialogHeader>{error && <p className="border border-red-200 bg-red-50 p-3 text-sm text-red-700" data-testid="volunteer-assign-error">{error}</p>}<OperationsPersonPicker occurrenceId={occurrenceId} selectedId={person?.person_id} onSelect={setPerson} testIdPrefix="volunteer-person" /><DialogFooter><Button type="button" variant="outline" onClick={() => onOpenChange(false)} data-testid="volunteer-assign-cancel-button">Cancelar</Button><Button disabled={!person || saving} onClick={() => onAssign(person)} className="bg-emerald-700 hover:bg-emerald-800" data-testid="volunteer-assign-submit-button">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}Enviar convocatoria</Button></DialogFooter></DialogContent></Dialog>;
};