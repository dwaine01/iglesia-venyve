import React, { useState } from 'react';
import axios from 'axios';
import { CheckCircle2, Loader2, MapPin, Phone, Save, Sparkles } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';

const STATUS_LABELS = {
  assigned: 'Asignado',
  not_found: 'No encontrado',
  visited: 'Visitado',
  rejected: 'Rechazó',
  wants_followup: 'Quiere seguimiento',
};

const STATUS_COLORS = {
  assigned: 'bg-slate-100 text-slate-700',
  not_found: 'bg-amber-100 text-amber-800',
  visited: 'bg-blue-100 text-blue-800',
  rejected: 'bg-red-100 text-red-800',
  wants_followup: 'bg-emerald-100 text-emerald-800',
};

export const VisitCard = ({ visit, canManage, onUpdated, onTransfer }) => {
  const { API, getAuthHeaders } = useAuth();
  const [status, setStatus] = useState(visit.status);
  const [visitDate, setVisitDate] = useState(visit.visit_date || '');
  const [receivedMcd, setReceivedMcd] = useState(Boolean(visit.received_mcd));
  const [receivedNpt, setReceivedNpt] = useState(Boolean(visit.received_npt));
  const [lbsDecision, setLbsDecision] = useState(visit.lbs_decision || 'none');
  const [note, setNote] = useState(visit.note || '');
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await axios.put(`${API}/api/mentorship/outreach/visits/${visit.visit_id}/report`, {
        status, visit_date: visitDate || null, received_mcd: receivedMcd, received_npt: receivedNpt, lbs_decision: lbsDecision, note: note || null,
      }, getAuthHeaders());
      toast.success('Informe actualizado');
      if (onUpdated) onUpdated();
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'No se pudo guardar el informe');
    } finally {
      setBusy(false);
    }
  };

  const startSevenWeeks = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/mentorship/outreach/visits/${visit.visit_id}/start-seven-weeks`, {}, getAuthHeaders());
      toast.success('Se inició la Ley de las 7 Semanas');
      if (onUpdated) onUpdated();
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'No se pudo iniciar el proceso');
    } finally {
      setBusy(false);
    }
  };

  const needsTransfer = visit.lbs_decision === 'needs_lbs' && !visit.mentor_lbs_qualified;

  return (
    <div className="rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid={`outreach-visit-card-${visit.visit_id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-[#101D36]" data-testid={`outreach-visit-name-${visit.visit_id}`}>{visit.contact_name || 'Sin nombre'}</p>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            {visit.contact_phone && <span className="inline-flex items-center gap-1"><Phone className="h-3 w-3" />{visit.contact_phone}</span>}
            {visit.contact_zone && <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3" />{visit.contact_zone}</span>}
            {visit.campaign_name && <span>· {visit.campaign_name}</span>}
            {canManage && visit.mentor_name && <span>· Mentor: {visit.mentor_name}</span>}
          </div>
        </div>
        <Badge className={STATUS_COLORS[visit.status]} data-testid={`outreach-visit-status-badge-${visit.visit_id}`}>{STATUS_LABELS[visit.status]}</Badge>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Estado de la visita</Label>
          <Select value={status} onValueChange={setStatus} disabled={Boolean(visit.enrollment_id)}>
            <SelectTrigger data-testid={`outreach-visit-status-select-${visit.visit_id}`}><SelectValue /></SelectTrigger>
            <SelectContent className="bg-white">
              {Object.entries(STATUS_LABELS).map(([key, label]) => <SelectItem key={key} value={key}>{label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Fecha de visita</Label>
          <Input type="date" value={visitDate} onChange={(event) => setVisitDate(event.target.value)} data-testid={`outreach-visit-date-input-${visit.visit_id}`} />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <label className="flex min-h-11 items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm" data-testid={`outreach-visit-mcd-checkbox-${visit.visit_id}`}>
          <Checkbox checked={receivedMcd} onCheckedChange={(value) => setReceivedMcd(Boolean(value))} className="h-6 w-6" /> Recibió &quot;Mi conexión con Dios&quot;
        </label>
        <label className="flex min-h-11 items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm" data-testid={`outreach-visit-npt-checkbox-${visit.visit_id}`}>
          <Checkbox checked={receivedNpt} onCheckedChange={(value) => setReceivedNpt(Boolean(value))} className="h-6 w-6" /> Recibió &quot;Nací para triunfar&quot;
        </label>
      </div>

      <div className="mt-4 space-y-1.5">
        <Label>LBS</Label>
        <Select value={lbsDecision} onValueChange={setLbsDecision}>
          <SelectTrigger data-testid={`outreach-visit-lbs-select-${visit.visit_id}`}><SelectValue /></SelectTrigger>
          <SelectContent className="bg-white">
            <SelectItem value="none">Sin decisión</SelectItem>
            <SelectItem value="accepted">Aceptó LBS</SelectItem>
            <SelectItem value="needs_lbs">Necesita LBS</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {needsTransfer && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900" data-testid={`outreach-visit-transfer-warning-${visit.visit_id}`}>
          <span>Necesita LBS y este mentor no está capacitado.</span>
          <Button size="sm" variant="outline" onClick={() => onTransfer(visit)} data-testid={`outreach-visit-transfer-button-${visit.visit_id}`}>Transferir a mentor capacitado</Button>
        </div>
      )}
      {!needsTransfer && lbsDecision === 'needs_lbs' && visit.lbs_decision !== 'needs_lbs' && (
        <p className="mt-2 text-xs text-amber-700" data-testid={`outreach-visit-unsaved-lbs-hint-${visit.visit_id}`}>Guarde el informe para habilitar, si corresponde, la transferencia a un mentor capacitado en LBS.</p>
      )}

      <div className="mt-4 space-y-1.5">
        <Label>Nota</Label>
        <Textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Observaciones de la visita" data-testid={`outreach-visit-note-input-${visit.visit_id}`} />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button size="sm" disabled={busy} onClick={save} className="bg-[#132443]" data-testid={`outreach-visit-save-button-${visit.visit_id}`}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Guardar informe
        </Button>
        {visit.status === 'wants_followup' && !visit.enrollment_id && (
          <Button size="sm" variant="outline" disabled={busy} onClick={startSevenWeeks} data-testid={`outreach-visit-start-seven-weeks-button-${visit.visit_id}`}>
            <Sparkles className="h-4 w-4" /> Iniciar Ley de las 7 Semanas
          </Button>
        )}
        {status === 'wants_followup' && visit.status !== 'wants_followup' && !visit.enrollment_id && (
          <p className="text-xs text-slate-500" data-testid={`outreach-visit-unsaved-status-hint-${visit.visit_id}`}>Guarde el informe para poder iniciar la Ley de las 7 Semanas.</p>
        )}
        {visit.enrollment_id && (
          <Badge variant="outline" data-testid={`outreach-visit-seven-weeks-badge-${visit.visit_id}`}>
            <CheckCircle2 className="mr-1 h-3.5 w-3.5" />7 Semanas iniciada
          </Badge>
        )}
      </div>
    </div>
  );
};
