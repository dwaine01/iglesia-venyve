import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Radio } from 'lucide-react';

import { useInvasionToday } from '../../context/InvasionTodayContext';

/** Acceso al Radio de la invasión de hoy (participantes y responsables). */
export function RadioButton() {
  const navigate = useNavigate();
  const location = useLocation();
  const { data, current } = useInvasionToday();
  const target = current || data?.active?.[0] || (data?.managed || []).find((item) => item.active_today);
  if (!target) return null;
  const active = location.pathname.endsWith('/radio');
  return (
    <button type="button" onClick={() => navigate(`/invasiones/${target.campaign_id}/radio`)} aria-current={active ? 'page' : undefined}
      className={`inline-flex h-11 shrink-0 items-center gap-1.5 rounded-full border-2 px-3 text-[15px] font-bold ${active ? 'border-[#132443] bg-[#132443] text-white' : 'border-[#132443] bg-white text-[#132443]'}`} data-testid="radio-button" aria-label="Radio de la invasión">
      <Radio className="h-5 w-5" /><span className="max-[379px]:sr-only">Radio</span>
    </button>
  );
}
