/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { FinanceShell } from '../../components/finance/FinanceShell';
import { FinancePeriodsPanel } from '../../components/finance/FinancePeriodsPanel';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { useAuth } from '../../context/AuthContext';
import { displayLabel } from '../../lib/displayLabels';

export default function FinanceSetupPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const [catalog, setCatalog] = useState({ funds: [], accounts: [] }); const [settings, setSettings] = useState({});
  const [fund, setFund] = useState({ code: '', name: '', restriction_type: 'unrestricted', purpose: '' });
  const [account, setAccount] = useState({ code: '', name: '', account_type: 'asset' });
  const load = () => Promise.all([axios.get(`${API}/api/finance/catalog`, getAuthHeaders()), axios.get(`${API}/api/finance/settings`, getAuthHeaders())]).then(([c, s]) => { setCatalog(c.data); setSettings(s.data); });
  useEffect(() => { load(); }, []);
  const create = async (kind, payload) => { try { await axios.post(`${API}/api/finance/${kind}`, payload, getAuthHeaders()); toast.success('Registro creado'); await load(); } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo guardar'); } };
  return <FinanceShell title="Configuración contable" description="Base configurable, fondos separados, catálogo institucional y cierres controlados.">
    <section className="grid gap-6 lg:grid-cols-2">
      <form onSubmit={(e) => { e.preventDefault(); create('funds', fund); }} className="space-y-3 border bg-white p-5" data-testid="fund-form"><h2 className="font-['Spectral'] text-xl font-semibold">Nuevo fondo</h2><Input placeholder="Código" value={fund.code} onChange={(e) => setFund({ ...fund, code: e.target.value })} required data-testid="fund-code-input" /><Input placeholder="Nombre" value={fund.name} onChange={(e) => setFund({ ...fund, name: e.target.value })} required data-testid="fund-name-input" /><Select value={fund.restriction_type} onValueChange={(v) => setFund({ ...fund, restriction_type: v })}><SelectTrigger data-testid="fund-restriction-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="unrestricted">Sin restricción</SelectItem><SelectItem value="donor_restricted">Restricción del donante</SelectItem><SelectItem value="board_designated">Designado por Junta</SelectItem></SelectContent></Select><Input placeholder="Propósito" value={fund.purpose} onChange={(e) => setFund({ ...fund, purpose: e.target.value })} required data-testid="fund-purpose-input" /><Button data-testid="create-fund-button">Crear fondo</Button></form>
      <form onSubmit={(e) => { e.preventDefault(); create('accounts', account); }} className="space-y-3 border bg-white p-5" data-testid="account-form"><h2 className="font-['Spectral'] text-xl font-semibold">Nueva cuenta</h2><Input placeholder="Código" value={account.code} onChange={(e) => setAccount({ ...account, code: e.target.value })} required data-testid="account-code-input" /><Input placeholder="Nombre" value={account.name} onChange={(e) => setAccount({ ...account, name: e.target.value })} required data-testid="account-name-input" /><Select value={account.account_type} onValueChange={(v) => setAccount({ ...account, account_type: v })}><SelectTrigger data-testid="account-type-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white">{['asset','liability','net_assets','revenue','expense'].map(v => <SelectItem key={v} value={v}>{displayLabel(v)}</SelectItem>)}</SelectContent></Select><Button data-testid="create-account-button">Crear cuenta</Button></form>
    </section>
    {user?.rol === 'pastor' && <section className="mt-6 border bg-white p-5"><h2 className="font-['Spectral'] text-xl font-semibold">Política contable</h2><div className="mt-4 max-w-sm"><Label>Base contable</Label><Select value={settings.accounting_basis || 'cash'} onValueChange={async (value) => { await axios.put(`${API}/api/finance/settings`, { accounting_basis: value }, getAuthHeaders()); setSettings({ ...settings, accounting_basis: value }); toast.success('Política actualizada'); }}><SelectTrigger data-testid="accounting-basis-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="cash">Base de efectivo</SelectItem><SelectItem value="modified_cash">Efectivo modificado</SelectItem><SelectItem value="accrual">Base devengada</SelectItem></SelectContent></Select></div></section>}
    <section className="mt-6 grid gap-6 lg:grid-cols-2"><div className="border bg-white p-5"><h2 className="font-semibold">Fondos</h2>{catalog.funds.map(f => <div key={f.fund_id} className="mt-2 flex justify-between border-t pt-2 text-sm"><span>{f.code} · {f.name}</span><span>{displayLabel(f.restriction_type)}</span></div>)}</div><div className="border bg-white p-5"><h2 className="font-semibold">Catálogo de cuentas</h2>{catalog.accounts.map(a => <div key={a.account_id} className="mt-2 flex justify-between border-t pt-2 text-sm"><span>{a.code} · {a.name}</span><span>{displayLabel(a.account_type)}</span></div>)}</div></section>
    <FinancePeriodsPanel />
  </FinanceShell>;
}