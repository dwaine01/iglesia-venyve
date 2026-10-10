import React from 'react';
import { formatUsdCents } from '../../lib/campaignFormat';

// Ticker horizontal: TODOS los donantes pasan por aquí con nombre y monto,
// sin excepción, aunque su aporte sea pequeño y no alcance a completar una pieza visible.
export const CampaignDonorFeed = ({ feed = [] }) => {
  if (feed.length === 0) {
    return (
      <div className="rounded-xl border border-white/10 bg-black/40 px-4 py-2 text-center text-sm text-slate-400" data-testid="campaign-donor-feed">
        Aún no hay donativos registrados.
      </div>
    );
  }

  const items = [...feed, ...feed];

  return (
    <div className="overflow-hidden rounded-xl border border-white/10 bg-black/40 py-2" data-testid="campaign-donor-feed">
      <div className="campaign-ticker-track flex w-max gap-6 px-4">
        {items.map((item, idx) => (
          <span key={idx} className="flex items-center gap-2 whitespace-nowrap text-sm" data-testid={`campaign-donor-feed-item-${idx}`}>
            <span className="text-slate-200">{item.donor_label}</span>
            <span className="font-semibold text-[#F4C430]">{formatUsdCents(item.amount_cents)}</span>
            <span className="text-white/20">•</span>
          </span>
        ))}
      </div>
    </div>
  );
};
