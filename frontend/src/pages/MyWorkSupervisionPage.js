import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import { Eye, Loader2 } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import MyWorkPage, { mentorLabel } from './MyWorkPage';

/** MT3 · Supervisar «Mi Trabajo» por mentor (coordinador general, pastoral,
 * encargados de Consolidación): el mismo panel del mentor, en lectura, con
 * selección para reasignar pendientes. El backend valida los permisos. */
export default function MyWorkSupervisionPage() {
  const { API, getAuthHeaders } = useAuth();
  const [params, setParams] = useSearchParams();
  const [mentors, setMentors] = useState(null);
  const [error, setError] = useState('');
  const mentorId = params.get('mentor') || '';
  useEffect(() => {
    axios.get(`${API}/api/my-work/mentors`, getAuthHeaders()).then((response) => setMentors(response.data.items || [])).catch((requestError) => setError(apiErrorMessage(requestError, 'Sin acceso a la supervisión')));
  }, [API, getAuthHeaders]);
  if (error) return <div className="mx-auto max-w-xl p-4"><p className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800" data-testid="my-work-supervision-error">{error}</p></div>;
  if (!mentors) return <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
  const current = mentors.find((item) => item.person_id === mentorId);
  const header = (
    <header className="space-y-2">
      <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.2em] text-[#7A5F22]"><Eye className="h-4 w-4" />Supervisar Mi Trabajo</p>
      <select value={mentorId} onChange={(event) => { const next = new URLSearchParams(params); next.set('mentor', event.target.value); next.delete('vista'); setParams(next, { replace: true }); }}
        className="h-12 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 text-lg font-semibold text-[#101D36]" data-testid="my-work-mentor-select">
        <option value="">Elige un mentor…</option>
        {mentors.map((item) => <option key={item.person_id} value={item.person_id}>{mentorLabel(item)}</option>)}
      </select>
      {current && <p className="text-sm text-slate-600">Vista de supervisión: puedes consultar y reasignar pendientes; cada atención conserva quién la hizo.</p>}
    </header>
  );
  if (!mentorId) return <div className="mx-auto w-full max-w-5xl space-y-4 p-4 sm:p-6" data-testid="my-work-supervision">{header}</div>;
  return <MyWorkPage key={mentorId} mentorPersonId={mentorId} header={header} supervise mentors={mentors} />;
}
