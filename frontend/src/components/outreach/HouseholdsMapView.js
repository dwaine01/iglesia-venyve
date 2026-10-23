import React from 'react';
import { Home, MapPin } from 'lucide-react';

import { Badge } from '../ui/badge';

const mapsLink = (address) => `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`;

export const HouseholdsMapView = ({ myCampaigns, myHouseholds, availableByCampaign }) => {
  if (!myCampaigns || myCampaigns.length === 0) {
    return <p className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500" data-testid="outreach-map-empty-state">Participe en una invasión para ver su mapa de casas.</p>;
  }

  return (
    <div className="space-y-5" data-testid="outreach-map-view">
      {myCampaigns.map((campaign) => {
        const assigned = (myHouseholds || []).filter((household) => household.campaign_id === campaign.campaign_id);
        const available = availableByCampaign?.[campaign.campaign_id] || [];
        const rows = [
          ...assigned.map((household) => ({ ...household, kind: 'assigned' })),
          ...available.map((household) => ({ ...household, kind: 'available' })),
        ];
        return (
          <div key={campaign.campaign_id} className="rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid={`outreach-map-campaign-${campaign.campaign_id}`}>
            <h4 className="font-['Spectral'] text-base font-semibold text-[#101D36]">{campaign.name}</h4>
            {rows.length === 0 ? (
              <p className="mt-2 text-sm text-slate-400">Sin casas asignadas ni disponibles todavía.</p>
            ) : (
              <div className="mt-2 space-y-1.5" data-testid={`outreach-map-rows-${campaign.campaign_id}`}>
                {rows.map((household) => {
                  const address = [household.address_line1, household.sector].filter(Boolean).join(' · ') || 'Sin dirección';
                  return (
                    <a
                      key={household.household_id}
                      href={mapsLink(address)}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center justify-between gap-2 rounded-lg border border-[#E8E5DE] p-2 text-sm text-[#101D36] hover:border-[#132443]"
                      data-testid={`outreach-map-row-${household.household_id}`}
                    >
                      <span className="flex items-center gap-2"><Home className="h-4 w-4 text-slate-400" />{address}</span>
                      <span className="flex items-center gap-2">
                        <Badge variant="outline" className={household.kind === 'assigned' ? 'text-[#132443]' : 'text-amber-700'}>{household.kind === 'assigned' ? 'Mía' : 'Disponible'}</Badge>
                        <MapPin className="h-3.5 w-3.5 text-slate-400" />
                      </span>
                    </a>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
