import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { Badge } from '../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Button } from '../../components/ui/button';
import { PurchaseOrderFormDialog } from '../../components/library/PurchaseOrderFormDialog';
import { PurchaseOrderDetailDialog } from '../../components/library/PurchaseOrderDetailDialog';

const STATUS_LABEL = { draft: 'Borrador', submitted: 'Enviada a Finanzas', approved: 'Aprobada', rejected: 'Rechazada', changes_requested: 'Devuelta para cambios', ordered: 'Ordenada', partially_received: 'Recibida parcial', received: 'Recibida completa', closed: 'Cerrada', cancelled: 'Cancelada' };
const STATUS_BADGE = {
  draft: 'bg-slate-100 text-slate-700', submitted: 'bg-amber-100 text-amber-700', approved: 'bg-emerald-100 text-emerald-700',
  rejected: 'bg-red-100 text-red-700', changes_requested: 'bg-orange-100 text-orange-700', ordered: 'bg-blue-100 text-blue-700',
  partially_received: 'bg-indigo-100 text-indigo-700', received: 'bg-emerald-100 text-emerald-700', closed: 'bg-slate-200 text-slate-600', cancelled: 'bg-red-100 text-red-500',
};

export default function LibraryPurchaseOrdersPage() {
  const { API, getAuthHeaders } = useAuth();
  const [orders, setOrders] = useState([]);
  const [statusFilter, setStatusFilter] = useState('all');
  const [canDecide, setCanDecide] = useState(false);

  const refresh = useCallback(async () => {
    const { data } = await axios.get(`${API}/api/library/purchase-orders`, statusFilter !== 'all' ? { params: { status: statusFilter }, ...getAuthHeaders() } : getAuthHeaders());
    setOrders(data.items || []);
    setCanDecide(!!data.can_decide);
  }, [API, statusFilter]);

  useEffect(() => { refresh(); }, [refresh]);

  return <main className="min-h-screen bg-[#F4F1EA] px-4 py-6 sm:px-8" data-testid="library-purchase-orders-page">
    <div className="mx-auto max-w-6xl space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div><Link to="/libreria" className="text-sm text-[#0879BE]">← Librería 360</Link><h1 className="font-serif text-3xl text-[#132443]">Órdenes de compra</h1></div>
        <PurchaseOrderFormDialog onSaved={refresh} />
      </header>

      <div className="flex items-center gap-2">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-56" data-testid="po-status-filter"><SelectValue placeholder="Filtrar por estado" /></SelectTrigger>
          <SelectContent className="bg-white">
            <SelectItem value="all">Todos los estados</SelectItem>
            {Object.entries(STATUS_LABEL).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-2">
        <Table><TableHeader><TableRow><TableHead>Número</TableHead><TableHead>Proveedor</TableHead><TableHead>Total</TableHead><TableHead>Esperado</TableHead><TableHead>Estado</TableHead><TableHead /></TableRow></TableHeader>
          <TableBody>{orders.map((po) => <TableRow key={po.po_id} data-testid={`po-row-${po.po_id}`}>
            <TableCell className="font-medium">{po.po_number}</TableCell>
            <TableCell>{po.provider_name}</TableCell>
            <TableCell>${(po.total_cents / 100).toFixed(2)}</TableCell>
            <TableCell>{po.expected_date || '—'}</TableCell>
            <TableCell><Badge className={STATUS_BADGE[po.status]}>{STATUS_LABEL[po.status]}</Badge></TableCell>
            <TableCell className="flex gap-2">
              {po.status === 'draft' && <PurchaseOrderFormDialog po={po} onSaved={refresh} />}
              <PurchaseOrderDetailDialog poId={po.po_id} onChanged={refresh} trigger={<Button size="sm" variant="outline" data-testid={`open-po-detail-${po.po_id}`}>Ver detalle</Button>} />
            </TableCell>
          </TableRow>)}</TableBody>
        </Table>
        {orders.length === 0 && <p className="p-4 text-sm text-slate-500" data-testid="po-empty-state">No hay órdenes de compra con este filtro.</p>}
      </div>
      {canDecide && <p className="text-xs text-slate-500" data-testid="po-decide-hint">Como usuario de Finanzas, puedes aprobar/rechazar/devolver órdenes en estado "Enviada a Finanzas" desde el detalle.</p>}
    </div>
  </main>;
}
