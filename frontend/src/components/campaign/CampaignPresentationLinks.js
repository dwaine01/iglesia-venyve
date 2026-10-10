import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Copy, Link2, Ban } from 'lucide-react';

import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';

export const CampaignPresentationLinks = ({ base, getAuthHeaders }) => {
  const [links, setLinks] = useState([]);
  const [label, setLabel] = useState('');
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(async () => {
    const { data } = await axios.get(`${base}/presentation-links`, getAuthHeaders());
    setLinks(data.items || []);
  }, [base]);

  useEffect(() => { refresh(); }, [refresh]);

  const create = async () => {
    setCreating(true);
    try {
      await axios.post(`${base}/presentation-links`, { label: label.trim() || null }, getAuthHeaders());
      setLabel('');
      await refresh();
      toast.success('Enlace de presentación creado');
    } catch (err) {
      toast.error('No se pudo crear el enlace');
    } finally { setCreating(false); }
  };

  const revoke = async (tokenId) => {
    try {
      await axios.post(`${base}/presentation-links/${tokenId}/revoke`, {}, getAuthHeaders());
      await refresh();
      toast.success('Enlace revocado');
    } catch (err) { toast.error('No se pudo revocar el enlace'); }
  };

  const copyUrl = (token) => {
    const url = `${window.location.origin}/campanas/ven-y-come/pantalla?token=${token}`;
    navigator.clipboard?.writeText(url);
    toast.success('Enlace copiado al portapapeles');
  };

  return (
    <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5" data-testid="campaign-presentation-links-panel">
      <h3 className="flex items-center gap-2 font-serif text-lg text-[#132443]"><Link2 className="h-4 w-4" />Enlaces de pantalla (proyector)</h3>
      <div className="flex gap-2">
        <Input placeholder="Etiqueta (opcional, ej: Proyector principal)" value={label} onChange={(e) => setLabel(e.target.value)} data-testid="campaign-link-label-input" />
        <Button onClick={create} disabled={creating} data-testid="campaign-create-link-button">Crear</Button>
      </div>
      <ul className="space-y-2">
        {links.map((item) => (
          <li key={item.token_id} className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm" data-testid={`campaign-link-row-${item.token_id}`}>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{item.label || 'Enlace sin etiqueta'}</p>
              {item.active ? <Badge className="bg-emerald-100 text-emerald-700">Activo</Badge> : <Badge className="bg-red-100 text-red-700">Revocado</Badge>}
            </div>
            {item.active && (
              <div className="flex items-center gap-1">
                <Button size="icon" variant="ghost" onClick={() => copyUrl(item.token)} title="Copiar enlace" data-testid={`campaign-copy-link-${item.token_id}`}><Copy className="h-4 w-4" /></Button>
                <Button size="icon" variant="ghost" onClick={() => revoke(item.token_id)} title="Revocar" data-testid={`campaign-revoke-link-${item.token_id}`}><Ban className="h-4 w-4 text-red-600" /></Button>
              </div>
            )}
          </li>
        ))}
        {links.length === 0 && <p className="text-sm text-slate-400">Aún no hay enlaces de presentación creados.</p>}
      </ul>
    </div>
  );
};
