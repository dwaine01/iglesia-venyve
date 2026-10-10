import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import { PartyPopper, WifiOff, Maximize } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { BusPuzzleReveal } from '../../components/campaign/BusPuzzleReveal';
import { formatUsdCents } from '../../lib/campaignFormat';

const API = process.env.REACT_APP_BACKEND_URL;

export default function CampaignScreenPage() {
  const [searchParams] = useSearchParams();
  const { token: sessionToken, user, loading: authLoading } = useAuth();
  const urlToken = searchParams.get('token');
  const resolvedToken = urlToken || (user ? sessionToken : null);

  const [summary, setSummary] = useState(null);
  const [connected, setConnected] = useState(false);
  const [tokenRevoked, setTokenRevoked] = useState(false);
  const [announcement, setAnnouncement] = useState(null);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const announceTimerRef = useRef(null);

  const fetchSummary = useCallback(async () => {
    if (!resolvedToken) return;
    try {
      const { data } = await axios.get(`${API}/api/campaigns/venycome/public/summary`, { params: { token: resolvedToken } });
      setSummary(data);
      setTokenRevoked(false);
    } catch (err) {
      if (err?.response?.status === 403) setTokenRevoked(true);
      // otros errores de red: conservar el último estado conocido en pantalla
    }
  }, [resolvedToken]);

  const showAnnouncement = useCallback((data) => {
    setAnnouncement({ ...data, ts: Date.now() });
    clearTimeout(announceTimerRef.current);
    announceTimerRef.current = setTimeout(() => setAnnouncement(null), 7000);
  }, []);

  useEffect(() => {
    if (!resolvedToken) return;
    fetchSummary();
    let closedByUs = false;

    const connect = () => {
      const wsUrl = `${API.replace(/^http/, 'ws')}/api/campaigns/venycome/public/ws?token=${encodeURIComponent(resolvedToken)}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'summary') setSummary(data);
          if (data.type === 'announcement') showAnnouncement(data);
        } catch (err) { /* mensaje inválido, ignorar */ }
      };
      ws.onclose = (event) => {
        setConnected(false);
        if (event.code === 4403) { setTokenRevoked(true); return; }
        if (!closedByUs) reconnectRef.current = setTimeout(connect, 2500);
      };
      ws.onerror = () => ws.close();
    };
    connect();

    const pollId = setInterval(() => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) fetchSummary();
    }, 5000);

    return () => {
      closedByUs = true;
      clearTimeout(reconnectRef.current);
      clearInterval(pollId);
      wsRef.current?.close();
    };
  }, [resolvedToken, fetchSummary, showAnnouncement]);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
    else document.exitFullscreen?.();
  };

  if (authLoading) return null;

  if (!resolvedToken || tokenRevoked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-black px-6 text-center text-white" data-testid="campaign-screen-unauthorized">
        <p className="text-lg text-slate-300">
          {tokenRevoked ? 'Este enlace de presentación fue revocado. Solicite uno nuevo al operador.' : 'Este enlace requiere un token de presentación válido o una sesión iniciada.'}
        </p>
      </div>
    );
  }

  const percent = summary?.percent || 0;
  const atGoal = percent >= 1;

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#07080c] text-white" data-testid="campaign-screen-page">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(181,149,63,0.18),transparent_60%)]" />
      <div className="relative z-10 mx-auto flex min-h-screen max-w-[1600px] flex-col items-center justify-center gap-8 px-8 py-10 text-center">
        <div>
          <h1 className="font-serif text-3xl font-black uppercase leading-tight text-[#F4C430] sm:text-5xl lg:text-6xl" data-testid="campaign-screen-headline">
            ¡Este autobús lleva más que comida,<br />lleva una visión!
          </h1>
          <p className="mt-3 text-base text-slate-300 sm:text-xl" data-testid="campaign-screen-subtitle">Cada donación completa una pieza de este sueño</p>
        </div>

        <div className="w-full max-w-5xl">
          <BusPuzzleReveal percent={percent} />
        </div>

        <div className="w-full max-w-3xl space-y-3" data-testid="campaign-screen-stats">
          <div className="h-5 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#B5953F] to-[#F4C430] transition-all duration-1000"
              style={{ width: `${Math.round(percent * 100)}%` }}
              data-testid="campaign-progress-bar"
            />
          </div>
          <div className="flex flex-wrap justify-between gap-4 text-sm sm:text-base">
            <Stat label="Comprometido" value={summary?.committed_cents} />
            <Stat label="Recibido" value={summary?.received_cents} />
            <Stat label="Pendiente" value={summary?.pending_cents} />
            <Stat label="Meta" value={summary?.goal_cents} highlight />
          </div>
          <p className="text-3xl font-black text-[#F4C430]" data-testid="campaign-percent-label">{Math.round(percent * 100)}%</p>
        </div>

        {atGoal && (
          <div className="animate-pulse rounded-2xl border border-[#F4C430]/40 bg-[#F4C430]/10 px-8 py-4" data-testid="campaign-goal-reached-banner">
            <p className="flex items-center gap-2 text-xl font-bold text-[#F4C430] sm:text-2xl">
              <PartyPopper className="h-7 w-7" />¡LA VISIÓN SIGUE AVANZANDO! ¡GRACIAS POR HACERLA REALIDAD!
            </p>
          </div>
        )}
      </div>

      {announcement && (
        <div className="fixed inset-x-0 bottom-10 z-20 flex justify-center px-6" data-testid="campaign-announcement-banner">
          <div key={announcement.ts} className="campaign-announcement-pop rounded-2xl border border-[#F4C430]/50 bg-black/80 px-10 py-5 text-center shadow-2xl backdrop-blur">
            <p className="text-2xl font-bold text-white sm:text-3xl">¡Gracias, {announcement.donor_label}!</p>
            <p className="text-xl font-black text-[#F4C430] sm:text-2xl">{formatUsdCents(announcement.amount_cents)} · {announcement.donation_type === 'received' ? 'Recibido' : 'Promesa'}</p>
          </div>
        </div>
      )}

      {!connected && (
        <div className="fixed right-4 top-4 z-20 flex items-center gap-2 rounded-full bg-black/60 px-3 py-1.5 text-xs text-amber-300" data-testid="campaign-connection-indicator">
          <WifiOff className="h-3.5 w-3.5" />Reconectando…
        </div>
      )}

      <button
        type="button"
        onClick={toggleFullscreen}
        className="fixed bottom-4 right-4 z-20 flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5 text-xs text-white/60 hover:bg-white/20"
        data-testid="campaign-fullscreen-toggle"
      >
        <Maximize className="h-3.5 w-3.5" />Pantalla completa
      </button>
    </div>
  );
}

function Stat({ label, value, highlight }) {
  return (
    <div data-testid={`campaign-stat-${label.toLowerCase()}`}>
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`text-lg font-bold sm:text-2xl ${highlight ? 'text-[#F4C430]' : 'text-white'}`}>{formatUsdCents(value || 0)}</p>
    </div>
  );
}
