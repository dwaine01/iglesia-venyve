import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { errorDetailText } from '../../lib/errorText';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { PersonMatchDialog } from './PersonMatchDialog';

/* «Pasar a Consolidación» en un toque (desde Mis Visitas, el informe o Mis personas):
 * confirma, abre el expediente («Nuevo y seguimiento») con su origen y, si se elige,
 * pide la transferencia al equipo de Consolidación o a otro mentor (queda pendiente
 * hasta que la acepten). Si ya tenía expediente, lo dice y lo abre. */
export function ToConsolidationDialog({ target, onClose, onDone }) {
  const { API, getAuthHeaders } = useAuth();
  const [who, setWho] = useState('me');
  const [mentorId, setMentorId] = useState('');
  const [note, setNote] = useState('');
  const [mentors, setMentors] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [match, setMatch] = useState(null);

  useEffect(() => {
    if (!target) return;
    setWho('me'); setMentorId(''); setNote(''); setResult(null); setMatch(null);
    // La lista de mentores solo la ve quien puede asignar; si no, se ofrece «yo» o «el equipo».
    axios.get(`${API}/api/mentorship/mentors`, getAuthHeaders()).then((response) => setMentors((response.data.items || []).filter((item) => item.has_account !== false))).catch(() => setMentors([]));
  }, [target, API, getAuthHeaders]);

  if (!target) return null;
  // Se avisa al cerrar (si se recargara la lista antes, se perdería esta pantalla de «Listo»).
  const close = () => { if (result && onDone) onDone(result); onClose(); };
  const send = async (extra = {}) => {
    if (who === 'mentor' && !mentorId) { toast.error('Elija el mentor'); return; }
    setBusy(true);
    try {
      const response = await axios.post(`${API}/api/mentorship/outreach/visits/${target.visit_id}/to-consolidation`, {
        transfer_to: who === 'me' ? null : who === 'team' ? 'team' : mentorId, note: note.trim() || null, ...extra,
      }, getAuthHeaders());
      setResult(response.data); setMatch(null);
      if (response.data.already) toast.info(response.data.message); else toast.success(response.data.message);
    } catch (error) {
      const detail = error?.response?.data?.detail;
      if (error?.response?.status === 409 && detail && typeof detail === 'object' && detail.candidates) {
        setMatch({ message: detail.message, candidates: detail.candidates, requiresConfirmation: Boolean(detail.requires_confirmation) });
      } else toast.error(errorDetailText(error, 'No se pudo pasar a Consolidación'));
    } finally { setBusy(false); }
  };
  const option = (value, label, help) => (
    <label key={value} className={`flex min-h-12 cursor-pointer items-start gap-3 rounded-xl border p-3 ${who === value ? 'border-[#132443] bg-[#F4F6FA]' : 'border-[#E8E5DE] bg-white'}`}>
      <input type="radio" name="to-consolidation-who" value={value} checked={who === value} onChange={() => setWho(value)} className="mt-1 h-5 w-5 accent-[#132443]" data-testid={`to-consolidation-who-${value}`} />
      <span><span className="block text-[15px] font-semibold text-[#101D36]">{label}</span>{help && <span className="block text-sm text-slate-600">{help}</span>}</span>
    </label>
  );

  return (
    <>
      <Dialog open onOpenChange={(open) => { if (!open) close(); }}>
        <DialogContent className="vv-fit bg-white sm:max-w-md" data-testid="to-consolidation-dialog">
          {result ? (
            <div className="space-y-4" data-testid="to-consolidation-done">
              <DialogHeader><DialogTitle className="flex items-center gap-2"><CheckCircle2 className="h-6 w-6 text-emerald-600" />{result.already ? 'Ya estaba en Consolidación' : 'Pasó a Consolidación'}</DialogTitle>
                <DialogDescription className="text-base text-slate-700">{result.message}</DialogDescription></DialogHeader>
              <div className="grid gap-2">
                <Link to={`/procesos/consolidacion/${result.enrollment_id}`} onClick={() => { if (onDone) onDone(result); }} className="inline-flex min-h-12 items-center justify-center rounded-xl bg-[#132443] text-base font-semibold text-white" data-testid="to-consolidation-open">Ver su expediente</Link>
                <button type="button" onClick={close} className="min-h-12 rounded-xl border border-[#D9D4C7] bg-white text-base font-semibold text-[#101D36]">Cerrar</button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <DialogHeader>
                <DialogTitle>¿Pasar a {target.name} a Consolidación?</DialogTitle>
                <DialogDescription>Se abre su expediente en la etapa «Nuevo y seguimiento», con su origen: invasión, vivienda, quién la visitó, libros entregados y notas.</DialogDescription>
              </DialogHeader>
              <div className="space-y-2" role="radiogroup" aria-label="¿Quién le dará seguimiento?">
                <p className="text-sm font-semibold text-slate-700">¿Quién le dará seguimiento?</p>
                {option('me', target.mentorName ? `${target.mentorName} (quien la visitó)` : 'El mentor que la visitó')}
                {option('team', 'El equipo de Consolidación', 'El encargado le asigna mentor. Queda en «Transferencias pendientes».')}
                {mentors && mentors.length > 0 && option('mentor', 'Otro mentor', 'Recibe un aviso y debe aceptarla.')}
                {who === 'mentor' && (
                  <select value={mentorId} onChange={(event) => setMentorId(event.target.value)} className="h-12 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 text-base" data-testid="to-consolidation-mentor">
                    <option value="">Elegir mentor…</option>
                    {mentors.filter((item) => item.person_id !== target.mentorPersonId).map((item) => <option key={item.person_id} value={item.person_id}>{item.name}</option>)}
                  </select>
                )}
              </div>
              <label className="block"><span className="text-sm font-semibold text-slate-700">Nota para Consolidación</span>
                <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={2} className="mt-1 w-full rounded-lg border border-[#D9D4C7] p-3 text-base" placeholder="Ej.: aceptó a Jesús; prefiere llamadas en la noche" data-testid="to-consolidation-note" /></label>
              <div className="sticky-actions">
                <button type="button" onClick={() => send()} disabled={busy} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#132443] text-base font-semibold text-white disabled:opacity-60" data-testid="to-consolidation-confirm">
                  {busy && <Loader2 className="h-5 w-5 animate-spin" />}Sí, pasar a Consolidación
                </button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
      <PersonMatchDialog match={match} busy={busy} onPick={(personId) => send({ person_id: personId })}
        onConfirmDistinct={(reason) => send({ confirm_distinct_person: true, distinct_reason: reason })} onClose={() => setMatch(null)} />
    </>
  );
}
