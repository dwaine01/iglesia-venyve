import React, { useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
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
import { errorDetailText } from '../../lib/errorText';
import { PersonMatchDialog } from './PersonMatchDialog';

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

const DECISION_LABELS = {
  pending: 'Pendiente de contacto',
  no_response: 'Intento sin respuesta',
  pending_decision: 'Pendiente de decisión',
  desisted: 'Desistió',
  accepted: 'Aceptó seguimiento',
  start_scheduled: 'Inicio acordado',
};

const boolToTri = (value) => (value === true ? 'yes' : value === false ? 'no' : 'unspecified');
const triToBool = (value) => (value === 'yes' ? true : value === 'no' ? false : null);

export const VisitCard = ({ visit, canManage, onUpdated, onTransfer, highlight = false }) => {
  const { API, getAuthHeaders } = useAuth();
  const [status, setStatus] = useState(visit.status);
  const [visitDate, setVisitDate] = useState(visit.visit_date || '');
  const [receivedMcd, setReceivedMcd] = useState(Boolean(visit.received_mcd));
  const [receivedNpt, setReceivedNpt] = useState(Boolean(visit.received_npt));
  const [lbsDecision, setLbsDecision] = useState(visit.lbs_decision || 'none');
  const [birthDate, setBirthDate] = useState(visit.contact_birth_date || '');
  const [spiritualStatus, setSpiritualStatus] = useState(visit.spiritual_status || 'unspecified');
  const [attendsChurch, setAttendsChurch] = useState(boolToTri(visit.attends_church));
  const [isBackslidden, setIsBackslidden] = useState(boolToTri(visit.is_backslidden));
  const [addressLine1, setAddressLine1] = useState(visit.address_line1 || '');
  const [addressLine2, setAddressLine2] = useState(visit.address_line2 || '');
  const [addressCity, setAddressCity] = useState(visit.address_city || '');
  const [addressState, setAddressState] = useState(visit.address_state || '');
  const [addressZip, setAddressZip] = useState(visit.address_zip || '');
  const [agreedStartDate, setAgreedStartDate] = useState(visit.agreed_start_date || '');
  const [callSchedule, setCallSchedule] = useState(visit.call_schedule || 'unspecified');
  const [note, setNote] = useState(visit.note || '');
  const [busy, setBusy] = useState(false);

  const [personMatch, setPersonMatch] = useState(null);

  const extractMatch = (error, action) => {
    const detail = error?.response?.data?.detail;
    if (error?.response?.status === 409 && detail && typeof detail === 'object' && detail.candidates) {
      setPersonMatch({ action, message: detail.message, candidates: detail.candidates, requiresConfirmation: Boolean(detail.requires_confirmation) });
      return true;
    }
    return false;
  };

  const save = async (overrides = {}) => {
    setBusy(true);
    try {
      await axios.put(`${API}/api/mentorship/outreach/visits/${visit.visit_id}/report`, {
        status, visit_date: visitDate || null, received_mcd: receivedMcd, received_npt: receivedNpt, lbs_decision: lbsDecision,
        contact_birth_date: birthDate || null, spiritual_status: spiritualStatus === 'unspecified' ? null : spiritualStatus,
        attends_church: triToBool(attendsChurch), is_backslidden: triToBool(isBackslidden),
        address_line1: addressLine1 || null, address_line2: addressLine2 || null, address_city: addressCity || null,
        address_state: addressState || null, address_zip: addressZip || null, agreed_start_date: agreedStartDate || null,
        call_schedule: callSchedule === 'unspecified' ? null : callSchedule, note: note || null,
        ...overrides,
      }, getAuthHeaders());
      toast.success('Informe actualizado');
      setPersonMatch(null);
      if (onUpdated) onUpdated();
    } catch (error) {
      if (!extractMatch(error, { type: 'save', overrides })) toast.error(errorDetailText(error, 'No se pudo guardar el informe'));
    } finally {
      setBusy(false);
    }
  };

  const startSevenWeeks = async (overrides = {}) => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/mentorship/outreach/visits/${visit.visit_id}/start-seven-weeks`, overrides, getAuthHeaders());
      toast.success('Se inició la Ley de las 7 Semanas');
      setPersonMatch(null);
      if (onUpdated) onUpdated();
    } catch (error) {
      if (!extractMatch(error, { type: 'start', overrides })) toast.error(errorDetailText(error, 'No se pudo iniciar el proceso'));
    } finally {
      setBusy(false);
    }
  };

  const pickPersonMatch = (personId) => {
    const { type, overrides } = personMatch.action;
    const next = { ...overrides, person_id: personId };
    if (type === 'save') save(next); else startSevenWeeks(next);
  };

  const confirmDistinctPerson = (reason) => {
    const { type, overrides } = personMatch.action;
    const next = { ...overrides, confirm_distinct_person: true, distinct_reason: reason };
    if (type === 'save') save(next); else startSevenWeeks(next);
  };

  const needsTransfer = visit.lbs_decision === 'needs_lbs' && !visit.mentor_lbs_qualified;
  const locked = Boolean(visit.read_only);

  return (
    <>
    <div id={`visita-${visit.visit_id}`} className={`rounded-xl border bg-white p-4 shadow-sm ${highlight ? 'border-[#C8A951] ring-2 ring-[#C8A951]/50' : 'border-[#E8E5DE]'}`} data-testid={`outreach-visit-card-${visit.visit_id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-[#101D36]" data-testid={`outreach-visit-name-${visit.visit_id}`}>{visit.contact_name || 'Sin nombre'}</p>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            {visit.contact_phone && <span className="inline-flex items-center gap-1"><Phone className="h-3 w-3" />{visit.contact_phone}</span>}
            {visit.contact_zone && <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3" />{visit.contact_zone}</span>}
            {visit.campaign_name && <span>· {visit.campaign_name}</span>}
            {visit.household_id && <span data-testid={`outreach-visit-household-badge-${visit.visit_id}`}>· Hogar</span>}
            {canManage && visit.mentor_name && <span>· Mentor: {visit.mentor_name}</span>}
          </div>
          {visit.assigned_by_name && <p className="mt-1 text-xs font-semibold text-[#9A7A2F]" data-testid={`outreach-visit-assigned-by-${visit.visit_id}`}>Asignada por {visit.assigned_by_name}{visit.assigned_at ? ` · ${new Date(visit.assigned_at).toLocaleDateString('es-US', { day: 'numeric', month: 'short' })}` : ''}</p>}
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge className={STATUS_COLORS[visit.status]} data-testid={`outreach-visit-status-badge-${visit.visit_id}`}>{STATUS_LABELS[visit.status]}</Badge>
          {visit.decision_status && <Badge variant="outline" className="text-[10px]" data-testid={`outreach-visit-decision-badge-${visit.visit_id}`}>{DECISION_LABELS[visit.decision_status] || visit.decision_status}</Badge>}
          {locked && <Badge variant="outline" className="border-slate-300 text-[10px] text-slate-500" data-testid={`outreach-visit-readonly-badge-${visit.visit_id}`}>Solo lectura · supervisión</Badge>}
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Estado de la visita</Label>
          <Select value={status} onValueChange={setStatus} disabled={locked || Boolean(visit.enrollment_id)}>
            <SelectTrigger data-testid={`outreach-visit-status-select-${visit.visit_id}`}><SelectValue /></SelectTrigger>
            <SelectContent className="bg-white">
              {Object.entries(STATUS_LABELS).map(([key, label]) => <SelectItem key={key} value={key}>{label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Fecha de visita</Label>
          <Input type="date" value={visitDate} onChange={(event) => setVisitDate(event.target.value)} disabled={locked} data-testid={`outreach-visit-date-input-${visit.visit_id}`} />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <label className={`flex min-h-11 items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm ${visit.mcd_delivered ? 'opacity-70' : ''}`} data-testid={`outreach-visit-mcd-checkbox-${visit.visit_id}`}>
          <Checkbox checked={receivedMcd} disabled={locked || visit.mcd_delivered} onCheckedChange={(value) => setReceivedMcd(Boolean(value))} className="h-6 w-6" /> Recibió &quot;Mi conexión con Dios&quot;{visit.mcd_delivered ? ' (ya entregado)' : ''}
        </label>
        <label className={`flex min-h-11 items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm ${visit.npt_delivered ? 'opacity-70' : ''}`} data-testid={`outreach-visit-npt-checkbox-${visit.visit_id}`}>
          <Checkbox checked={receivedNpt} disabled={locked || visit.npt_delivered} onCheckedChange={(value) => setReceivedNpt(Boolean(value))} className="h-6 w-6" /> Recibió &quot;Nací para triunfar&quot;{visit.npt_delivered ? ' (ya entregado)' : ''}
        </label>
      </div>
      {(receivedMcd || receivedNpt) && <p className="mt-1 text-xs text-slate-400" data-testid={`outreach-visit-delivery-hint-${visit.visit_id}`}>Al guardar, se descuenta 1 unidad de su inventario de Librería 360 por cada material marcado.</p>}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Fecha de nacimiento</Label>
          <Input type="date" value={birthDate} onChange={(event) => setBirthDate(event.target.value)} disabled={locked} data-testid={`outreach-visit-birthdate-input-${visit.visit_id}`} />
        </div>
        <div className="space-y-1.5">
          <Label>Estado espiritual</Label>
          <Select value={spiritualStatus} onValueChange={setSpiritualStatus} disabled={locked}>
            <SelectTrigger data-testid={`outreach-visit-spiritual-status-select-${visit.visit_id}`}><SelectValue /></SelectTrigger>
            <SelectContent className="bg-white">
              <SelectItem value="unspecified">Sin especificar</SelectItem>
              <SelectItem value="cristiano">Cristiano</SelectItem>
              <SelectItem value="no_cristiano">No cristiano</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>¿Asiste a una iglesia?</Label>
          <Select value={attendsChurch} onValueChange={setAttendsChurch} disabled={locked}>
            <SelectTrigger data-testid={`outreach-visit-attends-church-select-${visit.visit_id}`}><SelectValue /></SelectTrigger>
            <SelectContent className="bg-white">
              <SelectItem value="unspecified">Sin especificar</SelectItem>
              <SelectItem value="yes">Sí, asiste</SelectItem>
              <SelectItem value="no">No asiste</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>¿Está descarriado?</Label>
          <Select value={isBackslidden} onValueChange={setIsBackslidden} disabled={locked}>
            <SelectTrigger data-testid={`outreach-visit-backslidden-select-${visit.visit_id}`}><SelectValue /></SelectTrigger>
            <SelectContent className="bg-white">
              <SelectItem value="unspecified">Sin especificar</SelectItem>
              <SelectItem value="yes">Sí, descarriado</SelectItem>
              <SelectItem value="no">No</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5 sm:col-span-2">
          <Label>Dirección (calle)</Label>
          <Input value={addressLine1} onChange={(event) => setAddressLine1(event.target.value)} placeholder="Calle y número" disabled={locked} data-testid={`outreach-visit-address-line1-input-${visit.visit_id}`} />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label>Referencia (opcional)</Label>
          <Input value={addressLine2} onChange={(event) => setAddressLine2(event.target.value)} placeholder="Apto, edificio, punto de referencia" disabled={locked} data-testid={`outreach-visit-address-line2-input-${visit.visit_id}`} />
        </div>
        <div className="space-y-1.5">
          <Label>Ciudad</Label>
          <Input value={addressCity} onChange={(event) => setAddressCity(event.target.value)} disabled={locked} data-testid={`outreach-visit-address-city-input-${visit.visit_id}`} />
        </div>
        <div className="space-y-1.5">
          <Label>Estado</Label>
          <Input value={addressState} onChange={(event) => setAddressState(event.target.value)} disabled={locked} data-testid={`outreach-visit-address-state-input-${visit.visit_id}`} />
        </div>
        <div className="space-y-1.5">
          <Label>Código postal</Label>
          <Input value={addressZip} onChange={(event) => setAddressZip(event.target.value)} disabled={locked} data-testid={`outreach-visit-address-zip-input-${visit.visit_id}`} />
        </div>
      </div>

      {status === 'wants_followup' && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2" data-testid={`outreach-visit-call-plan-${visit.visit_id}`}>
          <div className="space-y-1.5">
            <Label>Fecha de inicio acordada</Label>
            <Input type="date" value={agreedStartDate} onChange={(event) => setAgreedStartDate(event.target.value)} disabled={locked} data-testid={`outreach-visit-agreed-start-date-input-${visit.visit_id}`} />
          </div>
          <div className="space-y-1.5">
            <Label>Horario de llamadas acordado</Label>
            <Select value={callSchedule} onValueChange={setCallSchedule} disabled={locked}>
              <SelectTrigger data-testid={`outreach-visit-call-schedule-select-${visit.visit_id}`}><SelectValue /></SelectTrigger>
              <SelectContent className="bg-white">
                <SelectItem value="unspecified">Sin especificar</SelectItem>
                <SelectItem value="morning">Mañana</SelectItem>
                <SelectItem value="midday">Mediodía</SelectItem>
                <SelectItem value="night">Noche</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      )}

      <div className="mt-4 space-y-1.5">
        <Label>LBS</Label>
        <Select value={lbsDecision} onValueChange={setLbsDecision} disabled={locked}>
          <SelectTrigger data-testid={`outreach-visit-lbs-select-${visit.visit_id}`}><SelectValue /></SelectTrigger>
          <SelectContent className="bg-white">
            <SelectItem value="none">Sin decisión</SelectItem>
            <SelectItem value="accepted">Aceptó LBS</SelectItem>
            <SelectItem value="needs_lbs">Necesita LBS</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {needsTransfer && !locked && (
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
        <Textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Observaciones de la visita" disabled={locked} data-testid={`outreach-visit-note-input-${visit.visit_id}`} />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {!locked && (
          <Button size="sm" disabled={busy} onClick={() => save()} className="bg-[#132443]" data-testid={`outreach-visit-save-button-${visit.visit_id}`}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Guardar informe
          </Button>
        )}
        {!locked && visit.status === 'wants_followup' && !visit.enrollment_id && (
          <Button size="sm" variant="outline" disabled={busy} onClick={() => startSevenWeeks()} data-testid={`outreach-visit-start-seven-weeks-button-${visit.visit_id}`}>
            <Sparkles className="h-4 w-4" /> Iniciar Ley de las 7 Semanas
          </Button>
        )}
        {!locked && status === 'wants_followup' && visit.status !== 'wants_followup' && !visit.enrollment_id && (
          <p className="text-xs text-slate-500" data-testid={`outreach-visit-unsaved-status-hint-${visit.visit_id}`}>Guarde el informe para poder iniciar la Ley de las 7 Semanas.</p>
        )}
        {visit.enrollment_id && (
          <Link to={`/procesos/consolidacion/${visit.enrollment_id}`} data-testid={`outreach-visit-seven-weeks-badge-${visit.visit_id}`}>
            <Badge variant="outline" className="cursor-pointer hover:bg-[#F6F4EF]">
              <CheckCircle2 className="mr-1 h-3.5 w-3.5" />7 Semanas iniciada · Ver expediente
            </Badge>
          </Link>
        )}
      </div>
    </div>
    <PersonMatchDialog match={personMatch} busy={busy} onPick={pickPersonMatch} onConfirmDistinct={confirmDistinctPerson} onClose={() => setPersonMatch(null)} />
    </>
  );
};
