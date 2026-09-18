import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

const TILE_URL = process.env.REACT_APP_MAP_TILE_URL;

const visibility = (map, mode) => {
  ['geo-heatmap', 'geo-clusters', 'geo-cluster-count', 'geo-unclustered', 'geo-pins'].forEach((id) => {
    if (!map.getLayer(id)) return;
    const visible = mode === 'heatmap' ? id === 'geo-heatmap' : mode === 'pins' ? id === 'geo-pins' : id !== 'geo-heatmap' && id !== 'geo-pins';
    map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none');
  });
};

export const GeoMapCanvas = ({ center, features = [], zones, mode, onSelect }) => {
  const containerRef = useRef(null); const mapRef = useRef(null); const featuresRef = useRef(features);
  useEffect(() => { featuresRef.current = features; }, [features]);
  useEffect(() => {
    if (!center || mapRef.current || !containerRef.current) return undefined;
    const map = new maplibregl.Map({
      container: containerRef.current, center: [center.longitude, center.latitude], zoom: 10.7,
      style: { version: 8, sources: { osm: { type: 'raster', tiles: [TILE_URL], tileSize: 256, attribution: '© OpenStreetMap contributors' } }, layers: [{ id: 'osm', type: 'raster', source: 'osm' }] },
      attributionControl: true,
    });
    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.on('load', () => {
      map.addSource('geo-zones', { type: 'geojson', data: zones || { type: 'FeatureCollection', features: [] } });
      map.addLayer({ id: 'geo-zones-fill', type: 'fill', source: 'geo-zones', paint: { 'fill-color': ['match', ['get', 'zone'], 'north', '#1B6B93', 'east', '#3C8D40', 'south', '#D97706', '#B5953F'], 'fill-opacity': 0.08 } });
      map.addLayer({ id: 'geo-zones-line', type: 'line', source: 'geo-zones', paint: { 'line-color': '#1B2A4A', 'line-opacity': 0.35, 'line-width': 1.5 } });
      const data = { type: 'FeatureCollection', features: featuresRef.current };
      map.addSource('geo-raw', { type: 'geojson', data });
      map.addSource('geo-clustered', { type: 'geojson', data, cluster: true, clusterMaxZoom: 14, clusterRadius: 46 });
      map.addLayer({ id: 'geo-heatmap', type: 'heatmap', source: 'geo-raw', maxzoom: 16, paint: { 'heatmap-weight': ['interpolate', ['linear'], ['coalesce', ['get', 'count'], 1], 1, 0.2, 20, 1], 'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 8, 0.8, 14, 2], 'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], 0, 'rgba(27,107,147,0)', 0.25, '#87B9A4', 0.5, '#E8C35A', 0.75, '#D97706', 1, '#9F1239'], 'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 8, 18, 14, 38], 'heatmap-opacity': 0.8 } });
      map.addLayer({ id: 'geo-clusters', type: 'circle', source: 'geo-clustered', filter: ['has', 'point_count'], paint: { 'circle-color': '#1B2A4A', 'circle-radius': ['step', ['get', 'point_count'], 18, 20, 24, 75, 31], 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
      map.addLayer({ id: 'geo-cluster-count', type: 'symbol', source: 'geo-clustered', filter: ['has', 'point_count'], layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-size': 12 }, paint: { 'text-color': '#fff' } });
      const pointColor = ['match', ['get', 'entity_kind'], 'cell', '#2F6B4F', '#C49A2C'];
      map.addLayer({ id: 'geo-unclustered', type: 'circle', source: 'geo-clustered', filter: ['!', ['has', 'point_count']], paint: { 'circle-color': pointColor, 'circle-radius': 7, 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
      map.addLayer({ id: 'geo-pins', type: 'circle', source: 'geo-raw', paint: { 'circle-color': pointColor, 'circle-radius': ['interpolate', ['linear'], ['coalesce', ['get', 'count'], 1], 1, 6, 20, 14], 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
      visibility(map, mode);
      map.on('click', 'geo-clusters', async (event) => {
        const feature = map.queryRenderedFeatures(event.point, { layers: ['geo-clusters'] })[0];
        const zoom = await map.getSource('geo-clustered').getClusterExpansionZoom(feature.properties.cluster_id);
        map.easeTo({ center: feature.geometry.coordinates, zoom });
      });
      map.on('click', (event) => {
        const hit = map.queryRenderedFeatures(event.point, { layers: ['geo-unclustered', 'geo-pins'] })[0];
        if (!hit) return;
        const id = hit.properties.entity_id;
        const selected = featuresRef.current.find((item) => item.properties.entity_id === id) || hit;
        onSelect?.(selected);
      });
      map.on('mouseenter', ['geo-clusters', 'geo-unclustered', 'geo-pins'], () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mousemove', (event) => {
        const hit = map.queryRenderedFeatures(event.point, { layers: ['geo-clusters', 'geo-unclustered', 'geo-pins'] })[0];
        if (!hit) { popup.remove(); return; }
        const element = document.createElement('div'); element.dataset.testid = 'geo-hover-popup'; element.className = 'px-1 py-0.5 text-xs font-semibold';
        element.textContent = hit.properties.point_count ? `${hit.properties.point_count} ubicaciones` : hit.properties.name || `${hit.properties.count || 1} ubicaciones · Zona ${hit.properties.zone || 'pendiente'}`;
        popup.setLngLat(event.lngLat).setDOMContent(element).addTo(map);
      });
      map.on('mouseleave', () => { map.getCanvas().style.cursor = ''; popup.remove(); });
    });
    mapRef.current = map;
    return () => { popup.remove(); map.remove(); mapRef.current = null; };
  }, [center]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const map = mapRef.current; if (!map?.isStyleLoaded()) return;
    const data = { type: 'FeatureCollection', features };
    map.getSource('geo-raw')?.setData(data); map.getSource('geo-clustered')?.setData(data);
  }, [features]);
  useEffect(() => { const map = mapRef.current; if (map?.isStyleLoaded()) visibility(map, mode); }, [mode]);
  useEffect(() => { const source = mapRef.current?.getSource('geo-zones'); if (source && zones) source.setData(zones); }, [zones]);
  return <div ref={containerRef} className="h-[58vh] min-h-[420px] w-full overflow-hidden border bg-slate-100 md:max-h-[760px]" data-testid="geo-map-canvas" aria-label="Mapa geográfico interactivo" />;
};