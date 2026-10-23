import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, ShieldAlert, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { errorDetailText } from '../../lib/errorText';

const COLLECTION_LABEL = {
  front_groups: 'Grupo Frontal',
  outreach_campaigns: 'Invasión',
};

export default function AdminDeletionsPage() {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API}/api/admin/audit/deletions`, getAuthHeaders())
      .then(({ data }) => setItems(data.items || []))
      .catch((error) => toast.error(errorDetailText(error, 'No se pudo cargar el historial de borrados')))
      .finally(() => setLoading(false));
  }, [API, getAuthHeaders]);

  return (
    <div className="space-y-6 p-4 sm:p-6" data-testid="admin-deletions-page">
      <header className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-red-100 text-red-700"><Trash2 className="h-5 w-5" /></div>
        <div>
          <h1 className="font-['Spectral'] text-2xl font-semibold text-[#101D36] sm:text-3xl">Historial de Borrados</h1>
          <p className="text-sm text-slate-500">Quién, cuándo y por qué se borró algo de forma total y permanente</p>
        </div>
      </header>

      <div className="flex items-center gap-2 rounded-xl border border-[#E8E5DE] bg-[#F6F4EF] p-3 text-xs text-slate-600" data-testid="admin-deletions-banner">
        <ShieldAlert className="h-4 w-4 text-[#132443]" /> Solo la pastora/pastor general o un coordinador general puede ver este historial.
      </div>

      {loading && <Loader2 className="h-6 w-6 animate-spin text-slate-400" />}
      <div className="space-y-2" data-testid="admin-deletions-list">
        {items.map((item) => (
          <div key={`${item.target_id}-${item.deleted_at}`} className="rounded-xl border border-[#E8E5DE] bg-white p-3 text-sm" data-testid={`admin-deletion-row-${item.target_id}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium text-[#101D36]">{COLLECTION_LABEL[item.collection] || item.collection}: {item.detail?.name || item.target_id}</p>
              <span className="text-xs text-slate-400">{item.deleted_at ? new Date(item.deleted_at).toLocaleString('es-ES') : ''}</span>
            </div>
            <p className="mt-1 text-slate-600">Motivo: {item.reason}</p>
            {item.detail && (
              <p className="mt-1 text-xs text-slate-500">
                {Object.entries(item.detail).filter(([key]) => key !== 'name').map(([key, value]) => `${key}: ${value}`).join(' · ')}
              </p>
            )}
          </div>
        ))}
        {!loading && items.length === 0 && <p className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">Sin borrados registrados todavía.</p>}
      </div>
    </div>
  );
}
