import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';

/* Pantalla de bienvenida (salón o pastora), a pantalla completa. Sin menú ni
 * sesión de personal: se empareja con un código de un solo uso y su token solo
 * puede leer los NOMBRES autorizados. Diseñada para un televisor de 40" leído a
 * unos 12 metros: letras enormes y alto contraste. ProPresenter o el operador
 * pueden abrir esta misma página. El operador la controla desde «Bienvenida en
 * vivo»; esta página solo muestra lo que el servidor indica. */

const API = process.env.REACT_APP_BACKEND_URL;
const DEVICE_KEY = 'vv_screen_device';
const C = { bg: '#0B1530', gold: '#E7C766', white: '#FFFFFF', soft: 'rgba(255,255,255,0.78)' };

function readDevice() {
  try { return JSON.parse(localStorage.getItem(DEVICE_KEY) || 'null'); } catch { return null; }
}

export default function WelcomeScreenPage() {
  const [device, setDevice] = useState(readDevice);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [view, setView] = useState(null);
  const [offline, setOffline] = useState(false);
  const [showTools, setShowTools] = useState(true);
  const hideTimer = useRef(null);

  const unpair = useCallback(() => { try { localStorage.removeItem(DEVICE_KEY); } catch { /* sin almacenamiento */ } setDevice(null); setView(null); }, []);
  useEffect(() => {
    if (!device) return undefined;
    let alive = true;
    const load = () => axios.get(`${API}/api/screen/welcome`, { headers: { 'X-Device-Token': device.token }, timeout: 8000 })
      .then((response) => { if (alive) { setView(response.data); setOffline(false); } })
      .catch((requestError) => { if (!alive) return; if ([401, 403].includes(requestError?.response?.status)) unpair(); else setOffline(true); });
    load();
    const timer = setInterval(load, 2000);
    return () => { alive = false; clearInterval(timer); };
  }, [device, unpair]);

  // El botón de pantalla completa aparece al mover el ratón y se esconde solo.
  useEffect(() => {
    const show = () => { setShowTools(true); clearTimeout(hideTimer.current); hideTimer.current = setTimeout(() => setShowTools(false), 4000); };
    show();
    window.addEventListener('mousemove', show); window.addEventListener('pointerdown', show);
    return () => { window.removeEventListener('mousemove', show); window.removeEventListener('pointerdown', show); clearTimeout(hideTimer.current); };
  }, []);

  const pair = async (event) => {
    event.preventDefault(); setError('');
    try {
      const response = await axios.post(`${API}/api/kiosk/pair`, { code, expected_kinds: ['screen_tv', 'screen_pastora'] });
      const value = { token: response.data.token, name: response.data.device_name };
      try { localStorage.setItem(DEVICE_KEY, JSON.stringify(value)); } catch { /* sin almacenamiento */ }
      setDevice(value); setCode('');
    } catch (requestError) { setError(requestError?.response?.data?.detail || 'No se pudo emparejar. Revise el código y la conexión.'); }
  };
  const fullscreen = () => { if (document.fullscreenElement) document.exitFullscreen?.(); else document.documentElement.requestFullscreen?.(); };

  const page = (children) => (
    <div style={{ minHeight: '100vh', background: C.bg, color: C.white, fontFamily: 'Inter, system-ui, sans-serif', display: 'flex', flexDirection: 'column', cursor: showTools ? 'default' : 'none', overflow: 'hidden' }} data-testid="welcome-screen">
      {children}
      {showTools && device && (
        <button type="button" onClick={fullscreen} style={{ position: 'fixed', right: 24, bottom: 24, minHeight: 56, padding: '0 24px', borderRadius: 16, border: '2px solid rgba(255,255,255,0.4)', background: 'rgba(255,255,255,0.12)', color: C.white, fontSize: 20, fontWeight: 700 }}
          data-testid="welcome-screen-fullscreen">Pantalla completa</button>
      )}
    </div>
  );

  if (!device) {
    return page(
      <form onSubmit={pair} style={{ margin: 'auto', width: 'min(640px, 92vw)', display: 'grid', gap: 20 }} data-testid="welcome-screen-pair">
        <h1 style={{ fontSize: 40, margin: 0, fontFamily: 'Spectral, Georgia, serif', color: C.gold }}>Emparejar pantalla de bienvenida</h1>
        <p style={{ fontSize: 22, margin: 0, color: C.soft }}>Escriba el código que aparece en Registro de visitantes › Tabletas y pantallas. Solo lo hace el personal autorizado.</p>
        <input value={code} onChange={(event) => setCode(event.target.value.toUpperCase())} placeholder="Código de 8 letras" style={{ minHeight: 72, fontSize: 34, letterSpacing: '0.2em', borderRadius: 16, border: 'none', padding: '0 20px', textAlign: 'center' }} data-testid="welcome-screen-code" />
        {error && <p style={{ fontSize: 22, color: '#FFB4A8', margin: 0 }}>{error}</p>}
        <button type="submit" disabled={code.trim().length < 6} style={{ minHeight: 72, fontSize: 28, fontWeight: 800, borderRadius: 16, border: 'none', background: C.gold, color: C.bg, opacity: code.trim().length < 6 ? 0.5 : 1 }} data-testid="welcome-screen-pair-submit">Emparejar pantalla</button>
      </form>,
    );
  }

  const names = view?.names || [];
  const one = view?.mode === 'one';
  return page(
    <>
      <header style={{ padding: '4vh 5vw 0', textAlign: 'center' }}>
        <p style={{ margin: 0, fontFamily: 'Spectral, Georgia, serif', fontSize: 'min(8vh, 6vw)', fontWeight: 700, color: C.gold, lineHeight: 1.1 }}>¡Bienvenidos a Casa de Oración!</p>
        {view?.service_label && <p style={{ margin: '1vh 0 0', fontSize: 'min(4vh, 3vw)', color: C.soft }}>{view.service_label}</p>}
      </header>
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2vh 4vw 6vh', textAlign: 'center' }}>
        {!view ? <p style={{ fontSize: 'min(5vh, 4vw)', color: C.soft }}>Conectando…</p>
          : names.length === 0 ? <p style={{ fontSize: 'min(7vh, 5vw)', fontWeight: 700, margin: 0, lineHeight: 1.2 }} data-testid="welcome-screen-empty">Nos alegra que estés aquí</p>
            : (
              <div key={`${view.page}-${names.join('|')}`} style={{ display: 'grid', gap: one ? 0 : '3vh', animation: 'vvFade 700ms ease-out' }} data-testid="welcome-screen-names">
                {names.map((name) => (
                  <p key={name} style={{ margin: 0, fontWeight: 800, lineHeight: 1.08, fontSize: one ? 'min(17vh, 11vw)' : 'min(10vh, 6.5vw)', overflowWrap: 'anywhere' }}>{name}</p>
                ))}
              </div>
            )}
      </main>
      {offline && <p style={{ position: 'fixed', left: 24, bottom: 24, margin: 0, fontSize: 18, color: C.soft }}>Sin conexión: se muestra lo último recibido.</p>}
      <style>{'@keyframes vvFade { from { opacity: 0; transform: translateY(2vh); } to { opacity: 1; transform: none; } }'}</style>
    </>,
  );
}
