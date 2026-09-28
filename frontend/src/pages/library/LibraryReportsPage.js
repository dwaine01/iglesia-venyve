import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Download, FileSpreadsheet, FileText, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';

export default function LibraryReportsPage() {
  const { API, getAuthHeaders } = useAuth();
  const [catalog, setCatalog] = useState([]);
  const [reportKey, setReportKey] = useState(null);
  const [books, setBooks] = useState([]);
  const [users, setUsers] = useState([]);
  const [filters, setFilters] = useState({ date_from: '', date_to: '', book_id: '', process_key: '', person_id: '', responsible_user_id: '', status: '', payment_type: '' });
  const [personQuery, setPersonQuery] = useState('');
  const [personResults, setPersonResults] = useState([]);
  const [personLabel, setPersonLabel] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    axios.get(`${API}/api/library/reports/catalog`, getAuthHeaders()).then((r) => setCatalog(r.data.items || []));
    axios.get(`${API}/api/library/books`, getAuthHeaders()).then((r) => setBooks(r.data.items || [])).catch(() => setBooks([]));
    axios.get(`${API}/api/core/governance/users`, getAuthHeaders()).then((r) => setUsers(r.data.items || [])).catch(() => setUsers([]));
  }, [API]);

  const processKeys = useMemo(() => [...new Set(books.map((b) => b.process_key).filter(Boolean))], [books]);
  const grouped = useMemo(() => { const g = {}; catalog.forEach((r) => { (g[r.group] = g[r.group] || []).push(r); }); return g; }, [catalog]);
  const selectedMeta = catalog.find((r) => r.key === reportKey);

  const searchPerson = async (query) => {
    setPersonQuery(query);
    if (query.trim().length < 2) return setPersonResults([]);
    const { data } = await axios.get(`${API}/api/library/scan/search-person`, { ...getAuthHeaders(), params: { q: query } });
    setPersonResults(data.items || []);
  };

  const runReport = useCallback(async () => {
    if (!reportKey) return;
    if (selectedMeta?.requires_person && !filters.person_id) return toast.error('Este reporte requiere seleccionar una persona');
    setLoading(true);
    try {
      const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
      const { data } = await axios.get(`${API}/api/library/reports/${reportKey}`, { ...getAuthHeaders(), params: { ...params, format: 'json' } });
      setResult(data);
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo generar el reporte'); }
    finally { setLoading(false); }
  }, [API, reportKey, filters, selectedMeta]);

  const exportFile = async (format) => {
    if (!reportKey) return;
    if (selectedMeta?.requires_person && !filters.person_id) return toast.error('Este reporte requiere seleccionar una persona');
    try {
      const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
      const response = await axios.get(`${API}/api/library/reports/${reportKey}`, { ...getAuthHeaders(), params: { ...params, format }, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url; link.download = `${reportKey}.${format}`; document.body.appendChild(link); link.click(); link.remove();
      window.URL.revokeObjectURL(url);
    } catch { toast.error('No se pudo exportar el archivo'); }
  };

  return <main className="min-h-screen bg-[#F4F1EA] px-4 py-6 sm:px-8" data-testid="library-reports-page">
    <div className="mx-auto max-w-6xl space-y-5">
      <header><Link to="/libreria" className="text-sm text-[#0879BE]">← Librería 360</Link><h1 className="font-serif text-3xl text-[#132443]">Centro de Reportes</h1></header>

      <div className="grid gap-5 lg:grid-cols-[260px_1fr]">
        <aside className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4" data-testid="reports-catalog-list">
          {Object.entries(grouped).map(([group, items]) => <div key={group}>
            <p className="text-xs font-semibold uppercase text-slate-400">{group}</p>
            <ul className="mt-1 space-y-1">{items.map((item) => <li key={item.key}>
              <button type="button" onClick={() => { setReportKey(item.key); setResult(null); }} className={`w-full rounded-lg px-2 py-1.5 text-left text-sm ${reportKey === item.key ? 'bg-[#132443] text-white' : 'hover:bg-slate-100'}`} data-testid={`report-picker-${item.key}`}>{item.name}</button>
            </li>)}</ul>
          </div>)}
        </aside>

        <section className="space-y-4">
          {!reportKey ? <p className="text-sm text-slate-500" data-testid="reports-empty-hint">Seleccione un reporte de la lista para configurar filtros.</p> : <>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3" data-testid="reports-filter-panel">
              <h2 className="font-serif text-lg text-[#132443]">{selectedMeta?.name}</h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div><Label>Desde</Label><Input type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} data-testid="report-filter-date-from" /></div>
                <div><Label>Hasta</Label><Input type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} data-testid="report-filter-date-to" /></div>
                <div><Label>Material</Label><Select value={filters.book_id || 'all'} onValueChange={(v) => setFilters({ ...filters, book_id: v === 'all' ? '' : v })}><SelectTrigger data-testid="report-filter-book"><SelectValue placeholder="Todos" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todos</SelectItem>{books.map((b) => <SelectItem key={b.book_id} value={b.book_id}>{b.name}</SelectItem>)}</SelectContent></Select></div>
                <div><Label>Proceso</Label><Select value={filters.process_key || 'all'} onValueChange={(v) => setFilters({ ...filters, process_key: v === 'all' ? '' : v })}><SelectTrigger data-testid="report-filter-process"><SelectValue placeholder="Todos" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todos</SelectItem>{processKeys.map((pk) => <SelectItem key={pk} value={pk}>{pk}</SelectItem>)}</SelectContent></Select></div>
                <div><Label>Responsable</Label><Select value={filters.responsible_user_id || 'all'} onValueChange={(v) => setFilters({ ...filters, responsible_user_id: v === 'all' ? '' : v })}><SelectTrigger data-testid="report-filter-responsible"><SelectValue placeholder="Todos" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todos</SelectItem>{users.map((u) => <SelectItem key={u.user_id || u._id} value={u.user_id || u._id}>{u.nombre || u.email}</SelectItem>)}</SelectContent></Select></div>
                <div><Label>Gratis/Pago</Label><Select value={filters.payment_type || 'all'} onValueChange={(v) => setFilters({ ...filters, payment_type: v === 'all' ? '' : v })}><SelectTrigger data-testid="report-filter-payment-type"><SelectValue placeholder="Todos" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todos</SelectItem><SelectItem value="gratis">Gratis</SelectItem><SelectItem value="pagado">Pagado</SelectItem></SelectContent></Select></div>
                <div><Label>Estado (órdenes)</Label><Input value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })} placeholder="ej. draft, ordered" data-testid="report-filter-status" /></div>
                <div>
                  <Label>Persona {selectedMeta?.requires_person && '(requerida)'}</Label>
                  <div className="flex items-center gap-1"><Search className="h-4 w-4 text-slate-400" /><Input value={personLabel || personQuery} onChange={(e) => { setPersonLabel(''); searchPerson(e.target.value); }} placeholder="Buscar persona" data-testid="report-filter-person-search" /></div>
                  {personResults.length > 0 && <ul className="rounded border bg-white text-sm" data-testid="report-person-results">{personResults.map((p) => <li key={p.person_id} className="cursor-pointer p-1 hover:bg-slate-50" onClick={() => { setFilters({ ...filters, person_id: p.person_id }); setPersonLabel(p.display_name); setPersonResults([]); }} data-testid={`report-person-result-${p.person_id}`}>{p.display_name}</li>)}</ul>}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={runReport} disabled={loading} className="bg-[#132443]" data-testid="run-report-button">Ver reporte</Button>
                <Button onClick={() => exportFile('pdf')} variant="outline" data-testid="export-report-pdf-button"><FileText className="h-4 w-4" />Exportar PDF</Button>
                <Button onClick={() => exportFile('xlsx')} variant="outline" data-testid="export-report-xlsx-button"><FileSpreadsheet className="h-4 w-4" />Exportar Excel</Button>
              </div>
            </div>

            {result && <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white p-2" data-testid="report-result-table">
              <Table><TableHeader><TableRow>{result.columns.map((c) => <TableHead key={c}>{c}</TableHead>)}</TableRow></TableHeader>
                <TableBody>{result.rows.map((row, idx) => <TableRow key={idx} data-testid={`report-result-row-${idx}`}>{row.map((cell, cidx) => <TableCell key={cidx}>{String(cell)}</TableCell>)}</TableRow>)}</TableBody>
              </Table>
              {result.rows.length === 0 && <p className="p-4 text-sm text-slate-500" data-testid="report-no-results">Sin resultados para los filtros seleccionados.</p>}
            </div>}
          </>}
        </section>
      </div>
    </div>
  </main>;
}
