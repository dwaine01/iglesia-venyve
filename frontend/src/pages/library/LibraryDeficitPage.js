import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, RefreshCw, ShoppingCart } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { BookThumbnail } from '../../components/library/BookThumbnail';

export default function LibraryDeficitPage() {
  const { API, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [creating, setCreating] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/api/library/reservations/deficit-report`, getAuthHeaders());
      setRows(data.items || []);
    } finally { setLoading(false); }
  }, [API]);

  useEffect(() => { refresh(); }, [refresh]);

  const recalculate = async () => {
    setSyncing(true);
    try {
      const { data } = await axios.post(`${API}/api/library/reservations/sync`, {}, getAuthHeaders());
      toast.success(`Reservas actualizadas: ${data.created} creadas, ${data.released} liberadas`);
      await refresh();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo recalcular'); }
    finally { setSyncing(false); }
  };

  const createOrder = async (bookId) => {
    setCreating(bookId);
    try {
      const { data } = await axios.post(`${API}/api/library/purchase-orders/from-deficit`, { book_id: bookId }, getAuthHeaders());
      toast.success(`Borrador ${data.po_number} creado. Complételo en Órdenes de compra.`);
      navigate('/libreria/ordenes-compra');
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo crear la orden'); }
    finally { setCreating(null); }
  };

  const withDeficit = rows.filter((r) => r.deficit > 0);
  const withoutDeficit = rows.filter((r) => r.deficit === 0);

  return <main className="min-h-screen bg-[#F4F1EA] px-4 py-6 sm:px-8" data-testid="library-deficit-page">
    <div className="mx-auto max-w-6xl space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div><Link to="/libreria" className="text-sm text-[#0879BE]">← Librería 360</Link><h1 className="font-serif text-3xl text-[#132443]">Reserva Automática</h1><p className="text-sm text-slate-600">Cálculo en vivo de materiales requeridos por inscripciones activas a procesos.</p></div>
        <Button variant="outline" onClick={recalculate} disabled={syncing} data-testid="recalculate-reservations-button"><RefreshCw className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />Recalcular ahora</Button>
      </header>

      {loading ? <p className="text-sm text-slate-500">Calculando…</p> : <>
        {withDeficit.length > 0 && <div className="rounded-2xl border border-red-200 bg-red-50 p-5" data-testid="deficit-alert-panel">
          <p className="flex items-center gap-2 font-medium text-red-800"><AlertTriangle className="h-4 w-4" />{withDeficit.length} material(es) con déficit de inventario</p>
          <Table className="mt-3"><TableHeader><TableRow><TableHead /><TableHead>Material</TableHead><TableHead>Proceso</TableHead><TableHead>Inscritos</TableHead><TableHead>Stock</TableHead><TableHead>Reservado (otros)</TableHead><TableHead>Disponible real</TableHead><TableHead>Déficit</TableHead><TableHead /></TableRow></TableHeader>
            <TableBody>{withDeficit.map((row) => <TableRow key={row.book_id} data-testid={`deficit-row-${row.book_id}`}>
              <TableCell><BookThumbnail fileId={row.cover_file_id} size={32} /></TableCell>
              <TableCell>{row.book_name}</TableCell><TableCell>{row.process_name}</TableCell>
              <TableCell>{row.enrolled_count}</TableCell><TableCell>{row.stock}</TableCell><TableCell>{row.other_reserved}</TableCell><TableCell>{row.available_real}</TableCell>
              <TableCell><Badge className="bg-red-100 text-red-700" data-testid={`deficit-badge-${row.book_id}`}>Se necesitan {row.deficit} unidades adicionales</Badge></TableCell>
              <TableCell><Button size="sm" className="bg-[#132443]" onClick={() => createOrder(row.book_id)} disabled={creating === row.book_id} data-testid={`create-po-from-deficit-${row.book_id}`}><ShoppingCart className="h-4 w-4" />Crear Orden de Compra</Button></TableCell>
            </TableRow>)}</TableBody>
          </Table>
        </div>}
        {withDeficit.length === 0 && <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-sm text-emerald-800" data-testid="no-deficit-message">No hay déficit de materiales para los procesos con inscripciones activas actualmente.</div>}

        <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="deficit-full-table">
          <h2 className="font-serif text-lg text-[#132443]">Detalle por material vinculado a un proceso</h2>
          <Table className="mt-3"><TableHeader><TableRow><TableHead /><TableHead>Material</TableHead><TableHead>Proceso</TableHead><TableHead>Inscritos</TableHead><TableHead>Stock</TableHead><TableHead>Reservado (otros)</TableHead><TableHead>Disponible real</TableHead><TableHead>Déficit</TableHead></TableRow></TableHeader>
            <TableBody>{[...withDeficit, ...withoutDeficit].map((row) => <TableRow key={row.book_id} data-testid={`deficit-full-row-${row.book_id}`}>
              <TableCell><BookThumbnail fileId={row.cover_file_id} size={28} /></TableCell>
              <TableCell>{row.book_name}</TableCell><TableCell>{row.process_name}</TableCell>
              <TableCell>{row.enrolled_count}</TableCell><TableCell>{row.stock}</TableCell><TableCell>{row.other_reserved}</TableCell><TableCell>{row.available_real}</TableCell>
              <TableCell><Badge className={row.deficit > 0 ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}>{row.deficit}</Badge></TableCell>
            </TableRow>)}</TableBody>
          </Table>
          {rows.length === 0 && <p className="mt-3 text-sm text-slate-500">No hay materiales del catálogo vinculados a un proceso todavía.</p>}
        </div>
      </>}
    </div>
  </main>;
}
