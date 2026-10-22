import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Compass, GraduationCap, History, Loader2, Save } from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Switch } from './ui/switch';
import { Textarea } from './ui/textarea';

const ACTION_LABELS = {
  mentor_badge_activated: 'Insignia de Mentor activada',
  mentor_badge_deactivated: 'Insignia de Mentor desactivada',
  mentor_lbs_enabled: 'Habilitado para impartir LBS',
  mentor_lbs_disabled: 'Deshabilitado para impartir LBS',
};

export default function MentorBadgeSection({ personId, API, getAuthHeaders }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [savingBadge, setSavingBadge] = useState(false);
  const [savingLbs, setSavingLbs] = useState(false);
  const [since, setSince] = useState('');
  const [note, setNote] = useState('');
  const [lbsNote, setLbsNote] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await axios.get(`${API}/api/mentorship/badge/${personId}`, getAuthHeaders());
      setData(response.data);
      setSince(response.data.since || '');
      setNote(response.data.note || '');
      setLbsNote(response.data.lbs_note || '');
    } catch (requestError) {
      setError(requestError?.response?.data?.detail || 'No se pudo cargar la insignia de Mentor.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [personId]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleBadge = async (active) => {
    setSavingBadge(true);
    try {
      await axios.put(`${API}/api/mentorship/badge/${personId}`, { active, since: since || null, note: note || null }, getAuthHeaders());
      toast.success(active ? 'Insignia de Mentor activada' : 'Insignia de Mentor desactivada');
      await load();
    } catch (requestError) {
      toast.error(requestError?.response?.data?.detail || 'No se pudo actualizar la insignia.');
    } finally {
      setSavingBadge(false);
    }
  };

  const toggleLbs = async (canTeachLbs) => {
    setSavingLbs(true);
    try {
      await axios.put(`${API}/api/mentorship/lbs/${personId}`, { can_teach_lbs: canTeachLbs, note: lbsNote || null }, getAuthHeaders());
      toast.success(canTeachLbs ? 'Capacitado para impartir LBS' : 'Ya no está capacitado para impartir LBS');
      await load();
    } catch (requestError) {
      toast.error(requestError?.response?.data?.detail || 'No se pudo actualizar la capacitación LBS.');
    } finally {
      setSavingLbs(false);
    }
  };

  if (loading) {
    return <section className="rounded-lg border border-[#E8E5DE] bg-white p-5" data-testid="mentor-badge-section"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></section>;
  }

  if (error || !data) {
    return (
      <section className="rounded-lg border border-[#E8E5DE] bg-white p-5" data-testid="mentor-badge-section">
        <p className="text-sm text-red-600" data-testid="mentor-badge-error">{error || 'No se pudo cargar la información.'}</p>
      </section>
    );
  }

  return (
    <section className="space-y-5" data-testid="mentor-badge-section">
      <div className="rounded-lg border border-[#E8E5DE] bg-white p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#132443]/10 text-[#132443]"><Compass className="h-5 w-5" /></div>
          <div>
            <h2 className="font-['Spectral'] text-2xl font-semibold text-[#101D36]">Mentor / Acompañamiento</h2>
            <p className="text-sm text-slate-500">Insignia para visitas, "invasiones" y la Ley de las 7 Semanas.</p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Badge variant={data.active ? 'default' : 'outline'} className={data.active ? 'bg-[#132443] text-white' : ''} data-testid="mentor-badge-status">
            {data.active ? 'Insignia activa' : 'Sin insignia de Mentor'}
          </Badge>
          <Badge variant={data.lbs_qualified ? 'default' : 'outline'} className={data.lbs_qualified ? 'bg-[#8A6D2F] text-white' : ''} data-testid="mentor-lbs-status">
            <GraduationCap className="mr-1 h-3.5 w-3.5" /> {data.lbs_qualified ? 'Capacitado para LBS' : 'No capacitado para LBS'}
          </Badge>
        </div>

        {!data.can_manage && (
          <p className="mt-4 border-l-4 border-amber-500 bg-amber-50 p-3 text-sm text-amber-900" data-testid="mentor-badge-read-only-notice">
            Solo lectura. Administrar la insignia requiere permiso de Mentoría.
          </p>
        )}

        {data.can_manage && (
          <div className="mt-6 grid gap-6 md:grid-cols-2">
            <div className="space-y-3 border-t border-slate-100 pt-5 md:border-r md:border-t-0 md:pr-6 md:pt-0">
              <div className="flex items-center justify-between">
                <Label htmlFor="mentor-badge-switch" className="text-sm font-semibold text-[#101D36]">Insignia de Mentor</Label>
                <Switch id="mentor-badge-switch" checked={data.active} disabled={savingBadge} onCheckedChange={toggleBadge} data-testid="mentor-badge-switch" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mentor-badge-since">Desde</Label>
                <Input id="mentor-badge-since" type="date" value={since} onChange={(event) => setSince(event.target.value)} data-testid="mentor-badge-since-input" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mentor-badge-note">Nota</Label>
                <Textarea id="mentor-badge-note" value={note} onChange={(event) => setNote(event.target.value)} placeholder="Observación sobre la insignia" data-testid="mentor-badge-note-input" />
              </div>
              <Button size="sm" disabled={savingBadge} onClick={() => toggleBadge(data.active)} className="bg-[#132443]" data-testid="mentor-badge-save-button">
                {savingBadge ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Guardar nota/fecha
              </Button>
            </div>

            <div className="space-y-3 border-t border-slate-100 pt-5 md:pt-0">
              <div className="flex items-center justify-between">
                <Label htmlFor="mentor-lbs-switch" className="text-sm font-semibold text-[#101D36]">Capacitado para impartir LBS</Label>
                <Switch id="mentor-lbs-switch" checked={data.lbs_qualified} disabled={savingLbs} onCheckedChange={toggleLbs} data-testid="mentor-lbs-switch" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mentor-lbs-note">Nota</Label>
                <Textarea id="mentor-lbs-note" value={lbsNote} onChange={(event) => setLbsNote(event.target.value)} placeholder="Observación sobre la capacitación LBS" data-testid="mentor-lbs-note-input" />
              </div>
              <Button size="sm" variant="outline" disabled={savingLbs} onClick={() => toggleLbs(data.lbs_qualified)} data-testid="mentor-lbs-save-button">
                {savingLbs ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Guardar nota
              </Button>
              <p className="text-xs text-slate-500">Aplica a todos los Grupos Frontales. Si no está capacitado, la persona se transfiere a otro mentor con LBS.</p>
            </div>
          </div>
        )}
      </div>

      {data.history?.length > 0 && (
        <div className="rounded-lg border border-[#E8E5DE] bg-white p-5" data-testid="mentor-badge-history">
          <div className="flex items-center gap-2"><History className="h-5 w-5 text-slate-500" /><h3 className="font-['Spectral'] text-xl font-semibold text-[#101D36]">Historial</h3></div>
          <div className="mt-4 space-y-3">
            {data.history.map((item) => (
              <div key={item.history_id} className="flex items-start justify-between border-b border-slate-100 pb-3 text-sm last:border-0" data-testid={`mentor-badge-history-item-${item.history_id}`}>
                <div>
                  <b className="block text-[#101D36]">{ACTION_LABELS[item.action] || item.action}</b>
                  {item.detail?.note && <p className="text-xs text-slate-500">{item.detail.note}</p>}
                  <p className="text-xs text-slate-400">Por {item.actor_name || 'usuario'}</p>
                </div>
                <time className="shrink-0 text-xs text-slate-400">{new Date(item.occurred_at).toLocaleString('es')}</time>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
