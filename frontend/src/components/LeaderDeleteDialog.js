import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, Loader2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { errorDetailText } from '../lib/errorText';

const plain = (value) => (value || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();

// Eliminación PERMANENTE de la cuenta de un líder (solo autoridad pastoral;
// el backend lo valida). Las personas y su Persona 360 se conservan.
export function LeaderDeleteDialog({ leader, onClose, onDeleted }) {
  const { API, getAuthHeaders } = useAuth();
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [confirmName, setConfirmName] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setPreview(null); setError(''); setConfirmName('');
    if (!leader) return;
    axios.get(`${API}/api/pastor/leaders/${leader._id}/delete-preview`, getAuthHeaders())
      .then((response) => setPreview(response.data))
      .catch((requestError) => setError(errorDetailText(requestError, 'No se pudo preparar la eliminación')));
  }, [API, getAuthHeaders, leader]);

  const matches = preview && plain(confirmName) === plain(preview.name);
  const submit = async () => {
    setDeleting(true);
    try {
      const response = await axios.delete(`${API}/api/pastor/leaders/${leader._id}`, { ...getAuthHeaders(), data: { confirm_name: confirmName } });
      toast.success(`Cuenta de ${preview.name} eliminada. ${response.data.people_unassigned} persona(s) quedaron sin líder para reasignar.`);
      onDeleted?.();
      onClose();
    } catch (requestError) { toast.error(errorDetailText(requestError, 'No se pudo eliminar la cuenta')); } finally { setDeleting(false); }
  };

  return (
    <Dialog open={Boolean(leader)} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="max-h-[92vh] overflow-y-auto bg-white sm:max-w-lg" data-testid="leader-delete-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-red-700"><AlertTriangle className="h-5 w-5" />Eliminar cuenta de líder</DialogTitle>
          <DialogDescription>Esta acción es permanente: la cuenta y su acceso se borran y no se pueden recuperar.</DialogDescription>
        </DialogHeader>
        {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
        {!preview && !error && <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" />}
        {preview && <div className="space-y-4">
          <dl className="space-y-1 rounded-lg border border-[#E7E2D6] bg-[#FAFAF8] p-3 text-sm" data-testid="leader-delete-summary">
            <div className="flex justify-between gap-3"><dt className="text-slate-500">Nombre</dt><dd className="text-right font-semibold text-[#1B2A4A]">{preview.name}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-slate-500">Correo</dt><dd className="break-all text-right font-medium text-[#1B2A4A]">{preview.email}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-slate-500">Personas asignadas</dt><dd className="text-right font-semibold text-[#1B2A4A]" data-testid="leader-delete-people">{preview.people_assigned}</dd></div>
          </dl>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
            <li>Las <b>{preview.people_assigned}</b> persona(s) y todo su historial en Persona 360 se conservan; quedan <b>sin líder</b> y aparecen en el Panel General para reasignarlas.</li>
            <li>Su ficha de Persona 360 también se conserva (solo se borra la cuenta de acceso).</li>
            {(preview.groups_led > 0 || preview.front_group_assignments > 0) && <li>Deja de figurar en {preview.groups_led > 0 ? `${preview.groups_led} grupo(s) frontal(es) que lidera` : 'sus grupos frontales'}; esos grupos quedan con el líder «por definir».</li>}
            {preview.active_invasions.length > 0 && <li>Sale de las invasiones activas: {preview.active_invasions.join(', ')} (si ya registró visitas, se conserva como historial).</li>}
            {preview.mentor_badge_active && <li>Su insignia de mentor se desactiva.</li>}
            <li>Queda registrado en el Historial de borrados.</li>
          </ul>
          <div className="space-y-1.5">
            <Label htmlFor="leader-delete-confirm">Para confirmar, escribe el nombre del líder: <b>{preview.name}</b></Label>
            <Input id="leader-delete-confirm" value={confirmName} onChange={(event) => setConfirmName(event.target.value)} autoComplete="off" className="h-12 text-base" data-testid="leader-delete-confirm-input" />
          </div>
        </div>}
        <DialogFooter className="grid grid-cols-2 gap-2 sm:flex">
          <Button variant="outline" className="min-h-12" onClick={onClose}>Cancelar</Button>
          <Button className="min-h-12 bg-red-600 text-white hover:bg-red-700" disabled={!matches || deleting} onClick={submit} data-testid="leader-delete-submit">
            {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}Eliminar cuenta
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
