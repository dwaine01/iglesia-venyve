import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import { Loader2, Search, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

export const GeoPersonSearch = ({ disabled, onSelect }) => {
  const { API, getAuthHeaders } = useAuth(); const anchorRef = useRef(null);
  const [query, setQuery] = useState(''); const [selectedQuery, setSelectedQuery] = useState('');
  const [items, setItems] = useState([]); const [loading, setLoading] = useState(false); const [error, setError] = useState('');
  const [position, setPosition] = useState(null);
  const positionResults = useCallback(() => {
    const rect = anchorRef.current?.getBoundingClientRect(); if (!rect) return;
    const width = Math.min(360, Math.max(280, window.innerWidth - 16));
    setPosition({ top: rect.bottom + 4, left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)), width });
  }, []);
  useLayoutEffect(() => { if (items.length || error) positionResults(); }, [error, items.length, positionResults]);
  useEffect(() => {
    if (!items.length && !error) return undefined;
    window.addEventListener('resize', positionResults); window.addEventListener('scroll', positionResults, true);
    return () => { window.removeEventListener('resize', positionResults); window.removeEventListener('scroll', positionResults, true); };
  }, [error, items.length, positionResults]);
  useEffect(() => {
    if (disabled || query.trim().length < 2 || query === selectedQuery) { setItems([]); setError(''); return undefined; }
    const timer = setTimeout(async () => {
      setLoading(true);
      try { const response = await axios.get(`${API}/api/geo/search`, { ...getAuthHeaders(), params: { q: query.trim(), limit: 10 } }); setItems(response.data.items || []); setError(''); }
      catch { setItems([]); setError('No se pudo buscar'); }
      finally { setLoading(false); }
    }, 250);
    return () => clearTimeout(timer);
  }, [API, disabled, getAuthHeaders, query, selectedQuery]);
  const choose = (event, item) => {
    event.preventDefault(); event.stopPropagation(); onSelect(item); setSelectedQuery(item.name); setQuery(item.name); setItems([]);
  };
  const results = (items.length > 0 || error) && position && typeof document !== 'undefined' ? createPortal(
    <div className="fixed z-[200] max-h-72 overflow-y-auto border bg-white shadow-2xl" style={position} data-testid="geo-person-search-results">{error && <p className="p-3 text-xs text-red-600" data-testid="geo-person-search-error">{error}</p>}{items.map((item) => <button type="button" key={item.person_id} className="flex w-full items-center justify-between border-b px-3 py-2 text-left hover:bg-amber-50" onPointerDown={(event) => choose(event, item)} data-testid={`geo-person-search-result-${item.person_id}`}><span><b className="block text-sm">{item.name}</b><small className="text-slate-500">{item.person_number} · Zona {item.subzone}</small></span><Search className="h-4 w-4 text-amber-700" /></button>)}</div>, document.body,
  ) : null;
  return <><div ref={anchorRef} className="relative min-w-[8rem] flex-1 sm:max-w-sm" data-testid="geo-person-search"><Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><Input className="h-9 bg-white pl-9 pr-9" value={query} disabled={disabled} onChange={(event) => { setSelectedQuery(''); setQuery(event.target.value); }} placeholder={disabled ? 'Búsqueda requiere acceso preciso' : 'Buscar Persona por nombre o VV'} data-testid="geo-person-search-input" />{loading && <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-amber-700" />}{query && !loading && <Button type="button" variant="ghost" size="icon" className="absolute right-0 top-0 h-9 w-9" onClick={() => { setSelectedQuery(''); setQuery(''); setItems([]); }} aria-label="Limpiar búsqueda" data-testid="clear-geo-person-search"><X className="h-4 w-4" /></Button>}</div>{results}</>;
};