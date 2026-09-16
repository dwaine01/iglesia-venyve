import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { jsPDF } from 'jspdf';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { FileDown, Plus, Search, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';

import { FinanceEmpty, FinanceShell, Money } from '../../components/finance/FinanceShell';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { useAuth } from '../../context/AuthContext';
import { displayLabel } from '../../lib/displayLabels';

export default function FinanceContributorsPage() {
  const { personId } = useParams();
  const navigate = useNavigate();
  const { API, getAuthHeaders } = useAuth();
  const currentYear = new Date().getFullYear();
  const [search, setSearch] = useState('');
  const [results, setResults] = useState([]);
  const [catalog, setCatalog] = useState({ funds: [], contribution_types: [] });
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState(null);
  const [filters, setFilters] = useState({ year: String(currentYear), start: '', end: '', contribution_type: 'all', fund_id: 'all', payment_method: 'all' });

  useEffect(() => {
    axios.get(`${API}/api/finance/catalog`, getAuthHeaders()).then((response) => setCatalog(response.data));
  }, [API, getAuthHeaders]);
  useEffect(() => {
    if (search.trim().length < 2) { setResults([]); return undefined; }
    const timer = setTimeout(() => axios.get(`${API}/api/finance/contributors/search?search=${encodeURIComponent(search)}`, getAuthHeaders()).then((response) => setResults(response.data.items || [])), 250);
    return () => clearTimeout(timer);
  }, [API, getAuthHeaders, search]);
  useEffect(() => {
    if (!personId) { setSummary(null); return; }
    const params = new URLSearchParams();
    if (filters.year !== 'all' && !filters.start && !filters.end) params.set('year', filters.year);
    if (filters.start) params.set('start', filters.start);
    if (filters.end) params.set('end', filters.end);
    if (filters.contribution_type !== 'all') params.set('contribution_type', filters.contribution_type);
    if (filters.fund_id !== 'all') params.set('fund_id', filters.fund_id);
    if (filters.payment_method !== 'all') params.set('payment_method', filters.payment_method);
    axios.get(`${API}/api/finance/contributors/${personId}?${params}`, getAuthHeaders()).then((response) => setSummary(response.data)).catch((error) => toast.error(error?.response?.data?.detail || 'No se pudo cargar el historial'));
  }, [API, filters, getAuthHeaders, personId]);

  const typeNames = useMemo(() => Object.fromEntries((catalog.contribution_types || []).map((item) => [item.type_key, item.name])), [catalog]);
  const generateStatement = async () => {
    try {
      const response = await axios.post(`${API}/api/finance/contributors/${personId}/annual-statements/${filters.year === 'all' ? currentYear : filters.year}`, {}, getAuthHeaders());
      const statement = response.data;
      const document = new jsPDF();
      const organization = statement.organization_snapshot || {};
      const template = statement.template_snapshot || {};
      let y = 18;
      document.setFont('times', 'bold'); document.setFontSize(18); document.text(organization.legal_name || 'VEN Y VE 360', 18, y); y += 9;
      document.setFont('helvetica', 'normal'); document.setFontSize(10); document.text([organization.address, organization.city_state_zip].filter(Boolean).join(' · '), 18, y); y += 14;
      document.setFont('times', 'bold'); document.setFontSize(15); document.text(template.title || 'Carta anual de contribuciones', 18, y); y += 9;
      document.setFont('helvetica', 'normal'); document.setFontSize(10); document.text(`Contribuyente: ${statement.person_snapshot.name}`, 18, y); y += 6; document.text(`Año: ${statement.year}`, 18, y); y += 9;
      if (!template.approved) { document.setTextColor(180, 40, 40); document.text('BORRADOR — TEXTO LEGAL/FISCAL PENDIENTE DE APROBACIÓN', 18, y); y += 9; document.setTextColor(0, 0, 0); }
      if (template.intro_text) { const lines = document.splitTextToSize(template.intro_text, 175); document.text(lines, 18, y); y += lines.length * 5 + 5; }
      statement.items.forEach((item) => { if (y > 270) { document.addPage(); y = 18; } document.text(`${item.received_date} · ${item.contribution_type_name} · ${item.fund_name}`, 18, y); document.text((item.amount_cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' }), 190, y, { align: 'right' }); y += 6; });
      y += 5; document.setFont('helvetica', 'bold'); document.text(`Total incluido: ${(statement.total_cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })}`, 190, y, { align: 'right' }); y += 10;
      document.setFont('helvetica', 'normal'); if (template.acknowledgment_text) document.text(document.splitTextToSize(template.acknowledgment_text, 175), 18, y);
      document.save(`carta-contribuciones-${statement.person_snapshot.name}-${statement.year}.pdf`);
      toast.success(template.approved ? 'Carta anual generada' : 'Borrador generado; requiere aprobación legal/administrativa');
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo generar la carta'); }
  };
  const loadHistory = async () => { try { const response = await axios.get(`${API}/api/finance/contributors/${personId}/history`, getAuthHeaders()); setHistory(response.data); } catch { toast.error('No se pudo cargar la auditoría'); } };

  return <FinanceShell title="Contribuyentes" description="Buscar Persona 360, consultar historial autorizado, registrar contribuciones y generar cartas anuales sin exponer datos fuera de Finanzas.">
    <section className="border bg-white p-4 sm:p-6" data-testid="finance-contributor-search-panel"><div className="relative max-w-2xl"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><Input className="pl-9" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar a Eduardo, Rubén u otra Persona 360" data-testid="finance-contributor-search-input" /></div>{results.length > 0 && <div className="mt-3 grid gap-2 md:grid-cols-2">{results.map((person) => <button type="button" key={person.person_id} className="flex items-center justify-between border p-3 text-left hover:bg-[#F3F5F4]" onClick={() => navigate(`/finanzas/contribuyentes/${person.person_id}`)} data-testid={`finance-contributor-result-${person.person_id}`}><span><b>{person.name}</b><small className="block text-slate-500">VV {person.vv_number || '—'}</small></span><span className="text-xs text-slate-500">{person.contribution_count} registros</span></button>)}</div>}</section>
    {!personId ? <div className="mt-6"><FinanceEmpty>Busque una Persona 360 para abrir su ficha financiera autorizada.</FinanceEmpty></div> : !summary ? <p className="mt-6" data-testid="finance-contributor-loading">Cargando historial…</p> : <>
      <section className="mt-6 border bg-[#102A2D] p-5 text-white" data-testid="finance-contributor-header"><div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-xs uppercase text-[#D6BE70]">Ficha financiera confidencial</p><h2 className="mt-1 font-['Spectral'] text-3xl font-semibold" data-testid="finance-contributor-name">{summary.person.name}</h2><p className="mt-1 text-sm text-white/60">Persona 360 · VV {summary.person.vv_number || '—'}</p></div><div className="flex flex-wrap gap-2"><Button asChild variant="outline"><Link to={`/finanzas/contribuciones?person_id=${summary.person.person_id}&person_name=${encodeURIComponent(summary.person.name)}`} data-testid="new-contribution-for-person"><Plus className="h-4 w-4" />Nueva contribución</Link></Button><Button onClick={generateStatement} data-testid="generate-annual-statement-button"><FileDown className="h-4 w-4" />Generar carta anual</Button></div></div></section>
      <section className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6"><Select value={filters.year} onValueChange={(value) => setFilters({ ...filters, year: value, start: '', end: '' })}><SelectTrigger data-testid="contributor-year-filter"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todos los años</SelectItem>{[0,1,2,3,4].map((offset) => <SelectItem key={currentYear-offset} value={String(currentYear-offset)}>{currentYear-offset}</SelectItem>)}</SelectContent></Select><Input type="date" value={filters.start} onChange={(event) => setFilters({ ...filters, start: event.target.value, year: 'all' })} data-testid="contributor-start-date-filter" /><Input type="date" value={filters.end} onChange={(event) => setFilters({ ...filters, end: event.target.value, year: 'all' })} data-testid="contributor-end-date-filter" /><Select value={filters.contribution_type} onValueChange={(value) => setFilters({ ...filters, contribution_type: value })}><SelectTrigger data-testid="contributor-type-filter"><SelectValue placeholder="Concepto" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todos los conceptos</SelectItem>{(catalog.contribution_types || []).map((item) => <SelectItem key={item.type_key} value={item.type_key}>{item.name}</SelectItem>)}</SelectContent></Select><Select value={filters.fund_id} onValueChange={(value) => setFilters({ ...filters, fund_id: value })}><SelectTrigger data-testid="contributor-fund-filter"><SelectValue placeholder="Fondo" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todos los fondos</SelectItem>{catalog.funds.map((item) => <SelectItem key={item.fund_id} value={item.fund_id}>{item.name}</SelectItem>)}</SelectContent></Select><Select value={filters.payment_method} onValueChange={(value) => setFilters({ ...filters, payment_method: value })}><SelectTrigger data-testid="contributor-method-filter"><SelectValue placeholder="Método" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todos los métodos</SelectItem>{['cash','check','zelle','ach','transfer','pushpay','other'].map((item) => <SelectItem key={item} value={item}>{displayLabel(item)}</SelectItem>)}</SelectContent></Select></section>
      <section className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><div className="border bg-white p-4"><p className="text-xs uppercase text-slate-500">Total</p><p className="mt-2 text-2xl font-semibold" data-testid="contributor-total"><Money cents={summary.total_cents} /></p></div><div className="border bg-white p-4"><p className="text-xs uppercase text-slate-500">Elegible según configuración</p><p className="mt-2 text-2xl font-semibold" data-testid="contributor-reportable-total"><Money cents={summary.reportable_total_cents} /></p></div>{Object.entries(summary.totals_by_type).slice(0,2).map(([key, value]) => <div key={key} className="border bg-white p-4"><p className="text-xs uppercase text-slate-500">{typeNames[key] || displayLabel(key)}</p><p className="mt-2 text-2xl font-semibold"><Money cents={value} /></p></div>)}</section>
      <section className="mt-5 overflow-x-auto border bg-white" data-testid="contributor-history-table"><table className="w-full min-w-[920px] text-sm"><thead><tr className="border-b bg-slate-50"><th className="p-3 text-left">Fecha</th><th className="p-3 text-left">Concepto</th><th className="p-3 text-left">Fondo / proyecto</th><th className="p-3 text-left">Método</th><th className="p-3 text-left">Referencia</th><th className="p-3 text-right">Monto</th><th className="p-3 text-right">Acción</th></tr></thead><tbody>{summary.items.map((item, index) => <tr key={`${item.contribution_id}-${index}`} className="border-b"><td className="p-3">{item.received_date}</td><td className="p-3">{item.contribution_type_name}</td><td className="p-3">{item.fund_name}{item.campaign_name ? ` · ${item.campaign_name}` : ''}</td><td className="p-3">{displayLabel(item.payment_method)}</td><td className="p-3">{item.reference || '—'}</td><td className="p-3 text-right font-semibold"><Money cents={item.amount_cents} /></td><td className="p-3 text-right">{summary.items.findIndex((row) => row.contribution_id === item.contribution_id) === index && <Button asChild size="sm" variant="outline"><Link to={`/finanzas/contribuciones?correct_id=${item.contribution_id}&person_name=${encodeURIComponent(summary.person.name)}`} data-testid={`correct-contribution-${item.contribution_id}`}>Corregir</Link></Button>}</td></tr>)}</tbody></table>{!summary.items.length && <FinanceEmpty>No hay contribuciones para estos filtros.</FinanceEmpty>}</section>
      <section className="mt-5 border bg-white p-4" data-testid="contributor-audit-panel"><div className="flex items-center justify-between"><h2 className="font-['Spectral'] text-xl font-semibold">Auditoría y correcciones</h2><Button variant="outline" onClick={loadHistory} data-testid="load-contributor-audit-button"><ShieldCheck className="h-4 w-4" />Consultar historial</Button></div>{history && <div className="mt-3 text-sm"><p>{history.corrections.length} corrección(es) · {history.audit_events.length} evento(s) auditables</p>{history.corrections.slice(0, 10).map((item) => <p key={item.correction_id} className="mt-2 border-t pt-2">{item.created_at} · {item.reason}</p>)}</div>}</section>
      <p className="mt-4 flex items-center gap-2 text-xs text-slate-500"><ShieldCheck className="h-4 w-4" />Esta información solo se obtiene desde endpoints protegidos por RBAC financiero.</p>
    </>}
  </FinanceShell>;
}