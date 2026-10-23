import React, { useState } from 'react';
import axios from 'axios';
import { ChevronDown, ChevronUp, Home, Loader2, MapPin, Plus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { errorDetailText } from '../../lib/errorText';
import { VisitCard } from './VisitCard';

const RESULT_LABELS = {
  no_answer: 'Sin respuesta',
  not_home: 'No está en casa',
  refused: 'Rechazó',
  contacted: 'Contacto logrado',
};

export const HouseholdCard = ({ household, readOnly, onLogAttempt, onChanged }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState(null);

  const toggle = async () => {
    if (open) { setOpen(false); return; }
    setOpen(true);
    if (detail) return;
    setLoading(true);
    try {
      const response = await axios.get(`${API}/api/mentorship/outreach/households/${household.household_id}`, getAuthHeaders());
      setDetail(response.data);
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo cargar el detalle del hogar'));
    } finally {
      setLoading(false);
    }
  };

  const refresh = async () => {
    setDetail(null);
    if (open) {
      const response = await axios.get(`${API}/api/mentorship/outreach/households/${household.household_id}`, getAuthHeaders());
      setDetail(response.data);
    }
    if (onChanged) onChanged();
  };

  const address = [household.address_line1, household.sector].filter(Boolean).join(' · ') || 'Sin dirección registrada';

  return (
    <div className="rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid={`outreach-household-card-${household.household_id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <button type="button" onClick={toggle} className="flex items-start gap-2 text-left" data-testid={`outreach-household-toggle-${household.household_id}`}>
          <Home className="mt-0.5 h-4 w-4 text-[#132443]" />
          <div>
            <p className="font-semibold text-[#101D36]">{address}</p>
            <p className="mt-0.5 flex items-center gap-1 text-xs text-slate-500">
              {household.is_draft && <Badge variant="outline" className="mr-1 text-[10px]">Borrador</Badge>}
              {household.attempts || 0} intento(s)
              {household.campaign_name && <span>· {household.campaign_name}</span>}
            </p>
          </div>
        </button>
        <div className="flex items-center gap-2">
          {!readOnly && (
            <Button size="sm" variant="outline" onClick={() => onLogAttempt(household)} data-testid={`outreach-household-log-attempt-${household.household_id}`}>
              <Plus className="h-4 w-4" /> Registrar intento
            </Button>
          )}
          <button type="button" onClick={toggle} data-testid={`outreach-household-expand-${household.household_id}`}>
            {open ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
          </button>
        </div>
      </div>

      {open && (
        <div className="mt-4 space-y-3 border-t border-[#E8E5DE] pt-3">
          {loading || !detail ? (
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          ) : (
            <>
              <div className="space-y-1.5" data-testid={`outreach-household-events-${household.household_id}`}>
                {detail.events.length === 0 && <p className="text-xs text-slate-400">Sin intentos registrados todavía.</p>}
                {detail.events.map((event) => (
                  <div key={event.visit_event_id} className="flex items-center gap-2 text-xs text-slate-600">
                    <MapPin className="h-3 w-3 text-slate-400" />
                    <span className="font-medium">{RESULT_LABELS[event.result] || event.result}</span>
                    <span>· {new Date(event.occurred_at).toLocaleString('es-DO')}</span>
                    {event.is_draft && <Badge variant="outline" className="text-[10px]">Borrador</Badge>}
                    {event.note && <span className="text-slate-400">· {event.note}</span>}
                  </div>
                ))}
              </div>
              {detail.visits.length > 0 && (
                <div className="space-y-3">
                  {detail.visits.map((visit) => (
                    <VisitCard key={`${visit.visit_id}-${visit.updated_at}`} visit={visit} canManage={false} onUpdated={refresh} onTransfer={() => {}} />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};
