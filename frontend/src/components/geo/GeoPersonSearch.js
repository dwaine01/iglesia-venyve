import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, Search, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

export const GeoPersonSearch = ({ disabled, onSelect }) => {
  const { API, getAuthHeaders } = useAuth(); const [query, setQuery] = useState('');
  const [selectedQuery, setSelectedQuery] = useState('');
  const [items, setItems] = useState([]); const [loading, setLoading] = useState(false); const [error, setError] = useState('');
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
  const choose = (item) => { setSelectedQuery(item.name); setQuery(item.name); setItems([]); onSelect(item); };
  return <div className="relative min-w-0 flex-1 sm:max-w-sm" data-testid="geo-person-search"><Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><Input className="h-9 bg-white pl-9 pr-9" value={query} disabled={disabled} onChange={(event) => { setSelectedQuery(''); setQuery(event.target.value); }} placeholder={disabled ? 'Búsqueda requiere acceso preciso' : 'Buscar Persona por nombre o VV'} data-testid="geo-person-search-input" />{loading && <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-amber-700" />}{query && !loading && <Button type="button" variant="ghost" size="icon" className="absolute right-0 top-0 h-9 w-9" onClick={() => { setSelectedQuery(''); setQuery(''); setItems([]); }} aria-label="Limpiar búsqueda" data-testid="clear-geo-person-search"><X className="h-4 w-4" /></Button>}{(items.length > 0 || error) && <div className="absolute left-0 right-0 top-10 z-50 max-h-72 overflow-y-auto border bg-white shadow-xl" data-testid="geo-person-search-results">{error && <p className="p-3 text-xs text-red-600">{error}</p>}{items.map((item) => <button type="button" key={item.person_id} className="flex w-full items-center justify-between border-b px-3 py-2 text-left hover:bg-amber-50" onClick={() => choose(item)} data-testid={`geo-person-search-result-${item.person_id}`}><span><b className="block text-sm">{item.name}</b><small className="text-slate-500">{item.person_number} · Zona {item.subzone}</small></span><Search className="h-4 w-4 text-amber-700" /></button>)}</div>}</div>;
};