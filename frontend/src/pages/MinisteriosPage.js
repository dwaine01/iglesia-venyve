import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { BriefcaseBusiness, Church, Plus, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { MinistryCatalogCard } from '../components/ministries/MinistryCatalogCard';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Skeleton } from '../components/ui/skeleton';
import { Textarea } from '../components/ui/textarea';

const detailText = (error, fallback) => typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : fallback;

export default function MinisteriosPage() {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ nombre: '', descripcion: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const response = await axios.get(`${API}/api/ministries`, getAuthHeaders());
      setItems(response.data.items || []);
    } catch (requestError) {
      setError(detailText(requestError, 'No se pudo cargar el catálogo de Ministerios.'));
    } finally { setLoading(false); }
  }, [API, getAuthHeaders]);

  useEffect(() => { load(); }, [load]);

  const create = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      await axios.post(`${API}/api/ministries`, { ...form, suggested_age_groups: [] }, getAuthHeaders());
      setOpen(false); setForm({ nombre: '', descripcion: '' }); toast.success('Ministerio creado.'); await load();
    } catch (requestError) { toast.error(detailText(requestError, 'No se pudo crear el Ministerio.')); }
    finally { setSaving(false); }
  };

  const archive = async (ministry) => {
    if (!window.confirm(`¿Archivar ${ministry.nombre}? Sus asignaciones se conservarán.`)) return;
    try {
      await axios.post(`${API}/api/ministries/${ministry.ministry_id}/archive`, {}, getAuthHeaders());
      toast.success('Ministerio archivado; sus asignaciones fueron conservadas.'); await load();
    } catch (requestError) { toast.error(detailText(requestError, 'No se pudo archivar el Ministerio.')); }
  };

  return (
    <div className="directory-surface min-h-screen px-4 py-7 sm:px-6 lg:px-8" data-testid="ministries-page">
      <div className="mx-auto max-w-7xl space-y-7">
        <header className="flex flex-col gap-5 border-b border-slate-200 pb-7 sm:flex-row sm:items-end sm:justify-between">
          <div><p className="mb-2 text-xs font-semibold uppercase text-amber-700">Dominio central</p><h1 className="flex items-center gap-3 text-4xl font-bold text-slate-950 sm:text-5xl" data-testid="ministries-title"><Church className="h-9 w-9 text-amber-700" />Ministerios</h1><p className="mt-2 text-sm text-slate-600 sm:text-base">Un catálogo central; muchas Personas y funciones.</p></div>
          <div className="flex flex-col gap-2 sm:flex-row"><Button variant="outline" asChild><Link to="/directorio" data-testid="ministries-open-directory-link"><BriefcaseBusiness className="mr-2 h-4 w-4" />Abrir directorio</Link></Button><Button onClick={() => setOpen(true)} data-testid="create-ministry-button" className="bg-slate-900 text-white hover:bg-slate-800"><Plus className="mr-2 h-4 w-4" />Crear Ministerio</Button></div>
        </header>

        {error ? <Alert variant="destructive" data-testid="ministries-error-alert"><AlertTitle>No pudimos cargar los Ministerios</AlertTitle><AlertDescription className="flex items-center justify-between gap-3"><span>{error}</span><Button variant="outline" size="sm" onClick={load} data-testid="ministries-retry-button"><RefreshCw className="mr-2 h-4 w-4" />Reintentar</Button></AlertDescription></Alert> : loading ? <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3" data-testid="ministries-loading-state">{Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-56 rounded-lg" />)}</div> : items.length === 0 ? <div className="rounded-lg border border-dashed bg-white px-6 py-16 text-center" data-testid="ministries-empty-state"><Church className="mx-auto h-10 w-10 text-amber-700" /><p className="mt-4 font-semibold text-slate-900">Aún no hay Ministerios activos</p><Button className="mt-5 bg-slate-900" onClick={() => setOpen(true)} data-testid="ministries-empty-create-button">Crear el primero</Button></div> : <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3" data-testid="ministries-catalog-grid">{items.map((item) => <MinistryCatalogCard key={item.ministry_id} ministry={item} onArchive={archive} />)}</div>}

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent data-testid="create-ministry-dialog">
            <form onSubmit={create} className="space-y-4"><DialogHeader><DialogTitle>Crear Ministerio</DialogTitle><DialogDescription>Puede recibir Personas aunque todavía no tenga líder.</DialogDescription></DialogHeader><div className="space-y-2"><Label htmlFor="ministry-name-input">Nombre</Label><Input id="ministry-name-input" data-testid="ministry-name-input" value={form.nombre} onChange={(event) => setForm((current) => ({ ...current, nombre: event.target.value }))} required /></div><div className="space-y-2"><Label htmlFor="ministry-description-input">Descripción</Label><Textarea id="ministry-description-input" data-testid="ministry-description-input" value={form.descripcion} onChange={(event) => setForm((current) => ({ ...current, descripcion: event.target.value }))} /></div><DialogFooter><Button variant="outline" type="button" onClick={() => setOpen(false)} data-testid="cancel-create-ministry-button">Cancelar</Button><Button disabled={saving} data-testid="submit-create-ministry-button" className="bg-slate-900">{saving ? 'Creando…' : 'Crear Ministerio'}</Button></DialogFooter></form>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}