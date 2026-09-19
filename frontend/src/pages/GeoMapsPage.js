import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { CircleAlert, Loader2, MapPinned } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { GeoComparisonBand } from '../components/geo/GeoComparisonBand';
import { GeoDetailPanel } from '../components/geo/GeoDetailPanel';
import { GeoMapCanvas } from '../components/geo/GeoMapCanvas';
import { GeoMapToolbar } from '../components/geo/GeoMapToolbar';
import { GeoReviewDialog } from '../components/geo/GeoReviewDialog';
import { GeoSectorEditorDrawer } from '../components/geo/GeoSectorEditorDrawer';
import { GeoUnlocatedDrawer } from '../components/geo/GeoUnlocatedDrawer';
import { Presentation2To1Shell } from '../components/geo/Presentation2To1Shell';

const emptyCatalog = { front_groups: [], cells: [], stages: [] };
const initialFilters = { category: '', zone: '', subzone: '', stage: '', front_group_id: '', cell_id: '', period_start: '' };

export default function GeoMapsPage() {
  const { API, getAuthHeaders } = useAuth(); const [kind, setKind] = useState('people');
  const [mode, setMode] = useState('clusters'); const [filters, setFilters] = useState(initialFilters);
  const [config, setConfig] = useState(null); const [catalog, setCatalog] = useState(emptyCatalog);
  const [summary, setSummary] = useState({}); const [features, setFeatures] = useState([]); const [sectors, setSectors] = useState([]);
  const [comparison, setComparison] = useState(null); const [compare, setCompare] = useState(false);
  const [selected, setSelected] = useState(null); const [selectedPersonId, setSelectedPersonId] = useState(null); const [focusTarget, setFocusTarget] = useState(null); const [focusGeometry, setFocusGeometry] = useState(null);
  const [reviewOpen, setReviewOpen] = useState(false); const [sectorEditorOpen, setSectorEditorOpen] = useState(false);
  const [unlocatedOpen, setUnlocatedOpen] = useState(false);
  const [draftCoordinates, setDraftCoordinates] = useState([]); const [selectedVertex, setSelectedVertex] = useState(null); const [drawingSector, setDrawingSector] = useState(false);
  const [presentationMode, setPresentationMode] = useState(false); const [loading, setLoading] = useState(true);
  const [error, setError] = useState(''); const [backfilling, setBackfilling] = useState(false);
  const canViewPrecise = Boolean(config?.permissions?.view_precise); const canManage = Boolean(config?.permissions?.manage_locations);
  const providerConfigured = Boolean(config?.map_policy?.geocoding_configured); const geocodioConfigured = Boolean(config?.map_policy?.geocoding_providers?.geocodio);
  const queryParams = useMemo(() => ({
    entity_kind: kind, categories: filters.category || undefined, zone: filters.zone || undefined,
    subzone: filters.subzone || undefined, stage: filters.stage || undefined,
    front_group_id: filters.front_group_id || undefined, cell_id: filters.cell_id || undefined,
    period_start: filters.period_start ? new Date(`${filters.period_start}T00:00:00`).toISOString() : undefined,
  }), [filters, kind]);

  const loadBase = useCallback(async () => {
    const [configResponse, catalogResponse, summaryResponse, sectorResponse] = await Promise.all([
      axios.get(`${API}/api/geo/config`, getAuthHeaders()), axios.get(`${API}/api/geo/catalog`, getAuthHeaders()),
      axios.get(`${API}/api/geo/summary`, getAuthHeaders()), axios.get(`${API}/api/geo/sectors`, getAuthHeaders()),
    ]);
    setConfig(configResponse.data); setCatalog(catalogResponse.data); setSummary(summaryResponse.data); setSectors(sectorResponse.data.items || []);
  }, [API, getAuthHeaders]);
  const loadMap = useCallback(async () => {
    setLoading(true); setError('');
    try { const endpoint = canViewPrecise ? 'precise' : 'aggregate'; const response = await axios.get(`${API}/api/geo/${endpoint}`, { ...getAuthHeaders(), params: queryParams }); setFeatures(response.data.features || []); }
    catch (requestError) { setError(apiErrorMessage(requestError, 'No se pudo cargar el Mapa 360')); }
    finally { setLoading(false); }
  }, [API, canViewPrecise, getAuthHeaders, queryParams]);
  const refresh = useCallback(async () => { await loadBase(); await loadMap(); }, [loadBase, loadMap]);
  useEffect(() => { loadBase().catch((requestError) => { setError(apiErrorMessage(requestError, 'No se pudo abrir el Mapa 360')); setLoading(false); }); }, [loadBase]);
  useEffect(() => { if (config) loadMap(); }, [config, loadMap]);
  useEffect(() => { if (!compare) { setComparison(null); return; } axios.get(`${API}/api/geo/comparison?days=90`, getAuthHeaders()).then((response) => setComparison(response.data)).catch(() => setComparison(null)); }, [API, compare, getAuthHeaders]);
  useEffect(() => { if (!canViewPrecise && mode === 'pins') setMode('heatmap'); }, [canViewPrecise, mode]);
  useEffect(() => {
    if (!selectedPersonId) return;
    const household = features.find((feature) => feature.properties?.entity_kind === 'household' && Array.isArray(feature.properties?.residents) && feature.properties.residents.some((resident) => resident.person_id === selectedPersonId));
    if (household) setSelected(household);
  }, [features, selectedPersonId]);
  const backfill = async () => {
    setBackfilling(true); try { const response = await axios.post(`${API}/api/geo/backfill?limit=250`, {}, getAuthHeaders()); toast.success(`${response.data.queued} ubicaciones enviadas a geocodificación automática`); setTimeout(refresh, 1800); }
    catch (requestError) { toast.error(apiErrorMessage(requestError, 'No se pudo iniciar la geocodificación')); } finally { setBackfilling(false); }
  };
  const selectPerson = (person) => {
    const fallback = { type: 'Feature', geometry: { type: 'Point', coordinates: [person.longitude, person.latitude] }, properties: { entity_kind: 'person', entity_id: person.person_id, name: person.name, person_number: person.person_number, zone: person.zone, zone_number: person.zone_number, subzone: person.subzone } };
    setSelected(fallback); setSelectedPersonId(person.person_id); setFocusTarget(person); setKind('people'); setMode('pins');
  };
  const focusSector = (sector) => { setFocusGeometry(sector.geometry); };
  const openPresentation = () => { setKind('people'); setMode('pins'); setPresentationMode(true); };

  if (presentationMode && config) return <Presentation2To1Shell config={config} sectors={sectors.filter((item) => item.status === 'active')} features={features} onExit={() => setPresentationMode(false)} />;
  return <main className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-[#F4F1EA]" data-testid="geo-maps-page">
    <GeoMapToolbar kind={kind} setKind={setKind} mode={mode} setMode={setMode} filters={filters} setFilters={setFilters} catalog={catalog} summary={summary} canViewPrecise={canViewPrecise} canManage={canManage} providerConfigured={providerConfigured} compare={compare} setCompare={setCompare} backfilling={backfilling} onBackfill={backfill} onReview={() => setReviewOpen(true)} onPersonSelect={selectPerson} onEditSectors={() => setSectorEditorOpen(true)} onPresent={openPresentation} onUnlocated={() => setUnlocatedOpen(true)} />
    <section className="relative min-h-0 flex-1 overflow-hidden bg-white" data-testid="geo-map-workspace">
      {loading && <div className="absolute inset-0 z-30 flex items-center justify-center bg-white/70" data-testid="geo-map-loading"><Loader2 className="h-7 w-7 animate-spin text-amber-700" /></div>}
      {error && <div className="absolute left-3 right-3 top-3 z-40 border border-red-200 bg-red-50 p-3 text-sm text-red-700" data-testid="geo-map-error-alert">{error}</div>}
      {!geocodioConfigured && canManage && <div className="absolute left-3 top-3 z-20 max-w-sm border border-amber-300 bg-amber-50 p-2 text-xs text-amber-950 shadow" data-testid="geo-fallback-config-alert"><CircleAlert className="mr-1 inline h-4 w-4" /><b>Respaldo Geocodio pendiente.</b> Census seguirá activo, pero las direcciones no encontradas pasarán a revisión.</div>}
      {config && <GeoMapCanvas center={config.center} zones={config.zones} subzones={config.subzones} sectors={sectors.filter((item) => item.status === 'active')} features={features} mode={mode} focusTarget={focusTarget} focusGeometry={focusGeometry} onSelect={(feature) => { setSelectedPersonId(null); setSelected(feature); }} onSelectSector={(sectorId) => { const sector = sectors.find((item) => item.sector_id === sectorId); if (sector) focusSector(sector); }} editorActive={drawingSector} draftCoordinates={draftCoordinates} onDraftChange={setDraftCoordinates} selectedVertex={selectedVertex} onSelectVertex={setSelectedVertex} />}
      <GeoDetailPanel feature={selected} onClose={() => { setSelected(null); setSelectedPersonId(null); }} />
      {compare && comparison && <div className="absolute bottom-3 left-3 z-20 max-w-[calc(100%-1.5rem)]"><GeoComparisonBand comparison={comparison} compact /></div>}
      {!loading && !error && features.length === 0 && <div className="pointer-events-none absolute inset-x-8 top-20 z-10 mx-auto max-w-md border bg-white/95 p-4 text-center shadow-xl" data-testid="geo-map-empty"><MapPinned className="mx-auto h-6 w-6 text-amber-700" /><b className="mt-2 block">Aún no hay ubicaciones publicables</b><p className="mt-1 text-xs text-slate-500">Geocodifique pendientes o ajuste los filtros.</p></div>}
    </section>
    {canManage && config && <GeoReviewDialog open={reviewOpen} onOpenChange={setReviewOpen} center={config.center} onResolved={refresh} />}
    {canManage && <GeoSectorEditorDrawer open={sectorEditorOpen} onOpenChange={setSectorEditorOpen} sectors={sectors.filter((item) => item.status === 'active')} draft={draftCoordinates} setDraft={setDraftCoordinates} selectedVertex={selectedVertex} setSelectedVertex={setSelectedVertex} onSaved={refresh} onFocusSector={focusSector} onDrawingChange={setDrawingSector} />}
    {canManage && <GeoUnlocatedDrawer open={unlocatedOpen} onOpenChange={setUnlocatedOpen} />}
  </main>;
}