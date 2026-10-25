import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';

const when = (iso) => (iso ? new Date(iso).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' }) : '');
const STEP_ICON = { library: '📚', delivery: '🚪', recipient: '👤', followup: '📞', consolidation: '🌱' };

/** Recorrido de un libro: Librería → mentor → vivienda/persona → seguimiento → Consolidación. */
export function JourneyDialog({ movementId, onClose }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!movementId) return;
    setData(null);
    axios.get(`${API}/api/library/ledger/trace/movement/${movementId}`, getAuthHeaders()).then((response) => setData(response.data)).catch((error) => setData({ error: apiErrorMessage(error, 'No se pudo cargar el recorrido') }));
  }, [API, getAuthHeaders, movementId]);
  return (
    <Dialog open={Boolean(movementId)} onOpenChange={(value) => { if (!value) onClose(); }}>
      <DialogContent className="bg-white sm:max-w-md" data-testid="trace-journey">
        <DialogHeader><DialogTitle>Recorrido del libro</DialogTitle><DialogDescription>{data?.movement ? `${data.movement.quantity} × ${data.movement.book_name}` : ''}</DialogDescription></DialogHeader>
        {!data ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : data.error ? <p className="text-sm text-red-700">{data.error}</p> : (
          <ol className="relative space-y-3 border-l-2 border-[#E8E5DE] pl-5">
            {data.steps.map((step, index) => (
              <li key={index} data-testid={`trace-step-${step.step}`}>
                <span className="absolute -left-[11px] grid h-5 w-5 place-items-center rounded-full bg-white text-xs" aria-hidden>{STEP_ICON[step.step] || '•'}</span>
                <p className="text-[15px] font-semibold text-[#101D36]">{step.title}</p>
                {step.detail && <p className="text-sm text-slate-600">{step.detail}</p>}
                {step.at && <p className="text-xs text-slate-500">{when(step.at)}</p>}
                {step.person_id && <Link to={`/personas/${step.person_id}`} className="text-sm font-semibold text-[#0879BE] underline">Ver perfil</Link>}
                {step.enrollment_id && <Link to={`/procesos/consolidacion/${step.enrollment_id}`} className="text-sm font-semibold text-[#0879BE] underline">Ver expediente</Link>}
              </li>
            ))}
          </ol>
        )}
      </DialogContent>
    </Dialog>
  );
}
