import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import PersonAddressSection from '../components/PersonAddressSection';
import PersonContactSection from '../components/PersonContactSection';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { ArrowLeft, IdCard, Phone, Mail, Cake, Clock, MapPin, CheckCircle2, CircleDashed, ChevronRight } from 'lucide-react';

// P-001 Slice 2A - Person Profile 360 (shell full-screen).
// Consume unicamente el read-model /api/core/persons/{id}/profile.
// No inventa estados: si un dominio no tiene datos reales, se muestra tal
// como el backend lo declara (module_unavailable / no_record / has_summary).
const SECTION_LABELS = {
  resumen: 'Resumen',
  contacto: 'Contacto',
  direcciones: 'Direcciones',
  household: 'Household',
  familia: 'Familia',
  procesos: 'Procesos',
  historial: 'Historial',
};

export default function PersonaPerfilPage() {
  const { personId } = useParams();
  const { API, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('resumen');

  const refreshProfile = async () => {
    const response = await axios.get(
      `${API}/api/core/persons/${personId}/profile`,
      getAuthHeaders()
    );
    setProfile(response.data);
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    axios
      .get(`${API}/api/core/persons/${personId}/profile`, getAuthHeaders())
      .then((res) => {
        if (active) setProfile(res.data);
      })
      .catch((err) => {
        if (active) setError(err?.response?.data?.detail || 'No se pudo cargar el perfil.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [API, getAuthHeaders, personId]);

  const header = profile?.header;
  const sections = profile?.sections || [];
  const coreSection = sections.find((s) => s.section_key === 'core');
  const domainSections = sections.filter((s) => s.section_key !== 'core');
  const available = profile?.sections_available || ['resumen'];
  const planned = profile?.sections_planned || [];
  const allSections = [...available, ...planned];

  const fmtFecha = (iso) => {
    if (!iso) return null;
    try {
      return new Date(iso).toLocaleDateString('es', { year: 'numeric', month: 'long', day: 'numeric' });
    } catch {
      return iso;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] p-4 md:p-8">
        <div className="max-w-5xl mx-auto space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (error || !header) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] p-4 md:p-8">
        <div className="max-w-5xl mx-auto space-y-4">
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md p-3">
            {error || 'Persona no encontrada.'}
          </div>
          <Button variant="outline" onClick={() => navigate('/personas')}>
            Volver a Personas
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] p-4 md:p-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <button
          onClick={() => navigate('/personas')}
          className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="w-4 h-4" />
          Volver a Personas
        </button>

        {/* Cabecera tipo pasaporte */}
        <Card className="border-none shadow-md overflow-hidden">
          <div className="h-2 bg-gradient-to-r from-[#C8A951] to-[#8A6D2F]" />
          <CardHeader className="pb-3">
            <div className="flex flex-col md:flex-row md:items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-[#F5F0E8] border-2 border-[#C8A951] flex items-center justify-center text-xl font-semibold text-[#8A6D2F] shrink-0">
                {header.initials}
              </div>
              <div className="flex-1 min-w-0">
                <CardTitle className="text-2xl flex items-center gap-2 flex-wrap">
                  <IdCard className="w-6 h-6 text-[#C8A951]" />
                  {header.nombre_completo}
                  {header.age_category && (
                    <Badge variant="secondary" className="capitalize w-fit">
                      {header.age_category}
                    </Badge>
                  )}
                </CardTitle>
                <p className="font-mono text-sm text-[#8A6D2F] mt-1">{header.person_number}</p>
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-gray-600">
                {header.primary_contact && (
                  <div className="flex items-center gap-1.5">
                    {header.primary_contact.includes('@') ? (
                      <Mail className="w-4 h-4 text-gray-400" />
                    ) : (
                      <Phone className="w-4 h-4 text-gray-400" />
                    )}
                    {header.primary_contact}
                  </div>
                )}
                {header.city && (
                  <div className="flex items-center gap-1.5">
                    <MapPin className="w-4 h-4 text-gray-400" />
                    {header.city}
                  </div>
                )}
                {header.fecha_nacimiento && (
                  <div className="flex items-center gap-1.5">
                    <Cake className="w-4 h-4 text-gray-400" />
                    {fmtFecha(header.fecha_nacimiento)}
                  </div>
                )}
              </div>
            </div>
          </CardHeader>

          <CardContent>
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="flex-wrap h-auto">
                {allSections.map((s) => (
                  <TabsTrigger key={s} value={s} disabled={!available.includes(s)}>
                    {SECTION_LABELS[s] || s}
                  </TabsTrigger>
                ))}
              </TabsList>

              <TabsContent value="resumen" className="pt-4 space-y-4">
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-3">Resumen 360°</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {domainSections.map((s) => (
                      <div
                        key={s.section_key}
                        data-testid={`resumen-360-card-${s.section_key}`}
                        role={available.includes(s.section_key) ? 'button' : undefined}
                        tabIndex={available.includes(s.section_key) ? 0 : undefined}
                        onClick={
                          available.includes(s.section_key)
                            ? () => setActiveTab(s.section_key)
                            : undefined
                        }
                        onKeyDown={
                          available.includes(s.section_key)
                            ? (e) => {
                                if (e.key === 'Enter' || e.key === ' ') setActiveTab(s.section_key);
                              }
                            : undefined
                        }
                        className={
                          (s.status_code === 'has_summary'
                            ? 'rounded-lg border border-[#C8A951]/40 bg-[#FBF8F1] p-3'
                            : 'rounded-lg border border-gray-200 bg-gray-50/60 p-3') +
                          (available.includes(s.section_key) ? ' cursor-pointer hover:shadow-sm transition-shadow' : '')
                        }
                      >
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <div className="flex items-center gap-2">
                            {s.status_code === 'has_summary' ? (
                              <CheckCircle2 className="w-4 h-4 text-[#8A6D2F]" />
                            ) : (
                              <CircleDashed className="w-4 h-4 text-gray-300" />
                            )}
                            <span className="text-sm font-medium text-gray-800">{s.status_label}</span>
                          </div>
                          {available.includes(s.section_key) && <ChevronRight className="w-4 h-4 text-gray-400" />}
                        </div>
                        {s.status_code === 'has_summary' ? (
                          <p className="text-sm text-gray-600">{s.summary}</p>
                        ) : s.status_code === 'no_record' ? (
                          <p className="text-xs text-gray-400">Sin registros todavía.</p>
                        ) : (
                          <p className="text-xs text-gray-400">Módulo aún no disponible.</p>
                        )}
                        {s.primary_date && (
                          <p className="text-xs text-gray-400 mt-1">{fmtFecha(s.primary_date)}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {coreSection?.primary_date && (
                  <div className="flex items-start gap-2 text-xs text-gray-400 pt-2 border-t">
                    <Clock className="w-3.5 h-3.5 mt-0.5" />
                    <span>Persona creada el {fmtFecha(coreSection.primary_date)}</span>
                  </div>
                )}
              </TabsContent>

              {profile.contacto && (
                <TabsContent value="contacto" className="pt-5">
                  <PersonContactSection
                    personId={personId}
                    domain={profile.contacto}
                    API={API}
                    getAuthHeaders={getAuthHeaders}
                    onChanged={refreshProfile}
                  />
                </TabsContent>
              )}

              {profile.direcciones && (
                <TabsContent value="direcciones" className="pt-5">
                  <PersonAddressSection
                    personId={personId}
                    domain={profile.direcciones}
                    API={API}
                    getAuthHeaders={getAuthHeaders}
                    onChanged={refreshProfile}
                  />
                </TabsContent>
              )}

              {planned.map((s) => (
                <TabsContent key={s} value={s} className="pt-4">
                  <div className="text-center text-gray-400 py-10 text-sm">
                    {SECTION_LABELS[s] || s} — próximamente en un siguiente ticket del Core de Personas.
                  </div>
                </TabsContent>
              ))}
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
