import React, { useState } from 'react';
import axios from 'axios';
import { Check, Search, UserPlus } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

const messageFrom = (error) => {
  const detail = error?.response?.data?.detail;
  return typeof detail === 'string' ? detail : detail?.message || 'No se pudo completar la asignación.';
};

export const MinistryAssignmentPanel = ({ ministryId, roles, API, getAuthHeaders, onAssigned }) => {
  const [query, setQuery] = useState('');
  const [candidates, setCandidates] = useState([]);
  const [selected, setSelected] = useState(null);
  const [roleId, setRoleId] = useState('');
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);

  const search = async () => {
    setSearching(true);
    try {
      const response = await axios.get(`${API}/api/core/persons/directory/search`, {
        ...getAuthHeaders(), params: { q: query.trim() || undefined, limit: 20 },
      });
      setCandidates(response.data.items || []);
    } catch (error) {
      toast.error(messageFrom(error));
    } finally {
      setSearching(false);
    }
  };

  const assign = async () => {
    if (!selected || !roleId) return;
    setSaving(true);
    try {
      await axios.post(`${API}/api/ministries/person/${selected.person_id}/assignments`, {
        person_id: selected.person_id,
        ministry_id: ministryId,
        role_id: roleId,
        activo: true,
        fecha_inicio: new Date().toISOString().slice(0, 10),
      }, getAuthHeaders());
      toast.success(`${selected.nombre_completo} fue asignado correctamente.`);
      setSelected(null); setCandidates([]); setQuery(''); setRoleId('');
      await onAssigned();
    } catch (error) {
      toast.error(messageFrom(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5" data-testid="ministry-assignment-panel">
      <h2 className="font-bold text-slate-950">Agregar Persona existente</h2>
      <p className="mt-1 text-sm text-slate-500">La asignación se vincula a su única ficha 360.</p>
      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_minmax(220px,0.7fr)_auto]">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => event.key === 'Enter' && search()}
          placeholder="Nombre, VV, talento..."
          data-testid="ministry-person-search-input"
        />
        <Button variant="outline" onClick={search} disabled={searching} data-testid="ministry-person-search-button">
          <Search className="mr-2 h-4 w-4" />{searching ? 'Buscando…' : 'Buscar'}
        </Button>
        <Select value={roleId || undefined} onValueChange={setRoleId}>
          <SelectTrigger data-testid="ministry-role-select"><SelectValue placeholder="Función en el Ministerio" /></SelectTrigger>
          <SelectContent>{roles.map((role) => <SelectItem key={role.role_id} value={role.role_id}>{role.nombre}</SelectItem>)}</SelectContent>
        </Select>
        <Button onClick={assign} disabled={!selected || !roleId || saving} data-testid="ministry-assign-person-button" className="bg-slate-900 text-white hover:bg-slate-800">
          <UserPlus className="mr-2 h-4 w-4" />{saving ? 'Asignando…' : 'Asignar'}
        </Button>
      </div>

      {candidates.length > 0 && (
        <div className="mt-4 grid gap-2 md:grid-cols-2" data-testid="ministry-search-results">
          {candidates.map((person) => (
            <button
              type="button"
              key={person.person_id}
              data-testid={`ministry-candidate-${person.person_id}`}
              onClick={() => setSelected(person)}
              className={`flex items-center gap-3 rounded-lg border p-3 text-left transition-colors ${selected?.person_id === person.person_id ? 'border-amber-400 bg-amber-50' : 'border-slate-200 bg-white hover:bg-slate-50'}`}
            >
              <div className="min-w-0 flex-1"><p className="truncate font-semibold">{person.nombre_completo}</p><p className="font-mono text-xs text-amber-700">{person.person_number}</p></div>
              {selected?.person_id === person.person_id && <Check className="h-5 w-5 text-emerald-600" />}
            </button>
          ))}
        </div>
      )}
    </section>
  );
};