import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { useParams, useSearchParams } from 'react-router-dom';

import { rememberedToken } from '../lib/appManifest';
import { API_BASE } from '../lib/apiBase';
import { useWelcomeSync } from '../lib/useWelcomeSync';

/* PANTALLA GIGANTE para el público (/g/<enlace>), por ProPresenter en la pantalla grande del centro, 16:9
 * (pensada para 1920×1080). Sigue la MISMA posición que la pantalla de la pastora: cuando ella ve «Juan Gómez»,
 * aquí aparece Juan Gómez con una entrada suave. SOLO LEE: recibe únicamente el nombre que se está mostrando
 * (nunca «invitado por», «registrando» ni otro dato) y su enlace no puede mover la posición. Si el operador
 * quita a alguien, no sale; mientras alguien aún se registra, tampoco. Sin nombre: bienvenida general.
 * Texto del saludo: ?m=1 (por defecto), ?m=2 o ?m=3. */

const API = API_BASE;
const MESSAGES = {
  1: { eyebrow: 'Te damos la bienvenida', line: 'Gracias por acompañarnos hoy. ¡Esta también es tu casa!' },
  2: { eyebrow: '¡Qué alegría tenerte aquí!', line: 'Te recibimos con los brazos abiertos en Casa de Oración' },
  3: { eyebrow: 'Bendecimos tu vida', line: 'Gracias por venir. Dios tiene algo especial para ti hoy' },
};
const C = { bg: '#0A1430', bg2: '#16295A', gold: '#E7C766', goldSoft: 'rgba(231,199,102,0.55)', white: '#FFFFFF', soft: 'rgba(255,255,255,0.86)' };
// Unidad que escala igual en cualquier pantalla 16:9 (1u = 1/100 del ancho de un lienzo 16:9 que cabe completo).
const U = (n) => `calc(${n} * min(1vw, 1.7778vh))`;
const nameSize = (name) => (name.length <= 14 ? 8.4 : name.length <= 20 ? 7 : name.length <= 28 ? 5.6 : 4.4);

export default function StageWelcomePage() {
  const params = useParams();
  const [search] = useSearchParams();
  const [token] = useState(() => rememberedToken('vv_stage_link', params.token));
  const [view, setView] = useState(null);
  const [error, setError] = useState(token ? '' : 'Abra el enlace de la pantalla gigante que aparece en Registro de visitantes › Enlaces.');
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((value) => value + 1), []);
  const { live } = useWelcomeSync({ api: API, mode: 'stage', linkToken: token, onNamesChanged: reload, enabled: Boolean(token) && !error });
  const message = MESSAGES[search.get('m')] || MESSAGES[1];

  useEffect(() => {
    if (!token) return undefined;
    let alive = true;
    const load = () => axios.get(`${API}/api/stage/welcome`, { params: { link: token }, timeout: 8000 })
      .then((response) => { if (!alive) return; setView(response.data); setError(''); try { localStorage.setItem('vv_stage_link', token); } catch { /* sin almacenamiento */ } })
      .catch((requestError) => { if (alive && requestError?.response?.status === 401) setError(requestError.response.data?.detail || 'Este enlace ya no funciona.'); });
    load();
    // Con WebSocket cambia al instante (cada aviso vuelve a leer); sin él, cada 2 s.
    const timer = setInterval(load, live ? 6000 : 2000);
    return () => { alive = false; clearInterval(timer); };
  }, [token, live, reloadKey]);

  const shown = view?.shown;
  return (
    <div style={{ position: 'fixed', inset: 0, background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', cursor: 'none' }} data-testid="stage-screen">
      <div style={{ position: 'relative', width: U(100), height: U(56.25), overflow: 'hidden', fontFamily: 'Inter, system-ui, sans-serif', color: C.white,
        background: `radial-gradient(ellipse 70% 60% at 50% 55%, ${C.bg2} 0%, ${C.bg} 70%)` }}>
        {/* Luz dorada suave y marco fino: elegante, sin distraer. */}
        <div style={{ position: 'absolute', left: '50%', top: '58%', width: U(70), height: U(30), transform: 'translate(-50%, -50%)', borderRadius: '50%',
          background: 'radial-gradient(ellipse at center, rgba(231,199,102,0.16) 0%, rgba(231,199,102,0) 70%)', animation: 'stageGlow 8s ease-in-out infinite' }} />
        <div style={{ position: 'absolute', inset: U(1.6), border: `${U(0.12)} solid ${C.goldSoft}`, borderRadius: U(1.2), pointerEvents: 'none' }} />
        <div style={{ position: 'absolute', top: U(3.2), left: 0, right: 0, display: 'flex', justifyContent: 'center' }}>
          <span style={{ background: '#fff', borderRadius: U(1), padding: `${U(0.7)} ${U(1.4)}`, boxShadow: '0 0.6vh 3vh rgba(0,0,0,0.35)' }}>
            <img src="/logo-iglesia.png" srcSet="/logo-iglesia.png 1x, /logo-iglesia@2x.png 2x" alt="Primera Iglesia del Nazareno · Casa de oración Ven y Ve" style={{ display: 'block', height: U(6.4), width: 'auto' }} data-testid="stage-logo" />
          </span>
        </div>

        <div style={{ position: 'absolute', left: U(6), right: U(6), top: U(15), bottom: U(5), display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
          {error ? <p style={{ fontSize: U(2.4), color: C.soft }} data-testid="stage-error">{error}</p>
            : shown ? (
              <div key={shown.id} data-testid="stage-visitor">
                <p style={{ margin: 0, fontSize: U(2.3), fontWeight: 700, letterSpacing: '0.28em', textTransform: 'uppercase', color: C.gold, animation: 'stageFade 900ms ease-out both' }} data-testid="stage-eyebrow">{message.eyebrow}</p>
                <p style={{ margin: `${U(1.6)} 0 0`, fontFamily: 'Spectral, Georgia, serif', fontWeight: 700, lineHeight: 1.04, fontSize: U(nameSize(shown.name)), textShadow: '0 0.5vh 2.5vh rgba(0,0,0,0.45)',
                  overflowWrap: 'anywhere', animation: 'stageName 1400ms cubic-bezier(0.16, 1, 0.3, 1) 150ms both' }} data-testid="stage-name">{shown.name}</p>
                <div style={{ margin: `${U(2.4)} auto 0`, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: U(1.2), animation: 'stageLine 1200ms ease-out 500ms both' }}>
                  <span style={{ height: U(0.14), width: U(12), background: `linear-gradient(90deg, transparent, ${C.gold})` }} />
                  <span style={{ width: U(0.9), height: U(0.9), background: C.gold, transform: 'rotate(45deg)' }} />
                  <span style={{ height: U(0.14), width: U(12), background: `linear-gradient(90deg, ${C.gold}, transparent)` }} />
                </div>
                <p style={{ margin: `${U(2.2)} 0 0`, fontSize: U(2.6), fontWeight: 500, color: C.soft, animation: 'stageFade 1000ms ease-out 800ms both' }} data-testid="stage-message">{message.line}</p>
              </div>
            ) : (
              <div key="general" data-testid="stage-general">
                <p style={{ margin: 0, fontFamily: 'Spectral, Georgia, serif', fontWeight: 700, fontSize: U(6.2), lineHeight: 1.1, color: C.gold, animation: 'stageName 1400ms cubic-bezier(0.16, 1, 0.3, 1) both' }}>¡Bienvenidos a Casa de Oración!</p>
                <div style={{ margin: `${U(2.4)} auto 0`, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: U(1.2), animation: 'stageLine 1200ms ease-out 400ms both' }}>
                  <span style={{ height: U(0.14), width: U(12), background: `linear-gradient(90deg, transparent, ${C.gold})` }} />
                  <span style={{ width: U(0.9), height: U(0.9), background: C.gold, transform: 'rotate(45deg)' }} />
                  <span style={{ height: U(0.14), width: U(12), background: `linear-gradient(90deg, ${C.gold}, transparent)` }} />
                </div>
                <p style={{ margin: `${U(2.2)} 0 0`, fontSize: U(3), color: C.soft, animation: 'stageFade 1000ms ease-out 700ms both' }}>Nos alegra que estés aquí. ¡Esta es tu casa!</p>
              </div>
            )}
        </div>
      </div>
      <style>{`
        @keyframes stageName { from { opacity: 0; transform: translateY(3vh) scale(0.97); letter-spacing: 0.08em; filter: blur(6px); } to { opacity: 1; transform: none; letter-spacing: 0; filter: blur(0); } }
        @keyframes stageFade { from { opacity: 0; transform: translateY(1.2vh); } to { opacity: 1; transform: none; } }
        @keyframes stageLine { from { opacity: 0; transform: scaleX(0.2); } to { opacity: 1; transform: scaleX(1); } }
        @keyframes stageGlow { 0%, 100% { opacity: 0.75; } 50% { opacity: 1; } }
        @media (prefers-reduced-motion: reduce) { [data-testid="stage-screen"] * { animation: none !important; } }
      `}</style>
    </div>
  );
}
