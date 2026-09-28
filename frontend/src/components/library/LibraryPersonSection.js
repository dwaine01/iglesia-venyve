import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { BookOpen } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { canDeliverLibraryBooks } from '../../lib/accessControl';
import { Badge } from '../ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { DeliverBookDialog } from './DeliverBookDialog';

const PAYMENT_LABELS = { pagado: 'Pagado', pendiente: 'Pendiente', exonerado: 'Exonerado', beca: 'Beca', descuento: 'Descuento', pago_parcial: 'Pago parcial', no_aplica: 'Gratis' };
const TYPE_LABELS = { DELIVERY: 'Entregado', LOAN: 'Prestado', LOAN_RETURN: 'Devuelto', RETURN: 'Devuelto', ASSIGNMENT: 'Asignado' };

export const LibraryPersonSection = ({ personId, user }) => {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/api/library/persons/${personId}/materials`, getAuthHeaders());
      setItems(data.items || []);
    } finally { setLoading(false); }
  }, [API, personId]);

  useEffect(() => { refresh(); }, [refresh]);

  return <section className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="library-person-section">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="flex items-center gap-2 font-serif text-lg text-[#132443]"><BookOpen className="h-5 w-5" />Libros y Materiales</h3>
      {canDeliverLibraryBooks(user) && <DeliverBookDialog personId={personId} onDelivered={refresh} />}
    </div>
    {loading ? <p className="mt-4 text-sm text-slate-500">Cargando…</p> : items.length === 0 ? (
      <p className="mt-4 text-sm text-slate-500" data-testid="library-person-empty">Sin materiales registrados todavía.</p>
    ) : <Table className="mt-4" data-testid="library-person-materials-table">
      <TableHeader><TableRow><TableHead>Material</TableHead><TableHead>Proceso</TableHead><TableHead>Fecha</TableHead><TableHead>Estado</TableHead><TableHead>Pago</TableHead></TableRow></TableHeader>
      <TableBody>{items.map((item) => <TableRow key={item.movement_id} data-testid={`library-person-material-row-${item.movement_id}`}>
        <TableCell>{item.book_name}</TableCell>
        <TableCell>{item.process_key || '—'}</TableCell>
        <TableCell>{(item.occurred_at || '').slice(0, 10)}</TableCell>
        <TableCell><Badge variant="outline">{TYPE_LABELS[item.movement_type] || item.movement_type}</Badge></TableCell>
        <TableCell>{item.amount_paid_cents ? `$${(item.amount_paid_cents / 100).toFixed(2)} pagado` : (PAYMENT_LABELS[item.payment_status] || 'Gratis')}</TableCell>
      </TableRow>)}</TableBody>
    </Table>}
  </section>;
};
