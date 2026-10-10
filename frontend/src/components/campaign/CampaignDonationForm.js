import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Tv } from 'lucide-react';

import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Checkbox } from '../ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { dollarsToCents, formatUsdCents } from '../../lib/campaignFormat';

const QUICK_AMOUNTS = [2500, 5000, 10000, 25000, 50000, 100000];

export const CampaignDonationForm = ({ base, getAuthHeaders, onCreated }) => {
  const [donorName, setDonorName] = useState('');
  const [amountCents, setAmountCents] = useState(0);
  const [customAmount, setCustomAmount] = useState('');
  const [donationType, setDonationType] = useState('received');
  const [anonymous, setAnonymous] = useState(false);
  const [consentShowName, setConsentShowName] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const idemKeyRef = useRef(crypto.randomUUID());

  const resetForm = () => {
    setDonorName(''); setAmountCents(0); setCustomAmount('');
    setAnonymous(false); setConsentShowName(false); setDonationType('received');
    idemKeyRef.current = crypto.randomUUID();
  };

  const pickQuick = (cents) => { setAmountCents(cents); setCustomAmount((cents / 100).toFixed(2)); };

  useEffect(() => {
    const handler = (e) => {
      const tag = document.activeElement?.tagName;
      const typing = tag === 'INPUT' || tag === 'TEXTAREA';
      if (!typing && e.key >= '1' && e.key <= '6') {
        const idx = Number(e.key) - 1;
        if (QUICK_AMOUNTS[idx]) pickQuick(QUICK_AMOUNTS[idx]);
      }
      if (e.key === 'Escape') resetForm();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!amountCents || amountCents <= 0) { toast.error('Ingrese un monto válido mayor a $0'); return; }
    setSubmitting(true);
    try {
      await axios.post(`${base}/donations`, {
        donor_name: anonymous ? null : (donorName.trim() || null),
        amount_cents: amountCents,
        donation_type: donationType,
        anonymous,
        consent_show_name: anonymous ? false : consentShowName,
        idempotency_key: idemKeyRef.current,
      }, getAuthHeaders());
      toast.success('Donativo mostrado en pantalla');
      resetForm();
      await onCreated();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'No se pudo registrar el donativo. Intente de nuevo.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5" data-testid="campaign-donation-form">
      <h3 className="font-serif text-lg text-[#132443]">Registrar donativo</h3>

      <div className="grid grid-cols-3 gap-2 sm:grid-cols-6" data-testid="campaign-quick-amounts">
        {QUICK_AMOUNTS.map((cents) => (
          <button
            type="button"
            key={cents}
            onClick={() => pickQuick(cents)}
            data-testid={`campaign-quick-amount-${cents}`}
            className={`rounded-lg border px-2 py-2 text-sm font-semibold transition-colors ${amountCents === cents ? 'border-[#B5953F] bg-[#B5953F]/10 text-[#132443]' : 'border-slate-200 text-slate-600 hover:border-[#B5953F]/50'}`}
          >
            {formatUsdCents(cents)}
          </button>
        ))}
      </div>

      <div>
        <Label htmlFor="campaign-custom-amount">Monto libre (USD)</Label>
        <Input
          id="campaign-custom-amount"
          type="number"
          min="0.01"
          step="0.01"
          value={customAmount}
          onChange={(e) => { setCustomAmount(e.target.value); setAmountCents(dollarsToCents(e.target.value)); }}
          placeholder="0.00"
          data-testid="campaign-custom-amount-input"
        />
      </div>

      <div>
        <Label htmlFor="campaign-donor-name">Nombre del donante (opcional)</Label>
        <Input
          id="campaign-donor-name"
          value={donorName}
          onChange={(e) => setDonorName(e.target.value)}
          disabled={anonymous}
          placeholder="Ej: Familia Pérez"
          data-testid="campaign-donor-name-input"
        />
      </div>

      <div>
        <Label>Tipo de donativo</Label>
        <Select value={donationType} onValueChange={setDonationType}>
          <SelectTrigger data-testid="campaign-donation-type-select"><SelectValue /></SelectTrigger>
          <SelectContent className="bg-white">
            <SelectItem value="received">Recibido</SelectItem>
            <SelectItem value="promise">Promesa</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-wrap gap-4">
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={anonymous} onCheckedChange={(v) => { setAnonymous(Boolean(v)); if (v) setConsentShowName(false); }} data-testid="campaign-anonymous-checkbox" />
          Donante anónimo
        </label>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={consentShowName} disabled={anonymous} onCheckedChange={(v) => setConsentShowName(Boolean(v))} data-testid="campaign-consent-checkbox" />
          Autoriza mostrar nombre y monto en pantalla
        </label>
      </div>

      <Button type="submit" disabled={submitting || !amountCents} className="w-full bg-[#132443] hover:bg-[#1c3461]" data-testid="campaign-submit-donation-button">
        <Tv className="h-4 w-4" />{submitting ? 'Registrando…' : 'Registrar y revelar piezas'}
      </Button>
      <p className="text-xs text-slate-400">Atajos: teclas 1–6 montos rápidos · Esc limpia el formulario</p>
    </form>
  );
};
