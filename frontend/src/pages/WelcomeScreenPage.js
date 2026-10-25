import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Maximize } from 'lucide-react';

import { adoptShortPath, rememberedToken, useAppManifest } from '../lib/appManifest';

/* Pantalla de bienvenida (/pantalla-bienvenida/<enlace>), a pantalla completa:
 * un nombre a la vez, GRANDE, para leerlo en voz alta. La encargada avanza con la
 * flecha derecha y retrocede con la izquierda (teclado o botones táctiles). El
 * enlace solo puede leer los nombres; quitar o corregir se hace en «Bienvenida en
 * vivo». ProPresenter o el operador pueden abrir esta misma página. */

const API = process.env.REACT_APP_BACKEND_URL;
const C = { bg: '#0B1530', gold: '#E7C766', white: '#FFFFFF', soft: 'rgba(255,255,255,0.78)' };

export default function WelcomeScreenPage() {
  const params = useParams();
  // El enlace se guarda en el equipo: el acceso directo «Bienvenida» abre sin el enlace en la dirección.
  const [token] = useState(() => rememberedToken('vv_screen_link', params.token));
  useAppManifest('/manifest-bienvenida.json', 'Bienvenida');
  const [view, setView] = useState(null);
  const [linkError, setLinkError] = useState(token ? '' : 'Abra el enlace de pantalla que aparece en Registro de visitantes › Enlaces.');
  const [offline, setOffline] = useState(false);
  const [currentId, setCurrentId] = useState(null);
  const lastIndex = useRef(0);

  useEffect(() => {
    if (!token) return undefined;
    let alive = true;
    const load = () => axios.get(`${API}/api/screen/welcome`, { params: { link: token }, timeout: 8000 })
      .then((response) => { if (alive) { setView(response.data); setOffline(false); setLinkError(''); adoptShortPath('vv_screen_link', response.data.short_path); } })
      .catch((requestError) => { if (!alive) return; if (requestError?.response?.status === 401) setLinkError(requestError.response.data?.detail || 'Este enlace ya no funciona.'); else setOffline(true); });
    load();
    const timer = setInterval(load, 2500);
    return () => { alive = false; clearInterval(timer); };
  }, [token]);

  // Se sigue al mismo nombre aunque lleguen nuevos o se quite uno.
  const names = useMemo(() => view?.names || [], [view]);
  let index = names.findIndex((item) => item.id === currentId);
  if (index < 0) index = Math.min(lastIndex.current, Math.max(0, names.length - 1));
  lastIndex.current = index;
  const go = useCallback((delta) => {
    if (!names.length) return;
    const next = Math.min(names.length - 1, Math.max(0, index + delta));
    setCurrentId(names[next].id); lastIndex.current = next;
  }, [names, index]);
  useEffect(() => {
    const onKey = (event) => {
      if (['ArrowRight', 'PageDown'].includes(event.key)) { event.preventDefault(); go(1); }
      if (['ArrowLeft', 'PageUp'].includes(event.key)) { event.preventDefault(); go(-1); }
      if (event.key === 'Home') { event.preventDefault(); go(-names.length); }
      if (event.key === 'End') { event.preventDefault(); go(names.length); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [go, names.length]);
  const fullscreen = () => { if (document.fullscreenElement) document.exitFullscreen?.(); else document.documentElement.requestFullscreen?.(); };

  const arrow = (delta, disabled, testId, children) => (
    <button type="button" onClick={() => go(delta)} disabled={disabled} aria-label={delta > 0 ? 'Siguiente nombre' : 'Nombre anterior'} data-testid={testId}
      style={{ minWidth: 'min(22vw, 260px)', minHeight: 'min(12vh, 110px)', borderRadius: 24, border: '3px solid rgba(255,255,255,0.35)', background: 'rgba(255,255,255,0.08)', color: C.white,
        fontSize: 'min(4vh, 30px)', fontWeight: 800, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 10, opacity: disabled ? 0.3 : 1, cursor: disabled ? 'default' : 'pointer' }}>{children}</button>
  );

  const current = names[index];
  return (
    <div style={{ minHeight: '100vh', background: C.bg, color: C.white, fontFamily: 'Inter, system-ui, sans-serif', display: 'flex', flexDirection: 'column', overflow: 'hidden' }} data-testid="welcome-screen">
      <header style={{ padding: '3vh 5vw 0', textAlign: 'center' }}>
        {/* El logo tiene letras verdes y azules: va sobre un fondo claro para verse nítido. */}
        <span style={{ display: 'inline-block', background: '#fff', borderRadius: 'min(2.4vh, 24px)', padding: 'min(1.2vh, 12px) min(2.4vh, 24px)', marginBottom: '1.6vh' }}>
          <img src="/logo-iglesia.png" srcSet="/logo-iglesia.png 1x, /logo-iglesia@2x.png 2x" alt="Primera Iglesia del Nazareno · Casa de oración Ven y Ve" style={{ display: 'block', height: '13vh', width: 'auto' }} data-testid="welcome-screen-logo" />
        </span>
        <p style={{ margin: 0, fontFamily: 'Spectral, Georgia, serif', fontSize: 'min(6vh, 5vw)', fontWeight: 700, color: C.gold, lineHeight: 1.1 }}>¡Bienvenidos a Casa de Oración!</p>
        {view?.service_label && <p style={{ margin: '1vh 0 0', fontSize: 'min(3.6vh, 2.8vw)', color: C.soft }}>{view.service_label}</p>}
      </header>
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2vh 4vw', textAlign: 'center' }}>
        {linkError ? <div data-testid="welcome-screen-error"><p style={{ fontSize: 'min(6vh, 5vw)', fontWeight: 800, margin: 0 }}>Esta pantalla necesita el enlace nuevo</p><p style={{ fontSize: 'min(3.5vh, 3vw)', color: C.soft }}>{linkError}</p></div>
          : !view ? <p style={{ fontSize: 'min(5vh, 4vw)', color: C.soft }}>Conectando…</p>
            : !current ? <p style={{ fontSize: 'min(7vh, 5vw)', fontWeight: 700, margin: 0, lineHeight: 1.2 }} data-testid="welcome-screen-empty">Todavía no hay visitantes registrados en este servicio</p>
              : (
                <div key={current.id} style={{ animation: 'vvFade 500ms ease-out' }}>
                  <p style={{ margin: 0, fontWeight: 800, lineHeight: 1.08, fontSize: current.invited_by ? 'min(14vh, 10vw)' : 'min(16vh, 11vw)', overflowWrap: 'anywhere' }} data-testid="welcome-screen-name">{current.name}</p>
                  {current.registering && <p style={{ margin: '1.6vh 0 0', fontSize: 'min(2.8vh, 2vw)', color: C.soft, fontStyle: 'italic' }} data-testid="welcome-screen-registering">registrando…</p>}
                  {current.invited_by && <p style={{ margin: '3vh 0 0', fontSize: 'min(6vh, 4.2vw)', fontWeight: 600, color: C.gold, lineHeight: 1.2, overflowWrap: 'anywhere' }} data-testid="welcome-screen-invited">Invitado por {current.invited_by}</p>}
                </div>
              )}
      </main>
      {!linkError && view && (
        <footer style={{ padding: '0 4vw 4vh', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
          {arrow(-1, index <= 0, 'welcome-prev', <><ChevronLeft size={36} aria-hidden />Anterior</>)}
          <p style={{ margin: 0, fontSize: 'min(4.5vh, 3.4vw)', fontWeight: 700, color: C.gold }} data-testid="welcome-counter">{names.length ? `Nombre ${index + 1} de ${names.length}` : ''}</p>
          {arrow(1, index >= names.length - 1, 'welcome-next', <>Siguiente<ChevronRight size={36} aria-hidden /></>)}
        </footer>
      )}
      <button type="button" onClick={fullscreen} aria-label="Pantalla completa" style={{ position: 'fixed', right: 16, top: 16, width: 52, height: 52, borderRadius: 14, border: '2px solid rgba(255,255,255,0.3)', background: 'transparent', color: C.soft }} data-testid="welcome-fullscreen"><Maximize size={26} aria-hidden /></button>
      {offline && <p style={{ position: 'fixed', left: 16, top: 16, margin: 0, fontSize: 18, color: C.soft }}>Sin conexión: se muestra lo último recibido.</p>}
      <style>{'@keyframes vvFade { from { opacity: 0; transform: translateY(2vh); } to { opacity: 1; transform: none; } }'}</style>
    </div>
  );
}
