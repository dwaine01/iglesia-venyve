import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { errorDetailText } from '../../lib/errorText';
import { HouseholdCard } from './HouseholdCard';
import { VisitCard } from './VisitCard';

export const MyBranchPanel = () => {
  const { API, getAuthHeaders } = useAuth();
  const [overview, setOverview] = useState(null);
  const [library, setLibrary] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/api/mentorship/outreach/my-branch-overview`, getAuthHeaders());
      setOverview(response.data);
      if (response.data?.is_supervisor) {
        const libraryRes = await axios.get(`${API}/api/mentorship/outreach/my-branch-library`, getAuthHeaders());
        setLibrary(libraryRes.data.items || []);
      }
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo cargar la supervisión de tu rama'));
    } finally {
      setLoading(false);
    }
  }, [API, getAuthHeaders]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <Loader2 className="h-6 w-6 animate-spin text-slate-400" data-testid="outreach-my-branch-loading" />;
  if (!overview?.is_supervisor) {
    return <p className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500" data-testid="outreach-my-branch-empty">No supervisas a ningún mentor de invasiones todavía.</p>;
  }

  return (
    <div className="space-y-6" data-testid="outreach-my-branch-panel">
      <div className="flex items-center gap-2 rounded-xl border border-[#E8E5DE] bg-[#F6F4EF] p-3 text-xs text-slate-600" data-testid="outreach-my-branch-banner">
        <ShieldCheck className="h-4 w-4 text-[#132443]" /> Supervisión de tu rama · solo lectura, no puedes editar los informes de otros mentores.
      </div>
      <div>
        <h3 className="font-['Spectral'] text-lg font-semibold text-[#101D36]">Hogares de tu rama</h3>
        <div className="mt-3 space-y-3" data-testid="outreach-my-branch-households">
          {overview.households.map((household) => <HouseholdCard key={household.household_id} household={household} readOnly onLogAttempt={() => {}} onChanged={load} />)}
          {overview.households.length === 0 && <p className="text-sm text-slate-400">Sin hogares registrados todavía.</p>}
        </div>
      </div>
      <div>
        <h3 className="font-['Spectral'] text-lg font-semibold text-[#101D36]">Contactos de tu rama</h3>
        <div className="mt-3 space-y-3" data-testid="outreach-my-branch-visits">
          {overview.visits.map((visit) => <VisitCard key={`${visit.visit_id}-${visit.updated_at}`} visit={visit} canManage onUpdated={load} onTransfer={() => {}} />)}
          {overview.visits.length === 0 && <p className="text-sm text-slate-400">Sin contactos registrados todavía.</p>}
        </div>
      </div>
      {library.length > 0 && (
        <div>
          <h3 className="font-['Spectral'] text-lg font-semibold text-[#101D36]">Materiales de tu rama</h3>
          <div className="mt-3 space-y-2" data-testid="outreach-my-branch-library">
            {library.map((item) => (
              <div key={`${item.mentor_person_id}-${item.book_id}`} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#E8E5DE] p-3 text-sm" data-testid={`outreach-branch-library-row-${item.mentor_person_id}-${item.book_id}`}>
                <div><b className="text-[#101D36]">{item.mentor_name}</b><span className="ml-2 text-slate-500">{item.book_name}</span></div>
                <span className="text-xs text-slate-500">Asignado: {item.assigned} · Entregado: {item.delivered_total} · Devuelto: {item.returned} · En custodia: {item.in_custody}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
