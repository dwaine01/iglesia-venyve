import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { CheckCircle2, Search, UserRound } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Input } from '../ui/input';

export const OperationsPersonPicker = ({ occurrenceId, selectedId, onSelect, testIdPrefix = 'operations-person' }) => {
  const { API, getAuthHeaders } = useAuth(); const [q, setQ] = useState(''); const [items, setItems] = useState([]);
  useEffect(() => { if (q.trim().length < 2) { setItems([]); return undefined; } const timer = setTimeout(() => { axios.get(`${API}/api/operations/occurrences/${occurrenceId}/checkin/search`, { ...getAuthHeaders(), params: { q } }).then((response) => setItems(response.data.items || [])).catch(() => setItems([])); }, 250); return () => clearTimeout(timer); }, [API, getAuthHeaders, occurrenceId, q]);
  return <div className="space-y-2" data-testid={`${testIdPrefix}-picker`}><div className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><Input value={q} onChange={(event) => setQ(event.target.value)} placeholder="Buscar por nombre o número VV" className="pl-9" data-testid={`${testIdPrefix}-search-input`} /></div>{items.length > 0 && <div className="max-h-52 divide-y overflow-y-auto border bg-white">{items.filter((item) => item.person_id).map((item) => <button type="button" key={item.person_id} onClick={() => onSelect(item)} className="flex w-full items-center gap-3 p-3 text-left hover:bg-emerald-50" data-testid={`${testIdPrefix}-result-${item.person_id}`}><span className="flex h-8 w-8 items-center justify-center bg-slate-100"><UserRound className="h-4 w-4" /></span><span className="min-w-0 flex-1"><b className="block truncate text-sm">{item.name}</b><small className="text-slate-500">{item.person_number || 'Sin número VV'}</small></span>{selectedId === item.person_id && <CheckCircle2 className="h-5 w-5 text-emerald-700" />}</button>)}</div>}</div>;
};