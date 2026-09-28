import React, { useState } from 'react';
import axios from 'axios';
import { ArrowLeft, BookOpen, Loader2, RotateCcw, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { canManageLibraryInventory } from '../../lib/accessControl';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Textarea } from '../../components/ui/textarea';
import { BookThumbnail } from '../../components/library/BookThumbnail';
import { ScannerInput } from '../../components/library/ScannerInput';

const PAYMENT_LABELS = { pagado: 'Pagado', pendiente: 'Pendiente', exonerado: 'Exonerado', beca: 'Beca', descuento: 'Descuento', pago_parcial: 'Pago parcial', no_aplica: 'Gratis' };
const MATERIAL_STATUS_LABEL = { received: 'Recibido', reserved: 'Reservado', pending: 'Pendiente' };

export default function LibraryScanPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const [step, setStep] = useState('material');
  const [material, setMaterial] = useState(null);
  const [materialScanMethod, setMaterialScanMethod] = useState('MANUAL');
  const [action, setAction] = useState(null);
  const [person, setPerson] = useState(null);
  const [personScanMethod, setPersonScanMethod] = useState('MANUAL');
  const [snapshot, setSnapshot] = useState(null);
  const [searchResults, setSearchResults] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [users, setUsers] = useState([]);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ quantity: '1', payment_status: 'no_aplica', amount_paid: '0', payment_method: 'efectivo', notes: '', target_user_id: '' });
  const [matchingPOs, setMatchingPOs] = useState([]);
  const [selectedPO, setSelectedPO] = useState(null);
  const [receivePoQty, setReceivePoQty] = useState('1');

  const reset = () => {
    setStep('material'); setMaterial(null); setAction(null); setPerson(null); setSnapshot(null);
    setSearchResults([]); setSearchQuery(''); setForm({ quantity: '1', payment_status: 'no_aplica', amount_paid: '0', payment_method: 'efectivo', notes: '', target_user_id: '' });
    setMatchingPOs([]); setSelectedPO(null); setReceivePoQty('1');
  };

  const onMaterialCode = async (code, method) => {
    try {
      const { data } = await axios.get(`${API}/api/library/scan/resolve-material`, { ...getAuthHeaders(), params: { code } });
      setMaterial(data); setMaterialScanMethod(method);
      setForm((f) => ({ ...f, payment_status: data.member_price_cents ? 'pendiente' : 'no_aplica', amount_paid: data.member_price_cents ? String((data.member_price_cents / 100).toFixed(2)) : '0' }));
      setStep('action');
    } catch { toast.error('No se encontró ningún material con ese código. Intente buscar manualmente.'); }
  };

  const searchMaterial = async (query) => {
    setSearchQuery(query);
    if (query.trim().length < 2) return setSearchResults([]);
    const { data } = await axios.get(`${API}/api/library/books`, { ...getAuthHeaders(), params: { active: true } });
    setSearchResults((data.items || []).filter((b) => b.name.toLowerCase().includes(query.toLowerCase())).slice(0, 8));
  };

  const pickMaterial = (book) => { setMaterial({ ...book, available_central: undefined }); setMaterialScanMethod('MANUAL'); setStep('action'); setForm((f) => ({ ...f, payment_status: book.member_price_cents ? 'pendiente' : 'no_aplica', amount_paid: book.member_price_cents ? String((book.member_price_cents / 100).toFixed(2)) : '0' })); };

  const chooseAction = async (nextAction) => {
    setAction(nextAction);
    if (nextAction === 'transfer' && users.length === 0) {
      const { data } = await axios.get(`${API}/api/core/governance/users`, getAuthHeaders()).catch(() => ({ data: { items: [] } }));
      setUsers(data.items || []);
    }
    if (nextAction === 'receive_po') {
      const [ordered, partial] = await Promise.all([
        axios.get(`${API}/api/library/purchase-orders`, { ...getAuthHeaders(), params: { status: 'ordered' } }),
        axios.get(`${API}/api/library/purchase-orders`, { ...getAuthHeaders(), params: { status: 'partially_received' } }),
      ]);
      const all = [...(ordered.data.items || []), ...(partial.data.items || [])];
      setMatchingPOs(all.filter((po) => po.lines.some((l) => l.book_id === material.book_id)));
      return setStep('receive_po');
    }
    setStep(nextAction === 'lookup' ? 'lookup' : nextAction === 'transfer' ? 'confirm' : 'person');
  };

  const confirmReceivePo = async () => {
    if (!selectedPO) return toast.error('Seleccione una orden de compra');
    setBusy(true);
    try {
      await axios.post(`${API}/api/library/purchase-orders/${selectedPO.po_id}/receive`, {
        lines: [{ book_id: material.book_id, quantity_received_now: Number(receivePoQty || 0) }], scan_method: materialScanMethod,
      }, getAuthHeaders());
      toast.success(`Recepción registrada en ${selectedPO.po_number}`); reset();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo registrar la recepción'); }
    finally { setBusy(false); }
  };

  const onPersonCode = async (code, method) => {
    try {
      const { data } = await axios.post(`${API}/api/library/scan/resolve-person`, { code }, getAuthHeaders());
      await selectPerson(data, method);
    } catch { toast.error('No se encontró ninguna persona con ese código. Intente la búsqueda manual.'); }
  };

  const searchPerson = async (query) => {
    setSearchQuery(query);
    if (query.trim().length < 2) return setSearchResults([]);
    const { data } = await axios.get(`${API}/api/library/scan/search-person`, { ...getAuthHeaders(), params: { q: query } });
    setSearchResults(data.items || []);
  };

  const selectPerson = async (personData, method = 'MANUAL') => {
    setPerson(personData); setPersonScanMethod(method); setSearchResults([]); setSearchQuery('');
    const { data } = await axios.get(`${API}/api/library/scan/persons/${personData.person_id}/library-snapshot`, getAuthHeaders());
    setSnapshot(data);
    setStep('confirm');
  };

  const confirmDeliver = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/library/persons/${person.person_id}/deliver`, {
        book_id: material.book_id, quantity: Number(form.quantity || 1), process_key: material.process_key,
        payment_status: form.payment_status, amount_paid_cents: ['pagado', 'pago_parcial'].includes(form.payment_status) ? Math.round(Number(form.amount_paid || 0) * 100) : 0,
        payment_method: form.payment_method, notes: form.notes, scan_method: materialScanMethod !== 'MANUAL' ? materialScanMethod : personScanMethod,
      }, getAuthHeaders());
      toast.success(`Material entregado a ${person.display_name}`); reset();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo confirmar la entrega'); }
    finally { setBusy(false); }
  };

  const confirmReturn = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/library/movements`, {
        book_id: material.book_id, movement_type: 'RETURN', quantity: Number(form.quantity || 1),
        from_holder: { type: 'person', id: person.person_id }, to_holder: { type: 'warehouse', id: 'central' },
        person_id: person.person_id, notes: form.notes, scan_method: materialScanMethod !== 'MANUAL' ? materialScanMethod : personScanMethod,
      }, getAuthHeaders());
      toast.success('Devolución registrada'); reset();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo registrar la devolución'); }
    finally { setBusy(false); }
  };

  const confirmTransfer = async () => {
    if (!form.target_user_id) return toast.error('Seleccione a quién transferir');
    setBusy(true);
    try {
      await axios.post(`${API}/api/library/movements`, {
        book_id: material.book_id, movement_type: 'TRANSFER', quantity: Number(form.quantity || 1),
        from_holder: { type: 'warehouse', id: 'central' }, to_holder: { type: 'user', id: form.target_user_id },
        notes: form.notes, scan_method: materialScanMethod,
      }, getAuthHeaders());
      toast.success('Transferencia registrada'); reset();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo transferir el material'); }
    finally { setBusy(false); }
  };

  return <main className="min-h-screen bg-[#F4F1EA] px-4 py-6 sm:px-8" data-testid="library-scan-page">
    <div className="mx-auto max-w-3xl space-y-5">
      <header className="flex items-center justify-between">
        <div><Link to="/libreria" className="text-sm text-[#0879BE]">← Librería 360</Link><h1 className="font-serif text-3xl text-[#132443]">Escanear</h1></div>
        {step !== 'material' && <Button variant="outline" size="sm" onClick={reset} data-testid="scan-restart-button"><RotateCcw className="h-4 w-4" />Empezar de nuevo</Button>}
      </header>

      {step === 'material' && <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4" data-testid="scan-step-material">
        <h2 className="font-serif text-lg text-[#132443]">1. Escanee o busque el material</h2>
        <ScannerInput onDetected={onMaterialCode} testIdPrefix="material-scanner" placeholder="Código QR/barras del material" />
        <div className="flex items-center gap-2"><Search className="h-4 w-4 text-slate-400" /><Input value={searchQuery} onChange={(e) => searchMaterial(e.target.value)} placeholder="…o busque por nombre" data-testid="material-search-input" /></div>
        {searchResults.length > 0 && <ul className="rounded-lg border divide-y" data-testid="material-search-results">{searchResults.map((b) => <li key={b.book_id} className="flex cursor-pointer items-center gap-2 p-2 hover:bg-slate-50" onClick={() => pickMaterial(b)} data-testid={`material-search-result-${b.book_id}`}><BookThumbnail fileId={b.cover_file_id} size={28} />{b.name}</li>)}</ul>}
      </div>}

      {step === 'action' && material && <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4" data-testid="scan-step-action">
        <h2 className="font-serif text-lg text-[#132443]">2. Material identificado</h2>
        <div className="flex items-center gap-3"><BookThumbnail fileId={material.cover_file_id} size={64} /><div><p className="font-medium" data-testid="scan-material-name">{material.name}</p><p className="text-sm text-slate-500">{material.process_key || 'Sin proceso'} · {material.member_price_cents ? `$${(material.member_price_cents / 100).toFixed(2)}` : 'Gratis'}</p>{material.available_central !== undefined && <p className="text-xs text-slate-500">Disponible en central: {material.available_central}</p>}</div></div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <Button onClick={() => chooseAction('deliver')} className="bg-[#132443]" data-testid="scan-action-deliver"><BookOpen className="h-4 w-4" />Entregar</Button>
          <Button onClick={() => chooseAction('transfer')} variant="outline" data-testid="scan-action-transfer">Transferir</Button>
          <Button onClick={() => chooseAction('return')} variant="outline" data-testid="scan-action-return">Recibir devolución</Button>
          <Button onClick={() => chooseAction('lookup')} variant="outline" data-testid="scan-action-lookup">Consultar ficha</Button>
          {canManageLibraryInventory(user) && <Button onClick={() => chooseAction('receive_po')} variant="outline" data-testid="scan-action-receive-po">Recibir de OC</Button>}
        </div>
      </div>}

      {step === 'receive_po' && material && <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4" data-testid="scan-step-receive-po">
        <h2 className="font-serif text-lg text-[#132443]">Recibir de una orden de compra</h2>
        {matchingPOs.length === 0 ? <p className="text-sm text-slate-500" data-testid="receive-po-empty">No hay órdenes abiertas (ordenadas o parcialmente recibidas) que incluyan este material.</p> : <>
          <ul className="divide-y rounded-lg border" data-testid="receive-po-list">{matchingPOs.map((po) => <li key={po.po_id} className={`cursor-pointer p-2 text-sm ${selectedPO?.po_id === po.po_id ? 'bg-slate-100' : ''}`} onClick={() => setSelectedPO(po)} data-testid={`receive-po-option-${po.po_id}`}>{po.po_number} · {po.provider_name}</li>)}</ul>
          {selectedPO && <div><Label>Cantidad a recibir ahora</Label><Input type="number" min="1" value={receivePoQty} onChange={(e) => setReceivePoQty(e.target.value)} data-testid="receive-po-quantity-input" />
            <Button className="mt-3 w-full bg-[#132443]" disabled={busy} onClick={confirmReceivePo} data-testid="receive-po-confirm-button">{busy && <Loader2 className="h-4 w-4 animate-spin" />}CONFIRMAR RECEPCIÓN</Button>
          </div>}
        </>}
      </div>}

      {step === 'lookup' && material && <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-2" data-testid="scan-step-lookup">
        <h2 className="font-serif text-lg text-[#132443]">Ficha del material</h2>
        <p><strong>SKU:</strong> {material.sku || '—'}</p><p><strong>Proceso:</strong> {material.process_key || '—'}</p>
        <p><strong>Precio de lista:</strong> {material.member_price_cents ? `$${(material.member_price_cents / 100).toFixed(2)}` : 'Gratis'}</p>
        <p><strong>Ubicación:</strong> {material.location || '—'}</p>
      </div>}

      {step === 'person' && <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4" data-testid="scan-step-person">
        <h2 className="font-serif text-lg text-[#132443]">3. Escanee o busque a la persona</h2>
        <ScannerInput onDetected={onPersonCode} testIdPrefix="person-scanner" placeholder="QR del carnet, número de miembro o ID" />
        <div className="flex items-center gap-2"><Search className="h-4 w-4 text-slate-400" /><Input value={searchQuery} onChange={(e) => searchPerson(e.target.value)} placeholder="…o busque por nombre" data-testid="person-search-input" /></div>
        {searchResults.length > 0 && <ul className="rounded-lg border divide-y" data-testid="person-search-results">{searchResults.map((p) => <li key={p.person_id} className="cursor-pointer p-2 hover:bg-slate-50" onClick={() => selectPerson(p)} data-testid={`person-search-result-${p.person_id}`}>{p.display_name}</li>)}</ul>}
      </div>}

      {step === 'confirm' && material && <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4" data-testid="scan-step-confirm">
        <h2 className="font-serif text-lg text-[#132443]">4. Confirmar {action === 'deliver' ? 'entrega' : action === 'return' ? 'devolución' : 'transferencia'}</h2>
        <div className="flex items-center gap-3"><BookThumbnail fileId={material.cover_file_id} size={64} /><div>
          <p className="font-medium" data-testid="confirm-material-name">{material.name}</p>
          <p className="text-sm text-slate-500">Proceso: {material.process_key || '—'}</p>
          <p className="text-sm text-slate-500">Precio: {material.member_price_cents ? `$${(material.member_price_cents / 100).toFixed(2)}` : 'Gratis'}{material.member_price_cents ? ` · ${form.payment_status === 'pagado' ? 'Pagado' : 'Pendiente'}` : ''}</p>
          {person && <p className="text-sm text-slate-500" data-testid="confirm-person-name">Persona: {person.display_name}</p>}
          <p className="text-sm text-slate-500">Responsable: {user?.nombre || user?.email}</p>
        </div></div>

        {person && snapshot && <div className="rounded-lg bg-slate-50 p-3 text-xs" data-testid="confirm-person-snapshot">
          <p className="font-medium text-slate-700">Materiales de esta persona:</p>
          <ul className="mt-1 space-y-0.5">{snapshot.materials.map((m) => <li key={m.book_id}>{m.book_name} — <Badge variant="outline">{MATERIAL_STATUS_LABEL[m.status]}</Badge></li>)}</ul>
          {snapshot.materials.length === 0 && <p className="text-slate-500">Sin materiales requeridos actualmente.</p>}
          {snapshot.pending_payments.length > 0 && <p className="mt-2 text-amber-700">Pagos pendientes: {snapshot.pending_payments.length}</p>}
        </div>}

        <div className="grid grid-cols-2 gap-3">
          <div><Label>Cantidad</Label><Input type="number" min="1" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} data-testid="confirm-quantity-input" /></div>
          {action === 'transfer' && <div><Label>Transferir a</Label><Select value={form.target_user_id} onValueChange={(v) => setForm({ ...form, target_user_id: v })}><SelectTrigger data-testid="confirm-target-user-select"><SelectValue placeholder="Seleccione líder/coordinador/mentor" /></SelectTrigger><SelectContent className="bg-white">{users.map((u) => <SelectItem key={u.user_id || u._id} value={u.user_id || u._id}>{u.nombre || u.email}</SelectItem>)}</SelectContent></Select></div>}
        </div>
        {action === 'deliver' && material.member_price_cents > 0 && <div className="grid grid-cols-2 gap-3">
          <div><Label>Estado de pago</Label><Select value={form.payment_status} onValueChange={(v) => setForm({ ...form, payment_status: v })}><SelectTrigger data-testid="confirm-payment-status-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white">{Object.entries(PAYMENT_LABELS).map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent></Select></div>
          <div><Label>Monto pagado (USD)</Label><Input type="number" min="0" step="0.01" value={form.amount_paid} onChange={(e) => setForm({ ...form, amount_paid: e.target.value })} disabled={!['pagado', 'pago_parcial'].includes(form.payment_status)} data-testid="confirm-amount-paid-input" /></div>
        </div>}
        <div><Label>Notas (opcional)</Label><Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} data-testid="confirm-notes-input" /></div>

        <Button className="w-full bg-[#132443]" disabled={busy} onClick={action === 'deliver' ? confirmDeliver : action === 'return' ? confirmReturn : confirmTransfer} data-testid="confirm-action-button">
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}{action === 'deliver' ? 'CONFIRMAR ENTREGA' : action === 'return' ? 'CONFIRMAR DEVOLUCIÓN' : 'CONFIRMAR TRANSFERENCIA'}
        </Button>
      </div>}

      {step !== 'material' && <Button variant="ghost" size="sm" onClick={() => setStep(step === 'confirm' && action !== 'transfer' ? 'person' : ['confirm', 'person', 'lookup', 'receive_po'].includes(step) ? 'action' : 'material')} data-testid="scan-back-button"><ArrowLeft className="h-4 w-4" />Atrás</Button>}
    </div>
  </main>;
}
