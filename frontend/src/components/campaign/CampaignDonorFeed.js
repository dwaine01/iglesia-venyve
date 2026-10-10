import React from 'react';
import { formatUsdCents } from '../../lib/campaignFormat';

// Ticker/panel lateral: TODOS los donantes aparecen aquí con nombre y monto,
// sin excepción, aunque su aporte sea pequeño y no alcance a completar una pieza visible.
export const CampaignDonorFeed = ({ feed = [] }) => (
  <div className="flex h-full flex-col rounded-2xl border border-white/10 bg-black/40 p-4" data-testid="campaign-donor-feed">
    <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#F4C430]">Donantes</p>
    <div className="flex-1 space-y-1.5 overflow-y-auto pr-1">
      {feed.map((item, idx) => (
        <div key={idx} className="rounded-lg bg-white/5 px-2.5 py-1.5" data-testid={`campaign-donor-feed-item-${idx}`}>
          <p className="truncate text-sm text-slate-200">{item.donor_label}</p>
          <p className="text-sm font-semibold text-[#F4C430]">{formatUsdCents(item.amount_cents)}</p>
        </div>
      ))}
      {feed.length === 0 && <p className="text-sm text-slate-400">Aún no hay donativos registrados.</p>}
    </div>
  </div>
);
