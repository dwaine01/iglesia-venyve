/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import { Plus, Search, Trash2, UserRoundCheck } from 'lucide-react';
import { toast } from 'sonner';

import { FinanceEmpty, FinanceShell, Money } from '../../components/finance/FinanceShell';
import { Button } from '../../components/ui/button';
import { Checkbox } from '../../components/ui/checkbox';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Textarea } from '../../components/ui/textarea';
import { useAuth } from '../../context/AuthContext';
import { displayLabel } from '../../lib/displayLabels';

const today = () => new Date().toISOString().slice(0, 10);
const emptyLine = () => ({ contribution_type: 'tithe', fund_id: '', campaign_id: '', description: '', amount: '' });

export default function FinanceContributionsPage() {
  const { API, getAuthHeaders } = useAuth();
  const [searchParams] = useSearchParams();
  const [catalog, setCatalog] = useState({ funds: [], contribution_types: [] });
  const [campaigns, setCampaigns] = useState([]);
  const [batches, setBatches] = useState([]);
  const [items, setItems] = useState([]);
  const [people, setPeople] = useState([]);
  const [search, setSearch] = useState(searchParams.get('person_name') || '');
  const [selectedPerson, setSelectedPerson] = useState(
    searchParams.get('person_id') ? { person_id: searchParams.get('person_id'), name: searchParams.get('person_name') || 'Persona seleccionada' } : null
  );
  const [saving, setSaving] = useState(false);
  const [correctionLoaded, setCorrectionLoaded] = useState(false);
  const [correctionReason, setCorrectionReason] = useState('');
  const correctionId = searchParams.get('correct_id');
  const [form, setForm] = useState({
    anonymous: false,
    received_date: today(),
    payment_method: 'cash',
    reference: '',
    envelope_number: '',
    notes: '',
    batch_id: searchParams.get('batch_id') || '',
    allocations: [emptyLine()],
  });

  const load = async () => {
    const [catalogResponse, itemsResponse, campaignsResponse, batchesResponse] = await Promise.all([
      axios.get(`${API}/api/finance/catalog`, getAuthHeaders()),
      axios.get(`${API}/api/finance/contributions`, getAuthHeaders()),
      axios.get(`${API}/api/finance/campaigns`, getAuthHeaders()),
      axios.get(`${API}/api/finance/batches`, getAuthHeaders()),
    ]);
    setCatalog(catalogResponse.data);
    setItems(itemsResponse.data.items || []);
    setCampaigns(campaignsResponse.data.items || []);
    setBatches((batchesResponse.data.items || []).filter((item) => item.status === 'collecting'));
  };

  useEffect(() => { load().catch(() => toast.error('No se pudo cargar Finanzas')); }, []);
  useEffect(() => {
    if (!correctionId || correctionLoaded || !items.length) return;
    const original = items.find((item) => item.contribution_id === correctionId);
    if (!original) return;
    setSelectedPerson(original.person_id ? { person_id: original.person_id, name: searchParams.get('person_name') || 'Persona seleccionada' } : null);
    setSearch(searchParams.get('person_name') || '');
    setForm({ anonymous: original.anonymous, received_date: original.received_date, payment_method: original.payment_method, reference: original.reference || '', envelope_number: original.envelope_number || '', notes: original.notes || '', batch_id: '', allocations: (original.allocations || []).map((line) => ({ contribution_type: line.contribution_type || original.contribution_type, fund_id: line.fund_id, campaign_id: line.campaign_id || '', description: line.description || '', amount: String((line.amount_cents || 0) / 100) })) });
    setCorrectionLoaded(true);
  }, [correctionId, correctionLoaded, items, searchParams]);
  useEffect(() => {
    if (selectedPerson || search.trim().length < 2) { setPeople([]); return undefined; }
    const timer = setTimeout(() => {
      axios.get(`${API}/api/finance/contributors/search?search=${encodeURIComponent(search.trim())}`, getAuthHeaders())
        .then((response) => setPeople(response.data.items || []))
        .catch(() => setPeople([]));
    }, 250);
    return () => clearTimeout(timer);
  }, [API, getAuthHeaders, search, selectedPerson]);

  const totalCents = useMemo(
    () => form.allocations.reduce((sum, item) => sum + Math.round(Number(item.amount || 0) * 100), 0),
    [form.allocations]
  );

  const updateLine = (index, key, value) => setForm((current) => ({
    ...current,
    allocations: current.allocations.map((line, lineIndex) => lineIndex === index ? { ...line, [key]: value } : line),
  }));

  const submit = async (event) => {
    event.preventDefault();
    if (!form.anonymous && !selectedPerson) return toast.error('Seleccione una Persona 360 o marque Anónima');
    if (!totalCents) return toast.error('Registre al menos un monto');
    setSaving(true);
    try {
      const payload = {
        person_id: form.anonymous ? null : selectedPerson?.person_id,
        anonymous: form.anonymous,
        amount_cents: totalCents,
        received_date: form.received_date,
        payment_method: form.payment_method,
        reference: form.reference || null,
        envelope_number: form.envelope_number || null,
        notes: form.notes || null,
        batch_id: form.batch_id || null,
        source: 'manual',
        allocations: form.allocations.map((line) => ({
          contribution_type: line.contribution_type,
          fund_id: line.fund_id,
          campaign_id: line.campaign_id || null,
          description: line.description || null,
          amount_cents: Math.round(Number(line.amount) * 100),
        })),
      };
      if (correctionId) {
        if (correctionReason.trim().length < 5) { setSaving(false); return toast.error('Indique el motivo de la corrección'); }
        await axios.post(`${API}/api/finance/contributions/${correctionId}/correct`, { reason: correctionReason, correction_date: today(), replacement: payload }, getAuthHeaders());
        toast.success('Corrección registrada sin borrar el original');
      } else {
        await axios.post(`${API}/api/finance/contributions`, payload, getAuthHeaders());
        toast.success('Sobre o contribución registrado con asiento balanceado');
      }
      setForm((current) => ({ ...current, reference: '', envelope_number: '', notes: '', allocations: [emptyLine()] }));
      await load();
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'No se pudo registrar la contribución');
    } finally {
      setSaving(false);
    }
  };

  const types = catalog.contribution_types || [];
  return (
    <FinanceShell title="Registro rápido de sobres y contribuciones" description="Una Persona 360, varios conceptos y destinos, un solo registro auditable y un asiento balanceado.">
      <form onSubmit={submit} className="space-y-6 border bg-white p-4 sm:p-6" data-testid="contribution-form">
        {correctionId && <div className="border-l-4 border-amber-500 bg-amber-50 p-4" data-testid="contribution-correction-banner"><p className="font-semibold">Corrección trazable</p><p className="text-sm">Se conservará el registro original y se generará reversión/ajuste cuando corresponda.</p><Input className="mt-3" value={correctionReason} onChange={(event) => setCorrectionReason(event.target.value)} placeholder="Motivo obligatorio de la corrección" data-testid="contribution-correction-reason" /></div>}
        <section className="grid gap-4 lg:grid-cols-[1.4fr_repeat(4,minmax(0,1fr))]">
          <div className="relative">
            <Label htmlFor="finance-person-search">Persona 360</Label>
            <div className="relative mt-1">
              <Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
              <Input id="finance-person-search" className="pl-9" value={selectedPerson?.name || search} onChange={(event) => { setSelectedPerson(null); setSearch(event.target.value); }} disabled={form.anonymous} placeholder="Buscar por nombre" data-testid="contribution-person-search" />
            </div>
            {people.length > 0 && <div className="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto border bg-white shadow-xl" data-testid="contribution-person-results">{people.map((person) => <button type="button" key={person.person_id} className="flex w-full items-center justify-between border-b p-3 text-left text-sm hover:bg-[#F3F5F4]" onClick={() => { setSelectedPerson(person); setSearch(person.name); setPeople([]); }} data-testid={`contribution-person-option-${person.person_id}`}><span>{person.name}</span><span className="text-xs text-slate-500">{person.contribution_count} registros</span></button>)}</div>}
            {selectedPerson && <div className="mt-2 flex items-center gap-2 text-xs text-emerald-700" data-testid="selected-contribution-person"><UserRoundCheck className="h-4 w-4" />{selectedPerson.name}<Link className="ml-auto underline" to={`/finanzas/contribuyentes/${selectedPerson.person_id}`}>Ver historial</Link></div>}
            <label className="mt-2 flex items-center gap-2 text-sm"><Checkbox checked={form.anonymous} onCheckedChange={(value) => { setForm({ ...form, anonymous: Boolean(value) }); if (value) setSelectedPerson(null); }} data-testid="anonymous-contribution-checkbox" />Anónima</label>
          </div>
          <div><Label>Fecha efectiva</Label><Input className="mt-1" type="date" value={form.received_date} onChange={(event) => setForm({ ...form, received_date: event.target.value })} data-testid="contribution-date-input" /></div>
          <div><Label>Método</Label><Select value={form.payment_method} onValueChange={(value) => setForm({ ...form, payment_method: value })}><SelectTrigger className="mt-1" data-testid="contribution-method-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white">{['cash', 'check', 'zelle', 'ach', 'transfer', 'pushpay', 'other'].map((method) => <SelectItem key={method} value={method}>{displayLabel(method)}</SelectItem>)}</SelectContent></Select></div>
          <div><Label>Número de sobre</Label><Input className="mt-1" value={form.envelope_number} onChange={(event) => setForm({ ...form, envelope_number: event.target.value })} placeholder="Opcional" data-testid="contribution-envelope-input" /></div>
          <div><Label>Sesión de conteo</Label><Select value={form.batch_id || 'none'} onValueChange={(value) => setForm({ ...form, batch_id: value === 'none' ? '' : value })}><SelectTrigger className="mt-1" data-testid="contribution-batch-select"><SelectValue placeholder="Sin sesión" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="none">Registrar sin sesión</SelectItem>{batches.map((batch) => <SelectItem key={batch.batch_id} value={batch.batch_id}>{batch.service_name} · {batch.service_date}</SelectItem>)}</SelectContent></Select></div>
        </section>

        <fieldset className="space-y-3">
          <legend className="font-['Spectral'] text-xl font-semibold">Conceptos dentro del sobre</legend>
          {form.allocations.map((line, index) => <div key={index} className="grid gap-2 border-l-2 border-[#B5953F] bg-[#FAFBFA] p-3 md:grid-cols-[1fr_1fr_1fr_1fr_140px_auto]" data-testid={`contribution-line-${index}`}>
            <Select value={line.contribution_type} onValueChange={(value) => updateLine(index, 'contribution_type', value)}><SelectTrigger data-testid={`allocation-type-${index}`}><SelectValue placeholder="Concepto" /></SelectTrigger><SelectContent className="bg-white">{types.map((type) => <SelectItem key={type.type_key} value={type.type_key}>{type.name}</SelectItem>)}</SelectContent></Select>
            <Select value={line.fund_id} onValueChange={(value) => updateLine(index, 'fund_id', value)}><SelectTrigger data-testid={`allocation-fund-${index}`}><SelectValue placeholder="Fondo / destino" /></SelectTrigger><SelectContent className="bg-white">{catalog.funds.map((fund) => <SelectItem key={fund.fund_id} value={fund.fund_id}>{fund.name}</SelectItem>)}</SelectContent></Select>
            <Select value={line.campaign_id || 'none'} onValueChange={(value) => updateLine(index, 'campaign_id', value === 'none' ? '' : value)}><SelectTrigger data-testid={`allocation-campaign-${index}`}><SelectValue placeholder="Proyecto" /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="none">Sin proyecto</SelectItem>{campaigns.map((campaign) => <SelectItem key={campaign.campaign_id} value={campaign.campaign_id}>{campaign.name}</SelectItem>)}</SelectContent></Select>
            <Input value={line.description} onChange={(event) => updateLine(index, 'description', event.target.value)} placeholder="Descripción especial" data-testid={`allocation-description-${index}`} />
            <Input type="number" min="0.01" step="0.01" value={line.amount} onChange={(event) => updateLine(index, 'amount', event.target.value)} placeholder="Monto" required data-testid={`allocation-amount-${index}`} />
            <Button type="button" variant="outline" size="icon" disabled={form.allocations.length === 1} onClick={() => setForm((current) => ({ ...current, allocations: current.allocations.filter((_, lineIndex) => lineIndex !== index) }))} aria-label="Quitar concepto" data-testid={`remove-contribution-line-${index}`}><Trash2 className="h-4 w-4" /></Button>
          </div>)}
          <Button type="button" variant="outline" onClick={() => setForm((current) => ({ ...current, allocations: [...current.allocations, emptyLine()] }))} data-testid="add-contribution-allocation"><Plus className="h-4 w-4" />Añadir concepto</Button>
        </fieldset>

        <div className="grid gap-4 sm:grid-cols-2"><div><Label>Referencia bancaria / cheque</Label><Input className="mt-1" value={form.reference} onChange={(event) => setForm({ ...form, reference: event.target.value })} data-testid="contribution-reference-input" /></div><div><Label>Notas</Label><Textarea className="mt-1 min-h-20" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} data-testid="contribution-notes-input" /></div></div>
        <div className="flex flex-col gap-3 border-t pt-5 sm:flex-row sm:items-center sm:justify-between"><p className="text-2xl font-semibold" data-testid="contribution-total">Total: <Money cents={totalCents} /></p><Button disabled={saving || !totalCents || form.allocations.some((line) => !line.fund_id || !line.contribution_type)} data-testid="create-contribution-button">{saving ? 'Guardando…' : correctionId ? 'Registrar corrección' : 'Registrar contribución'}</Button></div>
      </form>

      <section className="mt-8 space-y-2" data-testid="recent-contributions-list"><h2 className="font-['Spectral'] text-2xl font-semibold">Registros recientes</h2>{items.length ? items.slice(0, 30).map((item) => <article key={item.contribution_id} className="flex flex-col justify-between gap-2 border bg-white p-4 sm:flex-row"><div><p className="font-semibold">{item.contribution_type === 'mixed' ? 'Sobre con varios conceptos' : displayLabel(item.contribution_type)} · {item.allocations?.length || 0} concepto(s)</p><p className="text-xs text-slate-500">{item.received_date} · {displayLabel(item.payment_method)} · {item.anonymous ? 'Anónima' : `Persona ${item.person_id?.slice(-8)}`}</p></div><Money cents={item.amount_cents} /></article>) : <FinanceEmpty>No hay contribuciones registradas.</FinanceEmpty>}</section>
    </FinanceShell>
  );
}