import React, { useEffect, useRef } from 'react';

const TILE_URL = process.env.REACT_APP_MAP_TILE_URL;
const zoneColors = { north: '#247BA0', east: '#2F8F6B', south: '#D97706', west: '#C0266D' };
const emptyCollection = () => ({ type: 'FeatureCollection', features: [] });

const createPinImage = (kind, color, large = false) => {
  const width = large ? 96 : 82; const height = large ? 112 : 96;
  const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
  const context = canvas.getContext('2d'); const cx = width / 2; const radius = large ? 30 : 25; const cy = radius + 8;
  context.shadowColor = 'rgba(15,23,42,.38)'; context.shadowBlur = 9; context.shadowOffsetY = 4;
  context.beginPath(); context.arc(cx, cy, radius, Math.PI * 0.18, Math.PI * 0.82, true); context.lineTo(cx, height - 5); context.closePath();
  context.fillStyle = color; context.fill(); context.shadowColor = 'transparent'; context.lineWidth = large ? 5 : 4; context.strokeStyle = '#fff'; context.stroke();
  context.fillStyle = '#fff'; context.strokeStyle = '#fff'; context.lineWidth = 4; context.lineCap = 'round'; context.lineJoin = 'round';
  if (kind === 'household') {
    context.beginPath(); context.moveTo(cx - 15, cy + 2); context.lineTo(cx, cy - 12); context.lineTo(cx + 15, cy + 2); context.stroke();
    context.strokeRect(cx - 11, cy + 2, 22, 17);
  } else if (kind === 'cell') {
    context.beginPath(); context.moveTo(cx - 16, cy); context.lineTo(cx, cy - 14); context.lineTo(cx + 16, cy); context.stroke();
    context.strokeRect(cx - 12, cy, 24, 19); context.beginPath(); context.moveTo(cx, cy + 5); context.lineTo(cx, cy + 14); context.moveTo(cx - 5, cy + 9); context.lineTo(cx + 5, cy + 9); context.stroke();
  } else if (kind === 'front_group') {
    [[cx, cy - 10], [cx - 12, cy + 9], [cx + 12, cy + 9]].forEach(([x, y]) => { context.beginPath(); context.arc(x, y, 6, 0, Math.PI * 2); context.fill(); });
  } else {
    context.fillRect(cx - 15, cy - 2, 30, 23); context.beginPath(); context.moveTo(cx - 20, cy - 2); context.lineTo(cx, cy - 20); context.lineTo(cx + 20, cy - 2); context.stroke();
    context.beginPath(); context.moveTo(cx, cy - 30); context.lineTo(cx, cy - 15); context.moveTo(cx - 7, cy - 25); context.lineTo(cx + 7, cy - 25); context.stroke();
  }
  return context.getImageData(0, 0, width, height);
};

const createLabelImage = (text, color, compact = false) => {
  const canvas = document.createElement('canvas'); canvas.width = compact ? 92 : 240; canvas.height = compact ? 48 : 58;
  const context = canvas.getContext('2d'); context.fillStyle = 'rgba(255,255,255,.94)'; context.strokeStyle = color; context.lineWidth = 4;
  context.beginPath(); context.roundRect(2, 2, canvas.width - 4, canvas.height - 4, 10); context.fill(); context.stroke();
  context.fillStyle = color; context.font = `700 ${compact ? 22 : 25}px sans-serif`; context.textAlign = 'center'; context.textBaseline = 'middle'; context.fillText(text, canvas.width / 2, canvas.height / 2 + 1);
  return context.getImageData(0, 0, canvas.width, canvas.height);
};

const imageKey = (value) => String(value || '').replace(/[^a-z0-9-]+/gi, '-').toLowerCase();
const createCountImage = (text) => {
  const canvas = document.createElement('canvas'); canvas.width = 64; canvas.height = 64;
  const context = canvas.getContext('2d'); context.fillStyle = '#FFFFFF'; context.strokeStyle = 'rgba(15,23,42,.7)'; context.lineWidth = 5;
  context.font = '800 28px sans-serif'; context.textAlign = 'center'; context.textBaseline = 'middle'; context.strokeText(text, 32, 33); context.fillText(text, 32, 33);
  return context.getImageData(0, 0, 64, 64);
};

const registerSectorImages = (map, sectors) => {
  (sectors || []).forEach((sector) => {
    const id = `sector-label-${imageKey(sector.sector_id)}`;
    if (!map.hasImage(id)) map.addImage(id, createLabelImage(sector.name || 'Sector', sector.color || '#1B2A4A', true), { pixelRatio: 2 });
  });
};

const registerImages = (map) => {
  const images = {
    'pin-household': createPinImage('household', '#B7791F'), 'pin-cell': createPinImage('cell', '#2F6B4F'),
    'pin-front-group': createPinImage('front_group', '#1B6B93'), 'pin-church': createPinImage('church', '#9F1239', true),
    'pin-ev-detected': createPinImage('household', '#7C3AED'), 'pin-ev-assigned': createPinImage('household', '#2563EB'),
    'pin-ev-visited': createPinImage('household', '#0F766E'), 'pin-ev-follow-up': createPinImage('household', '#D97706'),
    'pin-ev-connected': createPinImage('household', '#059669'), 'pin-ev-do-not-visit': createPinImage('household', '#64748B'),
  };
  Object.entries(images).forEach(([id, image]) => { if (!map.hasImage(id)) map.addImage(id, image, { pixelRatio: 2 }); });
  [[1, 'Zona 1 · Norte', zoneColors.north], [2, 'Zona 2 · Este', zoneColors.east], [3, 'Zona 3 · Sur', zoneColors.south], [4, 'Zona 4 · Oeste', zoneColors.west]].forEach(([number, label, color]) => map.addImage(`zone-label-${number}`, createLabelImage(label, color), { pixelRatio: 2 }));
  [1, 2, 3, 4].forEach((number) => ['A', 'B', 'C'].forEach((letter) => map.addImage(`subzone-label-${number}-${letter.toLowerCase()}`, createLabelImage(`${number}-${letter}`, '#1B2A4A', true), { pixelRatio: 2 })));
  for (let count = 1; count <= 99; count += 1) map.addImage(`count-${count}`, createCountImage(String(count)), { pixelRatio: 2 });
  map.addImage('count-99-plus', createCountImage('99+'), { pixelRatio: 2 });
};

const sectorCollection = (sectors) => ({
  type: 'FeatureCollection',
  features: (sectors || []).map((sector) => ({ type: 'Feature', geometry: sector.geometry, properties: { ...sector, label_icon: `sector-label-${imageKey(sector.sector_id)}`, geometry: undefined, stats: JSON.stringify(sector.stats || {}) } })),
});

const draftCollections = (coordinates) => {
  const vertices = (coordinates || []).map((coordinate, index) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: coordinate }, properties: { vertex_index: index } }));
  const polygon = coordinates?.length >= 3 ? [{ type: 'Feature', geometry: { type: 'Polygon', coordinates: [[...coordinates, coordinates[0]]] }, properties: {} }] : [];
  return { polygon: { type: 'FeatureCollection', features: polygon }, vertices: { type: 'FeatureCollection', features: vertices } };
};

const setVisibility = (map, mode, presentationLevel) => {
  const presenting = Boolean(presentationLevel);
  const visible = {
    'geo-heatmap': !presenting && mode === 'heatmap', 'geo-clusters': !presenting && mode === 'clusters',
    'geo-cluster-count': !presenting && mode === 'clusters', 'geo-unclustered': !presenting && mode === 'clusters',
    'geo-pins': !presenting && mode === 'pins', 'geo-household-counts': !presenting && mode === 'pins',
    'geo-front-group-pins': !presenting,
  };
  Object.entries(visible).forEach(([id, show]) => { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', show ? 'visible' : 'none'); });
};

const renderPresentationMarkers = (map, maplibregl, features, onSelect, markerRef) => {
  markerRef.current.forEach((marker) => marker.remove()); markerRef.current = [];
  (features || []).filter((item) => item.properties?.entity_kind === 'household').forEach((feature) => {
    const button = document.createElement('button'); const count = feature.properties.resident_count || 1;
    button.type = 'button'; button.dataset.testid = `geo-household-pin-${String(feature.properties.entity_id).replace(/[^a-z0-9-]+/gi, '-')}`;
    button.setAttribute('aria-label', `Hogar con ${count} personas`); button.className = 'relative flex h-16 w-14 items-center justify-center rounded-t-full rounded-bl-full border-4 border-white bg-amber-600 text-white shadow-2xl transition-transform hover:-translate-y-1';
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

export const GeoMapCanvas = ({
  center, features = [], zones, subzones, sectors = [], mode, focusTarget, focusGeometry,
  onSelect, onSelectZone, onSelectSector, editorActive = false, draftCoordinates = [],
  onDraftChange, selectedVertex, onSelectVertex, selectedSectorId, presentationLevel,
}) => {
  const maplibregl = typeof window !== 'undefined' ? window.maplibregl : null;
  const containerRef = useRef(null); const mapRef = useRef(null); const valuesRef = useRef({}); const presentationMarkersRef = useRef([]);
  valuesRef.current = { features, sectors, mode, presentationLevel, focusGeometry, editorActive, draftCoordinates, onDraftChange, onSelect, onSelectZone, onSelectSector, onSelectVertex };

  useEffect(() => {
    if (!maplibregl || !center || mapRef.current || !containerRef.current) return undefined;
    const map = new maplibregl.Map({
      container: containerRef.current, center: [center.longitude, center.latitude], zoom: 10.7,
      style: { version: 8, sources: { osm: { type: 'raster', tiles: [TILE_URL], tileSize: 256, attribution: '© OpenStreetMap contributors' } }, layers: [{ id: 'osm', type: 'raster', source: 'osm' }] }, attributionControl: true,
    });
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 18 });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.on('load', () => {
      registerImages(map);
      registerSectorImages(map, valuesRef.current.sectors);
      map.addSource('geo-zones', { type: 'geojson', data: zones || emptyCollection() });
      map.addLayer({ id: 'geo-zones-fill', type: 'fill', source: 'geo-zones', filter: ['==', ['get', 'feature_type'], 'zone'], paint: { 'fill-color': ['match', ['get', 'zone'], 'north', zoneColors.north, 'east', zoneColors.east, 'south', zoneColors.south, zoneColors.west], 'fill-opacity': 0.13 } });
      map.addLayer({ id: 'geo-zones-line', type: 'line', source: 'geo-zones', filter: ['==', ['get', 'feature_type'], 'zone'], paint: { 'line-color': ['match', ['get', 'zone'], 'north', zoneColors.north, 'east', zoneColors.east, 'south', zoneColors.south, zoneColors.west], 'line-opacity': 0.92, 'line-width': 3.5 } });
      map.addLayer({ id: 'geo-zone-labels', type: 'symbol', source: 'geo-zones', filter: ['==', ['get', 'feature_type'], 'zone_label'], layout: { 'icon-image': ['get', 'label_icon'], 'icon-allow-overlap': true } });
      map.addSource('geo-subzones', { type: 'geojson', data: subzones || emptyCollection() });
      map.addLayer({ id: 'geo-subzone-rings', type: 'line', source: 'geo-subzones', filter: ['==', ['get', 'feature_type'], 'subzone_ring'], paint: { 'line-color': '#1B2A4A', 'line-width': 2.25, 'line-dasharray': [2, 1.5], 'line-opacity': 0.72 } });
      map.addLayer({ id: 'geo-subzone-labels', type: 'symbol', source: 'geo-subzones', filter: ['==', ['get', 'feature_type'], 'subzone_label'], layout: { 'icon-image': ['get', 'label_icon'], 'icon-allow-overlap': true } });
      map.addSource('geo-sectors', { type: 'geojson', data: sectorCollection(valuesRef.current.sectors) });
      map.addLayer({ id: 'geo-sectors-fill', type: 'fill', source: 'geo-sectors', paint: { 'fill-color': ['get', 'color'], 'fill-opacity': ['case', ['==', ['get', 'sector_id'], selectedSectorId || ''], 0.48, 0.22] } });
      map.addLayer({ id: 'geo-sectors-line', type: 'line', source: 'geo-sectors', paint: { 'line-color': ['get', 'color'], 'line-width': ['case', ['==', ['get', 'sector_id'], selectedSectorId || ''], 5, 3], 'line-opacity': 0.96 } });
      map.addLayer({ id: 'geo-sector-labels', type: 'symbol', source: 'geo-sectors', layout: { 'icon-image': ['get', 'label_icon'], 'icon-allow-overlap': false } });
      const regular = valuesRef.current.features.filter((item) => item.properties?.entity_kind !== 'front_group');
      const groups = valuesRef.current.features.filter((item) => item.properties?.entity_kind === 'front_group');
      map.addSource('geo-raw', { type: 'geojson', data: { type: 'FeatureCollection', features: regular } });
      map.addSource('geo-clustered', { type: 'geojson', data: { type: 'FeatureCollection', features: regular }, cluster: true, clusterMaxZoom: 14, clusterRadius: 46 });
      map.addSource('geo-front-groups', { type: 'geojson', data: { type: 'FeatureCollection', features: groups } });
      map.addSource('geo-anchor', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'Point', coordinates: [center.longitude, center.latitude] }, properties: { entity_kind: 'church', entity_id: 'church-anchor', name: 'Iglesia Ven y Ve', address: center.address } } });
      map.addSource('geo-search-highlight', { type: 'geojson', data: emptyCollection() });
      map.addSource('geo-sector-draft', { type: 'geojson', data: emptyCollection() });
      map.addSource('geo-sector-draft-vertices', { type: 'geojson', data: emptyCollection() });
      map.addLayer({ id: 'geo-heatmap', type: 'heatmap', source: 'geo-raw', maxzoom: 16, paint: { 'heatmap-weight': ['interpolate', ['linear'], ['coalesce', ['get', 'resident_count'], ['get', 'count'], 1], 1, 0.2, 20, 1], 'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 8, 0.8, 14, 2], 'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], 0, 'rgba(27,107,147,0)', 0.25, '#87B9A4', 0.5, '#E8C35A', 0.75, '#D97706', 1, '#9F1239'], 'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 8, 18, 14, 38], 'heatmap-opacity': 0.82 } });
      map.addLayer({ id: 'geo-clusters', type: 'circle', source: 'geo-clustered', filter: ['has', 'point_count'], paint: { 'circle-color': '#1B2A4A', 'circle-radius': ['step', ['get', 'point_count'], 18, 20, 24, 75, 31], 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
      const countIcon = (property) => ['case', ['>', ['get', property], 99], 'count-99-plus', ['concat', 'count-', ['to-string', ['get', property]]]];
      map.addLayer({ id: 'geo-cluster-count', type: 'symbol', source: 'geo-clustered', filter: ['has', 'point_count'], layout: { 'icon-image': countIcon('point_count'), 'icon-size': 0.5, 'icon-allow-overlap': true } });
      const evangelismIcon = ['match', ['get', 'status'], 'assigned', 'pin-ev-assigned', 'visited', 'pin-ev-visited', 'follow_up', 'pin-ev-follow-up', 'connected', 'pin-ev-connected', 'do_not_visit', 'pin-ev-do-not-visit', 'pin-ev-detected'];
      const iconExpression = ['match', ['get', 'entity_kind'], 'cell', 'pin-cell', 'evangelism_target', evangelismIcon, 'pin-household'];
      map.addLayer({ id: 'geo-unclustered', type: 'symbol', source: 'geo-clustered', filter: ['!', ['has', 'point_count']], layout: { 'icon-image': iconExpression, 'icon-anchor': 'bottom', 'icon-allow-overlap': true } });
      map.addLayer({ id: 'geo-pins', type: 'symbol', source: 'geo-raw', layout: { 'icon-image': iconExpression, 'icon-anchor': 'bottom', 'icon-allow-overlap': true } });
      map.addLayer({ id: 'geo-household-counts', type: 'symbol', source: 'geo-raw', filter: ['==', ['get', 'entity_kind'], 'household'], layout: { 'icon-image': countIcon('resident_count'), 'icon-size': 0.45, 'icon-offset': [0, -52], 'icon-allow-overlap': true } });
      map.addLayer({ id: 'geo-front-group-pins', type: 'symbol', source: 'geo-front-groups', layout: { 'icon-image': 'pin-front-group', 'icon-anchor': 'bottom', 'icon-allow-overlap': true } });
      map.addLayer({ id: 'geo-church-anchor', type: 'symbol', source: 'geo-anchor', layout: { 'icon-image': 'pin-church', 'icon-anchor': 'bottom', 'icon-allow-overlap': true } });
      map.addLayer({ id: 'geo-search-halo', type: 'circle', source: 'geo-search-highlight', paint: { 'circle-radius': 24, 'circle-color': 'rgba(255,255,255,0)', 'circle-stroke-color': '#E11D48', 'circle-stroke-width': 5 } });
      map.addLayer({ id: 'geo-sector-draft-fill', type: 'fill', source: 'geo-sector-draft', paint: { 'fill-color': '#06B6D4', 'fill-opacity': 0.28 } });
      map.addLayer({ id: 'geo-sector-draft-line', type: 'line', source: 'geo-sector-draft', paint: { 'line-color': '#0891B2', 'line-width': 4, 'line-dasharray': [2, 1] } });
      map.addLayer({ id: 'geo-sector-draft-vertices-layer', type: 'circle', source: 'geo-sector-draft-vertices', paint: { 'circle-radius': 7, 'circle-color': '#F59E0B', 'circle-stroke-color': '#0B0F17', 'circle-stroke-width': 2 } });
      setVisibility(map, valuesRef.current.mode, valuesRef.current.presentationLevel);
      if (valuesRef.current.presentationLevel === 'households') renderPresentationMarkers(map, maplibregl, valuesRef.current.features, valuesRef.current.onSelect, presentationMarkersRef);
      const initialBounds = boundsForGeometry(valuesRef.current.focusGeometry);
      if (initialBounds) map.fitBounds(initialBounds, { padding: 80, duration: 0, maxZoom: 16 });
      map.on('click', 'geo-clusters', async (event) => { const feature = event.features?.[0]; if (!feature) return; const zoom = await map.getSource('geo-clustered').getClusterExpansionZoom(feature.properties.cluster_id); map.easeTo({ center: feature.geometry.coordinates, zoom }); });
      map.on('mousedown', 'geo-sector-draft-vertices-layer', (event) => {
        if (!valuesRef.current.editorActive) return; event.preventDefault(); const index = Number(event.features?.[0]?.properties?.vertex_index); valuesRef.current.onSelectVertex?.(index); map.dragPan.disable();
        const move = (moveEvent) => { const next = [...valuesRef.current.draftCoordinates]; next[index] = [moveEvent.lngLat.lng, moveEvent.lngLat.lat]; valuesRef.current.onDraftChange?.(next); };
        const up = () => { map.off('mousemove', move); map.dragPan.enable(); };
        map.on('mousemove', move); map.once('mouseup', up);
      });
      map.on('click', (event) => {
        const vertexHit = map.queryRenderedFeatures(event.point, { layers: ['geo-sector-draft-vertices-layer'] })[0];
        if (valuesRef.current.editorActive) {
          if (!vertexHit) valuesRef.current.onDraftChange?.([...valuesRef.current.draftCoordinates, [event.lngLat.lng, event.lngLat.lat]]);
          return;
        }
        const pin = map.queryRenderedFeatures(event.point, { layers: ['geo-church-anchor', 'geo-front-group-pins', 'geo-unclustered', 'geo-pins'] })[0];
        if (pin) { const id = pin.properties.entity_id; valuesRef.current.onSelect?.(valuesRef.current.features.find((item) => item.properties.entity_id === id) || pin); return; }
        const sector = map.queryRenderedFeatures(event.point, { layers: ['geo-sectors-fill'] })[0];
        if (sector) { valuesRef.current.onSelectSector?.(sector.properties.sector_id); return; }
        const zone = map.queryRenderedFeatures(event.point, { layers: ['geo-zones-fill'] })[0];
        if (zone) valuesRef.current.onSelectZone?.(zone.properties.zone);
      });
      map.on('mousemove', (event) => {
        const hit = map.queryRenderedFeatures(event.point, { layers: ['geo-sector-draft-vertices-layer', 'geo-church-anchor', 'geo-front-group-pins', 'geo-clusters', 'geo-unclustered', 'geo-pins', 'geo-sectors-fill', 'geo-zones-fill'] })[0];
        if (!hit) { popup.remove(); map.getCanvas().style.cursor = valuesRef.current.editorActive ? 'crosshair' : ''; return; }
        map.getCanvas().style.cursor = hit.layer.id === 'geo-sector-draft-vertices-layer' ? 'grab' : 'pointer';
        const element = document.createElement('div'); element.dataset.testid = 'geo-hover-popup'; element.className = 'px-1 py-0.5 text-xs font-semibold';
        element.textContent = hit.properties.name || hit.properties.zone_label || (hit.properties.point_count ? `${hit.properties.point_count} ubicaciones` : `${hit.properties.resident_count || hit.properties.count || 1} personas`); popup.setLngLat(event.lngLat).setDOMContent(element).addTo(map);
      });
    });
    mapRef.current = map;
    return () => { presentationMarkersRef.current.forEach((marker) => marker.remove()); presentationMarkersRef.current = []; popup.remove(); map.remove(); mapRef.current = null; };
  }, [center, maplibregl]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const map = mapRef.current; if (!map?.isStyleLoaded()) return;
    const regular = features.filter((item) => item.properties?.entity_kind !== 'front_group');
    const groups = features.filter((item) => item.properties?.entity_kind === 'front_group');
    const data = { type: 'FeatureCollection', features: regular };
    map.getSource('geo-raw')?.setData(data); map.getSource('geo-clustered')?.setData(data); map.getSource('geo-front-groups')?.setData({ type: 'FeatureCollection', features: groups });
    if (presentationLevel === 'households') renderPresentationMarkers(map, maplibregl, features, onSelect, presentationMarkersRef);
  }, [features, maplibregl, onSelect, presentationLevel]);
  useEffect(() => { const map = mapRef.current; const source = map?.getSource('geo-sectors'); if (source) { registerSectorImages(map, sectors); source.setData(sectorCollection(sectors)); } }, [sectors]);
  useEffect(() => {
    const map = mapRef.current; if (!map?.isStyleLoaded()) return;
    if (map.getLayer('geo-sectors-fill')) map.setPaintProperty('geo-sectors-fill', 'fill-opacity', ['case', ['==', ['get', 'sector_id'], selectedSectorId || ''], 0.48, 0.22]);
    if (map.getLayer('geo-sectors-line')) map.setPaintProperty('geo-sectors-line', 'line-width', ['case', ['==', ['get', 'sector_id'], selectedSectorId || ''], 5, 3]);
  }, [selectedSectorId]);
  useEffect(() => {
    const map = mapRef.current; if (!map?.isStyleLoaded()) return; const drafts = draftCollections(draftCoordinates);
    map.getSource('geo-sector-draft')?.setData(drafts.polygon); map.getSource('geo-sector-draft-vertices')?.setData(drafts.vertices);
    if (map.getLayer('geo-sector-draft-vertices-layer')) map.setPaintProperty('geo-sector-draft-vertices-layer', 'circle-color', ['case', ['==', ['get', 'vertex_index'], selectedVertex ?? -1], '#EF4444', '#F59E0B']);
  }, [draftCoordinates, selectedVertex]);
  useEffect(() => {
    const map = mapRef.current; if (!map?.isStyleLoaded()) return; setVisibility(map, mode, presentationLevel);
    if (presentationLevel === 'households') renderPresentationMarkers(map, maplibregl, features, onSelect, presentationMarkersRef);
    else { presentationMarkersRef.current.forEach((marker) => marker.remove()); presentationMarkersRef.current = []; }
  }, [features, maplibregl, mode, onSelect, presentationLevel]);
  useEffect(() => { const source = mapRef.current?.getSource('geo-zones'); if (source && zones) source.setData(zones); }, [zones]);
  useEffect(() => { const source = mapRef.current?.getSource('geo-subzones'); if (source && subzones) source.setData(subzones); }, [subzones]);
  useEffect(() => {
    const map = mapRef.current; const source = map?.getSource('geo-search-highlight'); if (!source) return;
    if (!focusTarget) { source.setData(emptyCollection()); return; }
    const coordinates = [focusTarget.longitude, focusTarget.latitude]; source.setData({ type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates }, properties: { name: focusTarget.name } }] });
    map.flyTo({ center: coordinates, zoom: 16, essential: true });
  }, [focusTarget]);
  useEffect(() => {
    const map = mapRef.current; const bounds = boundsForGeometry(focusGeometry); if (!map || !bounds) return;
    if (bounds[0][0] === bounds[1][0] && bounds[0][1] === bounds[1][1]) map.flyTo({ center: bounds[0], zoom: 16, essential: true });
    else map.fitBounds(bounds, { padding: 80, duration: 900, maxZoom: 16 });
  }, [focusGeometry]);
  if (!maplibregl) return <div className="flex h-full min-h-0 items-center justify-center border bg-amber-50 p-6 text-center text-sm text-amber-900" data-testid="geo-map-library-error">No se pudo cargar la biblioteca cartográfica local.</div>;
  return <div ref={containerRef} className="h-full min-h-0 w-full overflow-hidden bg-slate-100" data-testid="geo-map-canvas" aria-label="Mapa geográfico interactivo" />;
};