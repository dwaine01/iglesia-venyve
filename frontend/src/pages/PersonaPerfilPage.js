import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { ArrowLeft, IdCard, Phone, Mail, Cake, Clock } from 'lucide-react';

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
  const [person, setPerson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    axios
      .get(`${API}/api/core/persons/${personId}`, getAuthHeaders())
      .then((res) => {
        if (active) setPerson(res.data);
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

  const nombreCompleto = person ? `${person.nombre || ''} ${person.apellido || ''}`.trim() : '';
  const available = person?.sections_available || ['resumen'];
  const planned = person?.sections_planned || [];
  const allSections = [...available, ...planned];

  const fmtFecha = (iso) => {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleDateString('es', { year: 'numeric', month: 'long', day: 'numeric' });
    } catch {
      return iso;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] p-4 md:p-8">
        <div className="max-w-3xl mx-auto space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    );
  }

  if (error || !person) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] p-4 md:p-8">
        <div className="max-w-3xl mx-auto space-y-4">
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
      <div className="max-w-3xl mx-auto space-y-6">
        <button
          onClick={() => navigate('/personas')}
          className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="w-4 h-4" />
          Volver a Personas
        </button>

        <Card className="border-none shadow-md">
          <CardHeader className="pb-3">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
              <div>
                <CardTitle className="text-2xl flex items-center gap-2">
                  <IdCard className="w-6 h-6 text-[#C8A951]" />
                  {nombreCompleto}
                </CardTitle>
                <p className="font-mono text-sm text-[#8A6D2F] mt-1">{person.person_number}</p>
              </div>
              {person.age_category && (
                <Badge variant="secondary" className="capitalize w-fit">
                  {person.age_category}
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="resumen">
              <TabsList className="flex-wrap h-auto">
                {allSections.map((s) => (
                  <TabsTrigger key={s} value={s} disabled={!available.includes(s)}>
                    {SECTION_LABELS[s] || s}
                  </TabsTrigger>
                ))}
              </TabsList>

              <TabsContent value="resumen" className="pt-4">
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="flex items-start gap-2">
                    <Phone className="w-4 h-4 text-gray-400 mt-0.5" />
                    <div>
                      <dt className="text-xs text-gray-500">Teléfono</dt>
                      <dd className="text-gray-900">{person.telefono || '—'}</dd>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <Mail className="w-4 h-4 text-gray-400 mt-0.5" />
                    <div>
                      <dt className="text-xs text-gray-500">Email</dt>
                      <dd className="text-gray-900">{person.email || '—'}</dd>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <Cake className="w-4 h-4 text-gray-400 mt-0.5" />
                    <div>
                      <dt className="text-xs text-gray-500">Fecha de nacimiento</dt>
                      <dd className="text-gray-900">{fmtFecha(person.fecha_nacimiento)}</dd>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <Clock className="w-4 h-4 text-gray-400 mt-0.5" />
                    <div>
                      <dt className="text-xs text-gray-500">Persona creada</dt>
                      <dd className="text-gray-900">{fmtFecha(person.created_at)}</dd>
                    </div>
                  </div>
                </dl>
              </TabsContent>

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
