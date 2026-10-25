import React, { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { Activity, CalendarDays, ChevronRight, ClipboardCheck, ClipboardList, Footprints, Home, MapPinned, Menu, Plus, UserCircle } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { OUTREACH_CHANGED_EVENT, useInvasionToday } from '../../context/InvasionTodayContext';
import { canAccessOutreach, hasCapability, isGeneralCoordinator, isPastoralAuthority } from '../../lib/accessControl';
import { AddVisitDialog } from '../outreach/AddVisitDialog';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';

const HOME_PATHS = ['/', '/dashboard', '/dashboard-general', '/procesos/dashboard', '/mi-trabajo'];
const TYPING_TYPES = new Set(['checkbox', 'radio', 'button', 'submit', 'reset', 'range', 'file', 'color']);

// El teclado en pantalla achica el viewport visual (o hay un campo de texto
// con foco en un dispositivo táctil): la barra se esconde para no tapar el campo.
function useKeyboardOpen() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const viewport = window.visualViewport;
    const touch = window.matchMedia?.('(pointer: coarse)').matches;
    let timer = null;
    let pointerDown = false;
    const isOpen = () => {
      const element = document.activeElement;
      const typing = Boolean(element) && ((element.tagName === 'INPUT' && !TYPING_TYPES.has(element.type)) || element.tagName === 'TEXTAREA' || element.isContentEditable);
      const shrunk = viewport ? window.innerHeight - viewport.height > 150 : false;
      return shrunk || (typing && touch);
    };
    // Se esconde al instante; reaparece con retraso y nunca a mitad de un toque:
    // si la barra volviera de golpe, empujaría el botón fijo de guardar bajo el dedo.
    const check = () => {
      clearTimeout(timer);
      if (isOpen()) { setOpen(true); return; }
      timer = setTimeout(() => { if (!pointerDown && !isOpen()) setOpen(false); else if (!isOpen()) check(); }, 450);
    };
    const down = () => { pointerDown = true; };
    const up = () => { pointerDown = false; check(); };
    viewport?.addEventListener('resize', check);
    document.addEventListener('focusin', check);
    document.addEventListener('focusout', check);
    document.addEventListener('pointerdown', down, true);
    document.addEventListener('pointerup', up, true);
    document.addEventListener('pointercancel', up, true);
    return () => {
      clearTimeout(timer);
      viewport?.removeEventListener('resize', check);
      document.removeEventListener('focusin', check);
      document.removeEventListener('focusout', check);
      document.removeEventListener('pointerdown', down, true);
      document.removeEventListener('pointerup', up, true);
      document.removeEventListener('pointercancel', up, true);
    };
  }, []);
  return open;
}

const Badge = ({ count, testId }) => (count > 0
  ? <span className="absolute -right-2.5 -top-1.5 min-w-[20px] rounded-full bg-[#b91c1c] px-1 text-center text-[11px] font-bold leading-5 text-white ring-2 ring-white" data-testid={testId}>{count > 9 ? '9+' : count}</span>
  : null);

function Item({ to, icon: Icon, label, active, badge, testId, onClick }) {
  const body = (
    <>
      <span className={`absolute inset-x-4 top-0 h-[3px] rounded-b-full ${active ? 'bg-[#132443]' : 'bg-transparent'}`} aria-hidden />
      <span className="relative"><Icon className="h-6 w-6" strokeWidth={active ? 2.4 : 2} /><Badge count={badge} testId={`${testId}-badge`} /></span>
      <span className={`max-w-full truncate leading-4 ${label.length > 11 ? 'text-[10px] tracking-tight min-[380px]:text-[11px]' : 'text-[13px]'}`}>{label}</span>
    </>
  );
  const className = `relative flex min-h-[56px] min-w-0 flex-col items-center justify-center gap-1 px-0.5 ${active ? 'font-semibold text-[#132443]' : 'text-slate-500'}`;
  if (onClick) return <button type="button" onClick={onClick} className={className} data-testid={testId} aria-current={active ? 'page' : undefined}>{body}</button>;
  return <NavLink to={to} className={className} data-testid={testId} aria-current={active ? 'page' : undefined}>{body}</NavLink>;
}

/** Barra inferior tipo app, solo en celular y tablet (< 1024 px). Muestra
 * únicamente los accesos que la persona puede usar; el backend sigue
 * validando cada acción. */
export function MobileBottomNav({ isActiveMentor, menuOpen, onOpenMenu, onAddVisit, onOpenInvasion }) {
  const { user } = useAuth();
  const location = useLocation();
  const { data, current } = useInvasionToday();
  const keyboardOpen = useKeyboardOpen();
  if (!user || keyboardOpen) return null;
  const path = location.pathname;
  const search = new URLSearchParams(location.search);
  const outreach = canAccessOutreach(user, isActiveMentor);
  const invasion = current || data?.active?.[0] || data?.upcoming;
  const canAdd = outreach && data?.can_register_visits;
  const onOutreach = path === '/mentoria/visitas';
  // Coordinadores generales, autoridad, organizador y encargado general: Asistencia
  // (el backend decide quién; un mentor o colaborador nunca recibe `managed`).
  const managed = data?.managed || [];
  const programTarget = managed.find((item) => item.active_today) || invasion || managed[0];
  const onAttendance = /^\/invasiones\/(asistencia|[^/]+\/asistencia)$/.test(path);
  const onProgram = /^\/invasiones\/[^/]+\/programa$/.test(path);

  // Panorama de Consolidación (C3): pastoral, coordinador general y encargados.
  const consolidationViewer = isPastoralAuthority(user) || isGeneralCoordinator(user) || hasCapability(user, 'consolidation.assign');
  const consolidationItem = { key: 'consolidation', to: '/procesos/consolidacion', icon: Activity, label: 'Consolidación', active: path.startsWith('/procesos/consolidacion') };
  // MT2: «Inicio» del mentor activo = Mi Trabajo (la autoridad y coordinadores siguen con su panel).
  const homeTo = isActiveMentor && !isPastoralAuthority(user) && !isGeneralCoordinator(user) ? '/mi-trabajo' : '/';
  const items = [{ key: 'home', to: homeTo, icon: Home, label: 'Inicio', active: HOME_PATHS.includes(path) }];
  if (invasion || managed.length) {
    items.push({ key: 'invasion', icon: Footprints, label: 'Invasión', badge: invasion ? data?.pending_invitations : 0, onClick: onOpenInvasion,
      active: (path === '/mentoria/puerta-a-puerta' && !['pendientes', 'mapa'].includes(search.get('vista'))) || (onOutreach && search.get('tab') !== 'mapa') || (path === '/mi-perfil' && search.has('invasion')) || (path.startsWith('/invasiones/') && !onAttendance && !onProgram) || (!invasion && !consolidationViewer && path === '/procesos/consolidacion') });
  } else if (consolidationViewer) {
    // Acceso directo al módulo (Mi perfil sigue en «Más»).
    items.push(consolidationItem);
  } else {
    items.push({ key: 'profile', to: '/mi-perfil', icon: UserCircle, label: 'Mi perfil', active: path === '/mi-perfil' });
  }
  if (canAdd) items.push({ key: 'add', primary: true });
  if (managed.length) {
    // Con "+" caben 5: Programa queda dentro de Invasión y de Asistencia.
    items.push({ key: 'attendance', to: `/invasiones/${programTarget.campaign_id}/asistencia`, icon: ClipboardCheck, label: 'Asistencia', active: onAttendance });
    // Sin "+": el 4.º lugar es Consolidación para quien ve el panorama (Programa sigue en Invasión y Asistencia).
    if (!canAdd) items.push(consolidationViewer ? consolidationItem : { key: 'program', to: `/invasiones/${programTarget.campaign_id}/programa`, icon: ClipboardList, label: 'Programa', active: onProgram });
  } else if (outreach && invasion) {
    // Con invasión activa hoy: «Casas» abre los pendientes del puerta a puerta (lista y mapa).
    const today = current || data?.active?.[0];
    const onDoors = path === '/mentoria/puerta-a-puerta' && ['pendientes', 'mapa'].includes(search.get('vista'));
    items.push(today && canAdd
      ? { key: 'map', to: `/mentoria/puerta-a-puerta?invasion=${today.campaign_id}&vista=pendientes`, icon: MapPinned, label: 'Casas', active: onDoors }
      : { key: 'map', to: '/mentoria/visitas?tab=mapa', icon: MapPinned, label: 'Casas', active: onOutreach && search.get('tab') === 'mapa' });
  }
  else items.push({ key: 'map', to: '/mapas', icon: MapPinned, label: 'Mapa', active: path === '/mapas' });
  items.push({ key: 'more', icon: Menu, label: 'Más', onClick: onOpenMenu, active: menuOpen });

  return (
    <nav className="shrink-0 border-t border-[#E8E5DE] bg-white/95 pb-[env(safe-area-inset-bottom)] shadow-[0_-4px_16px_rgba(16,29,54,0.06)] backdrop-blur lg:hidden" aria-label="Navegación principal" data-testid="mobile-bottom-nav" data-print-hide>
      <div className="mx-auto grid max-w-2xl" style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}>
        {items.map((item) => (item.primary
          ? <div key="add" className="flex min-h-[56px] items-start justify-center">
              <button type="button" onClick={onAddVisit} className="-mt-5 flex flex-col items-center gap-0.5 text-[13px] font-semibold text-[#132443]" data-testid="mobile-nav-add-visit" aria-label={current ? `Registrar viviendas en ${current.name}` : 'Persona sin vivienda'}>
                <span className="flex h-14 w-14 items-center justify-center rounded-full bg-[#132443] text-white shadow-lg ring-4 ring-white"><Plus className="h-7 w-7" strokeWidth={2.6} /></span>
                Visita
              </button>
            </div>
          : <Item key={item.key} {...item} testId={`mobile-nav-${item.key}`} />))}
      </div>
    </nav>
  );
}

// Varias invasiones activas hoy: se pregunta una sola vez y se recuerda.
function InvasionChooser({ open, onOpenChange, items, onChoose }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white sm:max-w-md" data-testid="mobile-invasion-chooser">
        <DialogHeader><DialogTitle>¿En qué invasión estás hoy?</DialogTitle><DialogDescription>Lo recordaremos para tus próximas visitas. Puedes cambiarlo al agregar una visita.</DialogDescription></DialogHeader>
        <div className="space-y-2">
          {items.map((item) => (
            <button key={item.campaign_id} type="button" onClick={() => onChoose(item)} className="flex min-h-14 w-full items-center justify-between gap-3 rounded-xl border border-[#E8E5DE] bg-white p-3 text-left hover:bg-[#FBFAF7]" data-testid={`mobile-invasion-choose-${item.campaign_id}`}>
              <span className="min-w-0"><span className="block text-base font-semibold text-[#101D36]">{item.name}</span><span className="flex items-center gap-1 text-sm text-slate-500"><CalendarDays className="h-4 w-4" />{item.location || item.day_label}</span></span>
              <ChevronRight className="h-5 w-5 shrink-0 text-slate-400" />
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Barra inferior + sus acciones ("+ Agregar visita" ligada a la invasión
 * del día y el selector cuando hay varias activas). */
export default function MobileBottomBar({ isActiveMentor, menuOpen, onOpenMenu }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data, current, needsChoice, choose } = useInvasionToday();
  const [addOpen, setAddOpen] = useState(false);
  const [chooser, setChooser] = useState(null); // 'add' | 'invasion'
  const outreach = canAccessOutreach(user, isActiveMentor);
  // Con invasión activa hoy y permiso de registrar: el "+" y "Invasión" llevan
  // al puerta a puerta (calle activa + vivienda). Sin invasión: «Persona sin vivienda».
  const doors = (item) => navigate(`/mentoria/puerta-a-puerta?invasion=${item.campaign_id}`);
  const goToInvasion = (item) => {
    const today = item || current || data?.active?.[0];
    if (today && outreach && data?.can_register_visits) { doors(today); return; }
    const target = item || current || data?.active?.[0] || data?.upcoming;
    if (target) navigate(outreach ? `/mentoria/visitas?invasion=${target.campaign_id}` : `/mi-perfil?invasion=${target.campaign_id}`);
    else if (data?.managed?.length) navigate('/procesos/consolidacion'); // coordinador que no participa: panel de invasiones
  };
  const onAddVisit = () => {
    if (needsChoice) setChooser('add');
    else if (current) doors(current);
    else setAddOpen(true);
  };
  const onOpenInvasion = () => (needsChoice ? setChooser('invasion') : goToInvasion());
  const onChoose = (item) => {
    choose(item.campaign_id);
    const next = chooser;
    setChooser(null);
    if (next === 'add') doors(item); else goToInvasion(item);
  };
  return (
    <>
      <MobileBottomNav isActiveMentor={isActiveMentor} menuOpen={menuOpen} onOpenMenu={onOpenMenu} onAddVisit={onAddVisit} onOpenInvasion={onOpenInvasion} />
      <InvasionChooser open={Boolean(chooser)} onOpenChange={(value) => { if (!value) setChooser(null); }} items={data?.active || []} onChoose={onChoose} />
      {data?.can_register_visits && <AddVisitDialog open={addOpen} onOpenChange={setAddOpen} campaigns={data.active} forcedMentorId={user?.person_id}
        defaultCampaignId={current?.campaign_id || ''} invasionDay={current?.day || null} invasionLabel={current?.day_label || ''}
        onCreated={() => window.dispatchEvent(new Event(OUTREACH_CHANGED_EVENT))} />}
    </>
  );
}
