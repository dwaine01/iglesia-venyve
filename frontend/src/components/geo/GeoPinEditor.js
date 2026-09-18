import React, { useEffect, useRef } from 'react';

const TILE_URL = process.env.REACT_APP_MAP_TILE_URL;

export const GeoPinEditor = ({ center, value, onChange }) => {
  const maplibregl = typeof window !== 'undefined' ? window.maplibregl : null;
  const containerRef = useRef(null); const mapRef = useRef(null); const markerRef = useRef(null);
  useEffect(() => {
    if (!maplibregl || !center || mapRef.current || !containerRef.current) return undefined;
    const coordinates = value?.longitude && value?.latitude ? [value.longitude, value.latitude] : [center.longitude, center.latitude];
    const map = new maplibregl.Map({ container: containerRef.current, center: coordinates, zoom: 12, style: { version: 8, sources: { osm: { type: 'raster', tiles: [TILE_URL], tileSize: 256, attribution: '© OpenStreetMap contributors' } }, layers: [{ id: 'osm', type: 'raster', source: 'osm' }] } });
    const marker = new maplibregl.Marker({ color: '#B5953F', draggable: true }).setLngLat(coordinates).addTo(map);
    marker.on('dragend', () => { const point = marker.getLngLat(); onChange({ latitude: point.lat, longitude: point.lng }); });
    map.on('click', (event) => { marker.setLngLat(event.lngLat); onChange({ latitude: event.lngLat.lat, longitude: event.lngLat.lng }); });
    mapRef.current = map; markerRef.current = marker;
    return () => { marker.remove(); map.remove(); mapRef.current = null; };
  }, [center, maplibregl]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!maplibregl) return <div className="flex h-72 items-center justify-center border bg-amber-50 p-4 text-sm text-amber-900" data-testid="geo-pin-library-error">No se pudo cargar el editor cartográfico local.</div>;
  return <div ref={containerRef} className="h-72 w-full border bg-slate-100" data-testid="geo-manual-pin-editor" />;
};