import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Archive, ArrowRight, Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { ProcessShell } from '../../components/processes/ProcessShell';
import { useAuth } from '../../context/AuthContext';
import { displayLabel } from '../../lib/displayLabels';

export default function DiscipleshipPage() {
  const { API, getAuthHeaders } = useAuth(); const [items, setItems] = useState([]); const [loading, setLoading] = useState(true); const load = useCallback(() => axios.get(`${API}/api/processes/enrollments?process_key=discipleship`, getAuthHeaders()).then((response) => setItems(response.data.items || [])).catch((error) => toast.error(error?.response?.data?.detail || 'No se pudo cargar el legado')).finally(() => setLoading(false)), [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  return <ProcessShell title="Discipulado legado" description="Historial anterior conservado sin reescrituras ni conversiones automáticas.">
    <div className="border-l-4 border-amber-500 bg-amber-50 p-4" data-testid="legacy-discipleship-read-only-notice"><div className="flex gap-3"><Archive className="h-5 w-5 text-amber-700" /><div><p className="font-semibold text-amber-950">Solo lectura</p><p className="mt-1 text-sm text-amber-900">Use Formación para programas nuevos. La acreditación histórica siempre requiere una acción explícita.</p><Link to="/formacion" className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-[#0879BE]" data-testid="open-new-formation-link">Abrir Formación <ArrowRight className="h-4 w-4" /></Link></div></div></div>
    {loading ? <div className="flex min-h-40 items-center justify-center"><Loader2 className="h-5 w-5 animate-spin" /></div> : <div className="mt-6 space-y-3">{items.map((item) => <article key={item.enrollment_id} className="border bg-white p-4" data-testid={`legacy-discipleship-${item.enrollment_id}`}><div className="flex flex-col justify-between gap-2 sm:flex-row"><div><b>{item.person?.name || item.person_name_snapshot || item.person_id}</b><p className="text-sm text-slate-500">Etapa {displayLabel(item.current_stage_key)} · {item.progress_pct || 0}%</p></div><span className="text-sm font-semibold text-slate-600">{displayLabel(item.status)}</span></div></article>)}{items.length === 0 && <p className="border border-dashed p-6 text-center text-sm text-slate-500" data-testid="legacy-discipleship-empty">No hay expedientes legados.</p>}</div>}
  </ProcessShell>;
}