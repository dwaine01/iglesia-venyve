import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { BriefcaseBusiness, RefreshCw, UserPlus, UsersRound } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { DirectoryFilters } from '../components/directory/DirectoryFilters';
import { DirectoryPersonCard } from '../components/directory/DirectoryPersonCard';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';

const EMPTY_FILTERS = {
  q: '', occupationId: '', skillId: '', ageGroup: '', ministryId: '', roleId: '', gender: '',
};

const detailText = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  return typeof detail === 'string' ? detail : detail?.message || fallback;
};

export default function DirectorioTalentosPage() {
  const { API, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [catalog, setCatalog] = useState([]);
  const [ministries, setMinistries] = useState([]);
  const [roles, setRoles] = useState([]);
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.all([
      axios.get(`${API}/api/core/talents/catalog`, getAuthHeaders()),
      axios.get(`${API}/api/ministries`, getAuthHeaders()),
    ]).then(([talentResponse, ministryResponse]) => {
      if (!active) return;
      setCatalog(talentResponse.data.items || []);
      setMinistries(ministryResponse.data.items || []);
    }).catch((requestError) => {
      if (active) setError(detailText(requestError, 'No se pudieron cargar los catálogos.'));
    });
    return () => { active = false; };
  }, [API, getAuthHeaders]);

  useEffect(() => {
    let active = true;
    axios.get(`${API}/api/ministries/roles/catalog`, {
      ...getAuthHeaders(),
      params: filters.ministryId ? { ministry_id: filters.ministryId } : {},
    }).then((response) => {
      if (active) setRoles(response.data.items || []);
    }).catch(() => {
      if (active) setRoles([]);
    });
    return () => { active = false; };
  }, [API, filters.ministryId, getAuthHeaders]);

  const fetchDirectory = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await axios.get(`${API}/api/core/persons/directory/search`, {
        ...getAuthHeaders(),
        params: {
          q: filters.q.trim() || undefined,
          occupation_id: filters.occupationId || undefined,
          skill_id: filters.skillId || undefined,
          age_group: filters.ageGroup || undefined,
          ministry_id: filters.ministryId || undefined,
          ministry_role_id: filters.roleId || undefined,
          genero: filters.gender || undefined,
          limit: 100,
        },
      });
      setResults(response.data.items || []);
      setTotal(response.data.total || 0);
    } catch (requestError) {
      setResults([]);
      setTotal(0);
      setError(detailText(requestError, 'No se pudo consultar el directorio.'));
    } finally {
      setLoading(false);
    }
  }, [API, filters, getAuthHeaders]);

  useEffect(() => {
    const timer = setTimeout(fetchDirectory, 300);
    return () => clearTimeout(timer);
  }, [fetchDirectory, reloadKey]);

  const updateFilter = (key, value) => {
    setFilters((current) => ({
      ...current,
      [key]: value,
      ...(key === 'ministryId' ? { roleId: '' } : {}),
    }));
  };

  const option = (item, idKey) => ({ value: item[idKey], label: item.nombre });
  const occupationOptions = useMemo(
    () => catalog.filter((item) => ['ocupacion', 'ambos'].includes(item.tipo)).map((item) => option(item, 'talent_id')),
    [catalog]
  );
  const skillOptions = useMemo(
    () => catalog.filter((item) => ['habilidad', 'ambos'].includes(item.tipo)).map((item) => option(item, 'talent_id')),
    [catalog]
  );
  const ministryOptions = ministries.map((item) => option(item, 'ministry_id'));
  const roleOptions = roles.map((item) => option(item, 'role_id'));
  const activeLabels = [
    filters.q && `Texto: ${filters.q}`,
    occupationOptions.find((item) => item.value === filters.occupationId)?.label,
    skillOptions.find((item) => item.value === filters.skillId)?.label,
    ministryOptions.find((item) => item.value === filters.ministryId)?.label,
    roleOptions.find((item) => item.value === filters.roleId)?.label,
    filters.ageGroup && ({ ninez: 'Niñez', adolescencia: 'Adolescencia', adulto: 'Adulto' }[filters.ageGroup]),
    filters.gender && ({ masculino: 'Masculino', femenino: 'Femenino', no_especificado: 'No especificado' }[filters.gender]),
  ].filter(Boolean);

  return (
    <div className="directory-surface min-h-screen px-4 py-7 sm:px-6 lg:px-8" data-testid="talent-directory-page">
      <div className="mx-auto max-w-7xl space-y-7">
        <header className="flex flex-col gap-5 border-b border-slate-200 pb-7 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-amber-700">
              <BriefcaseBusiness className="h-4 w-4" />Directorio interno
            </p>
            <h1 className="text-4xl font-bold text-slate-950 sm:text-5xl" data-testid="talent-directory-title">
              Personas, dones y servicio
            </h1>
            <p className="mt-3 max-w-2xl text-sm text-slate-600 sm:text-base">
              Cruza ocupaciones, habilidades y asignaciones ministeriales sin duplicar ninguna ficha 360.
            </p>
          </div>
          <Button onClick={() => navigate('/personas/nueva')} data-testid="directory-new-person-button" className="bg-slate-900 text-white hover:bg-slate-800">
            <UserPlus className="mr-2 h-4 w-4" />Nueva Persona
          </Button>
        </header>

        <DirectoryFilters
          filters={filters}
          occupationOptions={occupationOptions}
          skillOptions={skillOptions}
          ministries={ministryOptions}
          roles={roleOptions}
          activeLabels={activeLabels}
          onChange={updateFilter}
          onClear={() => setFilters(EMPTY_FILTERS)}
        />

        <section aria-live="polite" aria-busy={loading}>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-slate-700">
              <UsersRound className="h-5 w-5 text-amber-700" />
              <p className="font-medium" data-testid="directory-results-count">
                {loading ? 'Buscando Personas…' : `${total} persona${total === 1 ? '' : 's'} encontrada${total === 1 ? '' : 's'}`}
              </p>
            </div>
          </div>

          {error ? (
            <Alert variant="destructive" data-testid="directory-error-alert">
              <AlertTitle>No pudimos completar la búsqueda</AlertTitle>
              <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <span>{error}</span>
                <Button variant="outline" size="sm" onClick={() => setReloadKey((value) => value + 1)} data-testid="directory-retry-button">
                  <RefreshCw className="mr-2 h-4 w-4" />Reintentar
                </Button>
              </AlertDescription>
            </Alert>
          ) : loading ? (
            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3" data-testid="directory-loading-state">
              {Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-72 w-full rounded-lg" />)}
            </div>
          ) : results.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-300 bg-white px-6 py-16 text-center" data-testid="directory-empty-state">
              <UsersRound className="mx-auto h-10 w-10 text-amber-700" />
              <p className="mt-4 font-semibold text-slate-900">No encontramos Personas con esos criterios</p>
              <p className="mt-1 text-sm text-slate-500">Prueba otra combinación de ocupación, habilidad o ministerio.</p>
              <Button variant="outline" className="mt-5" onClick={() => setFilters(EMPTY_FILTERS)} data-testid="directory-empty-clear-button">Limpiar filtros</Button>
            </div>
          ) : (
            <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3" data-testid="person-results-grid">
              {results.map((person) => <DirectoryPersonCard key={person.person_id} person={person} />)}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}