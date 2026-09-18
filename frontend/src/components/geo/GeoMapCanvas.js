import React, { useEffect, useRef } from 'react';

const TILE_URL = process.env.REACT_APP_MAP_TILE_URL;
const zoneColors = { north: '#247BA0', east: '#2F8F6B', south: '#D97706', west: '#7C5C9E' };

const createPinImage = (kind, color, large = false) => {
  const width = large ? 96 : 76; const height = large ? 112 : 92;
  const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
  const context = canvas.getContext('2d'); const cx = width / 2; const radius = large ? 30 : 24; const cy = radius + 8;
  context.shadowColor = 'rgba(15,23,42,.32)'; context.shadowBlur = 8; context.shadowOffsetY = 4;
  context.beginPath(); context.arc(cx, cy, radius, Math.PI * 0.18, Math.PI * 0.82, true); context.lineTo(cx, height - 5); context.closePath();
  context.fillStyle = color; context.fill(); context.shadowColor = 'transparent'; context.lineWidth = large ? 5 : 4; context.strokeStyle = '#fff'; context.stroke();
  context.fillStyle = '#fff'; context.strokeStyle = '#fff'; context.lineWidth = 4; context.lineCap = 'round'; context.lineJoin = 'round';
  if (kind === 'person') {
    context.beginPath(); context.arc(cx, cy - 8, 7, 0, Math.PI * 2); context.fill();
    context.beginPath(); context.arc(cx, cy + 13, 14, Math.PI, Math.PI * 2); context.stroke();
  } else if (kind === 'cell') {
    context.beginPath(); context.moveTo(cx - 16, cy); context.lineTo(cx, cy - 14); context.lineTo(cx + 16, cy); context.stroke();
    context.strokeRect(cx - 12, cy, 24, 19); context.beginPath(); context.moveTo(cx, cy + 5); context.lineTo(cx, cy + 14); context.moveTo(cx - 5, cy + 9); context.lineTo(cx + 5, cy + 9); context.stroke();
  } else if (kind === 'front_group') {
    [[cx, cy - 10], [cx - 12, cy + 9], [cx + 12, cy + 9]].forEach(([x, y]) => { context.beginPath(); context.arc(x, y, 6, 0, Math.PI * 2); context.fill(); });
    context.beginPath(); context.moveTo(cx, cy - 4); context.lineTo(cx - 8, cy + 5); context.moveTo(cx, cy - 4); context.lineTo(cx + 8, cy + 5); context.moveTo(cx - 6, cy + 9); context.lineTo(cx + 6, cy + 9); context.stroke();
  } else {
    context.fillRect(cx - 15, cy - 2, 30, 23); context.beginPath(); context.moveTo(cx - 20, cy - 2); context.lineTo(cx, cy - 20); context.lineTo(cx + 20, cy - 2); context.stroke();
    context.beginPath(); context.moveTo(cx, cy - 30); context.lineTo(cx, cy - 15); context.moveTo(cx - 7, cy - 25); context.lineTo(cx + 7, cy - 25); context.stroke();
  }
  return context.getImageData(0, 0, width, height);
};

const createLabelImage = (text, color, compact = false) => {
  const canvas = document.createElement('canvas'); canvas.width = compact ? 92 : 240; canvas.height = compact ? 48 : 58;
  const context = canvas.getContext('2d'); context.fillStyle = 'rgba(255,255,255,.92)'; context.strokeStyle = color; context.lineWidth = 4;
  const radius = 12; context.beginPath(); context.roundRect(2, 2, canvas.width - 4, canvas.height - 4, radius); context.fill(); context.stroke();
  context.fillStyle = color; context.font = `700 ${compact ? 22 : 25}px sans-serif`; context.textAlign = 'center'; context.textBaseline = 'middle'; context.fillText(text, canvas.width / 2, canvas.height / 2 + 1);
  return context.getImageData(0, 0, canvas.width, canvas.height);
};

const registerImages = (map) => {
  const images = {
    'pin-person': createPinImage('person', '#B7791F'), 'pin-cell': createPinImage('cell', '#2F6B4F'),
    'pin-front-group': createPinImage('front_group', '#1B6B93'), 'pin-church': createPinImage('church', '#9F1239', true),
  };
  Object.entries(images).forEach(([id, image]) => { if (!map.hasImage(id)) map.addImage(id, image, { pixelRatio: 2 }); });
  [[1, 'Zona 1 · Norte', zoneColors.north], [2, 'Zona 2 · Este', zoneColors.east], [3, 'Zona 3 · Sur', zoneColors.south], [4, 'Zona 4 · Oeste', zoneColors.west]].forEach(([number, label, color]) => map.addImage(`zone-label-${number}`, createLabelImage(label, color), { pixelRatio: 2 }));
  [1, 2, 3, 4].forEach((number) => ['A', 'B', 'C'].forEach((letter) => map.addImage(`subzone-label-${number}-${letter.toLowerCase()}`, createLabelImage(`${number}-${letter}`, '#1B2A4A', true), { pixelRatio: 2 })));
};

const setVisibility = (map, mode) => {
  const visible = {
    'geo-heatmap': mode === 'heatmap', 'geo-clusters': mode === 'clusters', 'geo-cluster-count': mode === 'clusters',
    'geo-unclustered': mode === 'clusters', 'geo-pins': mode === 'pins',
  };
  Object.entries(visible).forEach(([id, show]) => { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', show ? 'visible' : 'none'); });
};

const emptyCollection = () => ({ type: 'FeatureCollection', features: [] });

export const GeoMapCanvas = ({ center, features = [], zones, subzones, mode, focusTarget, onSelect }) => {
  const maplibregl = typeof window !== 'undefined' ? window.maplibregl : null;
  const containerRef = useRef(null); const mapRef = useRef(null); const featuresRef = useRef(features);
  useEffect(() => { featuresRef.current = features; }, [features]);

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
      map.addSource('geo-zones', { type: 'geojson', data: zones || emptyCollection() });
      map.addLayer({ id: 'geo-zones-fill', type: 'fill', source: 'geo-zones', filter: ['==', ['get', 'feature_type'], 'zone'], paint: { 'fill-color': ['match', ['get', 'zone'], 'north', zoneColors.north, 'east', zoneColors.east, 'south', zoneColors.south, zoneColors.west], 'fill-opacity': 0.16 } });
      map.addLayer({ id: 'geo-zones-line', type: 'line', source: 'geo-zones', filter: ['==', ['get', 'feature_type'], 'zone'], paint: { 'line-color': ['match', ['get', 'zone'], 'north', zoneColors.north, 'east', zoneColors.east, 'south', zoneColors.south, zoneColors.west], 'line-opacity': 0.92, 'line-width': 3.5 } });
      map.addLayer({ id: 'geo-zone-labels', type: 'symbol', source: 'geo-zones', filter: ['==', ['get', 'feature_type'], 'zone_label'], layout: { 'icon-image': ['get', 'label_icon'], 'icon-allow-overlap': true } });
      map.addSource('geo-subzones', { type: 'geojson', data: subzones || emptyCollection() });
      map.addLayer({ id: 'geo-subzone-rings', type: 'line', source: 'geo-subzones', filter: ['==', ['get', 'feature_type'], 'subzone_ring'], paint: { 'line-color': '#1B2A4A', 'line-width': 2.25, 'line-dasharray': [2, 1.5], 'line-opacity': 0.8 } });
      map.addLayer({ id: 'geo-subzone-labels', type: 'symbol', source: 'geo-subzones', filter: ['==', ['get', 'feature_type'], 'subzone_label'], layout: { 'icon-image': ['get', 'label_icon'], 'icon-allow-overlap': true } });
      const regular = featuresRef.current.filter((item) => item.properties?.entity_kind !== 'front_group');
      const groups = featuresRef.current.filter((item) => item.properties?.entity_kind === 'front_group');
      map.addSource('geo-raw', { type: 'geojson', data: { type: 'FeatureCollection', features: regular } });
      map.addSource('geo-clustered', { type: 'geojson', data: { type: 'FeatureCollection', features: regular }, cluster: true, clusterMaxZoom: 14, clusterRadius: 46 });
      map.addSource('geo-front-groups', { type: 'geojson', data: { type: 'FeatureCollection', features: groups } });
      map.addSource('geo-anchor', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'Point', coordinates: [center.longitude, center.latitude] }, properties: { entity_kind: 'church', entity_id: 'church-anchor', name: 'Iglesia Ven y Ve', address: center.address } } });
      map.addSource('geo-search-highlight', { type: 'geojson', data: emptyCollection() });
      map.addLayer({ id: 'geo-heatmap', type: 'heatmap', source: 'geo-raw', filter: ['==', ['get', 'entity_kind'], 'person'], maxzoom: 16, paint: { 'heatmap-weight': ['interpolate', ['linear'], ['coalesce', ['get', 'count'], 1], 1, 0.2, 20, 1], 'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 8, 0.8, 14, 2], 'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], 0, 'rgba(27,107,147,0)', 0.25, '#87B9A4', 0.5, '#E8C35A', 0.75, '#D97706', 1, '#9F1239'], 'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 8, 18, 14, 38], 'heatmap-opacity': 0.82 } });
      map.addLayer({ id: 'geo-clusters', type: 'circle', source: 'geo-clustered', filter: ['has', 'point_count'], paint: { 'circle-color': '#1B2A4A', 'circle-radius': ['step', ['get', 'point_count'], 18, 20, 24, 75, 31], 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
      map.addLayer({ id: 'geo-cluster-count', type: 'symbol', source: 'geo-clustered', filter: ['has', 'point_count'], layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-size': 12 }, paint: { 'text-color': '#fff' } });
      const iconExpression = ['match', ['get', 'entity_kind'], 'cell', 'pin-cell', 'pin-person'];
      map.addLayer({ id: 'geo-unclustered', type: 'symbol', source: 'geo-clustered', filter: ['!', ['has', 'point_count']], layout: { 'icon-image': iconExpression, 'icon-anchor': 'bottom', 'icon-allow-overlap': true } });
      map.addLayer({ id: 'geo-pins', type: 'symbol', source: 'geo-raw', layout: { 'icon-image': iconExpression, 'icon-anchor': 'bottom', 'icon-allow-overlap': true } });
      map.addLayer({ id: 'geo-front-group-pins', type: 'symbol', source: 'geo-front-groups', layout: { 'icon-image': 'pin-front-group', 'icon-anchor': 'bottom', 'icon-allow-overlap': true } });
      map.addLayer({ id: 'geo-church-anchor', type: 'symbol', source: 'geo-anchor', layout: { 'icon-image': 'pin-church', 'icon-anchor': 'bottom', 'icon-allow-overlap': true } });
      map.addLayer({ id: 'geo-search-halo', type: 'circle', source: 'geo-search-highlight', paint: { 'circle-radius': 20, 'circle-color': 'rgba(255,255,255,0)', 'circle-stroke-color': '#E11D48', 'circle-stroke-width': 5, 'circle-opacity': 0.95 } });
      setVisibility(map, mode);
      map.on('click', 'geo-clusters', async (event) => { const feature = map.queryRenderedFeatures(event.point, { layers: ['geo-clusters'] })[0]; const zoom = await map.getSource('geo-clustered').getClusterExpansionZoom(feature.properties.cluster_id); map.easeTo({ center: feature.geometry.coordinates, zoom }); });
      map.on('click', (event) => {
        const hit = map.queryRenderedFeatures(event.point, { layers: ['geo-church-anchor', 'geo-front-group-pins', 'geo-unclustered', 'geo-pins'] })[0];
        if (!hit) return; const id = hit.properties.entity_id; const selected = featuresRef.current.find((item) => item.properties.entity_id === id) || hit; onSelect?.(selected);
      });
      map.on('mousemove', (event) => {
        const hit = map.queryRenderedFeatures(event.point, { layers: ['geo-church-anchor', 'geo-front-group-pins', 'geo-clusters', 'geo-unclustered', 'geo-pins'] })[0];
        if (!hit) { popup.remove(); map.getCanvas().style.cursor = ''; return; }
        map.getCanvas().style.cursor = 'pointer'; const element = document.createElement('div'); element.dataset.testid = 'geo-hover-popup'; element.className = 'px-1 py-0.5 text-xs font-semibold';
        element.textContent = hit.properties.point_count ? `${hit.properties.point_count} ubicaciones` : hit.properties.name || `${hit.properties.count || 1} ubicaciones`; popup.setLngLat(event.lngLat).setDOMContent(element).addTo(map);
      });
      map.getCanvas().addEventListener('mouseleave', () => { map.getCanvas().style.cursor = ''; popup.remove(); });
    });
    mapRef.current = map;
    return () => { popup.remove(); map.remove(); mapRef.current = null; };
  }, [center, maplibregl]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const map = mapRef.current; if (!map?.isStyleLoaded()) return;
    const regular = features.filter((item) => item.properties?.entity_kind !== 'front_group');
    const groups = features.filter((item) => item.properties?.entity_kind === 'front_group');
    const data = { type: 'FeatureCollection', features: regular };
    map.getSource('geo-raw')?.setData(data); map.getSource('geo-clustered')?.setData(data); map.getSource('geo-front-groups')?.setData({ type: 'FeatureCollection', features: groups });
  }, [features]);
  useEffect(() => { const map = mapRef.current; if (map?.isStyleLoaded()) setVisibility(map, mode); }, [mode]);
  useEffect(() => { const source = mapRef.current?.getSource('geo-zones'); if (source && zones) source.setData(zones); }, [zones]);
  useEffect(() => { const source = mapRef.current?.getSource('geo-subzones'); if (source && subzones) source.setData(subzones); }, [subzones]);
  useEffect(() => {
    const map = mapRef.current; const source = map?.getSource('geo-search-highlight'); if (!source) return;
    if (!focusTarget) { source.setData(emptyCollection()); return; }
    const coordinates = [focusTarget.longitude, focusTarget.latitude];
    source.setData({ type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates }, properties: { name: focusTarget.name } }] });
    map.flyTo({ center: coordinates, zoom: 15.5, essential: true });
  }, [focusTarget]);
  if (!maplibregl) return <div className="flex h-full min-h-0 items-center justify-center border bg-amber-50 p-6 text-center text-sm text-amber-900" data-testid="geo-map-library-error">No se pudo cargar la biblioteca cartográfica local.</div>;
  return <div ref={containerRef} className="h-full min-h-0 w-full overflow-hidden bg-slate-100" data-testid="geo-map-canvas" aria-label="Mapa geográfico interactivo" />;
};