import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Eye, Pencil, Ban, CheckCircle2, Undo2, Trash2, ShieldCheck, Search, AlertTriangle, Phone, Mail, MessageSquare, StickyNote, Sparkles } from 'lucide-react';

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
import { Textarea } from '../ui/textarea';
import { formatUsdCents, normalizeSearchText } from '../../lib/campaignFormat';
import { useAuth } from '../../context/AuthContext';
import { hasCapability, isPastoralAuthority } from '../../lib/accessControl';

export const CampaignDonationHistory = ({ base, getAuthHeaders, donations, onChanged }) => {
  const { user } = useAuth();
  // «Recibido» (pasa a Finanzas) lo confirma solo el encargado de la campaña; la pastora no (el servidor también lo exige).
  const canReceive = hasCapability(user, 'campaign.venycome.manage') && !isPastoralAuthority(user);
  const [busyId, setBusyId] = useState(null);
  const [editing, setEditing] = useState(null);
  const [verifying, setVerifying] = useState(null);
  const [verifyMethod, setVerifyMethod] = useState('zelle');
  const [search, setSearch] = useState('');
  const [paymentFilter, setPaymentFilter] = useState('all');
  const [contactingId, setContactingId] = useState(null);
  const [contactInfo, setContactInfo] = useState(null);
  const [noteText, setNoteText] = useState('');
  const [savingNote, setSavingNote] = useState(false);
  const [aiDraft, setAiDraft] = useState('');
  const [draftingThanks, setDraftingThanks] = useState(false);
  const lastActive = donations.find((item) => item.status !== 'voided') || null;
  const isPendingVerification = (item) => item.donation_type === 'received' && item.status !== 'voided' && !item.verified;
  const pendingCount = donations.filter(isPendingVerification).length;
  const normalizedSearch = normalizeSearchText(search);
  const contactingItem = donations.find((item) => item.donation_id === contactingId) || null;
  const visibleDonations = donations
    .filter((item) => (normalizedSearch ? normalizeSearchText(item.anonymous ? 'anónimo' : (item.donor_name || '')).includes(normalizedSearch) : true))
    .filter((item) => {
      if (paymentFilter === 'paid') return Boolean(item.verified);
      if (paymentFilter === 'unpaid') return !item.verified && item.status !== 'voided';
      return true;
    });

  const run = async (id, fn) => {
    setBusyId(id);
    try { await fn(); await onChanged(); } catch (err) { toast.error(err?.response?.data?.detail || 'No se pudo completar la acción'); }
    finally { setBusyId(null); }
  };

  const showAgain = (id) => run(id, () => axios.post(`${base}/donations/${id}/show`, {}, getAuthHeaders()));
  const voidDonation = (id) => run(id, () => axios.post(`${base}/donations/${id}/void`, {}, getAuthHeaders()));
  const deleteDonation = (id) => run(id, () => axios.delete(`${base}/donations/${id}`, getAuthHeaders()));
  const unverifyDonation = (id) => run(id, async () => {
    await axios.post(`${base}/donations/${id}/unverify`, {}, getAuthHeaders());
    toast.success('Verificación revertida: el depósito en Finanzas fue anulado/revertido');
  });

  const openContact = async (item) => {
    setContactingId(item.donation_id);
    setContactInfo(null);
    setNoteText('');
    setAiDraft('');
    try {
      const { data } = await axios.get(`${base}/donations/${item.donation_id}/contact`, getAuthHeaders());
      setContactInfo(data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'No se pudo cargar la información de contacto');
    }
  };

  const generateThanks = async () => {
    if (!contactingItem?.person_id) return;
    setDraftingThanks(true);
    try {
      const { data } = await axios.post(`${base}/messages/draft`, {
        kind: 'thank_you', person_id: contactingItem.person_id, name: contactingItem.donor_name, amount_cents: contactingItem.amount_cents,
      }, getAuthHeaders());
      setAiDraft(data.text);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'No se pudo redactar el mensaje');
    } finally {
      setDraftingThanks(false);
    }
  };

  const saveNote = async () => {
    if (!contactingId || !noteText.trim()) return;
    setSavingNote(true);
    try {
      await axios.post(`${base}/donations/${contactingId}/notes`, { text: noteText.trim() }, getAuthHeaders());
      setNoteText('');
      toast.success('Nota guardada');
      await onChanged();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'No se pudo guardar la nota');
    } finally {
      setSavingNote(false);
    }
  };

  const smsHref = (phone, body) => `sms:${phone}?body=${encodeURIComponent(body)}`;
  const contactMessage = (item, info) => `Hola${item?.anonymous ? '' : ` ${item?.donor_name || ''}`}, para completar tu donativo de ${formatUsdCents(item?.amount_cents)} a la campaña Ven y Come puedes enviarlo por Zelle a: ${info?.zelle_info || '(pendiente de configurar)'}. ¡Gracias!`;

  const confirmVerify = async () => {
    if (!verifying) return;
    await run(verifying.donation_id, async () => {
      await axios.post(`${base}/donations/${verifying.donation_id}/receive`, { payment_method: verifyMethod }, getAuthHeaders());
      toast.success('Recibido: pasó a la colecta «Ven y Come» de Finanzas; allí lo cuadran y lo valida una segunda persona');
    });
    setVerifying(null);
  };

  const saveEdit = async () => {
    if (!editing) return;
    try {
      await axios.put(`${base}/donations/${editing.donation_id}`, {
        donor_name: editing.anonymous ? null : (editing.donor_name || null),
        person_id: editing.anonymous ? null : (editing.person_id || null),
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
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar donante por nombre…"
            className="pl-9"
            data-testid="campaign-donation-search-input"
          />
        </div>
        <Select value={paymentFilter} onValueChange={setPaymentFilter}>
          <SelectTrigger className="sm:w-48" data-testid="campaign-payment-filter-select"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-white">
            <SelectItem value="all">Todos</SelectItem>
            <SelectItem value="paid">Pagados (verificados)</SelectItem>
            <SelectItem value="unpaid">Pendientes de pago</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {pendingCount > 0 && (
        <div className="mt-3 flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800" data-testid="campaign-pending-verification-alert">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>
            {pendingCount === 1 ? '1 donativo recibido está' : `${pendingCount} donativos recibidos están`} pendiente{pendingCount === 1 ? '' : 's'} de verificar. Recuerda sellarlos para que se reflejen en Finanzas (Pro-Templo).
          </span>
        </div>
      )}
      <div className="mt-3 max-h-[480px] overflow-y-auto">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Donante</TableHead><TableHead>Monto</TableHead><TableHead>Tipo</TableHead><TableHead>Estado</TableHead><TableHead />
          </TableRow></TableHeader>
          <TableBody>
            {visibleDonations.map((item) => (
              <TableRow
                key={item.donation_id}
                data-testid={`campaign-donation-row-${item.donation_id}`}
                className={isPendingVerification(item) ? 'border-l-4 border-l-amber-400 bg-amber-50/60' : ''}
              >
                <TableCell>{item.anonymous ? 'Anónimo' : (item.donor_name || '—')} {item.person_id && !item.anonymous && <Badge variant="outline" className="ml-1 border-emerald-300 text-emerald-700" data-testid={`campaign-person-linked-badge-${item.donation_id}`}>360</Badge>}</TableCell>
                <TableCell className="font-semibold">{formatUsdCents(item.amount_cents)}</TableCell>
                <TableCell><Badge variant="outline">{item.donation_type === 'received' ? 'Recibido' : 'Promesa'}</Badge></TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {item.status === 'voided'
                      ? <Badge className="bg-red-100 text-red-700">Anulado</Badge>
                      : <Badge className="bg-emerald-100 text-emerald-700">Activo</Badge>}
                    {item.verified && (
                      <Badge className="bg-[#132443] text-white" data-testid={`campaign-verified-badge-${item.donation_id}`}>
                        <ShieldCheck className="mr-1 h-3 w-3 inline" />Verificado · {item.verified_payment_method === 'zelle' ? 'Zelle' : 'Efectivo'}
                      </Badge>
                    )}
                    {item.verified && canReceive && (
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <button
                            type="button"
                            disabled={busyId === item.donation_id}
                            className="text-[10px] text-slate-400 underline decoration-dotted underline-offset-2 hover:text-amber-600 disabled:opacity-50"
                            title="Revertir verificación (solo si fue un error)"
                            data-testid={`campaign-unverify-${item.donation_id}`}
                          >
                            fue un error, revertir
                          </button>
                        </AlertDialogTrigger>
                        <AlertDialogContent className="bg-white">
                          <AlertDialogHeader>
                            <AlertDialogTitle>¿Revertir esta verificación?</AlertDialogTitle>
                            <AlertDialogDescription>
                              Esto anulará/revertirá el depósito que se envió a Finanzas (fondo Pro-Templo) para {item.anonymous ? 'este donante anónimo' : (item.donor_name || 'este donante')} ({formatUsdCents(item.amount_cents)}), y el donativo quedará activo de nuevo para poder editarlo, anularlo o verificarlo correctamente.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel data-testid={`campaign-unverify-cancel-${item.donation_id}`}>Cancelar</AlertDialogCancel>
                            <AlertDialogAction onClick={() => unverifyDonation(item.donation_id)} data-testid={`campaign-unverify-confirm-${item.donation_id}`}>Revertir verificación</AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    )}
                    {isPendingVerification(item) && (
                      <Badge className="bg-amber-100 text-amber-800" data-testid={`campaign-pending-badge-${item.donation_id}`}>
                        <AlertTriangle className="mr-1 h-3 w-3 inline" />Sin verificar
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    {item.person_id && !item.anonymous && item.status !== 'voided' && (
                      <Button size="icon" variant="ghost" className="relative" title="Contacto rápido (llamar, mensajear, notas)" onClick={() => openContact(item)} data-testid={`campaign-contact-${item.donation_id}`}>
                        <Phone className="h-4 w-4 text-[#132443]" />
                        {item.contact_notes?.length > 0 && (
                          <span className="absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-[#B5953F] text-[9px] font-bold text-white" data-testid={`campaign-contact-notes-count-${item.donation_id}`}>
                            {item.contact_notes.length}
                          </span>
                        )}
                      </Button>
                    )}
                    <Button size="icon" variant="ghost" disabled={busyId === item.donation_id || item.status === 'voided'} title="Mostrar de nuevo" onClick={() => showAgain(item.donation_id)} data-testid={`campaign-show-again-${item.donation_id}`}><Eye className="h-4 w-4" /></Button>
                    {canReceive && item.status !== 'voided' && !item.verified && (
                      <Button size="sm" variant="outline" disabled={busyId === item.donation_id} title="El dinero llegó: pasa a Finanzas" onClick={() => { setVerifying(item); setVerifyMethod('cash'); }} data-testid={`campaign-receive-${item.donation_id}`}>
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />Recibido
                      </Button>
                    )}
                    {item.status !== 'voided' && !item.verified && (
                      <Button size="icon" variant="ghost" title="Editar" onClick={() => setEditing({ ...item })} data-testid={`campaign-edit-${item.donation_id}`}><Pencil className="h-4 w-4" /></Button>
                    )}
                    {item.status !== 'voided' && !item.verified && (
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
                    {!item.verified && (
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button size="icon" variant="ghost" title="Borrar (duplicado o error)" data-testid={`campaign-delete-${item.donation_id}`}><Trash2 className="h-4 w-4 text-red-600" /></Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent className="bg-white">
                          <AlertDialogHeader>
                            <AlertDialogTitle>¿Borrar este donativo del historial?</AlertDialogTitle>
                            <AlertDialogDescription>Se eliminará por completo (útil para registros duplicados o por error). Esta acción no se puede deshacer.</AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel data-testid={`campaign-delete-cancel-${item.donation_id}`}>Cancelar</AlertDialogCancel>
                            <AlertDialogAction onClick={() => deleteDonation(item.donation_id)} data-testid={`campaign-delete-confirm-${item.donation_id}`}>Borrar</AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {visibleDonations.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-sm text-slate-400">{normalizedSearch || paymentFilter !== 'all' ? 'Ningún donativo coincide con el filtro.' : 'Aún no hay donativos registrados.'}</TableCell></TableRow>}
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

      <Dialog open={Boolean(verifying)} onOpenChange={(open) => !open && setVerifying(null)}>
        <DialogContent className="bg-white" data-testid="campaign-verify-dialog">
          <DialogHeader>
            <DialogTitle>Recibido: pasar a Finanzas</DialogTitle>
            <DialogDescription>
              Confirma que el dinero de {verifying?.anonymous ? 'este donante anónimo' : (verifying?.donor_name || 'este donante')} ({formatUsdCents(verifying?.amount_cents)}) ya llegó a la cuenta.
              Entra como aporte a la colecta «Ven y Come» del día en Finanzas (fondo Pro-Templo). El efectivo se entrega a Finanzas para contarlo; el Zelle debe coincidir con la transacción del banco. Cuenta como ingreso cuando una segunda persona valida la colecta.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label>Método de pago</Label>
            <Select value={verifyMethod} onValueChange={setVerifyMethod}>
              <SelectTrigger data-testid="campaign-verify-method-select"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-white">
                <SelectItem value="zelle">Zelle</SelectItem>
                <SelectItem value="cash">Efectivo</SelectItem>
              </SelectContent>
            </Select>
            <Button className="w-full bg-[#132443]" onClick={confirmVerify} data-testid="campaign-verify-confirm-button">
              <ShieldCheck className="h-4 w-4" />Recibido · pasar a Finanzas
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(contactingId)} onOpenChange={(open) => !open && setContactingId(null)}>
        <DialogContent className="bg-white" data-testid="campaign-contact-dialog">
          <DialogHeader>
            <DialogTitle>Contacto rápido{contactingItem ? ` · ${contactingItem.donor_name || 'Donante'}` : ''}</DialogTitle>
            <DialogDescription>
              {contactingItem && `${formatUsdCents(contactingItem.amount_cents)} · ${contactingItem.donation_type === 'received' ? 'Recibido' : 'Promesa'}${contactingItem.verified ? ' · Verificado' : ''}`}
            </DialogDescription>
          </DialogHeader>
          {!contactInfo && <p className="text-sm text-slate-400" data-testid="campaign-contact-loading">Cargando información de contacto…</p>}
          {contactInfo && (
            <div className="space-y-4">
              <div className="space-y-2 rounded-lg border border-slate-200 p-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2 text-slate-600"><Phone className="h-4 w-4" />{contactInfo.phone || 'Sin teléfono registrado'}</span>
                  {contactInfo.phone && (
                    <div className="flex gap-1">
                      <a href={`tel:${contactInfo.phone}`} data-testid="campaign-contact-call-link"><Button size="sm" variant="outline"><Phone className="h-3.5 w-3.5" />Llamar</Button></a>
                      <a href={smsHref(contactInfo.phone, contactMessage(contactingItem, contactInfo))} data-testid="campaign-contact-sms-link"><Button size="sm" variant="outline"><MessageSquare className="h-3.5 w-3.5" />Mensaje con Zelle</Button></a>
                    </div>
                  )}
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2 text-slate-600"><Mail className="h-4 w-4" />{contactInfo.email || 'Sin correo registrado'}</span>
                  {contactInfo.email && <a href={`mailto:${contactInfo.email}`} data-testid="campaign-contact-email-link"><Button size="sm" variant="outline">Correo</Button></a>}
                </div>
                <p className="text-xs text-slate-400">Zelle de la iglesia: {contactInfo.zelle_info || 'No configurado aún en Configuración de campaña.'}</p>
              </div>

              {contactInfo.phone && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="flex items-center gap-2"><Sparkles className="h-4 w-4" />Mensaje de agradecimiento</Label>
                    <Button size="sm" variant="outline" disabled={draftingThanks} onClick={generateThanks} data-testid="campaign-contact-thankyou-draft-button">
                      {draftingThanks ? 'Generando…' : 'Generar mensaje'}
                    </Button>
                  </div>
                  {aiDraft && (
                    <div className="space-y-2">
                      <Textarea value={aiDraft} onChange={(e) => setAiDraft(e.target.value)} rows={3} data-testid="campaign-contact-thankyou-text" />
                      <a href={smsHref(contactInfo.phone, aiDraft)} data-testid="campaign-contact-thankyou-sms-link">
                        <Button size="sm" variant="outline"><MessageSquare className="h-3.5 w-3.5" />Enviar agradecimiento por SMS</Button>
                      </a>
                    </div>
                  )}
                </div>
              )}

              <div className="space-y-2">
                <Label className="flex items-center gap-2"><StickyNote className="h-4 w-4" />Nota de seguimiento</Label>
                <Textarea
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Ej: Dijo que manda el dinero mañana por Zelle a las 6pm."
                  data-testid="campaign-contact-note-input"
                />
                <Button size="sm" disabled={savingNote || !noteText.trim()} onClick={saveNote} data-testid="campaign-contact-note-save-button">Guardar nota</Button>
              </div>

              <div className="max-h-48 space-y-2 overflow-y-auto" data-testid="campaign-contact-notes-list">
                {(contactingItem?.contact_notes || []).slice().reverse().map((note) => (
                  <div key={note.note_id} className="rounded-lg bg-slate-50 p-2 text-sm" data-testid={`campaign-contact-note-${note.note_id}`}>
                    <p className="text-slate-700">{note.text}</p>
                    <p className="mt-1 text-xs text-slate-400">{note.created_by_name} · {new Date(note.created_at).toLocaleString('es-US', { dateStyle: 'short', timeStyle: 'short' })}</p>
                  </div>
                ))}
                {(!contactingItem?.contact_notes || contactingItem.contact_notes.length === 0) && (
                  <p className="text-xs text-slate-400">Aún no hay notas para este donativo.</p>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};
