import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Maximize } from 'lucide-react';

import { adoptShortPath, rememberedToken, useAppManifest } from '../lib/appManifest';
import { API_BASE } from '../lib/apiBase';
import { useWelcomeSync } from '../lib/useWelcomeSync';

/* Pantalla de la PASTORA «Visitas de hoy» (/b/<enlace>), a pantalla completa:
 * un nombre a la vez, GRANDE, para leerlo en voz alta. La encargada avanza con la
 * flecha derecha y retrocede con la izquierda (teclado o botones táctiles). TODAS las
 * pantallas abiertas (tableta, ProPresenter, otra pestaña) y el panel del operador
 * muestran el mismo nombre: la posición es una sola y vive en el servidor. El enlace
 * puede leer los nombres y mover esa posición; quitar o corregir se hace en «Bienvenida en vivo». */

const API = API_BASE;
const C = { bg: '#0B1530', gold: '#E7C766', white: '#FFFFFF', soft: 'rgba(255,255,255,0.78)' };

export default function WelcomeScreenPage() {
  const params = useParams();
  // El enlace se guarda en el equipo: el acceso directo «Bienvenida» abre sin el enlace en la dirección.
  const [token] = useState(() => rememberedToken('vv_screen_link', params.token));
  useAppManifest('/manifest-bienvenida.json', 'Bienvenida');
  const [view, setView] = useState(null);
  const [linkError, setLinkError] = useState(token ? '' : 'Abra el enlace de pantalla que aparece en Registro de visitantes › Enlaces.');
  const [offline, setOffline] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((value) => value + 1), []);
  const { position, live, move, accept } = useWelcomeSync({ api: API, mode: 'screen', linkToken: token, onNamesChanged: reload, enabled: Boolean(token) && !linkError });

  useEffect(() => {
    if (!token) return undefined;
    let alive = true;
    const load = () => axios.get(`${API}/api/screen/welcome`, { params: { link: token }, timeout: 8000 })
      .then((response) => { if (alive) { setView(response.data); accept(response.data.position); setOffline(false); setLinkError(''); adoptShortPath('vv_screen_link', response.data.short_path); } })
      .catch((requestError) => { if (!alive) return; if (requestError?.response?.status === 401) setLinkError(requestError.response.data?.detail || 'Este enlace ya no funciona.'); else setOffline(true); });
    load();
    // Con WebSocket la posición llega al instante y la lista se repasa cada 5 s; sin él (respaldo), todo cada 2 s.
    const timer = setInterval(load, live ? 5000 : 2000);
    return () => { alive = false; clearInterval(timer); };
  }, [token, live, reloadKey, accept]);

  // La posición es compartida: la misma persona en todas las pantallas aunque lleguen nuevos o se quite uno.
  const names = useMemo(() => view?.names || [], [view]);
  let index = names.findIndex((item) => item.id === position?.registration_id);
  if (index < 0) index = Math.min(Math.max(0, position?.index ?? 0), Math.max(0, names.length - 1));
  const staleNames = Boolean(position?.registration_id) && names.length > 0 && !names.some((item) => item.id === position.registration_id);
  useEffect(() => { if (staleNames) reload(); }, [staleNames, reload]);
  const go = useCallback((delta) => { if (names.length) move(delta > 0 ? 'next' : 'prev'); }, [names.length, move]);
  useEffect(() => {
    const onKey = (event) => {
      if (['ArrowRight', 'PageDown'].includes(event.key)) { event.preventDefault(); go(1); }
      if (['ArrowLeft', 'PageUp'].includes(event.key)) { event.preventDefault(); go(-1); }
      if (event.key === 'Home') { event.preventDefault(); move('first'); }
      if (event.key === 'End') { event.preventDefault(); move('last'); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [go, move]);
  const fullscreen = () => { if (document.fullscreenElement) document.exitFullscreen?.(); else document.documentElement.requestFullscreen?.(); };

  // Pantalla de la PASTORA (de espaldas a la gente): sin logo ni encabezado; solo «Visitas de hoy» y el nombre,
  // grande y legible a distancia. El operador la mueve; los botones quedan discretos abajo.
  const arrow = (delta, disabled, testId, children) => (
    <button type="button" onClick={() => go(delta)} disabled={disabled} aria-label={delta > 0 ? 'Siguiente nombre' : 'Nombre anterior'} data-testid={testId}
      style={{ minWidth: 'min(14vw, 180px)', minHeight: 'min(8vh, 72px)', borderRadius: 18, border: '2px solid rgba(255,255,255,0.22)', background: 'transparent', color: C.soft,
        fontSize: 'min(2.6vh, 22px)', fontWeight: 700, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, opacity: disabled ? 0.25 : 0.7, cursor: disabled ? 'default' : 'pointer' }}>{children}</button>
  );

  const current = names[index];
  return (
    <div style={{ minHeight: '100vh', background: C.bg, color: C.white, fontFamily: 'Inter, system-ui, sans-serif', display: 'flex', flexDirection: 'column', overflow: 'hidden' }} data-testid="welcome-screen">
      <header style={{ padding: '4vh 5vw 0', textAlign: 'center' }}>
        <p style={{ margin: 0, fontSize: 'min(6vh, 4.5vw)', fontWeight: 800, color: C.gold, letterSpacing: '0.04em', textTransform: 'uppercase' }} data-testid="welcome-screen-title">Visitas de hoy</p>
        {view?.service_label && <p style={{ margin: '0.6vh 0 0', fontSize: 'min(2.6vh, 2vw)', color: C.soft }}>{view.service_label}</p>}
      </header>
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2vh 4vw', textAlign: 'center' }}>
        {linkError ? <div data-testid="welcome-screen-error"><p style={{ fontSize: 'min(6vh, 5vw)', fontWeight: 800, margin: 0 }}>Esta pantalla necesita el enlace nuevo</p><p style={{ fontSize: 'min(3.5vh, 3vw)', color: C.soft }}>{linkError}</p></div>
          : !view ? <p style={{ fontSize: 'min(5vh, 4vw)', color: C.soft }}>Conectando…</p>
            : !current ? <p style={{ fontSize: 'min(7vh, 5vw)', fontWeight: 700, margin: 0, lineHeight: 1.2, color: C.soft }} data-testid="welcome-screen-empty">Todavía no hay visitantes registrados en este servicio</p>
              : (
                <div key={current.id} style={{ animation: 'vvFade 350ms ease-out' }}>
                  <p style={{ margin: 0, fontWeight: 800, lineHeight: 1.04, fontSize: 'min(21vh, 13vw)', letterSpacing: '-0.01em', overflowWrap: 'anywhere' }} data-testid="welcome-screen-name">{current.name}</p>
                  {current.invited_by && <p style={{ margin: '2.4vh 0 0', fontSize: 'min(3.6vh, 2.6vw)', fontWeight: 600, color: C.gold, lineHeight: 1.2, overflowWrap: 'anywhere' }} data-testid="welcome-screen-invited">Invitado por {current.invited_by}</p>}
                  {current.registering && <p style={{ margin: '1.4vh 0 0', fontSize: 'min(2.4vh, 1.8vw)', color: C.soft, fontStyle: 'italic' }} data-testid="welcome-screen-registering">registrando…</p>}
                </div>
              )}
      </main>
      {!linkError && view && (
        <footer style={{ padding: '0 4vw 3vh', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
          {arrow(-1, index <= 0, 'welcome-prev', <><ChevronLeft size={26} aria-hidden />Anterior</>)}
          <p style={{ margin: 0, fontSize: 'min(3vh, 2.4vw)', fontWeight: 700, color: C.soft }} data-testid="welcome-counter">{names.length ? `${index + 1} de ${names.length}` : ''}</p>
          {arrow(1, index >= names.length - 1, 'welcome-next', <>Siguiente<ChevronRight size={26} aria-hidden /></>)}
        </footer>
      )}
      <button type="button" onClick={fullscreen} aria-label="Pantalla completa" style={{ position: 'fixed', right: 16, top: 16, width: 44, height: 44, borderRadius: 12, border: '2px solid rgba(255,255,255,0.2)', background: 'transparent', color: C.soft, opacity: 0.6 }} data-testid="welcome-fullscreen"><Maximize size={22} aria-hidden /></button>
      {offline ? <p style={{ position: 'fixed', left: 16, top: 16, margin: 0, fontSize: 18, color: C.soft }}>Sin conexión: se muestra lo último recibido.</p>
        : view && <span title={live ? 'Sincronizada al instante con las demás pantallas' : 'Sincronizando cada 2 segundos'} style={{ position: 'fixed', left: 16, top: 16, width: 12, height: 12, borderRadius: 6, background: live ? '#3FB27F' : '#E7C766', opacity: 0.7 }} data-testid={live ? 'welcome-sync-live' : 'welcome-sync-polling'} />}
      <style>{'@keyframes vvFade { from { opacity: 0; transform: translateY(1.5vh); } to { opacity: 1; transform: none; } }'}</style>
    </div>
  );
}
