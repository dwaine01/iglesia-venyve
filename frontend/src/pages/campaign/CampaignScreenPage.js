import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import { PartyPopper, WifiOff, Maximize, Heart, Users, UtensilsCrossed } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { BusPuzzleReveal } from '../../components/campaign/BusPuzzleReveal';
import { CampaignDonorFeed } from '../../components/campaign/CampaignDonorFeed';
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

  const totalPieces = summary?.total_pieces || 120;

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
      <div className="relative z-10 mx-auto flex h-screen max-w-[1800px] flex-col gap-3 overflow-hidden px-6 py-4">
        <div className="relative overflow-hidden rounded-2xl border border-white/10" data-testid="campaign-header-banner">
          <img src="/campaign/header_bg.jpg" alt="" className="absolute inset-0 h-full w-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/60 to-black/85" />
          <div className="relative z-10 flex flex-col gap-2 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-center sm:text-left">
              <div className="flex flex-wrap items-baseline justify-center gap-2 sm:justify-start" data-testid="campaign-screen-headline">
                <span className="text-2xl text-[#F4C430] sm:text-4xl" style={{ fontFamily: "'Permanent Marker', cursive", transform: 'rotate(-3deg)', display: 'inline-block' }}>Juntos</span>
                <span className="text-lg text-white sm:text-2xl lg:text-3xl" style={{ fontFamily: "'Anton', sans-serif" }}>HACEMOS</span>
                <span className="text-lg text-[#F4C430] sm:text-2xl lg:text-3xl" style={{ fontFamily: "'Anton', sans-serif" }}>ESTO REALIDAD</span>
              </div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-200 sm:text-sm" data-testid="campaign-screen-subtitle">
                Ayúdanos a completar el bus
              </p>
            </div>

            <div className="flex items-center justify-center sm:justify-end">
              <div className="rounded-xl bg-[#F4C430] px-3 py-1.5 text-center text-[#1a1200] shadow-lg" style={{ transform: 'rotate(3deg)' }} data-testid="campaign-meta-badge">
                <p className="text-[9px] font-bold uppercase tracking-wide">Meta</p>
                <p className="text-lg font-black leading-none sm:text-xl">{formatUsdCents(summary?.goal_cents || 0)}</p>
                <p className="mt-0.5 text-[7px] font-semibold uppercase leading-tight">para la terminación del bus</p>
              </div>
            </div>
          </div>

          <div className="relative z-10 hidden items-center justify-center gap-6 border-t border-white/10 px-5 py-1.5 lg:flex" data-testid="campaign-header-callouts">
            <HeaderCallout icon={Heart} text="Tu donación completa una pieza" />
            <HeaderCallout icon={Users} text="Juntos avanzamos más rápido" />
            <HeaderCallout icon={UtensilsCrossed} text="Este bus será una bendición para nuestra comunidad" />
          </div>
        </div>

        <div className="flex min-h-0 flex-1 items-center justify-center">
          <div className="h-full w-full">
            <BusPuzzleReveal pieces={summary?.pieces || []} totalPieces={totalPieces} />
          </div>
        </div>

        <div className="mx-auto w-full max-w-5xl space-y-1.5" data-testid="campaign-screen-stats">
          <div className="h-3.5 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#B5953F] to-[#F4C430] transition-all duration-1000"
              style={{ width: `${Math.round(percent * 100)}%` }}
              data-testid="campaign-progress-bar"
            />
          </div>
          <div className="flex flex-wrap justify-between gap-3 text-sm sm:text-base">
            <Stat label="Comprometido" value={summary?.committed_cents} />
            <Stat label="Recibido" value={summary?.received_cents} />
            <Stat label="Restante" value={summary?.remaining_cents} />
            <Stat label="Meta" value={summary?.goal_cents} highlight />
          </div>
          <p className="text-center text-xl font-black text-[#F4C430] sm:text-2xl" data-testid="campaign-percent-label">{Math.round(percent * 100)}%</p>
        </div>

        <CampaignDonorFeed feed={summary?.donor_feed || []} />

        {atGoal && (
          <div className="mx-auto animate-pulse rounded-2xl border border-[#F4C430]/40 bg-[#F4C430]/10 px-6 py-2" data-testid="campaign-goal-reached-banner">
            <p className="flex items-center gap-2 text-base font-bold text-[#F4C430] sm:text-xl">
              <PartyPopper className="h-5 w-5" />¡LA VISIÓN SIGUE AVANZANDO! ¡GRACIAS POR HACERLA REALIDAD!
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

function HeaderCallout({ icon: Icon, text }) {
  return (
    <div className="flex max-w-[220px] items-center gap-2" data-testid="campaign-header-callout">
      <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border-2 border-[#F4C430] text-[#F4C430]">
        <Icon className="h-4 w-4" />
      </span>
      <p className="text-left text-[11px] font-bold uppercase leading-tight text-white">{text}</p>
    </div>
  );
}
