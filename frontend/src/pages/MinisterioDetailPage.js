import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Church, Search, UserPlus, UsersRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import PersonCanonicalLink from '../components/PersonCanonicalLink';
import PersonPhoto from '../components/PersonPhoto';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Input } from '../components/ui/input';

export default function MinisterioDetailPage() {
  const { ministryId } = useParams();
  const { API, getAuthHeaders } = useAuth();
  const [ministry, setMinistry] = useState(null);
  const [roles, setRoles] = useState([]);
  const [query, setQuery] = useState('');
  const [candidates, setCandidates] = useState([]);
  const [selected, setSelected] = useState(null);
  const [roleId, setRoleId] = useState('');
  const load = async () => { const [detail, roleResponse] = await Promise.all([axios.get(`${API}/api/ministries/${ministryId}`, getAuthHeaders()), axios.get(`${API}/api/ministries/roles/catalog`, { ...getAuthHeaders(), params: { ministry_id: ministryId } })]); setMinistry(detail.data); setRoles(roleResponse.data.items || []); };
  useEffect(() => { load(); }, [ministryId]);
  const search = async () => { const response = await axios.get(`${API}/api/core/persons/directory/search`, { ...getAuthHeaders(), params: { q: query, limit: 20 } }); setCandidates(response.data.items || []); };
  const assign = async () => { if (!selected || !roleId) return; await axios.post(`${API}/api/ministries/person/${selected.person_id}/assignments`, { person_id: selected.person_id, ministry_id: ministryId, role_id: roleId, activo: true, fecha_inicio: new Date().toISOString().slice(0, 10) }, getAuthHeaders()); setSelected(null); setCandidates([]); setQuery(''); await load(); };
  if (!ministry) return <div className="p-8 text-gray-500">Cargando Ministerio...</div>;
  return <div className="min-h-screen bg-[#F7F5EF] p-4 lg:p-7"><div className="mx-auto max-w-7xl space-y-6">
    <Link to="/ministerios" className="inline-flex items-center gap-2 text-sm text-gray-600"><ArrowLeft className="h-4 w-4" />Todos los Ministerios</Link>
    <div className="rounded-xl border bg-white p-6 shadow-sm"><div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"><div><h1 className="flex items-center gap-3 text-3xl font-bold text-[#101D36]"><Church className="h-8 w-8 text-[#8A6D2F]" />{ministry.nombre}</h1><p className="mt-1 text-gray-500">{ministry.descripcion || 'Ministerio activo'}</p></div><div className="flex gap-2"><Badge className="bg-[#F3EACD] text-[#755B21]"><UsersRound className="mr-1 h-4 w-4" />{ministry.active_people_count} personas</Badge>{ministry.leadership_vacancy && <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-700">Liderazgo vacante</Badge>}</div></div></div>
    <Card><CardContent className="p-5"><h2 className="mb-3 font-bold text-[#101D36]">Agregar Persona existente</h2><div className="grid gap-2 md:grid-cols-[1fr_auto_1fr_auto]"><Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Nombre, VV, talento..." /><Button variant="outline" onClick={search}><Search className="mr-2 h-4 w-4" />Buscar</Button><select value={roleId} onChange={(e) => setRoleId(e.target.value)} className="h-9 rounded-md border bg-white px-3 text-sm"><option value="">Función en el Ministerio</option>{roles.map((role) => <option key={role.role_id} value={role.role_id}>{role.nombre}</option>)}</select><Button onClick={assign} disabled={!selected || !roleId} className="bg-[#132443]"><UserPlus className="mr-2 h-4 w-4" />Asignar</Button></div>{candidates.length > 0 && <div className="mt-3 grid gap-2 md:grid-cols-2">{candidates.map((person) => <button key={person.person_id} onClick={() => setSelected(person)} className={`rounded-lg border p-3 text-left ${selected?.person_id === person.person_id ? 'border-[#C8A951] bg-[#FBF8EF]' : ''}`}><p className="font-semibold">{person.nombre_completo}</p><p className="font-mono text-xs text-[#8A6D2F]">{person.person_number}</p></button>)}</div>}</CardContent></Card>
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{ministry.members.map((member) => <Card key={member.assignment_id}><CardContent className="flex gap-3 p-4"><PersonPhoto personId={member.person_id} available={member.photo_available} name={member.nombre_completo} /><div className="min-w-0 flex-1"><PersonCanonicalLink personId={member.person_id} className="font-semibold text-[#101D36]">{member.nombre_completo}</PersonCanonicalLink><p className="font-mono text-xs text-[#8A6D2F]">{member.person_number}</p><Badge variant="outline" className="mt-2">{member.role_name}</Badge></div></CardContent></Card>)}</div>
  </div></div>;
}
