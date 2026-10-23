import React, { useState } from 'react';

import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '../ui/dialog';
import { Textarea } from '../ui/textarea';

// Etapa 3: nunca crea ni fusiona una Persona 360 en silencio. Si hay una
// coincidencia fuerte/posible, el backend responde 409 con `candidates` y
// este diálogo deja elegir la existente o confirmar (con motivo) que es
// alguien distinto.
export const PersonMatchDialog = ({ match, busy, onPick, onConfirmDistinct, onClose }) => {
  const [reason, setReason] = useState('');
  if (!match) return null;
  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent data-testid="person-match-dialog">
        <DialogHeader><DialogTitle>¿Es la misma persona?</DialogTitle></DialogHeader>
        <p className="text-sm text-slate-600">{match.message}</p>
        <div className="space-y-2">
          {(match.candidates || []).map((candidate) => (
            <div key={candidate.person_id} className="flex items-center justify-between rounded-lg border border-slate-200 p-3" data-testid={`person-match-candidate-${candidate.person_id}`}>
              <div>
                <p className="font-medium text-[#101D36]">{candidate.nombre} {candidate.apellido}</p>
                <p className="text-xs text-slate-500">{candidate.person_number}{candidate.fecha_nacimiento ? ` · ${candidate.fecha_nacimiento}` : ''}</p>
              </div>
              <Button size="sm" disabled={busy} onClick={() => onPick(candidate.person_id)} data-testid={`person-match-use-${candidate.person_id}`}>Usar esta persona</Button>
            </div>
          ))}
        </div>
        {match.requiresConfirmation && (
          <div className="mt-2 space-y-2 border-t border-slate-200 pt-3">
            <Textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Motivo: por qué es una persona distinta (obligatorio)" data-testid="person-match-distinct-reason" />
            <Button variant="outline" disabled={busy || !reason.trim()} onClick={() => onConfirmDistinct(reason)} className="w-full" data-testid="person-match-confirm-distinct-button">Es una persona distinta</Button>
          </div>
        )}
        <DialogFooter><Button variant="ghost" onClick={onClose} data-testid="person-match-cancel-button">Cancelar</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
