import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { Loader2, Repeat } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';

/* «Transferencias pendientes»: personas que pasaron a Consolidación y te quieren
 * transferir (o, a quien supervisa, las pedidas al equipo de Consolidación).
 * Aceptar = pasa a ti (o al mentor elegido); «No puedo» = sigue con quien la visitó. */
export function TransfersPanel({ mentors = [], onChanged }) {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState(null);
  const [chosen, setChosen] = useState({});
  const [busy, setBusy] = useState('');
  const load = useCallback(() => {
    axios.get(`${API}/api/my-work/transfers`, getAuthHeaders()).then((response) => setItems(response.data.items || [])).catch(() => setItems([]));
  }, [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  if (!items || items.length === 0) return null;
  const decide = async (item, action) => {
    if (action === 'accept' && item.to_team && !chosen[item.enrollment_id]) { toast.error('Elija el mentor que le dará seguimiento'); return; }
    setBusy(`${item.enrollment_id}:${action}`);
    try {
      const response = await axios.post(`${API}/api/my-work/transfers/${item.enrollment_id}/${action}`, action === 'accept' ? { mentor_person_id: chosen[item.enrollment_id] || null } : {}, getAuthHeaders());
      toast.success(action === 'accept' ? `${item.person_name} ahora está con ${response.data.mentor_name || 'su nuevo mentor'}` : `${item.person_name} sigue con quien la visitó`);
      load(); if (onChanged) onChanged();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar')); } finally { setBusy(''); }
  };
  return (
    <section className="space-y-2 rounded-2xl border-2 border-amber-300 bg-amber-50 p-3" data-testid="my-work-transfers">
      <p className="flex items-center gap-2 text-base font-semibold text-amber-900"><Repeat className="h-5 w-5" />Transferencias pendientes ({items.length})</p>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.enrollment_id} className="rounded-xl border border-amber-200 bg-white p-3" data-testid="my-work-transfer">
            <p className="text-base font-semibold text-[#101D36]">{item.person_name}</p>
            <p className="text-sm text-slate-700">{item.to_team ? 'Para el equipo de Consolidación' : 'Te la quieren transferir'} · la visitó {item.from_mentor_name || '—'}{item.requested_by_name && item.requested_by_name !== item.from_mentor_name ? ` · la pasó ${item.requested_by_name}` : ''}</p>
            {(item.campaign_name || item.address) && <p className="text-sm text-slate-600">{[item.campaign_name, item.address].filter(Boolean).join(' · ')}</p>}
            {item.books.length > 0 && <p className="text-sm text-slate-600">Libros: {item.books.join(', ')}</p>}
            {item.note && <p className="text-sm italic text-slate-600">«{item.note}»</p>}
            {item.to_team && (
              <select value={chosen[item.enrollment_id] || ''} onChange={(event) => setChosen((current) => ({ ...current, [item.enrollment_id]: event.target.value }))} className="mt-2 h-12 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 text-base" data-testid="my-work-transfer-mentor">
                <option value="">Asignar a…</option>
                {mentors.map((mentor) => <option key={mentor.person_id} value={mentor.person_id}>{mentor.name}</option>)}
              </select>
            )}
            <div className="mt-2 grid grid-cols-3 gap-2">
              <button type="button" onClick={() => decide(item, 'accept')} disabled={Boolean(busy)} className="inline-flex min-h-11 items-center justify-center gap-1 rounded-xl bg-[#132443] text-[15px] font-semibold text-white disabled:opacity-60" data-testid="my-work-transfer-accept">{busy === `${item.enrollment_id}:accept` && <Loader2 className="h-4 w-4 animate-spin" />}{item.to_team ? 'Asignar' : 'Aceptar'}</button>
              <button type="button" onClick={() => decide(item, 'decline')} disabled={Boolean(busy)} className="min-h-11 rounded-xl border border-[#D9D4C7] bg-white text-[15px] font-semibold text-[#101D36]" data-testid="my-work-transfer-decline">No puedo</button>
              <Link to={`/procesos/consolidacion/${item.enrollment_id}`} className="inline-flex min-h-11 items-center justify-center rounded-xl border border-[#D9D4C7] bg-white text-[15px] font-semibold text-[#101D36]">Expediente</Link>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
