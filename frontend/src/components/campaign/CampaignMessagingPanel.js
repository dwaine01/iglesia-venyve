import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { MessageCircleHeart, Sparkles, Phone, CheckCircle2 } from 'lucide-react';

import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { formatUsdCents } from '../../lib/campaignFormat';

const smsHref = (phone, body) => `sms:${phone}?body=${encodeURIComponent(body)}`;

const RecipientRow = ({ base, getAuthHeaders, person, kind, amountCents, onContacted }) => {
  const [drafting, setDrafting] = useState(false);
  const [draft, setDraft] = useState('');
  const [marking, setMarking] = useState(false);

  const generate = async () => {
    setDrafting(true);
    try {
      const { data } = await axios.post(`${base}/messages/draft`, {
        kind, person_id: person.person_id, name: person.name, amount_cents: amountCents,
      }, getAuthHeaders());
      setDraft(data.text);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'No se pudo redactar el mensaje');
    } finally {
      setDrafting(false);
    }
  };

  const markContacted = async () => {
    setMarking(true);
    try {
      await axios.post(`${base}/messages/${person.person_id}/mark-contacted`, { kind, text: draft }, getAuthHeaders());
      toast.success('Marcado como contactado');
      await onContacted();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'No se pudo registrar el contacto');
    } finally {
      setMarking(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 p-3" data-testid={`campaign-msg-row-${person.person_id}`}>
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium text-slate-800">{person.name}</p>
          <p className="text-xs text-slate-400">
            {person.phone}{amountCents ? ` · ${formatUsdCents(amountCents)}` : ''}
            {person.last_contacted_at && ` · Contactado ${new Date(person.last_contacted_at).toLocaleDateString('es-US', { dateStyle: 'short' })}`}
          </p>
        </div>
        <Button size="sm" variant="outline" disabled={drafting} onClick={generate} data-testid={`campaign-msg-draft-${person.person_id}`}>
          <Sparkles className="h-3.5 w-3.5" />{drafting ? 'Redactando…' : 'Redactar con IA'}
        </Button>
      </div>
      {draft && (
        <div className="mt-3 space-y-2">
          <Textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={3} data-testid={`campaign-msg-draft-text-${person.person_id}`} />
          <div className="flex gap-2">
            <a href={smsHref(person.phone, draft)} data-testid={`campaign-msg-sms-link-${person.person_id}`}>
              <Button size="sm" variant="outline"><Phone className="h-3.5 w-3.5" />Enviar SMS</Button>
            </a>
            <Button size="sm" variant="ghost" disabled={marking} onClick={markContacted} data-testid={`campaign-msg-mark-contacted-${person.person_id}`}>
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />Marcar como contactado
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export const CampaignMessagingPanel = ({ base, getAuthHeaders }) => {
  const [pending, setPending] = useState([]);
  const [neverDonated, setNeverDonated] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const [p, n] = await Promise.all([
        axios.get(`${base}/messages/pending`, getAuthHeaders()),
        axios.get(`${base}/messages/never-donated`, getAuthHeaders()),
      ]);
      setPending(p.data.items);
      setNeverDonated(n.data.items);
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'No se pudieron cargar los mensajes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4" data-testid="campaign-messaging-panel">
      <h3 className="flex items-center gap-2 font-semibold text-[#132443]"><MessageCircleHeart className="h-4 w-4" />Mensajes a donantes</h3>
      <p className="mt-1 text-xs text-slate-400">
        Redactados con IA, listos para enviar por SMS desde tu teléfono. El envío automático se habilitará cuando esté lista la integración con Univerge Blue.
      </p>
      {loading && <p className="mt-4 text-sm text-slate-400">Cargando…</p>}
      {!loading && (
        <Tabs defaultValue="pending" className="mt-4">
          <TabsList>
            <TabsTrigger value="pending" data-testid="campaign-msg-tab-pending">Pendientes de pago ({pending.length})</TabsTrigger>
            <TabsTrigger value="never" data-testid="campaign-msg-tab-never">Aún no han donado ({neverDonated.length})</TabsTrigger>
          </TabsList>
          <TabsContent value="pending" className="mt-3 space-y-2">
            {pending.length === 0 && <p className="text-sm text-slate-400" data-testid="campaign-msg-pending-empty">Nadie tiene un donativo pendiente de pago con teléfono registrado.</p>}
            {pending.map((item) => (
              <RecipientRow key={item.person_id} base={base} getAuthHeaders={getAuthHeaders} person={item} kind="reminder" amountCents={item.amount_cents} onContacted={load} />
            ))}
          </TabsContent>
          <TabsContent value="never" className="mt-3 space-y-2">
            {neverDonated.length === 0 && <p className="text-sm text-slate-400" data-testid="campaign-msg-never-empty">No hay personas con teléfono registrado sin donativo.</p>}
            {neverDonated.map((item) => (
              <RecipientRow key={item.person_id} base={base} getAuthHeaders={getAuthHeaders} person={item} kind="invite" onContacted={load} />
            ))}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
};
