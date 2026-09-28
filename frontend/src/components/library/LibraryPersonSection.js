import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { BookOpen, FileSpreadsheet, FileText } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { canDeliverLibraryBooks } from '../../lib/accessControl';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { DeliverBookDialog } from './DeliverBookDialog';
import { BookThumbnail } from './BookThumbnail';

const PAYMENT_LABELS = { pagado: 'Pagado', pendiente: 'Pendiente', exonerado: 'Exonerado', beca: 'Beca', descuento: 'Descuento', pago_parcial: 'Pago parcial', no_aplica: 'Gratis' };
const TYPE_LABELS = { DELIVERY: 'Entregado', LOAN: 'Prestado', LOAN_RETURN: 'Devuelto', RETURN: 'Devuelto', ASSIGNMENT: 'Asignado' };

export const LibraryPersonSection = ({ personId, user }) => {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState([]);
  const [books, setBooks] = useState({});
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/api/library/persons/${personId}/materials`, getAuthHeaders());
      setItems(data.items || []);
      const booksRes = await axios.get(`${API}/api/library/books`, getAuthHeaders());
      setBooks(Object.fromEntries((booksRes.data.items || []).map((b) => [b.book_id, b])));
    } finally { setLoading(false); }
  }, [API, personId]);

  useEffect(() => { refresh(); }, [refresh]);

  const exportHistory = async (format) => {
    try {
      const response = await axios.get(`${API}/api/library/reports/person_ledger`, { ...getAuthHeaders(), params: { person_id: personId, format }, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url; link.download = `historial_libreria.${format}`; document.body.appendChild(link); link.click(); link.remove();
      window.URL.revokeObjectURL(url);
    } catch { /* noop */ }
  };

  return <section className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="library-person-section">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="flex items-center gap-2 font-serif text-lg text-[#132443]"><BookOpen className="h-5 w-5" />Libros y Materiales</h3>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" onClick={() => exportHistory('pdf')} data-testid="export-person-library-pdf"><FileText className="h-4 w-4" />PDF</Button>
        <Button size="sm" variant="outline" onClick={() => exportHistory('xlsx')} data-testid="export-person-library-xlsx"><FileSpreadsheet className="h-4 w-4" />Excel</Button>
        {canDeliverLibraryBooks(user) && <DeliverBookDialog personId={personId} onDelivered={refresh} />}
      </div>
    </div>
    {loading ? <p className="mt-4 text-sm text-slate-500">Cargando…</p> : items.length === 0 ? (
      <p className="mt-4 text-sm text-slate-500" data-testid="library-person-empty">Sin materiales registrados todavía.</p>
    ) : <Table className="mt-4" data-testid="library-person-materials-table">
      <TableHeader><TableRow><TableHead /><TableHead>Material</TableHead><TableHead>Proceso</TableHead><TableHead>Fecha</TableHead><TableHead>Estado</TableHead><TableHead>Pago</TableHead></TableRow></TableHeader>
      <TableBody>{items.map((item) => <TableRow key={item.movement_id} data-testid={`library-person-material-row-${item.movement_id}`}>
        <TableCell><BookThumbnail fileId={books[item.book_id]?.cover_file_id} size={28} /></TableCell>
        <TableCell>{item.book_name}</TableCell>
        <TableCell>{item.process_key || '—'}</TableCell>
        <TableCell>{(item.occurred_at || '').slice(0, 10)}</TableCell>
        <TableCell><Badge variant="outline">{TYPE_LABELS[item.movement_type] || item.movement_type}</Badge></TableCell>
        <TableCell>{item.amount_paid_cents ? `$${(item.amount_paid_cents / 100).toFixed(2)} pagado` : (PAYMENT_LABELS[item.payment_status] || 'Gratis')}</TableCell>
      </TableRow>)}</TableBody>
    </Table>}
  </section>;
};
