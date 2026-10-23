import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2 } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';

const ACTION_LABELS = {
  group_created: 'Grupo creado', group_designated: 'Pareja designada', group_conformed: 'Grupo conformado',
  member_assigned: 'Integrante asignado', member_quick_created: 'Alta rápida de integrante',
  member_ended: 'Baja de integrante', member_transferred_out: 'Traslado (salida)', member_transferred_in: 'Traslado (entrada)',
  primary_leader_assigned: 'Líder asignado', co_leader_assigned: 'Colíder asignado',
  group_moved: 'Grupo trasladado', group_updated: 'Grupo actualizado', group_archived: 'Grupo archivado',
};

export const FrontGroupHistoryPanel = ({ groupId }) => {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState([]); const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true; setLoading(true);
    axios.get(`${API}/api/front-groups/${groupId}/history`, getAuthHeaders())
      .then((response) => { if (active) setItems(response.data.items || []); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [API, getAuthHeaders, groupId]);

  if (loading) return <div className="grid min-h-40 place-items-center" data-testid="front-group-history-loading"><Loader2 className="h-5 w-5 animate-spin text-amber-700" /></div>;
  if (!items.length) return <p className="p-6 text-center text-sm text-slate-500" data-testid="front-group-history-empty">Sin eventos registrados.</p>;
  return <ul className="divide-y divide-slate-200 border border-slate-200 bg-white" data-testid="front-group-history-panel">
    {items.map((item) => <li key={item.event_id} className="px-5 py-3 text-sm" data-testid={`front-group-history-${item.event_id}`}>
      <div className="flex items-center justify-between"><b>{ACTION_LABELS[item.action] || item.action}</b><span className="text-xs text-slate-400">{new Date(item.occurred_at).toLocaleString('es-DO')}</span></div>
      <p className="mt-0.5 text-xs text-slate-500">{item.actor_name || 'Sistema'}</p>
    </li>)}
  </ul>;
};
