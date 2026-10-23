import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BookOpen, Loader2 } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';

export const MyLibraryHoldingsCard = () => {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    axios.get(`${API}/api/library/my-holdings`, getAuthHeaders())
      .then((response) => { if (active) setItems(response.data.items || []); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [API, getAuthHeaders]);

  if (loading) return <Loader2 className="h-5 w-5 animate-spin text-slate-400" data-testid="my-library-holdings-loading" />;
  if (items.length === 0) return null;

  return (
    <section className="rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid="my-library-holdings-card">
      <div className="mb-2 flex items-center gap-2">
        <BookOpen className="h-4 w-4 text-[#132443]" />
        <h3 className="font-['Spectral'] text-base font-semibold text-[#101D36]">Mi inventario de materiales</h3>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.book.book_id} className="rounded-lg border border-[#E8E5DE] p-3" data-testid={`my-library-holding-${item.book.book_id}`}>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-[#101D36]">{item.book.name}</span>
              <span className="text-slate-500">Me quedan: <strong className="text-[#101D36]">{item.on_hand}</strong></span>
            </div>
            {item.campaigns.length > 0 && (
              <div className="mt-2 space-y-1">
                {item.campaigns.map((campaign) => (
                  <div key={campaign.campaign_id} className="flex items-center justify-between text-xs text-slate-500" data-testid={`my-library-holding-campaign-${item.book.book_id}-${campaign.campaign_id}`}>
                    <span>{campaign.campaign_name}</span>
                    <span>Asignados: {campaign.assigned} · Entregados: {campaign.delivered} · Me quedan: {campaign.remaining}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
};
