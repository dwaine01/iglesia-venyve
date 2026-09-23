import React, { useEffect, useRef } from 'react';

const requiredMapEnv = (name) => {
  const value = process.env[name];
  if (!value) throw new Error(`Falta la variable requerida ${name}`);
  return value;
};

const TILE_URL = requiredMapEnv('REACT_APP_MAP_TILE_URL');
const SATELLITE_TILE_URL = process.env.REACT_APP_SATELLITE_TILE_URL || null;
const zoneColors = { north: '#247BA0', east: '#2F8F6B', south: '#D97706', west: '#C0266D' };
const emptyCollection = () => ({ type: 'FeatureCollection', features: [] });
const imageKey = (value) => String(value || '').replace(/[^a-z0-9-]+/gi, '-').toLowerCase();

const createPinImage = (kind, color, large = false) => {
  const width = large ? 96 : 82; const height = large ? 112 : 96;
  const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
  const context = canvas.getContext('2d'); const cx = width / 2; const radius = large ? 30 : 25; const cy = radius + 8;
  context.shadowColor = 'rgba(15,23,42,.3)'; context.shadowBlur = 8; context.shadowOffsetY = 3;
  context.beginPath(); context.arc(cx, cy, radius, Math.PI * .18, Math.PI * .82, true); context.lineTo(cx, height - 5); context.closePath();
  context.fillStyle = color; context.fill(); context.shadowColor = 'transparent'; context.lineWidth = 4; context.strokeStyle = '#fff'; context.stroke();
  context.fillStyle = '#fff'; context.strokeStyle = '#fff'; context.lineWidth = 4; context.lineCap = 'round'; context.lineJoin = 'round';
  if (kind === 'front_group') [[cx, cy - 10], [cx - 12, cy + 9], [cx + 12, cy + 9]].forEach(([x, y]) => { context.beginPath(); context.arc(x, y, 6, 0, Math.PI * 2); context.fill(); });
  else { context.fillRect(cx - 15, cy - 2, 30, 23); context.beginPath(); context.moveTo(cx - 20, cy - 2); context.lineTo(cx, cy - 20); context.lineTo(cx + 20, cy - 2); context.stroke(); context.beginPath(); context.moveTo(cx, cy - 30); context.lineTo(cx, cy - 15); context.moveTo(cx - 7, cy - 25); context.lineTo(cx + 7, cy - 25); context.stroke(); }
  return context.getImageData(0, 0, width, height);
};

const createLabelImage = (text, color, compact = false) => {
  const canvas = document.createElement('canvas'); canvas.width = compact ? 64 : 154; canvas.height = compact ? 30 : 36;
  const context = canvas.getContext('2d'); context.fillStyle = 'rgba(255,255,255,.86)'; context.strokeStyle = color; context.lineWidth = 2;
  context.beginPath(); context.roundRect(1, 1, canvas.width - 2, canvas.height - 2, 7); context.fill(); context.stroke();
  context.fillStyle = color; context.font = `700 ${compact ? 15 : 16}px sans-serif`; context.textAlign = 'center'; context.textBaseline = 'middle'; context.fillText(text, canvas.width / 2, canvas.height / 2 + 1);
  return context.getImageData(0, 0, canvas.width, canvas.height);
};

const registerImages = (map, sectors = []) => {
  const images = { 'pin-front-group': createPinImage('front_group', '#1B6B93'), 'pin-church': createPinImage('church', '#9F1239', true) };
  Object.entries(images).forEach(([id, image]) => { if (!map.hasImage(id)) map.addImage(id, image, { pixelRatio: 2 }); });
  [[1, 'Zona 1 · Norte', zoneColors.north], [2, 'Zona 2 · Este', zoneColors.east], [3, 'Zona 3 · Sur', zoneColors.south], [4, 'Zona 4 · Oeste', zoneColors.west]].forEach(([number, label, color]) => { if (!map.hasImage(`zone-label-${number}`)) map.addImage(`zone-label-${number}`, createLabelImage(label, color), { pixelRatio: 2 }); });
  [1, 2, 3, 4].forEach((number) => ['A', 'B', 'C'].forEach((letter) => { const id = `subzone-label-${number}-${letter.toLowerCase()}`; if (!map.hasImage(id)) map.addImage(id, createLabelImage(`${number}-${letter}`, '#334155', true), { pixelRatio: 2 }); }));
  sectors.forEach((sector) => { const id = `sector-label-${imageKey(sector.sector_id)}`; if (!map.hasImage(id)) map.addImage(id, createLabelImage(sector.name || 'Sector', sector.color || '#1B2A4A', true), { pixelRatio: 2 }); });
};

const sectorCollection = (sectors) => ({ type: 'FeatureCollection', features: (sectors || []).map((sector) => ({ type: 'Feature', geometry: sector.geometry, properties: { ...sector, label_icon: `sector-label-${imageKey(sector.sector_id)}`, geometry: undefined, stats: JSON.stringify(sector.stats || {}) } })) });
const draftCollections = (coordinates) => ({
  vertices: { type: 'FeatureCollection', features: (coordinates || []).map((coordinate, index) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: coordinate }, properties: { vertex_index: index } })) },
  polygon: { type: 'FeatureCollection', features: coordinates?.length >= 3 ? [{ type: 'Feature', geometry: { type: 'Polygon', coordinates: [[...coordinates, coordinates[0]]] }, properties: {} }] : [] },
});

const setVisibility = (map, mode, presentationLevel) => {
  const presenting = Boolean(presentationLevel);
  const visible = { 'geo-heatmap': !presenting && mode === 'heatmap', 'geo-points': !presenting && mode === 'pins', 'geo-front-group-pins': !presenting };
  Object.entries(visible).forEach(([id, show]) => { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', show ? 'visible' : 'none'); });
};

const renderPresentationMarkers = (map, maplibregl, features, onSelect, markerRef) => {
  markerRef.current.forEach((marker) => marker.remove()); markerRef.current = [];
  (features || []).filter((item) => item.properties?.entity_kind === 'household').forEach((feature) => {
    const button = document.createElement('button'); const count = feature.properties.resident_count || 1;
    button.type = 'button'; button.dataset.testid = `geo-household-pin-${String(feature.properties.entity_id).replace(/[^a-z0-9-]+/gi, '-')}`; button.setAttribute('aria-label', `Hogar con ${count} personas`);
    button.className = 'relative flex h-16 w-14 items-center justify-center rounded-t-full rounded-bl-full border-4 border-white bg-amber-600 text-white shadow-2xl transition-transform hover:-translate-y-1';
    const home = document.createElement('span'); home.textContent = '⌂'; home.className = 'text-3xl font-black'; button.appendChild(home);
    const badge = document.createElement('span'); badge.textContent = String(count); badge.className = 'absolute -right-3 -top-3 flex h-8 min-w-8 items-center justify-center rounded-full border-2 border-slate-950 bg-amber-300 px-1 text-base font-black text-slate-950'; button.appendChild(badge);
    button.addEventListener('click', (event) => { event.stopPropagation(); onSelect?.(feature); });
    markerRef.current.push(new maplibregl.Marker({ element: button, anchor: 'bottom' }).setLngLat(feature.geometry.coordinates).addTo(map));
  });
};

const boundsForGeometry = (geometry) => {
  const points = geometry?.type === 'Point' ? [geometry.coordinates] : (geometry?.coordinates || []).flat(3).filter((item) => Array.isArray(item) && item.length === 2 && typeof item[0] === 'number');
  if (!points.length) return null;
  return points.reduce((bounds, point) => [[Math.min(bounds[0][0], point[0]), Math.min(bounds[0][1], point[1])], [Math.max(bounds[1][0], point[0]), Math.max(bounds[1][1], point[1])]], [[points[0][0], points[0][1]], [points[0][0], points[0][1]]]);
};

const fitFeatures = (map, features, duration = 0) => {
  const points = (features || []).filter((feature) => feature.geometry?.type === 'Point' && Array.isArray(feature.geometry.coordinates)).map((feature) => feature.geometry.coordinates);
  if (!points.length) return;
  if (points.length === 1) { map.easeTo({ center: points[0], zoom: 14, duration }); return; }
  const bounds = points.reduce((value, point) => [[Math.min(value[0][0], point[0]), Math.min(value[0][1], point[1])], [Math.max(value[1][0], point[0]), Math.max(value[1][1], point[1])]], [[points[0][0], points[0][1]], [points[0][0], points[0][1]]]);
  map.fitBounds(bounds, { padding: 64, duration, maxZoom: 14 });
};

const addOverlayLayers = (map, values, center, selectedSectorId) => {
  registerImages(map, values.sectors);
  map.addSource('geo-zones', { type: 'geojson', data: values.zones || emptyCollection() });
  map.addLayer({ id: 'geo-zones-fill', type: 'fill', source: 'geo-zones', maxzoom: 14, filter: ['==', ['get', 'feature_type'], 'zone'], paint: { 'fill-color': ['match', ['get', 'zone'], 'north', zoneColors.north, 'east', zoneColors.east, 'south', zoneColors.south, zoneColors.west], 'fill-opacity': .065 } });
  map.addLayer({ id: 'geo-zones-line', type: 'line', source: 'geo-zones', maxzoom: 14, filter: ['==', ['get', 'feature_type'], 'zone'], paint: { 'line-color': ['match', ['get', 'zone'], 'north', zoneColors.north, 'east', zoneColors.east, 'south', zoneColors.south, zoneColors.west], 'line-opacity': .56, 'line-width': 1.35 } });
  map.addLayer({ id: 'geo-zone-labels', type: 'symbol', source: 'geo-zones', minzoom: 8, maxzoom: 12.7, filter: ['==', ['get', 'feature_type'], 'zone_label'], layout: { 'icon-image': ['get', 'label_icon'], 'icon-allow-overlap': false }, paint: { 'icon-opacity': .82 } });
  map.addSource('geo-subzones', { type: 'geojson', data: values.subzones || emptyCollection() });
  map.addLayer({ id: 'geo-subzone-rings', type: 'line', source: 'geo-subzones', minzoom: 10.5, maxzoom: 14, filter: ['==', ['get', 'feature_type'], 'subzone_ring'], paint: { 'line-color': '#475569', 'line-width': 1, 'line-dasharray': [2, 2], 'line-opacity': .42 } });
  map.addLayer({ id: 'geo-subzone-labels', type: 'symbol', source: 'geo-subzones', minzoom: 11, maxzoom: 14, filter: ['==', ['get', 'feature_type'], 'subzone_label'], layout: { 'icon-image': ['get', 'label_icon'], 'icon-allow-overlap': false }, paint: { 'icon-opacity': .74 } });
  map.addSource('geo-sectors', { type: 'geojson', data: sectorCollection(values.sectors) });
  map.addLayer({ id: 'geo-sectors-fill', type: 'fill', source: 'geo-sectors', maxzoom: 16, paint: { 'fill-color': ['get', 'color'], 'fill-opacity': ['case', ['==', ['get', 'sector_id'], selectedSectorId || ''], .2, .075] } });
  map.addLayer({ id: 'geo-sectors-line', type: 'line', source: 'geo-sectors', paint: { 'line-color': ['get', 'color'], 'line-width': ['case', ['==', ['get', 'sector_id'], selectedSectorId || ''], 3, 1.25], 'line-opacity': .68 } });
  map.addLayer({ id: 'geo-sector-labels', type: 'symbol', source: 'geo-sectors', minzoom: 12, maxzoom: 16, layout: { 'icon-image': ['get', 'label_icon'], 'icon-allow-overlap': false }, paint: { 'icon-opacity': .76 } });
  const regular = values.features.filter((item) => item.properties?.entity_kind !== 'front_group'); const groups = values.features.filter((item) => item.properties?.entity_kind === 'front_group');
  map.addSource('geo-raw', { type: 'geojson', data: { type: 'FeatureCollection', features: regular } }); map.addSource('geo-front-groups', { type: 'geojson', data: { type: 'FeatureCollection', features: groups } });
  map.addSource('geo-anchor', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'Point', coordinates: [center.longitude, center.latitude] }, properties: { entity_kind: 'church', entity_id: 'church-anchor', name: 'Iglesia Ven y Ve', address: center.address } } });
  map.addSource('geo-search-highlight', { type: 'geojson', data: emptyCollection() }); map.addSource('geo-sector-draft', { type: 'geojson', data: emptyCollection() }); map.addSource('geo-sector-draft-vertices', { type: 'geojson', data: emptyCollection() });
  map.addLayer({ id: 'geo-heatmap', type: 'heatmap', source: 'geo-raw', maxzoom: 16, paint: { 'heatmap-weight': ['interpolate', ['linear'], ['coalesce', ['get', 'resident_count'], ['get', 'count'], 1], 1, .2, 20, 1], 'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 8, .8, 14, 2], 'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], 0, 'rgba(27,107,147,0)', .25, '#87B9A4', .5, '#E8C35A', .75, '#D97706', 1, '#9F1239'], 'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 8, 18, 14, 38], 'heatmap-opacity': .74 } });
  const evangelismColor = ['match', ['get', 'status'], 'assigned', '#2563EB', 'visited', '#0F766E', 'follow_up', '#D97706', 'connected', '#059669', 'do_not_visit', '#64748B', '#7C3AED'];
  map.addLayer({ id: 'geo-points', type: 'circle', source: 'geo-raw', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 8, 3.5, 12, 5.25, 16, 7], 'circle-color': ['match', ['get', 'entity_kind'], 'cell', '#0F766E', 'evangelism_target', evangelismColor, '#C56B1A'], 'circle-opacity': .94, 'circle-stroke-color': '#FFFFFF', 'circle-stroke-width': 1.5 } });
  map.addLayer({ id: 'geo-front-group-pins', type: 'symbol', source: 'geo-front-groups', layout: { 'icon-image': 'pin-front-group', 'icon-anchor': 'bottom', 'icon-allow-overlap': true } }); map.addLayer({ id: 'geo-church-anchor', type: 'symbol', source: 'geo-anchor', layout: { 'icon-image': 'pin-church', 'icon-anchor': 'bottom', 'icon-allow-overlap': true } });
  map.addLayer({ id: 'geo-search-halo', type: 'circle', source: 'geo-search-highlight', paint: { 'circle-radius': 18, 'circle-color': 'rgba(255,255,255,0)', 'circle-stroke-color': '#E11D48', 'circle-stroke-width': 4 } });
  map.addLayer({ id: 'geo-sector-draft-fill', type: 'fill', source: 'geo-sector-draft', paint: { 'fill-color': '#06B6D4', 'fill-opacity': .28 } }); map.addLayer({ id: 'geo-sector-draft-line', type: 'line', source: 'geo-sector-draft', paint: { 'line-color': '#0891B2', 'line-width': 4, 'line-dasharray': [2, 1] } }); map.addLayer({ id: 'geo-sector-draft-vertices-layer', type: 'circle', source: 'geo-sector-draft-vertices', paint: { 'circle-radius': 7, 'circle-color': '#F59E0B', 'circle-stroke-color': '#0B0F17', 'circle-stroke-width': 2 } });
};

export const GeoMapCanvas = ({ center, features = [], zones, subzones, sectors = [], mode, basemap = 'clear', focusTarget, focusGeometry, onSelect, onSelectZone, onSelectSector, editorActive = false, draftCoordinates = [], onDraftChange, selectedVertex, onSelectVertex, selectedSectorId, presentationLevel }) => {
  const maplibregl = typeof window !== 'undefined' ? window.maplibregl : null;
  const containerRef = useRef(null); const mapRef = useRef(null); const valuesRef = useRef({}); const presentationMarkersRef = useRef([]);
  valuesRef.current = { features, zones, subzones, sectors, mode, basemap, presentationLevel, focusGeometry, editorActive, draftCoordinates, onDraftChange, onSelect, onSelectZone, onSelectSector, onSelectVertex };

  useEffect(() => {
    if (!maplibregl || !center || mapRef.current || !containerRef.current) return undefined;
    const sources = { 'basemap-clear-source': { type: 'raster', tiles: [TILE_URL], tileSize: 256, attribution: 'Tiles © Esri, HERE, Garmin, USGS, Intermap, INCREMENT P, NRCan, Esri Japan, METI, Esri China, and the GIS User Community' } };
    const layers = [{ id: 'basemap-clear', type: 'raster', source: 'basemap-clear-source', layout: { visibility: valuesRef.current.basemap === 'clear' || !SATELLITE_TILE_URL ? 'visible' : 'none' } }];
    if (SATELLITE_TILE_URL) { sources['basemap-satellite-source'] = { type: 'raster', tiles: [SATELLITE_TILE_URL], tileSize: 256, attribution: 'Tiles © Esri, Maxar, Earthstar Geographics, and the GIS User Community' }; layers.push({ id: 'basemap-satellite', type: 'raster', source: 'basemap-satellite-source', layout: { visibility: valuesRef.current.basemap === 'satellite' ? 'visible' : 'none' } }); }
    const map = new maplibregl.Map({ container: containerRef.current, center: [center.longitude, center.latitude], zoom: 10.7, attributionControl: true, style: { version: 8, sources, layers } });
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 14 }); map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.on('load', () => {
      addOverlayLayers(map, valuesRef.current, center, selectedSectorId); setVisibility(map, valuesRef.current.mode, valuesRef.current.presentationLevel); containerRef.current.dataset.basemap = valuesRef.current.basemap;
      if (valuesRef.current.presentationLevel === 'households') renderPresentationMarkers(map, maplibregl, valuesRef.current.features, valuesRef.current.onSelect, presentationMarkersRef);
      const initialBounds = boundsForGeometry(valuesRef.current.focusGeometry); if (initialBounds) map.fitBounds(initialBounds, { padding: 80, duration: 0, maxZoom: 16 }); else fitFeatures(map, valuesRef.current.features, 0);
      map.on('mousedown', 'geo-sector-draft-vertices-layer', (event) => { if (!valuesRef.current.editorActive) return; event.preventDefault(); const index = Number(event.features?.[0]?.properties?.vertex_index); valuesRef.current.onSelectVertex?.(index); map.dragPan.disable(); const move = (moveEvent) => { const next = [...valuesRef.current.draftCoordinates]; next[index] = [moveEvent.lngLat.lng, moveEvent.lngLat.lat]; valuesRef.current.onDraftChange?.(next); }; const up = () => { map.off('mousemove', move); map.dragPan.enable(); }; map.on('mousemove', move); map.once('mouseup', up); });
      map.on('click', (event) => {
        const vertexHit = map.queryRenderedFeatures(event.point, { layers: ['geo-sector-draft-vertices-layer'] })[0];
        if (valuesRef.current.editorActive) { if (!vertexHit) valuesRef.current.onDraftChange?.([...valuesRef.current.draftCoordinates, [event.lngLat.lng, event.lngLat.lat]]); return; }
        const pin = map.queryRenderedFeatures(event.point, { layers: ['geo-church-anchor', 'geo-front-group-pins', 'geo-points'] })[0]; if (pin) { const id = pin.properties.entity_id; valuesRef.current.onSelect?.(valuesRef.current.features.find((item) => item.properties.entity_id === id) || pin); return; }
        const sector = map.queryRenderedFeatures(event.point, { layers: ['geo-sectors-fill'] })[0]; if (sector) { valuesRef.current.onSelectSector?.(sector.properties.sector_id); return; }
        const zone = map.queryRenderedFeatures(event.point, { layers: ['geo-zones-fill'] })[0]; if (zone) valuesRef.current.onSelectZone?.(zone.properties.zone);
      });
      map.on('mousemove', (event) => { const hit = map.queryRenderedFeatures(event.point, { layers: ['geo-sector-draft-vertices-layer', 'geo-church-anchor', 'geo-front-group-pins', 'geo-points', 'geo-sectors-fill', 'geo-zones-fill'] })[0]; if (!hit) { popup.remove(); map.getCanvas().style.cursor = valuesRef.current.editorActive ? 'crosshair' : ''; return; } map.getCanvas().style.cursor = hit.layer.id === 'geo-sector-draft-vertices-layer' ? 'grab' : 'pointer'; const element = document.createElement('div'); element.dataset.testid = 'geo-hover-popup'; element.className = 'px-1 py-0.5 text-xs font-semibold'; element.textContent = hit.properties.name || hit.properties.zone_label || `${hit.properties.resident_count || hit.properties.count || 1} personas`; popup.setLngLat(event.lngLat).setDOMContent(element).addTo(map); });
    });
    mapRef.current = map;
    return () => { presentationMarkersRef.current.forEach((marker) => marker.remove()); presentationMarkersRef.current = []; popup.remove(); map.remove(); mapRef.current = null; };
  }, [center, maplibregl, selectedSectorId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { const map = mapRef.current; if (!map?.isStyleLoaded()) return; const regular = features.filter((item) => item.properties?.entity_kind !== 'front_group'); const groups = features.filter((item) => item.properties?.entity_kind === 'front_group'); map.getSource('geo-raw')?.setData({ type: 'FeatureCollection', features: regular }); map.getSource('geo-front-groups')?.setData({ type: 'FeatureCollection', features: groups }); if (!focusTarget && !focusGeometry && !editorActive) fitFeatures(map, features, 700); if (presentationLevel === 'households') renderPresentationMarkers(map, maplibregl, features, onSelect, presentationMarkersRef); }, [editorActive, features, focusGeometry, focusTarget, maplibregl, onSelect, presentationLevel]);
  useEffect(() => { const map = mapRef.current; const source = map?.getSource('geo-sectors'); if (source) { registerImages(map, sectors); source.setData(sectorCollection(sectors)); } }, [sectors]);
  useEffect(() => { const map = mapRef.current; if (!map?.isStyleLoaded()) return; if (map.getLayer('geo-sectors-fill')) map.setPaintProperty('geo-sectors-fill', 'fill-opacity', ['case', ['==', ['get', 'sector_id'], selectedSectorId || ''], .2, .075]); if (map.getLayer('geo-sectors-line')) map.setPaintProperty('geo-sectors-line', 'line-width', ['case', ['==', ['get', 'sector_id'], selectedSectorId || ''], 3, 1.25]); }, [selectedSectorId]);
  useEffect(() => { const map = mapRef.current; if (!map?.isStyleLoaded()) return; const drafts = draftCollections(draftCoordinates); map.getSource('geo-sector-draft')?.setData(drafts.polygon); map.getSource('geo-sector-draft-vertices')?.setData(drafts.vertices); if (map.getLayer('geo-sector-draft-vertices-layer')) map.setPaintProperty('geo-sector-draft-vertices-layer', 'circle-color', ['case', ['==', ['get', 'vertex_index'], selectedVertex ?? -1], '#EF4444', '#F59E0B']); }, [draftCoordinates, selectedVertex]);
  useEffect(() => { const map = mapRef.current; if (!map?.isStyleLoaded()) return; setVisibility(map, mode, presentationLevel); if (presentationLevel === 'households') renderPresentationMarkers(map, maplibregl, features, onSelect, presentationMarkersRef); else { presentationMarkersRef.current.forEach((marker) => marker.remove()); presentationMarkersRef.current = []; } }, [features, maplibregl, mode, onSelect, presentationLevel]);
  useEffect(() => { const source = mapRef.current?.getSource('geo-zones'); if (source && zones) source.setData(zones); }, [zones]);
  useEffect(() => { const source = mapRef.current?.getSource('geo-subzones'); if (source && subzones) source.setData(subzones); }, [subzones]);
  useEffect(() => { const map = mapRef.current; if (!map?.getLayer('basemap-clear')) return; const satelliteLayer = map.getLayer('basemap-satellite'); const effectiveBasemap = basemap === 'satellite' && satelliteLayer ? 'satellite' : 'clear'; map.setLayoutProperty('basemap-clear', 'visibility', effectiveBasemap === 'clear' ? 'visible' : 'none'); if (satelliteLayer) map.setLayoutProperty('basemap-satellite', 'visibility', effectiveBasemap === 'satellite' ? 'visible' : 'none'); if (containerRef.current) { containerRef.current.dataset.basemap = effectiveBasemap; containerRef.current.dataset.satelliteAvailable = satelliteLayer ? 'true' : 'false'; containerRef.current.dataset.clearLayer = map.getLayoutProperty('basemap-clear', 'visibility'); containerRef.current.dataset.satelliteLayer = satelliteLayer ? map.getLayoutProperty('basemap-satellite', 'visibility') : 'unavailable'; } }, [basemap]);
  useEffect(() => { const map = mapRef.current; const source = map?.getSource('geo-search-highlight'); if (!source) return; if (!focusTarget) { source.setData(emptyCollection()); return; } const coordinates = [focusTarget.longitude, focusTarget.latitude]; source.setData({ type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates }, properties: { name: focusTarget.name } }] }); map.flyTo({ center: coordinates, zoom: 16, essential: true }); }, [focusTarget]);
  useEffect(() => { const map = mapRef.current; const bounds = boundsForGeometry(focusGeometry); if (!map || !bounds) return; if (bounds[0][0] === bounds[1][0] && bounds[0][1] === bounds[1][1]) map.flyTo({ center: bounds[0], zoom: 16, essential: true }); else map.fitBounds(bounds, { padding: 80, duration: 900, maxZoom: 16 }); }, [focusGeometry]);
  if (!maplibregl) return <div className="flex h-full min-h-0 items-center justify-center border bg-amber-50 p-6 text-center text-sm text-amber-900" data-testid="geo-map-library-error">No se pudo cargar la biblioteca cartográfica local.</div>;
  return <div ref={containerRef} className="h-full min-h-0 w-full overflow-hidden bg-slate-100" data-testid="geo-map-canvas" data-basemap={basemap} aria-label="Mapa geográfico interactivo" />;
};