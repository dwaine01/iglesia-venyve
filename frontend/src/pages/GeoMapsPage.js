import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { CircleAlert, Layers3, Loader2, MapPinned, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { Button } from '../components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '../components/ui/tabs';
import { GeoComparisonBand } from '../components/geo/GeoComparisonBand';
import { GeoDetailPanel } from '../components/geo/GeoDetailPanel';
import { GeoFilters } from '../components/geo/GeoFilters';
import { GeoMapCanvas } from '../components/geo/GeoMapCanvas';
import { GeoReviewDialog } from '../components/geo/GeoReviewDialog';
import { GeoSummaryStrip } from '../components/geo/GeoSummaryStrip';

const emptyCatalog = { front_groups: [], cells: [], stages: [] };
const initialFilters = { category: '', zone: '', stage: '', front_group_id: '', cell_id: '', period_start: '' };

export default function GeoMapsPage() {
  const { API, getAuthHeaders } = useAuth(); const [kind, setKind] = useState('people');
  const [mode, setMode] = useState('heatmap'); const [filters, setFilters] = useState(initialFilters);
  const [config, setConfig] = useState(null); const [catalog, setCatalog] = useState(emptyCatalog);
  const [summary, setSummary] = useState({}); const [features, setFeatures] = useState([]);
  const [comparison, setComparison] = useState(null); const [compare, setCompare] = useState(false);
  const [selected, setSelected] = useState(null); const [reviewOpen, setReviewOpen] = useState(false);
  const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [backfilling, setBackfilling] = useState(false);
  const canViewPrecise = Boolean(config?.permissions?.view_precise); const canManage = Boolean(config?.permissions?.manage_locations);
  const queryParams = useMemo(() => ({ entity_kind: kind, categories: filters.category || undefined, zone: filters.zone || undefined, stage: filters.stage || undefined, front_group_id: filters.front_group_id || undefined, cell_id: filters.cell_id || undefined, period_start: filters.period_start ? new Date(`${filters.period_start}T00:00:00`).toISOString() : undefined }), [filters, kind]);

  const loadBase = useCallback(async () => {
    const [configResponse, catalogResponse, summaryResponse] = await Promise.all([
      axios.get(`${API}/api/geo/config`, getAuthHeaders()), axios.get(`${API}/api/geo/catalog`, getAuthHeaders()), axios.get(`${API}/api/geo/summary`, getAuthHeaders()),
    ]);
    setConfig(configResponse.data); setCatalog(catalogResponse.data); setSummary(summaryResponse.data);
  }, [API, getAuthHeaders]);
  const loadMap = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const endpoint = canViewPrecise ? 'precise' : 'aggregate';
      const response = await axios.get(`${API}/api/geo/${endpoint}`, { ...getAuthHeaders(), params: queryParams });
      setFeatures(response.data.features || []); setSelected(null);
    } catch (requestError) { setError(apiErrorMessage(requestError, 'No se pudo cargar el Mapa 360')); }
    finally { setLoading(false); }
  }, [API, canViewPrecise, getAuthHeaders, queryParams]);
  const refresh = useCallback(async () => { await loadBase(); await loadMap(); }, [loadBase, loadMap]);
  useEffect(() => { loadBase().catch((requestError) => { setError(apiErrorMessage(requestError, 'No se pudo abrir el Mapa 360')); setLoading(false); }); }, [loadBase]);
  useEffect(() => { if (config) loadMap(); }, [config, loadMap]);
  useEffect(() => { if (!compare) { setComparison(null); return; } axios.get(`${API}/api/geo/comparison?days=90`, getAuthHeaders()).then((response) => setComparison(response.data)).catch(() => setComparison(null)); }, [API, compare, getAuthHeaders]);
  useEffect(() => { if (!canViewPrecise && mode === 'pins') setMode('heatmap'); }, [canViewPrecise, mode]);
  const backfill = async () => { setBackfilling(true); try { const response = await axios.post(`${API}/api/geo/backfill?limit=250`, {}, getAuthHeaders()); toast.success(`${response.data.queued} ubicaciones enviadas a Census`); setTimeout(refresh, 1800); } catch (requestError) { toast.error(apiErrorMessage(requestError, 'No se pudo iniciar la geocodificación')); } finally { setBackfilling(false); } };

  return <main className="min-h-full bg-[#F4F1EA] p-4 sm:p-6 lg:p-8" data-testid="geo-maps-page"><div className="mx-auto max-w-[1680px] space-y-5"><header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-semibold uppercase text-amber-700">Inteligencia territorial</p><h1 className="font-['Spectral'] text-4xl font-semibold text-slate-950 sm:text-5xl">Mapa 360</h1><p className="mt-2 max-w-3xl text-sm text-slate-600">Comunidad, crecimiento y cobertura celular alrededor de 640 Demorest Rd.</p></div><div className="flex flex-wrap gap-2">{canManage && <Button variant="outline" onClick={backfill} disabled={backfilling} data-testid="geo-backfill-button">{backfilling ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}Geocodificar pendientes</Button>}{canManage && <Button variant="outline" onClick={() => setReviewOpen(true)} data-testid="open-geo-review-button"><CircleAlert className="h-4 w-4" />Verificar ({summary.review_total || 0})</Button>}<Button className={compare ? 'bg-slate-900 text-white' : ''} variant={compare ? 'default' : 'outline'} onClick={() => setCompare((value) => !value)} data-testid="toggle-geo-comparison"><Layers3 className="h-4 w-4" />Comparar 90 días</Button></div></header><GeoSummaryStrip summary={summary} />{compare && <GeoComparisonBand comparison={comparison} />}<Tabs value={kind} onValueChange={setKind}><TabsList className="grid w-full max-w-md grid-cols-2 bg-white" data-testid="geo-map-tabs"><TabsTrigger value="people" data-testid="geo-people-tab"><MapPinned className="mr-2 h-4 w-4" />Miembros y Personas</TabsTrigger><TabsTrigger value="cells" data-testid="geo-cells-tab"><Layers3 className="mr-2 h-4 w-4" />Células</TabsTrigger></TabsList></Tabs><GeoFilters filters={filters} setFilters={setFilters} catalog={catalog} mode={mode} setMode={setMode} canViewPrecise={canViewPrecise} /><section className="relative overflow-hidden border bg-white p-2" data-testid="geo-map-workspace">{loading && <div className="absolute inset-2 z-20 flex items-center justify-center bg-white/75" data-testid="geo-map-loading"><Loader2 className="h-7 w-7 animate-spin text-amber-700" /></div>}{error && <div className="absolute left-4 right-4 top-4 z-30 border border-red-200 bg-red-50 p-3 text-sm text-red-700" data-testid="geo-map-error-alert">{error}</div>}{config && <GeoMapCanvas center={config.center} zones={config.zones} features={features} mode={mode} entityKind={kind} onSelect={setSelected} />}<GeoDetailPanel feature={selected} onClose={() => setSelected(null)} />{!loading && !error && features.length === 0 && <div className="pointer-events-none absolute inset-x-8 top-24 z-10 mx-auto max-w-md border bg-white/95 p-5 text-center shadow-xl" data-testid="geo-map-empty"><MapPinned className="mx-auto h-6 w-6 text-amber-700" /><b className="mt-2 block">Aún no hay ubicaciones publicables</b><p className="mt-1 text-xs text-slate-500">Geocodifique pendientes o ajuste los filtros.</p></div>}</section></div>{canManage && config && <GeoReviewDialog open={reviewOpen} onOpenChange={setReviewOpen} center={config.center} onResolved={refresh} />}</main>;
}