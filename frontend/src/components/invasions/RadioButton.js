import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Radio } from 'lucide-react';

import { useRadio } from '../../context/RadioContext';

const DOT = { online: 'bg-emerald-500', connecting: 'bg-amber-400', offline: 'bg-slate-400' };

/** Acceso al Radio de la invasión de hoy (participantes y responsables), con
 * el estado de la conexión global: verde = escuchando; ámbar = conectando o
 * falta activar el audio; gris = sin red. */
export function RadioButton() {
  const navigate = useNavigate();
  const location = useLocation();
  const radio = useRadio();
  const target = radio?.channel;
  if (!target) return null;
  const active = location.pathname.endsWith('/radio');
  const dot = radio.prefs.enabled && radio.status !== 'off' && radio.status !== 'error'
    ? (radio.status === 'online' && radio.needsUnlock ? DOT.connecting : DOT[radio.status] || DOT.offline) : null;
  return (
    <button type="button" onClick={() => navigate(`/invasiones/${target.campaign_id}/radio`)} aria-current={active ? 'page' : undefined}
      className={`relative inline-flex h-11 shrink-0 items-center gap-1.5 rounded-full border-2 px-3 text-[15px] font-bold ${active ? 'border-[#132443] bg-[#132443] text-white' : 'border-[#132443] bg-white text-[#132443]'}`} data-testid="radio-button" aria-label="Radio de la invasión">
      <Radio className="h-5 w-5" /><span className="max-[379px]:sr-only">Radio</span>
      {dot && <span className={`absolute -right-0.5 -top-0.5 h-3.5 w-3.5 rounded-full border-2 border-white ${dot}`} data-testid="radio-button-dot" data-status={radio.status} aria-hidden />}
    </button>
  );
}
