import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { canManageLibraryInventory } from '../../lib/accessControl';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { ReceiveInventoryDialog } from '../../components/library/ReceiveInventoryDialog';
import { TransferBookDialog } from '../../components/library/TransferBookDialog';
import { ReportDamageLossDialog } from '../../components/library/ReportDamageLossDialog';
import { RequestBookDialog } from '../../components/library/RequestBookDialog';

const REQUEST_STATUS = { pending: 'Pendiente', approved: 'Aprobada', partial: 'Aprobada parcial', rejected: 'Rechazada' };

export default function LibraryMyInventoryPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const isManager = canManageLibraryInventory(user);
  const [holdings, setHoldings] = useState([]);
  const [requests, setRequests] = useState([]);
  const [returnQty, setReturnQty] = useState({});
  const [approveQty, setApproveQty] = useState({});

  const refresh = useCallback(async () => {
    const holdingsRes = await axios.get(`${API}/api/library/my-holdings`, getAuthHeaders());
    setHoldings(holdingsRes.data.items || []);
    const requestsRes = await axios.get(`${API}/api/library/requests`, getAuthHeaders());
    setRequests(requestsRes.data.items || []);
  }, [API]);

  useEffect(() => { refresh(); }, [refresh]);

  const doReturn = async (bookId) => {
    const quantity = Number(returnQty[bookId] || 0);
    if (!quantity) return;
    try {
      await axios.post(`${API}/api/library/movements`, { book_id: bookId, movement_type: 'RETURN', quantity, from_holder: { type: 'user', id: user.id }, to_holder: { type: 'warehouse', id: 'central' }, notes: 'Devolución a Librería Central' }, getAuthHeaders());
      toast.success('Material devuelto a Central'); await refresh();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo devolver'); }
  };

  const resolveRequest = async (requestId, quantityApproved) => {
    try {
      await axios.post(`${API}/api/library/requests/${requestId}/resolve`, { quantity_approved: quantityApproved, notes: '' }, getAuthHeaders());
      toast.success('Solicitud resuelta'); await refresh();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo resolver la solicitud'); }
  };

  return <main className="min-h-screen bg-[#F4F1EA] px-4 py-6 sm:px-8" data-testid="library-my-inventory-page">
    <div className="mx-auto max-w-5xl space-y-6">
      <header><Link to="/libreria" className="text-sm text-[#0879BE]">← Librería 360</Link><h1 className="font-serif text-3xl text-[#132443]">Mi inventario de Librería</h1></header>

      <div className="flex flex-wrap gap-2">
        <RequestBookDialog onRequested={refresh} />
        {isManager && <ReceiveInventoryDialog onReceived={refresh} />}
        {isManager && <TransferBookDialog onTransferred={refresh} />}
        {isManager && <ReportDamageLossDialog onReported={refresh} />}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="my-holdings-panel">
        <h2 className="font-serif text-lg text-[#132443]">Lo que tengo en mi poder</h2>
        {holdings.length === 0 ? <p className="mt-3 text-sm text-slate-500">No tiene materiales asignados actualmente.</p> : <Table className="mt-3">
          <TableHeader><TableRow><TableHead>Material</TableHead><TableHead>En mi poder</TableHead><TableHead>Devolver</TableHead></TableRow></TableHeader>
          <TableBody>{holdings.map((h) => <TableRow key={h.book.book_id} data-testid={`my-holding-row-${h.book.book_id}`}>
            <TableCell>{h.book.name}</TableCell><TableCell>{h.on_hand}</TableCell>
            <TableCell className="flex gap-2">
              <Input type="number" min="1" max={h.on_hand} className="w-20" value={returnQty[h.book.book_id] ?? ''} onChange={(e) => setReturnQty({ ...returnQty, [h.book.book_id]: e.target.value })} data-testid={`return-quantity-${h.book.book_id}`} />
              <Button size="sm" variant="outline" onClick={() => doReturn(h.book.book_id)} data-testid={`return-button-${h.book.book_id}`}>Devolver</Button>
            </TableCell>
          </TableRow>)}</TableBody>
        </Table>}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="library-requests-panel">
        <h2 className="font-serif text-lg text-[#132443]">{isManager ? 'Solicitudes de materiales' : 'Mis solicitudes'}</h2>
        {requests.length === 0 ? <p className="mt-3 text-sm text-slate-500">Sin solicitudes registradas.</p> : <Table className="mt-3">
          <TableHeader><TableRow><TableHead>Material</TableHead><TableHead>Solicitante</TableHead><TableHead>Cantidad</TableHead><TableHead>Estado</TableHead>{isManager && <TableHead>Aprobar</TableHead>}</TableRow></TableHeader>
          <TableBody>{requests.map((r) => <TableRow key={r.request_id} data-testid={`library-request-row-${r.request_id}`}>
            <TableCell>{r.book_name}</TableCell><TableCell>{r.requester_label}</TableCell><TableCell>{r.quantity_requested}{r.quantity_approved != null ? ` (aprobado: ${r.quantity_approved})` : ''}</TableCell>
            <TableCell><Badge variant={r.status === 'pending' ? 'outline' : 'default'}>{REQUEST_STATUS[r.status]}</Badge></TableCell>
            {isManager && <TableCell>{r.status === 'pending' ? <div className="flex gap-2">
              <Input type="number" min="0" max={r.quantity_requested} className="w-20" value={approveQty[r.request_id] ?? r.quantity_requested} onChange={(e) => setApproveQty({ ...approveQty, [r.request_id]: e.target.value })} data-testid={`approve-quantity-${r.request_id}`} />
              <Button size="sm" className="bg-[#132443]" onClick={() => resolveRequest(r.request_id, Number(approveQty[r.request_id] ?? r.quantity_requested))} data-testid={`resolve-request-${r.request_id}`}>Resolver</Button>
            </div> : '—'}</TableCell>}
          </TableRow>)}</TableBody>
        </Table>}
      </div>
    </div>
  </main>;
}
