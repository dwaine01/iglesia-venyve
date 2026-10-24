import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { Crosshair, Home, List, Loader2, MapPin, Maximize2, Minimize2, Navigation, Plus, RefreshCw, X } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { errorDetailText } from '../../lib/errorText';
import { LOW_ACCURACY_M, accuracyLabel, directionsUrl, getCurrentLocation } from '../../lib/geolocation';
import { useMapLibre } from '../../lib/mapLibre';
import { AddHouseholdDialog } from './AddHouseholdDialog';

const TILE_URL = process.env.REACT_APP_MAP_TILE_URL;
const CHURCH = [-83.089529154066, 39.941105761181];
export const CATEGORY = {
  mine: { label: 'Mis casas', color: '#2563eb' },
  available: { label: 'Disponibles', color: '#d97706' },
  visited: { label: 'Visitadas', color: '#16a34a' },
  assigned: { label: 'De otros mentores', color: '#64748b' },
};
const GEOCODING = {
  pending: 'Ubicando por la dirección…', not_found: 'No se encontró la dirección', ambiguous: 'Dirección ambigua',
  provider_error: 'No se pudo ubicar (servicio)', not_configured: 'Ubicación automática no configurada', needs_verification: 'Ubicada: conviene verificar',
};
const emptyCollection = { type: 'FeatureCollection', features: [] };
const addressOf = (item) => [item.address_line1, item.address_line2].filter(Boolean).join(', ') || item.sector || 'Casa sin dirección';
// Colores por resultado (Reporte de invasión): etiqueta + valor siempre visibles en la leyenda.
export const RESULT = {
  seven_weeks: { label: 'Iniciaron 7 Semanas', color: '#7c3aed' },
  followup: { label: 'Quieren seguimiento', color: '#16a34a' },
  contacted: { label: 'Contacto sin seguimiento', color: '#2563eb' },
  no_answer: { label: 'Sin respuesta', color: '#64748b' },
  pending: { label: 'Asignada, sin visitar', color: '#0ea5e9' },
  available: { label: 'Disponible', color: '#d97706' },
};
// Puerta a puerta: estado de cada vivienda (pendiente, programada, abrieron, sin visitar).
export const DOOR = {
  pending_revisit: { label: 'Pendiente de nueva visita', color: '#c2410c' },
  followup_scheduled: { label: 'Seguimiento programado', color: '#2563eb' },
  opened: { label: 'Abrieron', color: '#16a34a' },
  new: { label: 'Sin visitar', color: '#94a3b8' },
};
const doorKey = (item) => (DOOR[item.door_status] ? item.door_status : 'new');
const shortDate = (iso) => (iso ? new Date(iso.length === 10 ? `${iso}T12:00:00` : iso).toLocaleDateString('es', { day: 'numeric', month: 'short' }) : '');
const colorOf = (item, colorBy) => (colorBy === 'door' ? DOOR[doorKey(item)].color : colorBy === 'result' ? (RESULT[item.result] || RESULT.pending).color : (CATEGORY[item.category] || CATEGORY.assigned).color);
const collection = (points, colorBy) => ({
  type: 'FeatureCollection',
  features: points.map((item) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [item.longitude, item.latitude] }, properties: { id: item.household_id, category: item.category, color: colorOf(item, colorBy) } })),
});

// Mapa real de las casas de una invasión (MapLibre, carga diferida). Lo que se
// muestra lo decide el backend: el mentor recibe solo sus casas y las
// disponibles; el líder y los encargados, todas.
export function InvasionHousesMap({ campaigns, onRegisterVisit, onChanged, mentorPersonId, refreshKey = 0, colorBy = 'category', fixedHeight = null }) {
  const [pendingOnly, setPendingOnly] = useState(colorBy === 'door');
  const [mentorFilter, setMentorFilter] = useState('');
  const [sectorFilter, setSectorFilter] = useState('');
  const { API, getAuthHeaders } = useAuth();
  const { maplibregl, failed } = useMapLibre();
  const [campaignId, setCampaignId] = useState(campaigns[0]?.campaign_id || '');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [listOpen, setListOpen] = useState(false);
  const [me, setMe] = useState(null);
  const [busy, setBusy] = useState('');
  const [adding, setAdding] = useState(null);
  const containerRef = useRef(null); const mapRef = useRef(null); const fittedRef = useRef(''); const frameRef = useRef(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [height, setHeight] = useState(480);
  // El mapa ocupa desde su borde superior hasta el final de la pantalla (sin quedar cortado).
  useLayoutEffect(() => {
    const measure = () => { if (fixedHeight) { setHeight(fixedHeight); return; } const top = frameRef.current?.getBoundingClientRect().top ?? 0; setHeight(Math.max(420, Math.round(window.innerHeight - top - 16))); };
    measure(); window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [data, fixedHeight]);
  useEffect(() => { const timer = setTimeout(() => mapRef.current?.resize(), 50); return () => clearTimeout(timer); }, [fullscreen, height]);

  useEffect(() => { if (!campaigns.some((item) => item.campaign_id === campaignId)) setCampaignId(campaigns[0]?.campaign_id || ''); }, [campaigns, campaignId]);
  const load = useCallback(async () => {
    if (!campaignId) return;
    setLoading(true);
    try { setData((await axios.get(`${API}/api/mentorship/outreach/campaigns/${campaignId}/households/map`, getAuthHeaders())).data); }
    catch (error) { toast.error(errorDetailText(error, 'No se pudo cargar el mapa de casas')); setData(null); }
    finally { setLoading(false); }
  }, [API, getAuthHeaders, campaignId]);
  useEffect(() => { load(); }, [load, refreshKey]);
  // Mientras haya casas ubicándose por dirección, se refresca solo.
  useEffect(() => {
    if (!data?.unlocated?.some((item) => item.geocoding_status === 'pending')) return undefined;
    const timer = setTimeout(load, 4000);
    return () => clearTimeout(timer);
  }, [data, load]);

  const points = useMemo(() => (data?.points || []).filter((item) => (!mentorFilter || item.mentor_person_id === mentorFilter) && (!sectorFilter || (item.sector || 'Sin sector') === sectorFilter)
    && (colorBy !== 'door' || !pendingOnly || ['pending_revisit', 'followup_scheduled'].includes(item.door_status))), [data, mentorFilter, sectorFilter, colorBy, pendingOnly]);
  const mentorOptions = useMemo(() => Array.from(new Map((data?.points || []).concat(data?.unlocated || []).filter((item) => item.mentor_person_id && item.mentor_name).map((item) => [item.mentor_person_id, item.mentor_name])).entries()), [data]);
  const sectorOptions = useMemo(() => Array.from(new Set((data?.points || []).concat(data?.unlocated || []).map((item) => item.sector || 'Sin sector'))).sort(), [data]);
  const all = useMemo(() => [...points, ...(data?.unlocated || [])], [points, data]);
  const selected = all.find((item) => item.household_id === selectedId) || null;

  // Crear el mapa una vez que llega la biblioteca.
  useEffect(() => {
    if (!maplibregl || !containerRef.current || mapRef.current) return undefined;
    const map = new maplibregl.Map({
      container: containerRef.current, center: CHURCH, zoom: 13, attributionControl: { compact: true },
      style: { version: 8, sources: TILE_URL ? { osm: { type: 'raster', tiles: [TILE_URL], tileSize: 256, attribution: '© OpenStreetMap contributors' } } : {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#eef0ea' } }, ...(TILE_URL ? [{ id: 'osm', type: 'raster', source: 'osm' }] : [])] },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.on('load', () => {
      map.addSource('houses', { type: 'geojson', data: emptyCollection });
      map.addSource('me', { type: 'geojson', data: emptyCollection });
      map.addLayer({ id: 'me-dot', type: 'circle', source: 'me', paint: { 'circle-radius': 9, 'circle-color': '#0ea5e9', 'circle-stroke-width': 3, 'circle-stroke-color': '#ffffff' } });
      map.addLayer({ id: 'houses-selected', type: 'circle', source: 'houses', filter: ['==', ['get', 'id'], ''], paint: { 'circle-radius': 19, 'circle-color': 'rgba(16,29,54,0.18)', 'circle-stroke-width': 2, 'circle-stroke-color': '#101D36' } });
      map.addLayer({ id: 'houses', type: 'circle', source: 'houses', paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 6, 16, 11], 'circle-stroke-width': 2.5, 'circle-stroke-color': '#ffffff',
        'circle-color': ['get', 'color'],
      } });
      map.on('click', 'houses', (event) => { const id = event.features?.[0]?.properties?.id; if (id) { setSelectedId(id); setListOpen(false); } });
      map.on('mouseenter', 'houses', () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'houses', () => { map.getCanvas().style.cursor = ''; });
      map.isReadyForHouses = true; map.fire('houses-ready');
    });
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; fittedRef.current = ''; };
  }, [maplibregl]);

  // Pintar puntos y encuadrar la invasión.
  useEffect(() => {
    const map = mapRef.current; if (!map) return undefined;
    const paint = () => {
      map.getSource('houses')?.setData(collection(points, colorBy));
      if (points.length && fittedRef.current !== campaignId) {
        fittedRef.current = campaignId;
        const bounds = points.reduce((box, item) => box.extend([item.longitude, item.latitude]), new maplibregl.LngLatBounds([points[0].longitude, points[0].latitude], [points[0].longitude, points[0].latitude]));
        map.resize();
        const small = window.innerWidth < 1024; // en celular los botones flotantes ocupan la parte de abajo
        map.fitBounds(bounds, { padding: { top: 70, bottom: small ? 160 : 90, left: 50, right: 60 }, maxZoom: 17, duration: 0 });
      }
    };
    if (map.isReadyForHouses) paint(); else map.once('houses-ready', paint);
    return undefined;
  }, [points, campaignId, maplibregl, colorBy]);
  useEffect(() => { const map = mapRef.current; if (map?.isReadyForHouses) map.setFilter('houses-selected', ['==', ['get', 'id'], selectedId || '']); }, [selectedId, points]);
  useEffect(() => { const map = mapRef.current; if (map?.isReadyForHouses) map.getSource('me')?.setData(me ? { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: [me.longitude, me.latitude] }, properties: {} }] } : emptyCollection); }, [me]);

  const focus = (item) => { setSelectedId(item.household_id); setListOpen(false); if (item.latitude != null) mapRef.current?.flyTo({ center: [item.longitude, item.latitude], zoom: Math.max(mapRef.current.getZoom(), 16) }); };
  const locateMe = async () => {
    setBusy('me');
    try {
      const position = await getCurrentLocation(); setMe(position);
      mapRef.current?.flyTo({ center: [position.longitude, position.latitude], zoom: 17 });
      if (position.accuracy_m > LOW_ACCURACY_M) toast.message(`Tu ubicación es poco precisa (±${position.accuracy_m} m)`);
      return position;
    } catch (error) { toast.error(error.message); return null; } finally { setBusy(''); }
  };
  const run = async (key, action, success) => {
    setBusy(key);
    try { await action(); if (success) toast.success(success); await load(); onChanged?.(); } catch (error) { toast.error(errorDetailText(error, 'No se pudo completar')); } finally { setBusy(''); }
  };
  // La casa quedó con el punto aproximado de la calle: confirmarlo tal cual (o corregirlo con «mi ubicación»).
  const confirmPlace = (item) => run(`confirm-${item.household_id}`, () => axios.put(`${API}/api/mentorship/outreach/households/${item.household_id}/location`, { latitude: item.latitude, longitude: item.longitude, accuracy_m: item.location_accuracy_m, source: 'manual' }, getAuthHeaders()), 'Ubicación confirmada');
  const claim = (item) => run(`claim-${item.household_id}`, () => axios.post(`${API}/api/mentorship/outreach/households/${item.household_id}/claim`, {}, getAuthHeaders()), 'Casa tomada: ahora es tuya');
  const placeHere = async (item) => {
    setBusy(`place-${item.household_id}`);
    try {
      const position = await getCurrentLocation(); setMe(position);
      const response = await axios.put(`${API}/api/mentorship/outreach/households/${item.household_id}/location`, { latitude: position.latitude, longitude: position.longitude, accuracy_m: position.accuracy_m, source: 'gps' }, getAuthHeaders());
      if (response.data.low_accuracy) toast.message(`Guardada con ${accuracyLabel(position.accuracy_m)}. Puedes repetirla más cerca de la casa.`);
      else toast.success('Ubicación de la casa guardada');
      if (response.data.duplicates?.items?.length || response.data.duplicates?.hidden) toast.message('Atención: hay otra casa registrada a menos de 25 m');
      fittedRef.current = ''; await load(); onChanged?.();
    } catch (error) { toast.error(error.message && !error.response ? error.message : errorDetailText(error, 'No se pudo guardar la ubicación')); } finally { setBusy(''); }
  };
  const retryGeocoding = () => run('geocode', () => axios.post(`${API}/api/mentorship/outreach/campaigns/${campaignId}/households/geocode`, {}, getAuthHeaders()), 'Ubicando por dirección en segundo plano');

  if (!campaigns.length) return <p className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500" data-testid="outreach-map-empty-state">Participa en una invasión para ver su mapa de casas.</p>;
  const counts = data?.counts || {};
  const categories = Object.entries(CATEGORY).filter(([key]) => key !== 'assigned' || data?.scope === 'all');

  const card = selected && (
    <article className="space-y-3" data-testid="house-card">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold" style={{ color: CATEGORY[selected.category]?.color }}><span className="h-2.5 w-2.5 rounded-full" style={{ background: CATEGORY[selected.category]?.color }} />{CATEGORY[selected.category]?.label.replace(/s$/, '').replace('Mis casa', 'Mi casa').replace('De otros mentore', 'De otro mentor')}</span>
          <h3 className="mt-1 text-lg font-semibold text-[#101D36]" data-testid="house-card-address">{addressOf(selected)}</h3>
          {selected.location_reference && <p className="text-sm text-slate-600">{selected.location_reference}</p>}
          {colorBy === 'door' && <p className="mt-1 text-sm font-semibold" style={{ color: DOOR[doorKey(selected)].color }} data-testid="house-card-door-status">{DOOR[doorKey(selected)].label}{selected.followup_date ? ` · ${shortDate(selected.followup_date)}` : ''}{selected.last_attempt_at ? ` · última visita ${shortDate(selected.last_attempt_at)}` : ''}</p>}
          <p className="mt-1 text-xs text-slate-500">{selected.attempts ? `${selected.attempts} intento(s) de visita` : 'Sin visitas registradas'}{selected.latitude == null ? ` · ${GEOCODING[selected.geocoding_status] || 'Sin ubicación en el mapa'}` : selected.approximate ? ' · ubicación aproximada' : selected.location_source === 'gps' ? ` · GPS ${accuracyLabel(selected.location_accuracy_m)}` : selected.location_source === 'geocoded' ? ' · ubicada por dirección' : ''}</p>
        </div>
        <button type="button" onClick={() => setSelectedId(null)} className="grid h-11 w-11 shrink-0 place-items-center rounded-md hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {selected.can_claim && <button type="button" onClick={() => claim(selected)} disabled={Boolean(busy)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-[#d97706] px-4 text-base font-semibold text-white" data-testid="house-card-claim">{busy === `claim-${selected.household_id}` ? <Loader2 className="h-5 w-5 animate-spin" /> : <Home className="h-5 w-5" />}Tomar casa</button>}
        {selected.can_register_visit && <button type="button" onClick={() => onRegisterVisit?.(selected)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-[#101D36] px-4 text-base font-semibold text-white" data-testid="house-card-visit"><Plus className="h-5 w-5" />{colorBy === 'door' ? 'Registrar nueva visita' : 'Registrar visita'}</button>}
        <a href={directionsUrl(selected.latitude, selected.longitude, addressOf(selected))} target="_blank" rel="noreferrer" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg border border-[#D9D4C7] bg-white px-4 text-base font-semibold text-[#101D36]" data-testid="house-card-directions"><Navigation className="h-5 w-5" />Cómo llegar</a>
        {selected.can_edit_location && <button type="button" onClick={() => placeHere(selected)} disabled={Boolean(busy)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg border border-[#D9D4C7] bg-white px-4 text-sm font-semibold text-[#101D36]" data-testid="house-card-place">{busy === `place-${selected.household_id}` ? <Loader2 className="h-5 w-5 animate-spin" /> : <Crosshair className="h-5 w-5" />}{selected.latitude == null ? 'Ubicar con mi ubicación' : 'Corregir con mi ubicación'}</button>}
        {selected.can_edit_location && selected.location_approx && selected.latitude != null && <button type="button" onClick={() => confirmPlace(selected)} disabled={Boolean(busy)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg border border-[#D9D4C7] bg-white px-4 text-sm font-semibold text-[#101D36]" data-testid="house-card-confirm">{busy === `confirm-${selected.household_id}` ? <Loader2 className="h-5 w-5 animate-spin" /> : <MapPin className="h-5 w-5" />}Confirmar ubicación</button>}
      </div>
    </article>
  );

  const list = (
    <div className="space-y-3" data-testid="house-list">
      {data?.unlocated?.length > 0 && <section className="space-y-2" data-testid="house-list-unlocated">
        <div className="flex items-center justify-between gap-2"><h4 className="text-sm font-semibold text-[#8f382f]">Sin ubicar en el mapa ({data.unlocated.length})</h4>
          {data.scope === 'all' && <button type="button" onClick={retryGeocoding} disabled={Boolean(busy)} className="inline-flex min-h-10 items-center gap-1 rounded-md border border-[#D9D4C7] px-3 text-xs font-semibold" data-testid="house-list-geocode"><RefreshCw className="h-3.5 w-3.5" />Ubicar por dirección</button>}</div>
        {data.unlocated.map((item) => <button key={item.household_id} type="button" onClick={() => focus(item)} className="flex min-h-12 w-full items-center justify-between gap-2 rounded-lg border border-dashed border-[#e3c2bd] bg-white px-3 py-2 text-left" data-testid={`house-row-${item.household_id}`}><span className="min-w-0"><span className="block truncate text-sm font-medium text-[#101D36]">{addressOf(item)}</span><span className="block text-xs text-slate-500">{GEOCODING[item.geocoding_status] || 'Sin coordenadas: ubícala con tu ubicación'}</span></span><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: CATEGORY[item.category]?.color }} /></button>)}
      </section>}
      <section className="space-y-2">
        <h4 className="text-sm font-semibold text-[#101D36]">En el mapa ({points.length})</h4>
        {points.map((item) => <button key={item.household_id} type="button" onClick={() => focus(item)} className={`flex min-h-12 w-full items-center justify-between gap-2 rounded-lg border bg-white px-3 py-2 text-left ${selectedId === item.household_id ? 'border-[#101D36]' : 'border-[#EEECE6]'}`} data-testid={`house-row-${item.household_id}`}><span className="min-w-0"><span className="block truncate text-sm font-medium text-[#101D36]">{addressOf(item)}</span>{item.location_reference && <span className="block truncate text-xs text-slate-500">{item.location_reference}</span>}</span><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: CATEGORY[item.category]?.color }} /></button>)}
        {!points.length && <p className="text-sm text-slate-500">Todavía no hay casas ubicadas.</p>}
      </section>
    </div>
  );

  return (
    <div className="space-y-3" data-testid="outreach-map-view">
      <div className="flex flex-col gap-2 lg:flex-row lg:flex-wrap lg:items-center lg:justify-between">
        {campaigns.length > 1
          ? <select value={campaignId} onChange={(event) => { setCampaignId(event.target.value); setSelectedId(null); }} className="h-12 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 text-base lg:w-96" data-testid="house-map-campaign">{campaigns.map((item) => <option key={item.campaign_id} value={item.campaign_id}>{item.name}</option>)}</select>
          : <h3 className="font-['Spectral'] text-xl font-semibold text-[#101D36]">{campaigns[0].name}</h3>}
        {colorBy === 'door'
          ? <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm" data-testid="house-map-legend">{Object.entries(DOOR).map(([key, item]) => <li key={key} className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded-full ring-2 ring-white" style={{ background: item.color }} />{item.label} <b>{(data?.points || []).filter((point) => doorKey(point) === key).length}</b></li>)}</ul>
              <label className="inline-flex min-h-11 items-center gap-2 text-[15px] font-semibold text-[#101D36]"><input type="checkbox" checked={pendingOnly} onChange={(event) => setPendingOnly(event.target.checked)} className="h-5 w-5" data-testid="house-map-pending-only" />Solo pendientes</label>
            </div>
          : colorBy === 'result'
          ? <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm" data-testid="house-map-legend">{Object.entries(RESULT).map(([key, item]) => <li key={key} className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded-full ring-2 ring-white" style={{ background: item.color }} />{item.label} <b>{points.filter((point) => point.result === key).length}</b></li>)}</ul>
          : <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm" data-testid="house-map-legend">{categories.map(([key, item]) => <li key={key} className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded-full ring-2 ring-white" style={{ background: item.color }} />{item.label} <b>{counts[key] || 0}</b></li>)}<li className="inline-flex items-center gap-1.5 text-slate-500"><MapPin className="h-3.5 w-3.5" />Sin ubicar <b>{counts.unlocated || 0}</b></li></ul>}
        {colorBy === 'result' && (mentorOptions.length > 0 || sectorOptions.length > 1) && <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-2" data-testid="house-map-filters">
          {mentorOptions.length > 0 && <select value={mentorFilter} onChange={(event) => setMentorFilter(event.target.value)} className="h-11 rounded-lg border border-[#D9D4C7] bg-white px-3 text-sm" aria-label="Filtrar por mentor"><option value="">Todos los mentores</option>{mentorOptions.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select>}
          {sectorOptions.length > 1 && <select value={sectorFilter} onChange={(event) => setSectorFilter(event.target.value)} className="h-11 rounded-lg border border-[#D9D4C7] bg-white px-3 text-sm" aria-label="Filtrar por sector"><option value="">Todos los sectores</option>{sectorOptions.map((sector) => <option key={sector} value={sector}>{sector}</option>)}</select>}
        </div>}
      </div>
      {data?.scope === 'mine' && <p className="text-xs text-slate-500">Ves tus casas y las disponibles de esta invasión.</p>}
      {data && !data.geocoding_configured && counts.unlocated > 0 && <p className="text-xs text-amber-800">La ubicación automática por dirección no está configurada en el servidor: ubica las casas con «Ubicar con mi ubicación».</p>}

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div ref={frameRef} style={fullscreen ? undefined : { height }} className={fullscreen ? 'fixed inset-0 z-40 overflow-hidden bg-[#eef0ea]' : 'relative overflow-hidden rounded-xl border border-[#E8E5DE] bg-[#eef0ea]'} data-testid="house-map">
          {failed ? <div className="flex h-full items-center justify-center p-6 text-center text-sm text-amber-900">No se pudo cargar el mapa. Usa la lista de casas.</div>
            : !maplibregl ? <div className="flex h-full items-center justify-center text-sm text-slate-500"><Loader2 className="mr-2 h-5 w-5 animate-spin" />Cargando mapa…</div>
              : <div ref={containerRef} className="h-full w-full" data-testid="house-map-canvas" />}
          {loading && <div className="absolute left-1/2 top-3 -translate-x-1/2 rounded-full bg-white/90 px-3 py-1 text-xs shadow"><Loader2 className="mr-1 inline h-3.5 w-3.5 animate-spin" />Actualizando</div>}
          <button type="button" onClick={() => setFullscreen((value) => !value)} className="absolute left-3 top-3 inline-flex min-h-11 items-center gap-2 rounded-full bg-white px-4 text-sm font-semibold text-[#101D36] shadow-md lg:hidden" data-testid="house-map-fullscreen">{fullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}{fullscreen ? 'Salir' : 'Pantalla completa'}</button>
          <div className="absolute bottom-3 left-3 right-3 flex flex-wrap justify-end gap-2 lg:left-auto" style={fullscreen ? { paddingBottom: 'env(safe-area-inset-bottom)' } : undefined}>
            <button type="button" onClick={() => setListOpen(true)} className="inline-flex min-h-12 items-center gap-2 rounded-full bg-white px-4 text-sm font-semibold text-[#101D36] shadow-md lg:hidden" data-testid="house-map-list-toggle"><List className="h-5 w-5" />Lista</button>
            <button type="button" onClick={locateMe} disabled={busy === 'me'} className="inline-flex min-h-12 items-center gap-2 rounded-full bg-white px-4 text-sm font-semibold text-[#101D36] shadow-md" data-testid="house-map-locate">{busy === 'me' ? <Loader2 className="h-5 w-5 animate-spin" /> : <Crosshair className="h-5 w-5" />}Centrar en mí</button>
            {mentorPersonId && (campaigns.find((item) => item.campaign_id === campaignId)?.assigned_mentor_ids || []).includes(mentorPersonId) && <button type="button" onClick={() => setAdding({ location: me })} className="inline-flex min-h-12 items-center gap-2 rounded-full bg-[#101D36] px-4 text-sm font-semibold text-white shadow-md" data-testid="house-map-add"><Plus className="h-5 w-5" />Agregar casa</button>}
          </div>
          {selected && <div className="absolute inset-x-0 bottom-0 max-h-[70%] overflow-y-auto rounded-t-2xl bg-white p-4 shadow-2xl lg:hidden" data-testid="house-card-sheet">{card}</div>}
        </div>
        <aside className="hidden min-w-0 space-y-3 lg:block lg:overflow-y-auto" style={{ height }}>
          {selected && <div className="rounded-xl border border-[#101D36] bg-white p-4">{card}</div>}
          <div className="rounded-xl border border-[#E8E5DE] bg-[#FBFAF7] p-3">{list}</div>
        </aside>
      </div>

      {listOpen && <div className="fixed inset-0 z-50 flex flex-col bg-white text-[#101D36] lg:hidden" role="dialog" aria-modal="true" data-testid="house-list-sheet">
        <div className="flex items-center justify-between border-b border-[#E8E5DE] px-4 py-2"><p className="font-['Spectral'] text-lg font-semibold">Casas de la invasión</p><button type="button" onClick={() => setListOpen(false)} className="grid h-11 w-11 place-items-center rounded-md hover:bg-slate-100" aria-label="Cerrar"><X className="h-5 w-5" /></button></div>
        <div className="flex-1 overflow-y-auto p-4">{list}</div>
      </div>}
      {adding && <AddHouseholdDialog open onOpenChange={(value) => { if (!value) setAdding(null); }} campaigns={campaigns.filter((item) => item.campaign_id === campaignId)} defaultCampaignId={campaignId} initialLocation={adding.location} forcedMentorId={mentorPersonId} onCreated={() => { fittedRef.current = ''; load(); onChanged?.(); }} />}
    </div>
  );
}
