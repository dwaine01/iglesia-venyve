import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Eye, Pencil, Ban, CheckCircle2, Undo2 } from 'lucide-react';

import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '../ui/alert-dialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Checkbox } from '../ui/checkbox';
import { formatUsdCents } from '../../lib/campaignFormat';

export const CampaignDonationHistory = ({ base, getAuthHeaders, donations, onChanged }) => {
  const [busyId, setBusyId] = useState(null);
  const [editing, setEditing] = useState(null);
  const lastActive = donations.find((item) => item.status !== 'voided') || null;

  const run = async (id, fn) => {
    setBusyId(id);
    try { await fn(); await onChanged(); } catch (err) { toast.error(err?.response?.data?.detail || 'No se pudo completar la acción'); }
    finally { setBusyId(null); }
  };

  const showAgain = (id) => run(id, () => axios.post(`${base}/donations/${id}/show`, {}, getAuthHeaders()));
  const markReceived = (id) => run(id, () => axios.post(`${base}/donations/${id}/mark-received`, {}, getAuthHeaders()));
  const voidDonation = (id) => run(id, () => axios.post(`${base}/donations/${id}/void`, {}, getAuthHeaders()));

  const saveEdit = async () => {
    if (!editing) return;
    try {
      await axios.put(`${base}/donations/${editing.donation_id}`, {
        donor_name: editing.anonymous ? null : (editing.donor_name || null),
        amount_cents: editing.amount_cents,
        donation_type: editing.donation_type,
        anonymous: editing.anonymous,
        consent_show_name: editing.anonymous ? false : editing.consent_show_name,
      }, getAuthHeaders());
      toast.success('Donativo actualizado');
      setEditing(null);
      await onChanged();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'No se pudo editar el donativo');
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="campaign-donation-history">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-serif text-lg text-[#132443]">Historial de donativos</h3>
        {lastActive && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button size="sm" variant="outline" className="text-red-600" data-testid="campaign-undo-last-button">
                <Undo2 className="h-4 w-4" />Deshacer última operación
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent className="bg-white">
              <AlertDialogHeader>
                <AlertDialogTitle>¿Deshacer la última donación registrada?</AlertDialogTitle>
                <AlertDialogDescription>
                  Se anulará: {lastActive.anonymous ? 'Anónimo' : (lastActive.donor_name || '—')} · {formatUsdCents(lastActive.amount_cents)}. Puede revertirse editando el historial si fue un error.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel data-testid="campaign-undo-last-cancel">Cancelar</AlertDialogCancel>
                <AlertDialogAction onClick={() => voidDonation(lastActive.donation_id)} data-testid="campaign-undo-last-confirm">Deshacer</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </div>
      <div className="mt-3 max-h-[480px] overflow-y-auto">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Donante</TableHead><TableHead>Monto</TableHead><TableHead>Tipo</TableHead><TableHead>Estado</TableHead><TableHead />
          </TableRow></TableHeader>
          <TableBody>
            {donations.map((item) => (
              <TableRow key={item.donation_id} data-testid={`campaign-donation-row-${item.donation_id}`}>
                <TableCell>{item.anonymous ? 'Anónimo' : (item.donor_name || '—')}</TableCell>
                <TableCell className="font-semibold">{formatUsdCents(item.amount_cents)}</TableCell>
                <TableCell><Badge variant="outline">{item.donation_type === 'received' ? 'Recibido' : 'Promesa'}</Badge></TableCell>
                <TableCell>
                  {item.status === 'voided'
                    ? <Badge className="bg-red-100 text-red-700">Anulado</Badge>
                    : <Badge className="bg-emerald-100 text-emerald-700">Activo</Badge>}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    <Button size="icon" variant="ghost" disabled={busyId === item.donation_id || item.status === 'voided'} title="Mostrar de nuevo" onClick={() => showAgain(item.donation_id)} data-testid={`campaign-show-again-${item.donation_id}`}><Eye className="h-4 w-4" /></Button>
                    {item.donation_type === 'promise' && item.status !== 'voided' && (
                      <Button size="icon" variant="ghost" disabled={busyId === item.donation_id} title="Marcar recibido" onClick={() => markReceived(item.donation_id)} data-testid={`campaign-mark-received-${item.donation_id}`}><CheckCircle2 className="h-4 w-4 text-emerald-600" /></Button>
                    )}
                    {item.status !== 'voided' && (
                      <Button size="icon" variant="ghost" title="Editar" onClick={() => setEditing({ ...item })} data-testid={`campaign-edit-${item.donation_id}`}><Pencil className="h-4 w-4" /></Button>
                    )}
                    {item.status !== 'voided' && (
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button size="icon" variant="ghost" title="Anular" data-testid={`campaign-void-${item.donation_id}`}><Ban className="h-4 w-4 text-red-600" /></Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent className="bg-white">
                          <AlertDialogHeader>
                            <AlertDialogTitle>¿Anular este donativo?</AlertDialogTitle>
                            <AlertDialogDescription>No se eliminará del historial, pero dejará de contar en el total. Esta acción queda auditada.</AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel data-testid={`campaign-void-cancel-${item.donation_id}`}>Cancelar</AlertDialogCancel>
                            <AlertDialogAction onClick={() => voidDonation(item.donation_id)} data-testid={`campaign-void-confirm-${item.donation_id}`}>Anular</AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {donations.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-sm text-slate-400">Aún no hay donativos registrados.</TableCell></TableRow>}
          </TableBody>
        </Table>
      </div>

      <Dialog open={Boolean(editing)} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent className="bg-white" data-testid="campaign-edit-dialog">
          <DialogHeader>
            <DialogTitle>Editar donativo</DialogTitle>
            <DialogDescription>Los cambios quedan registrados en la auditoría de la campaña.</DialogDescription>
          </DialogHeader>
          {editing && (
            <div className="space-y-3">
              <div>
                <Label>Nombre</Label>
                <Input value={editing.donor_name || ''} disabled={editing.anonymous} onChange={(e) => setEditing({ ...editing, donor_name: e.target.value })} data-testid="campaign-edit-name-input" />
              </div>
              <div>
                <Label>Monto (USD)</Label>
                <Input type="number" min="0.01" step="0.01" value={(editing.amount_cents / 100).toFixed(2)} onChange={(e) => setEditing({ ...editing, amount_cents: Math.round(parseFloat(e.target.value || 0) * 100) })} data-testid="campaign-edit-amount-input" />
              </div>
              <div>
                <Label>Tipo</Label>
                <Select value={editing.donation_type} onValueChange={(v) => setEditing({ ...editing, donation_type: v })}>
                  <SelectTrigger data-testid="campaign-edit-type-select"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-white">
                    <SelectItem value="received">Recibido</SelectItem>
                    <SelectItem value="promise">Promesa</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox checked={editing.anonymous} onCheckedChange={(v) => setEditing({ ...editing, anonymous: Boolean(v), consent_show_name: v ? false : editing.consent_show_name })} data-testid="campaign-edit-anonymous-checkbox" />
                  Anónimo
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox checked={editing.consent_show_name} disabled={editing.anonymous} onCheckedChange={(v) => setEditing({ ...editing, consent_show_name: Boolean(v) })} data-testid="campaign-edit-consent-checkbox" />
                  Autoriza mostrar nombre
                </label>
              </div>
              <Button className="w-full bg-[#132443]" onClick={saveEdit} data-testid="campaign-edit-save-button">Guardar cambios</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};
