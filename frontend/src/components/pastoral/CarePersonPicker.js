import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, Search, UserRound, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

export const CarePersonPicker = ({ value, onChange, testId = 'care-person-picker' }) => {
  const { API, getAuthHeaders } = useAuth(); const [query, setQuery] = useState(''); const [items, setItems] = useState([]); const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (value || query.trim().length < 2) { setItems([]); return undefined; }
    const timer = setTimeout(() => { setLoading(true); axios.get(`${API}/api/care/people/search`, { ...getAuthHeaders(), params: { q: query.trim() } }).then((response) => setItems(response.data.items || [])).finally(() => setLoading(false)); }, 250);
    return () => clearTimeout(timer);
  }, [API, getAuthHeaders, query, value]);
  if (value) return <div className="flex items-center gap-3 border border-[#C8A951]/40 bg-[#FDF9EE] p-3" data-testid={`${testId}-selected`}><UserRound className="h-5 w-5 text-[#9A7E32]" /><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-[#0B1428]" data-testid={`${testId}-selected-name`}>{value.name}</p><p className="text-xs text-slate-500">{value.person_number}</p></div><Button type="button" size="icon" variant="ghost" onClick={() => { onChange(null); setQuery(''); }} aria-label="Cambiar Persona" data-testid={`${testId}-clear`}><X className="h-4 w-4" /></Button></div>;
  return <div className="relative"><div className="relative"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar Persona 360 por nombre o número" className="pl-9" data-testid={`${testId}-input`} />{loading && <Loader2 className="absolute right-3 top-2.5 h-4 w-4 animate-spin" />}</div>{items.length > 0 && <div className="absolute z-30 mt-1 max-h-60 w-full overflow-y-auto border bg-white shadow-xl" data-testid={`${testId}-results`}>{items.map((item) => <button type="button" key={item.person_id} onClick={() => onChange(item)} className="flex w-full items-center gap-3 border-b p-3 text-left hover:bg-[#FDF9EE]" data-testid={`${testId}-result-${item.person_id}`}><UserRound className="h-4 w-4 text-[#9A7E32]" /><span><b className="block text-sm">{item.name}</b><small className="text-slate-500">{item.person_number}</small></span></button>)}</div>}</div>;
};