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
import { Search, UserPlus, IdCard } from 'lucide-react';

export default function PersonasListPage() {
  const { API, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [persons, setPersons] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchPersons = useCallback(async (search) => {
    setLoading(true);
    setError('');
    try {
      const res = await axios.get(`${API}/api/core/persons`, {
        ...getAuthHeaders(),
        params: search ? { search, limit: 50 } : { limit: 50 },
      });
      setPersons(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo cargar el listado de personas.');
    } finally {
      setLoading(false);
    }
  }, [API, getAuthHeaders]);

  useEffect(() => {
    const timer = setTimeout(() => fetchPersons(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query, fetchPersons]);

  const nombreCompleto = (p) => `${p.nombre || ''} ${p.apellido || ''}`.trim();

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] p-4 md:p-8">
      <div className="max-w-5xl mx-auto space-y-6">
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
          <Button
            onClick={() => navigate('/personas/nueva')}
            className="bg-[#C8A951] hover:bg-[#B8964A] text-white gap-2"
          >
            <UserPlus className="w-4 h-4" />
            Nueva Persona
          </Button>
        </div>

        <Card className="border-none shadow-md">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-semibold text-gray-700">
              Buscar por nombre, apellido o número VV
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ej. María González o VV-000012"
                className="pl-9"
              />
            </div>
            {error && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md p-3 mb-4">
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
              <div className="text-center text-gray-500 py-10">
                No se encontraron personas{query ? ` para "${query}"` : ''}.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>VV</TableHead>
                      <TableHead>Nombre</TableHead>
                      <TableHead>Teléfono</TableHead>
                      <TableHead>Categoría</TableHead>
                      <TableHead className="text-right">Acción</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {persons.map((p) => (
                      <TableRow key={p.person_id} className="cursor-pointer hover:bg-gray-50">
                        <TableCell className="font-mono text-sm text-[#8A6D2F]">
                          {p.person_number}
                        </TableCell>
                        <TableCell className="font-medium">{nombreCompleto(p)}</TableCell>
                        <TableCell>{p.telefono || '—'}</TableCell>
                        <TableCell>
                          {p.age_category ? (
                            <Badge variant="secondary" className="capitalize">
                              {p.age_category}
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
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
