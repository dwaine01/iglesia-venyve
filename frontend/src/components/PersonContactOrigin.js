import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { BookOpen, DoorOpen, MapPin, Route, UserRoundCheck } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { JourneyDialog } from './library/JourneyDialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from './ui/alert-dialog';

// Perfil 360 · «Contactado por»: de dónde llegó la persona (visita de
// invasión y libros). «Mentor actual» sigue siendo la asignación de
// Consolidación; quien la contactó se muestra aparte.

/** Fecha corta en español; las fechas sin hora (AAAA-MM-DD) no se corren de día. */
export const shortDate = (value) => {
  if (!value) return '';
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00`) : new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' }).replace('.', '');
};

export const invasionLabel = (name) => (name ? `Invasión · ${name}` : 'Invasión');

export function useContactOrigin(personId) {
  const { API, getAuthHeaders } = useAuth();
  const [origin, setOrigin] = useState(null);
  const refresh = useCallback(() => {
    if (!personId) return;
    axios.get(`${API}/api/persons/${personId}/contact-origin`, getAuthHeaders()).then((response) => setOrigin(response.data)).catch(() => setOrigin(null));
  }, [API, getAuthHeaders, personId]);
  useEffect(() => { setOrigin(null); refresh(); }, [refresh]);
  return [origin, refresh];
}

/** «Asignar a <mentor>»: un toque, con confirmación (solo consolidation.assign; el backend valida). */
function AssignButton({ personId, origin, onAssigned }) {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const name = origin.first_contact?.mentor_name || 'su mentor';
  const assign = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/persons/${personId}/assign-contact-mentor`, {}, getAuthHeaders());
      toast.success(`Asignado a ${name} en Consolidación`);
      setOpen(false);
      onAssigned?.();
    } catch (error) {
      toast.error(apiErrorMessage(error, 'No se pudo asignar'));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="inline-flex min-h-11 items-center justify-center rounded-xl bg-[#101D36] px-4 text-[15px] font-semibold text-white" data-testid="contact-assign-button">Asignar a {name}</button>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent className="bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle>¿Asignar a {name}?</AlertDialogTitle>
            <AlertDialogDescription>Se abre (o se completa) su expediente de Consolidación con {name} como mentor, igual que «Iniciar 7 Semanas» desde la visita.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="min-h-11">Cancelar</AlertDialogCancel>
            <AlertDialogAction className="min-h-11" disabled={busy} onClick={(event) => { event.preventDefault(); assign(); }} data-testid="contact-assign-confirm">Sí, asignar</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

/** Cabecera: primer contacto + mentor actual (separados). */
export function ContactOriginCard({ personId, origin, onAssigned }) {
  const [journey, setJourney] = useState(null);
  if (!origin?.first_contact && !origin?.current_mentor) return null;
  const first = origin.first_contact;
  const current = origin.current_mentor;
  return (
    <section className="space-y-3 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid="contact-origin-card">
      {first && (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-[#7A5F22]">Primer contacto · Contactado por</p>
            <p className="mt-1 text-base text-[#101D36]" data-testid="contact-origin-line">
              <b>{first.mentor_name || 'Mentor'}</b>
              {[shortDate(first.at), first.campaign_name ? invasionLabel(first.campaign_name) : null, first.address, first.book ? `Libro ${first.book.book_name} entregado` : null].filter(Boolean).map((part) => <span key={part}> · {part}</span>)}
            </p>
          </div>
          {first.book?.movement_id && <button type="button" onClick={() => setJourney(first.book.movement_id)} className="inline-flex min-h-11 items-center gap-1 rounded-xl border border-[#D9D4C7] px-3 text-[15px] font-semibold text-[#101D36]" data-testid="contact-origin-journey"><Route className="h-4 w-4" />Ver recorrido</button>}
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#F1EFEA] pt-3">
        <p className="flex items-center gap-2 text-base text-[#101D36]" data-testid="contact-current-mentor">
          <UserRoundCheck className="h-4 w-4 text-blue-700" />
          <span>Mentor actual: <b>{current?.name || 'Pendiente de asignar'}</b>{!current && first?.mentor_name ? ` · Contactado por ${first.mentor_name}` : ''}</span>
        </p>
        {origin.can_assign && <AssignButton personId={personId} origin={origin} onAssigned={onAssigned} />}
      </div>
      <JourneyDialog movementId={journey} onClose={() => setJourney(null)} />
    </section>
  );
}

const KIND_ICON = { visit: DoorOpen, book: BookOpen };

/** Historial del contacto: visitas (abrieron / no abrieron), libros, seguimiento y Consolidación. */
export function ContactHistory({ origin }) {
  const [journey, setJourney] = useState(null);
  const rows = origin?.history || [];
  if (!rows.length) return null;
  return (
    <section className="space-y-2" data-testid="contact-history">
      <h3 className="font-serif text-lg text-[#132443]">Recorrido de contacto</h3>
      <ol className="divide-y divide-[#F1EFEA] rounded-xl border border-[#EEECE6]">
        {rows.map((row, index) => {
          const Icon = KIND_ICON[row.kind] || MapPin;
          const content = (
            <>
              <Icon className="mt-1 h-4 w-4 shrink-0 text-[#7A5F22]" />
              <span className="min-w-0">
                <span className="block text-[15px] font-semibold text-[#101D36]">{row.title}{row.detail ? <span className="font-normal text-slate-600"> · {row.detail}</span> : null}</span>
                <span className="block text-sm text-slate-600">{[shortDate(row.at), row.mentor, row.campaign ? invasionLabel(row.campaign) : null, row.address].filter(Boolean).join(' · ')}</span>
              </span>
            </>
          );
          return (
            <li key={`${row.kind}-${index}`} data-testid={`contact-history-${row.kind}`}>
              {row.movement_id
                ? <button type="button" onClick={() => setJourney(row.movement_id)} className="flex min-h-11 w-full items-start gap-3 px-3 py-2 text-left hover:bg-[#FBFAF7]">{content}</button>
                : <div className="flex min-h-11 items-start gap-3 px-3 py-2">{content}</div>}
            </li>
          );
        })}
      </ol>
      <JourneyDialog movementId={journey} onClose={() => setJourney(null)} />
    </section>
  );
}
