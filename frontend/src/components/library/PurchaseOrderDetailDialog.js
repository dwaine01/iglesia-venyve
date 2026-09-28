import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, Paperclip, Send } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { canDecideLibraryPO } from '../../lib/accessControl';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { Textarea } from '../ui/textarea';
import { ScannerInput } from './ScannerInput';

const STATUS_LABEL = { draft: 'Borrador', submitted: 'Enviada a Finanzas', approved: 'Aprobada', rejected: 'Rechazada', changes_requested: 'Devuelta para cambios', ordered: 'Ordenada', partially_received: 'Recibida parcial', received: 'Recibida completa', closed: 'Cerrada', cancelled: 'Cancelada' };

export const PurchaseOrderDetailDialog = ({ poId, trigger, onChanged }) => {
  const { API, getAuthHeaders, user } = useAuth();
  const [open, setOpen] = useState(false);
  const [po, setPo] = useState(null);
  const [receiveQty, setReceiveQty] = useState({});
  const [decisionNote, setDecisionNote] = useState('');
  const [comment, setComment] = useState('');
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [receiveScanMethod, setReceiveScanMethod] = useState('MANUAL');
  const canDecide = canDecideLibraryPO(user);

  const refresh = useCallback(async () => {
    const { data } = await axios.get(`${API}/api/library/purchase-orders/${poId}`, getAuthHeaders());
    setPo(data);
    const filesRes = await axios.get(`${API}/api/library/files/by-owner/purchase_order/${poId}`, getAuthHeaders()).catch(() => ({ data: { items: [] } }));
    setFiles(filesRes.data.items || []);
    await onChanged();
  }, [API, poId]);

  useEffect(() => { if (open) refresh(); }, [open, refresh]);

  const act = async (action, body) => {
    setBusy(true);
    try { await action(); toast.success('Actualizado'); await refresh(); }
    catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo completar la acción'); }
    finally { setBusy(false); }
  };

  const submitOrder = () => act(() => axios.post(`${API}/api/library/purchase-orders/${poId}/submit`, {}, getAuthHeaders()));
  const decide = (decision) => act(() => axios.post(`${API}/api/library/purchase-orders/${poId}/decision`, { action: decision, note: decisionNote }, getAuthHeaders()));
  const markOrdered = () => act(() => axios.post(`${API}/api/library/purchase-orders/${poId}/mark-ordered`, {}, getAuthHeaders()));
  const closeOrder = () => act(() => axios.post(`${API}/api/library/purchase-orders/${poId}/close`, {}, getAuthHeaders()));
  const cancelOrder = () => act(() => axios.post(`${API}/api/library/purchase-orders/${poId}/cancel`, {}, getAuthHeaders()));
  const receive = () => act(() => axios.post(`${API}/api/library/purchase-orders/${poId}/receive`, { lines: po.lines.map((l) => ({ book_id: l.book_id, quantity_received_now: Number(receiveQty[l.book_id] || 0) })), scan_method: receiveScanMethod }, getAuthHeaders()));
  const onReceiveScan = async (code, method) => {
    try {
      const { data } = await axios.get(`${API}/api/library/scan/resolve-material`, { ...getAuthHeaders(), params: { code } });
      const line = po.lines.find((l) => l.book_id === data.book_id);
      if (!line) return toast.error('Ese material no pertenece a esta orden');
      const remaining = line.quantity_ordered - line.quantity_received;
      const current = Number(receiveQty[line.book_id] || 0);
      if (current >= remaining) return toast.error('Ya se registró toda la cantidad pendiente para este material');
      setReceiveQty({ ...receiveQty, [line.book_id]: current + 1 });
      setReceiveScanMethod(method);
      toast.success(`+1 ${line.book_name} (${current + 1}/${remaining})`);
    } catch { toast.error('No se encontró ningún material con ese código'); }
  };
  const addComment = () => act(async () => { await axios.post(`${API}/api/library/purchase-orders/${poId}/comments`, { text: comment }, getAuthHeaders()); setComment(''); });
  const uploadFile = async (event) => {
    const file = event.target.files?.[0]; if (!file) return;
    const formData = new FormData(); formData.append('file', file);
    await act(() => axios.post(`${API}/api/library/files/po-attachment/${poId}`, formData, getAuthHeaders()));
  };

  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild>{trigger}</DialogTrigger>
    <DialogContent className="max-w-3xl" data-testid={`po-detail-dialog-${poId}`}>
      {!po ? <><DialogHeader><DialogTitle className="sr-only">Cargando orden de compra</DialogTitle><DialogDescription className="sr-only">Cargando detalle de la orden de compra</DialogDescription></DialogHeader><p>Cargando…</p></> : <>
        <DialogHeader><DialogTitle className="flex items-center gap-2">{po.po_number}<Badge data-testid="po-status-badge">{STATUS_LABEL[po.status]}</Badge></DialogTitle><DialogDescription>Detalle, aprobación, recepción y documentos de la orden de compra {po.po_number}.</DialogDescription></DialogHeader>
        <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
          <p className="text-sm text-slate-600">Proveedor: <strong>{po.provider_name}</strong> · Total: <strong>${(po.total_cents / 100).toFixed(2)}</strong> {po.expected_date && `· Esperado: ${po.expected_date}`}</p>
          {['ordered', 'partially_received'].includes(po.status) && <div className="rounded-lg border border-slate-200 bg-slate-50 p-3" data-testid="po-receive-scan-panel">
            <p className="mb-2 text-sm font-medium text-slate-700">Recepción rápida: escanee cada material para sumar 1 unidad</p>
            <ScannerInput onDetected={onReceiveScan} testIdPrefix="po-receive-scanner" placeholder="Código del material a recibir" />
          </div>}
          <Table><TableHeader><TableRow><TableHead>Material</TableHead><TableHead>Ordenado</TableHead><TableHead>Recibido</TableHead><TableHead>Costo unit.</TableHead>{['ordered', 'partially_received'].includes(po.status) && <TableHead>Recibir ahora</TableHead>}</TableRow></TableHeader>
            <TableBody>{po.lines.map((line) => <TableRow key={line.book_id} data-testid={`po-detail-line-${line.book_id}`}>
              <TableCell>{line.book_name}</TableCell><TableCell>{line.quantity_ordered}</TableCell><TableCell>{line.quantity_received}</TableCell><TableCell>${(line.unit_cost_cents / 100).toFixed(2)}</TableCell>
              {['ordered', 'partially_received'].includes(po.status) && <TableCell><Input type="number" min="0" max={line.quantity_ordered - line.quantity_received} className="w-20" value={receiveQty[line.book_id] ?? ''} onChange={(e) => setReceiveQty({ ...receiveQty, [line.book_id]: e.target.value })} data-testid={`po-receive-input-${line.book_id}`} /></TableCell>}
            </TableRow>)}</TableBody>
          </Table>

          <div className="flex flex-wrap gap-2">
            {po.status === 'draft' && <><Button disabled={busy} onClick={submitOrder} className="bg-[#132443]" data-testid="po-submit-button"><Send className="h-4 w-4" />Enviar a Finanzas</Button><Button disabled={busy} variant="outline" onClick={cancelOrder} data-testid="po-cancel-button">Cancelar</Button></>}
            {po.status === 'changes_requested' && <><Button disabled={busy} onClick={submitOrder} className="bg-[#132443]" data-testid="po-resubmit-button">Reenviar a Finanzas</Button><Button disabled={busy} variant="outline" onClick={cancelOrder} data-testid="po-cancel-button-2">Cancelar</Button></>}
            {po.status === 'approved' && <Button disabled={busy} onClick={markOrdered} className="bg-[#132443]" data-testid="po-mark-ordered-button">Marcar como Ordenada</Button>}
            {['ordered', 'partially_received'].includes(po.status) && <Button disabled={busy} onClick={receive} className="bg-[#132443]" data-testid="po-receive-button">Registrar recepción</Button>}
            {['received', 'partially_received'].includes(po.status) && <Button disabled={busy} variant="outline" onClick={closeOrder} data-testid="po-close-button">Cerrar orden</Button>}
          </div>

          {po.status === 'submitted' && canDecide && <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 space-y-2" data-testid="po-decision-panel">
            <Textarea placeholder="Nota para Librería (opcional)" value={decisionNote} onChange={(e) => setDecisionNote(e.target.value)} data-testid="po-decision-note-input" />
            <div className="flex gap-2">
              <Button disabled={busy} onClick={() => decide('approve')} className="bg-emerald-600" data-testid="po-approve-button">Aprobar</Button>
              <Button disabled={busy} onClick={() => decide('request_changes')} variant="outline" data-testid="po-request-changes-button">Devolver para cambios</Button>
              <Button disabled={busy} onClick={() => decide('reject')} variant="destructive" data-testid="po-reject-button">Rechazar</Button>
            </div>
          </div>}
          {po.status === 'submitted' && !canDecide && <p className="text-sm text-amber-700">Pendiente de decisión de Finanzas.</p>}
          {po.linked_expense_id && <p className="text-xs text-slate-500" data-testid="po-linked-expense">Vinculada a Finanzas (gasto #{po.linked_expense_id.slice(0, 8)}).</p>}

          <div>
            <p className="text-sm font-medium">Documentos adjuntos (facturas/recibos)</p>
            <ul className="mt-1 space-y-1 text-sm">{files.map((f) => <li key={f.file_id} data-testid={`po-attachment-${f.file_id}`}>{f.original_filename} {f.is_voided && <Badge variant="outline">Anulado</Badge>}</li>)}</ul>
            <label className="mt-2 inline-flex cursor-pointer items-center gap-2 text-sm text-[#0879BE]"><Paperclip className="h-4 w-4" />Adjuntar factura/recibo<input type="file" className="hidden" accept="image/jpeg,image/png,image/webp,application/pdf" onChange={uploadFile} data-testid="po-attachment-input" /></label>
          </div>

          <div>
            <p className="text-sm font-medium">Comentarios Librería ↔ Finanzas</p>
            <ul className="mt-1 space-y-1 text-sm">{po.comments.map((c) => <li key={c.comment_id} className="rounded bg-slate-50 px-2 py-1" data-testid={`po-comment-${c.comment_id}`}>{c.text}</li>)}</ul>
            <div className="mt-2 flex gap-2"><Input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Escribir un comentario…" data-testid="po-comment-input" /><Button disabled={busy || !comment.trim()} onClick={addComment} data-testid="po-comment-submit-button">Enviar</Button></div>
          </div>
        </div>
      </>}
    </DialogContent>
  </Dialog>;
};
