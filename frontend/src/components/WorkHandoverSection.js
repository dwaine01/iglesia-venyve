import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowRightLeft } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { Label } from './ui/label';

const LABELS = {
  disciples: 'Personas en Consolidación', contacts: 'Contactos con seguimiento', assigned_visits: 'Visitas por hacer',
  households: 'Viviendas pendientes', visitor_followups: 'Seguimientos de visitantes (tableta)', transfers_pending: 'Transferencias que esperan su respuesta',
  books: 'Libros en su poder',
};

/** El 409 del servidor cuando alguien tiene trabajo pendiente: {message, pending_work}. */
export const handoverFromError = (error) => {
  const detail = error?.response?.status === 409 ? error.response.data?.detail : null;
  return detail && typeof detail === 'object' && detail.pending_work ? detail : null;
};

/**
 * Trabajo pendiente de un líder o mentor y a quién pasarlo (auditoría 5/10): nada queda sin responsable
 * al eliminar su cuenta, quitarle la insignia o archivar su Perfil 360.
 */
export function WorkHandoverSection({ work, value, onChange, excludePersonId }) {
  const { API, getAuthHeaders } = useAuth();
  const [mentors, setMentors] = useState([]);
  const [loadError, setLoadError] = useState('');

  useEffect(() => {
    if (!work?.blocking) return;
    axios.get(`${API}/api/my-work/mentors`, getAuthHeaders())
      .then((response) => setMentors((response.data.items || []).filter((item) => item.person_id !== excludePersonId)))
      .catch(() => setLoadError('No se pudo cargar la lista de mentores'));
  }, [API, getAuthHeaders, work, excludePersonId]);

  if (!work?.blocking) return null;
  const rows = Object.entries(work.counts || {}).filter(([, count]) => count > 0);
  return (
    <div className="space-y-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm" data-testid="work-handover">
      <p className="flex items-center gap-2 font-semibold text-amber-900"><ArrowRightLeft className="h-4 w-4" />Tiene trabajo pendiente: elija a quién pasarlo</p>
      <ul className="space-y-1.5" data-testid="work-handover-list">
        {rows.map(([key, count]) => (
          <li key={key}>
            <span className="font-semibold text-[#1B2A4A]">{count}</span> {LABELS[key] || key}
            {(work.samples?.[key] || []).length > 0 && <span className="block text-xs text-slate-600">{work.samples[key].join(' · ')}{count > work.samples[key].length ? ' …' : ''}</span>}
          </li>
        ))}
      </ul>
      <div className="space-y-1.5">
        <Label htmlFor="work-handover-target">Pasar todo a</Label>
        <select id="work-handover-target" value={value || ''} onChange={(event) => onChange(event.target.value)} className="h-12 w-full rounded-md border border-slate-300 bg-white px-3 text-base" data-testid="work-handover-target">
          <option value="">Elija un mentor activo…</option>
          {mentors.map((mentor) => <option key={mentor.person_id} value={mentor.person_id}>{mentor.name}</option>)}
        </select>
        {loadError && <p className="text-xs text-red-700">{loadError}</p>}
        <p className="text-xs text-slate-600">Quién hizo cada atención no cambia; solo cambia el responsable de lo que falta. El nuevo responsable recibe un aviso.</p>
      </div>
    </div>
  );
}
