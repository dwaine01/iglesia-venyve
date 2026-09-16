import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { ArrowLeft, Church, RefreshCw, UsersRound } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { MinistryAssignmentPanel } from '../components/ministries/MinistryAssignmentPanel';
import { MinistryMemberCard } from '../components/ministries/MinistryMemberCard';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';

const detailText = (error, fallback) => typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : fallback;

export default function MinisterioDetailPage() {
  const { ministryId } = useParams();
  const { API, getAuthHeaders } = useAuth();
  const [ministry, setMinistry] = useState(null);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [detail, roleResponse] = await Promise.all([
        axios.get(`${API}/api/ministries/${ministryId}`, getAuthHeaders()),
        axios.get(`${API}/api/ministries/roles/catalog`, { ...getAuthHeaders(), params: { ministry_id: ministryId } }),
      ]);
      setMinistry(detail.data); setRoles(roleResponse.data.items || []);
    } catch (requestError) { setError(detailText(requestError, 'No se pudo cargar el Ministerio.')); }
    finally { setLoading(false); }
  }, [API, getAuthHeaders, ministryId]);

  useEffect(() => { load(); }, [load]);

  const deactivate = async (member) => {
    if (!window.confirm(`¿Retirar a ${member.nombre_completo} de este Ministerio?`)) return;
    try {
      await axios.put(`${API}/api/ministries/assignments/${member.assignment_id}`, { activo: false, fecha_fin: new Date().toISOString().slice(0, 10) }, getAuthHeaders());
      toast.success('Asignación ministerial finalizada.'); await load();
    } catch (requestError) { toast.error(detailText(requestError, 'No se pudo finalizar la asignación.')); }
  };

  if (loading) return <div className="directory-surface min-h-screen p-6" data-testid="ministry-detail-loading"><div className="mx-auto max-w-7xl space-y-4"><Skeleton className="h-7 w-52" /><Skeleton className="h-40 w-full" /><Skeleton className="h-56 w-full" /></div></div>;
  if (error || !ministry) return <div className="directory-surface min-h-screen p-6"><Alert variant="destructive" data-testid="ministry-detail-error"><AlertTitle>No pudimos abrir este Ministerio</AlertTitle><AlertDescription className="mt-2 flex items-center justify-between gap-3"><span>{error}</span><Button variant="outline" size="sm" onClick={load} data-testid="ministry-detail-retry-button"><RefreshCw className="mr-2 h-4 w-4" />Reintentar</Button></AlertDescription></Alert></div>;

  return (
    <div className="directory-surface min-h-screen px-4 py-7 sm:px-6 lg:px-8" data-testid="ministry-detail-page">
      <div className="mx-auto max-w-7xl space-y-7">
        <Link to="/ministerios" data-testid="back-to-ministries-link" className="inline-flex items-center gap-2 text-sm text-slate-600 transition-colors hover:text-amber-800"><ArrowLeft className="h-4 w-4" />Todos los Ministerios</Link>
        <header className="flex flex-col gap-5 border-b border-slate-200 pb-7 sm:flex-row sm:items-end sm:justify-between">
          <div><p className="mb-2 text-xs font-semibold uppercase text-amber-700">Ministerio activo</p><h1 className="flex items-center gap-3 text-4xl font-bold text-slate-950 sm:text-5xl" data-testid="ministry-detail-title"><Church className="h-9 w-9 text-amber-700" />{ministry.nombre}</h1><p className="mt-2 text-sm text-slate-600 sm:text-base">{ministry.descripcion || 'Unidad ministerial activa'}</p></div>
          <div className="flex flex-wrap gap-2"><Badge variant="outline" className="border-slate-300 bg-white" data-testid="ministry-detail-people-count"><UsersRound className="mr-1 h-4 w-4" />{ministry.active_people_count} personas</Badge><Badge variant="outline" className={ministry.leadership_vacancy ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-emerald-200 bg-emerald-50 text-emerald-700'} data-testid="ministry-detail-leadership-status">{ministry.leadership_vacancy ? 'Liderazgo vacante' : 'Liderazgo activo'}</Badge></div>
        </header>

        <MinistryAssignmentPanel ministryId={ministryId} roles={roles} API={API} getAuthHeaders={getAuthHeaders} onAssigned={load} />
        <section><div className="mb-4 flex items-center gap-2"><UsersRound className="h-5 w-5 text-amber-700" /><h2 className="text-xl font-bold text-slate-950">Equipo ministerial</h2></div>{ministry.members.length === 0 ? <div className="rounded-lg border border-dashed bg-white px-6 py-14 text-center text-sm text-slate-500" data-testid="ministry-members-empty-state">Este Ministerio todavía no tiene Personas asignadas.</div> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="ministry-members-grid">{ministry.members.map((member) => <MinistryMemberCard key={member.assignment_id} member={member} onDeactivate={deactivate} />)}</div>}</section>
      </div>
    </div>
  );
}