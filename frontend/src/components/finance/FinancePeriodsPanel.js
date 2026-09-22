/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { LockKeyhole, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { useAuth } from '../../context/AuthContext';
import { displayLabel } from '../../lib/displayLabels';
import { isPastoralAuthority } from '../../lib/accessControl';

export const FinancePeriodsPanel = () => {
  const { API, getAuthHeaders, user } = useAuth();
  const [items, setItems] = useState([]);
  const [checks, setChecks] = useState({});
  const [reasons, setReasons] = useState({});
  const [form, setForm] = useState({ name: '', start_date: '', end_date: '' });
  const load = () => axios.get(`${API}/api/finance/periods`, getAuthHeaders()).then((response) => setItems(response.data.items || []));
  useEffect(() => { load(); }, []);
  const create = async (event) => { event.preventDefault(); try { await axios.post(`${API}/api/finance/periods`, form, getAuthHeaders()); toast.success('Período creado'); setForm({ name: '', start_date: '', end_date: '' }); await load(); } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo crear'); } };
  const inspect = async (id) => { const response = await axios.get(`${API}/api/finance/periods/${id}/checklist`, getAuthHeaders()); setChecks({ ...checks, [id]: response.data.checks }); };
  const close = async (id) => { try { await axios.post(`${API}/api/finance/periods/${id}/close`, {}, getAuthHeaders()); toast.success('Período cerrado'); await load(); } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo cerrar'); await inspect(id); } };
  const reopen = async (id) => { try { await axios.post(`${API}/api/finance/periods/${id}/reopen`, { reason: reasons[id] }, getAuthHeaders()); toast.success('Período reabierto con auditoría'); await load(); } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo reabrir'); } };
  return <section className="mt-6 border bg-white p-5" data-testid="finance-periods-panel"><h2 className="font-['Spectral'] text-xl font-semibold">Cierre mensual</h2><form onSubmit={create} className="mt-3 grid gap-2 sm:grid-cols-4"><Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Agosto 2026" required data-testid="period-name-input" /><Input type="date" value={form.start_date} onChange={(event) => setForm({ ...form, start_date: event.target.value })} required data-testid="period-start-input" /><Input type="date" value={form.end_date} onChange={(event) => setForm({ ...form, end_date: event.target.value })} required data-testid="period-end-input" /><Button data-testid="create-period-button">Crear período</Button></form><div className="mt-5 space-y-3">{items.map((item) => <article key={item.period_id} className="border p-4" data-testid={`period-card-${item.period_id}`}><div className="flex flex-wrap items-center justify-between gap-3"><div><b>{item.name}</b><p className="text-xs text-slate-500">{item.start_date} → {item.end_date} · {displayLabel(item.status)}</p></div><div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => inspect(item.period_id)} data-testid={`inspect-period-${item.period_id}`}>Checklist</Button>{item.status === 'open' && <Button size="sm" onClick={() => close(item.period_id)} data-testid={`close-period-${item.period_id}`}><LockKeyhole className="h-4 w-4" />Cerrar</Button>}</div></div>{checks[item.period_id] && <div className="mt-3 grid gap-2 bg-slate-50 p-3 text-xs sm:grid-cols-2 lg:grid-cols-3" data-testid={`period-checklist-${item.period_id}`}>{Object.entries(checks[item.period_id]).filter(([key]) => key !== 'ready_to_close').map(([key, value]) => <p key={key} className="flex justify-between"><span>{displayLabel(key)}</span><b>{value}</b></p>)}</div>}{item.status === 'closed' && isPastoralAuthority(user) && <div className="mt-3 flex gap-2"><Input value={reasons[item.period_id] || ''} onChange={(event) => setReasons({ ...reasons, [item.period_id]: event.target.value })} placeholder="Motivo obligatorio de reapertura" data-testid={`reopen-reason-${item.period_id}`} /><Button variant="outline" onClick={() => reopen(item.period_id)} data-testid={`reopen-period-${item.period_id}`}><RotateCcw className="h-4 w-4" />Reabrir</Button></div>}</article>)}</div></section>;
};