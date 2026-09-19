import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Search, UserPlus, IdCard, FlaskConical, Upload } from 'lucide-react';
import PersonCanonicalLink from '../components/PersonCanonicalLink';
import { QaDemoCleanupDialog } from '../components/QaDemoCleanupDialog';
import { toast } from 'sonner';
import { canManageDirectMembership } from '../lib/accessControl';

export default function PersonasListPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [talentId, setTalentId] = useState('');
  const [gender, setGender] = useState('');
  const [ageGroup, setAgeGroup] = useState('');
  const [catalog, setCatalog] = useState([]);
  const [ministryId, setMinistryId] = useState('');
  const [ministryRoleId, setMinistryRoleId] = useState('');
  const [ministries, setMinistries] = useState([]);
  const [ministryRoles, setMinistryRoles] = useState([]);
  const [persons, setPersons] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [qaSummary, setQaSummary] = useState(null);
  const [cleanupOpen, setCleanupOpen] = useState(false);
  const [cleaningQa, setCleaningQa] = useState(false);
  const [cleanupError, setCleanupError] = useState('');

  const fetchPersons = useCallback(async (search) => {
    setLoading(true);
    setError('');
    try {
      const res = await axios.get(`${API}/api/core/persons/directory/search`, {
        ...getAuthHeaders(),
        params: {
          q: search || undefined,
          talent_id: talentId || undefined,
          genero: gender || undefined,
          age_group: ageGroup || undefined,
          ministry_id: ministryId || undefined,
          ministry_role_id: ministryRoleId || undefined,
          limit: 50,
        },
      });
      setPersons(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo cargar el listado de personas.');
    } finally {
      setLoading(false);
    }
  }, [API, ageGroup, gender, getAuthHeaders, ministryId, ministryRoleId, talentId]);

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/api/core/talents/catalog`, getAuthHeaders()),
      axios.get(`${API}/api/ministries`, getAuthHeaders()),
      axios.get(`${API}/api/ministries/roles/catalog`, getAuthHeaders()),
    ])
      .then(([talentResponse, ministryResponse, roleResponse]) => {
        setCatalog(talentResponse.data.items || []);
        setMinistries(ministryResponse.data.items || []);
        setMinistryRoles(roleResponse.data.items || []);
      })
      .catch(() => {
        setCatalog([]); setMinistries([]); setMinistryRoles([]);
      });
  }, [API, getAuthHeaders]);

  const loadQaSummary = useCallback(() => {
    if (user?.rol !== 'pastor') return;
    axios.get(`${API}/api/core/persons/qa-demo/summary`, getAuthHeaders())
      .then((response) => setQaSummary(response.data))
      .catch(() => setQaSummary(null));
  }, [API, getAuthHeaders, user?.rol]);

  useEffect(() => { loadQaSummary(); }, [loadQaSummary]);

  useEffect(() => {
    const timer = setTimeout(() => fetchPersons(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query, fetchPersons]);

  const nombreCompleto = (p) => `${p.nombre || ''} ${p.apellido || ''}`.trim();

  const cleanupQaDemo = async () => {
    setCleaningQa(true);
    setCleanupError('');
    try {
      const response = await axios.delete(`${API}/api/core/persons/qa-demo`, getAuthHeaders());
      toast.success(`${response.data.deleted_documents} artefactos QA eliminados`);
      setCleanupOpen(false);
      setQaSummary({ qa_users: 0, qa_persons: 0, total: 0 });
      await fetchPersons(query.trim());
    } catch (requestError) {
      setCleanupError(requestError?.response?.data?.detail || 'No se pudieron eliminar las muestras QA.');
    } finally {
      setCleaningQa(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] p-4 md:p-8" data-testid="persons-directory-page">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-gray-900 flex items-center gap-2">
              <IdCard className="w-7 h-7 text-[#C8A951]" />
              Personas
            </h1>
            <p className="text-gray-600 mt-1">
              Identidad única y permanente de cada persona en la iglesia (VV-XXXXXX).
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {canManageDirectMembership(user) && <Button variant="outline" onClick={() => navigate('/personas/importar')} className="bg-white" data-testid="membership-import-open-button"><Upload className="h-4 w-4" />Importar membresía</Button>}
            {user?.rol === 'pastor' && qaSummary?.total > 0 && <Button
              variant="outline"
              onClick={() => { setCleanupError(''); setCleanupOpen(true); }}
              className="border-red-200 bg-white text-red-700 hover:bg-red-50 hover:text-red-800"
              data-testid="qa-demo-cleanup-button"
            >
              <FlaskConical className="w-4 h-4" />
              Limpiar muestras ({qaSummary.total})
            </Button>}
            <Button
              onClick={() => navigate('/personas/nueva')}
              className="bg-[#C8A951] hover:bg-[#B8964A] text-white gap-2"
              data-testid="person-create-button"
            >
              <UserPlus className="w-4 h-4" />
              Nueva Persona
            </Button>
          </div>
        </div>
        <QaDemoCleanupDialog
          open={cleanupOpen}
          onOpenChange={setCleanupOpen}
          summary={qaSummary}
          busy={cleaningQa}
          error={cleanupError}
          onConfirm={cleanupQaDemo}
        />

        <Card className="border-none shadow-md">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold text-gray-700">
              Directorio interno de Personas y talentos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-7">
              <div className="relative md:col-span-2">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Nombre, VV, Pintor, Mecánico..."
                  className="pl-9"
                  data-testid="persons-search-input"
                />
              </div>
              <select value={talentId} onChange={(e) => setTalentId(e.target.value)} className="h-9 rounded-md border bg-white px-3 text-sm" data-testid="persons-talent-filter">
                <option value="">Toda ocupación/habilidad</option>
                {catalog.map((item) => <option key={item.talent_id} value={item.talent_id}>{item.nombre}</option>)}
              </select>
              <select value={gender} onChange={(e) => setGender(e.target.value)} className="h-9 rounded-md border bg-white px-3 text-sm" data-testid="persons-gender-filter">
                <option value="">Todo género</option><option value="masculino">Masculino</option><option value="femenino">Femenino</option><option value="no_especificado">No especificado</option>
              </select>
              <select value={ageGroup} onChange={(e) => setAgeGroup(e.target.value)} className="h-9 rounded-md border bg-white px-3 text-sm" data-testid="persons-age-filter">
                <option value="">Todo grupo de edad</option><option value="ninez">Niñez</option><option value="adolescencia">Adolescencia</option><option value="adulto">Adulto</option>
              </select>
              <select value={ministryId} onChange={(e) => setMinistryId(e.target.value)} className="h-9 rounded-md border bg-white px-3 text-sm" data-testid="persons-ministry-filter">
                <option value="">Todo Ministerio</option>{ministries.map((item) => <option key={item.ministry_id} value={item.ministry_id}>{item.nombre}</option>)}
              </select>
              <select value={ministryRoleId} onChange={(e) => setMinistryRoleId(e.target.value)} className="h-9 rounded-md border bg-white px-3 text-sm" data-testid="persons-ministry-role-filter">
                <option value="">Toda función ministerial</option>{ministryRoles.map((item) => <option key={item.role_id} value={item.role_id}>{item.nombre}</option>)}
              </select>
            </div>
            <div className="mb-4 rounded-md border border-dashed bg-gray-50 px-3 py-2 text-xs text-gray-500">
              Estado de Membresía: filtro preparado, disponible cuando el módulo Membresía sea fuente de verdad.
            </div>
            {error && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md p-3 mb-4" data-testid="persons-error-alert">
                {error}
              </div>
            )}

            {loading ? (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : persons.length === 0 ? (
              <div className="text-center text-gray-500 py-10" data-testid="persons-empty-state">
                No se encontraron personas{query ? ` para "${query}"` : ''}.
              </div>
            ) : (
              <>
              <div className="space-y-3 md:hidden" data-testid="persons-mobile-list">
                {persons.map((p) => (
                  <article key={p.person_id} className="rounded-md border border-gray-200 bg-white p-4 shadow-sm" data-testid={`person-mobile-card-${p.person_id}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0"><PersonCanonicalLink personId={p.person_id}><span className="font-semibold text-gray-900">{nombreCompleto(p)}</span></PersonCanonicalLink><p className="mt-1 font-mono text-xs text-[#8A6D2F]">{p.person_number}</p></div>
                      {p.age_group_label && <Badge variant="secondary" className="shrink-0">{p.age_group_label}</Badge>}
                    </div>
                    <p className="mt-3 text-sm font-medium text-gray-700">{p.talents?.ocupacion_principal?.nombre || 'Sin ocupación registrada'}</p>
                    {p.talents?.habilidades?.length > 0 && <p className="mt-1 break-words text-xs leading-5 text-gray-500">{p.talents.habilidades.map((item) => item.nombre).join(', ')}</p>}
                    <Button variant="outline" size="sm" onClick={() => navigate(`/personas/${p.person_id}`)} className="mt-4 w-full" data-testid={`person-open-mobile-${p.person_id}`}>Ver perfil</Button>
                  </article>
                ))}
                <p className="text-xs text-gray-400">Mostrando {persons.length} de {total} persona(s).</p>
              </div>
              <div className="hidden overflow-x-auto md:block" data-testid="persons-table">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>VV</TableHead>
                      <TableHead>Nombre</TableHead>
                      <TableHead>Ocupación / habilidades</TableHead>
                      <TableHead>Edad / categoría</TableHead>
                      <TableHead className="text-right">Acción</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {persons.map((p) => (
                      <TableRow key={p.person_id} className="cursor-pointer hover:bg-gray-50">
                        <TableCell className="font-mono text-sm text-[#8A6D2F]">
                          <PersonCanonicalLink personId={p.person_id}>{p.person_number}</PersonCanonicalLink>
                        </TableCell>
                        <TableCell className="font-medium">
                          <PersonCanonicalLink personId={p.person_id}>{nombreCompleto(p)}</PersonCanonicalLink>
                        </TableCell>
                        <TableCell>
                          <p className="font-medium text-gray-800">{p.talents?.ocupacion_principal?.nombre || '—'}</p>
                          {p.talents?.habilidades?.length > 0 && <p className="max-w-xs text-xs text-gray-500">{p.talents.habilidades.map((item) => item.nombre).join(', ')}</p>}
                        </TableCell>
                        <TableCell>
                          {p.age_group_label ? (
                            <Badge variant="secondary">
                              {p.age_years} años · {p.age_group_label}
                            </Badge>
                          ) : (
                            '—'
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigate(`/personas/${p.person_id}`)}
                            data-testid={`person-open-${p.person_id}`}
                          >
                            Ver perfil
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <p className="text-xs text-gray-400 mt-3">
                  Mostrando {persons.length} de {total} persona(s).
                </p>
              </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
