import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { ShieldPlus, UserMinus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

export const LibrarianManagerPanel = () => {
  const { API, getAuthHeaders } = useAuth();
  const [librarians, setLibrarians] = useState([]);
  const [search, setSearch] = useState('');
  const [candidates, setCandidates] = useState([]);

  const refresh = useCallback(async () => {
    const { data } = await axios.get(`${API}/api/library/librarians`, getAuthHeaders());
    setLibrarians(data.items || []);
  }, [API]);

  useEffect(() => { refresh(); }, [refresh]);

  const searchUsers = async () => {
    if (!search.trim()) return setCandidates([]);
    const { data } = await axios.get(`${API}/api/core/governance/users`, getAuthHeaders());
    const term = search.trim().toLowerCase();
    setCandidates((data.items || []).filter((item) => item.nombre?.toLowerCase().includes(term) || item.email?.toLowerCase().includes(term)).slice(0, 8));
  };

  const grant = async (userId) => {
    try {
      await axios.post(`${API}/api/library/librarians`, { user_id: userId }, getAuthHeaders());
      toast.success('Encargado de Librería asignado'); setCandidates([]); setSearch(''); await refresh();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo asignar el rol'); }
  };

  const revoke = async (userId) => {
    await axios.delete(`${API}/api/library/librarians/${userId}`, getAuthHeaders());
    toast.success('Rol de Encargado de Librería removido'); await refresh();
  };

  return <div className="rounded-2xl border border-slate-200 bg-white p-5" data-testid="library-librarians-panel">
    <h3 className="font-serif text-lg text-[#132443]">Encargados de Librería</h3>
    <ul className="mt-3 space-y-2">{librarians.map((item) => <li key={item.user_id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm" data-testid={`librarian-row-${item.user_id}`}>
      <span>{item.nombre} · {item.email}</span>
      <Button size="sm" variant="ghost" onClick={() => revoke(item.user_id)} data-testid={`revoke-librarian-${item.user_id}`}><UserMinus className="h-4 w-4" /></Button>
    </li>)}{librarians.length === 0 && <p className="text-sm text-slate-500">Ningún usuario tiene este rol todavía.</p>}</ul>
    <div className="mt-4 flex gap-2">
      <Input placeholder="Buscar por nombre o correo…" value={search} onChange={(e) => setSearch(e.target.value)} data-testid="librarian-search-input" />
      <Button variant="outline" onClick={searchUsers} data-testid="librarian-search-button">Buscar</Button>
    </div>
    {candidates.length > 0 && <ul className="mt-2 space-y-1">{candidates.map((candidate) => <li key={candidate.user_id} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-sm" data-testid={`librarian-candidate-${candidate.user_id}`}>
      <span>{candidate.nombre} · {candidate.email}</span>
      <Button size="sm" onClick={() => grant(candidate.user_id)} className="bg-[#132443]" data-testid={`grant-librarian-${candidate.user_id}`}><ShieldPlus className="h-4 w-4" />Asignar</Button>
    </li>)}</ul>}
  </div>;
};
