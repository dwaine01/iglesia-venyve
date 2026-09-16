import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { Archive, Church, Plus, UsersRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';

export default function MinisteriosPage() {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ nombre: '', descripcion: '' });
  const load = async () => { const response = await axios.get(`${API}/api/ministries`, getAuthHeaders()); setItems(response.data.items || []); };
  useEffect(() => { load(); }, []);
  const create = async (event) => { event.preventDefault(); await axios.post(`${API}/api/ministries`, { ...form, suggested_age_groups: [] }, getAuthHeaders()); setOpen(false); setForm({ nombre: '', descripcion: '' }); await load(); };
  const archive = async (id) => { if (!window.confirm('¿Archivar este Ministerio? Sus asignaciones se conservan.')) return; await axios.post(`${API}/api/ministries/${id}/archive`, {}, getAuthHeaders()); await load(); };
  return <div className="min-h-screen bg-[#F7F5EF] p-4 lg:p-7"><div className="mx-auto max-w-7xl space-y-6">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h1 className="flex items-center gap-3 text-3xl font-bold text-[#101D36]"><Church className="h-8 w-8 text-[#8A6D2F]" />Ministerios</h1><p className="mt-1 text-gray-500">Un catálogo central; muchas Personas y funciones.</p></div><Button onClick={() => setOpen(true)} className="bg-[#132443]"><Plus className="mr-2 h-4 w-4" />Crear Ministerio</Button></div>
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{items.map((item) => <Card key={item.ministry_id} className="border-[#E8E5DE]"><CardContent className="p-5"><div className="flex items-start justify-between"><div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#F3EACD]"><Church className="h-5 w-5 text-[#755B21]" /></div>{item.leadership_vacancy ? <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-700">Liderazgo vacante</Badge> : <Badge className="bg-emerald-50 text-emerald-700">Liderazgo activo</Badge>}</div><Link to={item.canonical_ministry_path} className="mt-4 block text-xl font-bold text-[#101D36] hover:text-[#8A6D2F]">{item.nombre}</Link><p className="mt-1 min-h-10 text-sm text-gray-500">{item.descripcion || 'Unidad ministerial activa'}</p><div className="mt-4 flex items-center justify-between border-t pt-4"><span className="flex items-center gap-2 text-sm text-gray-600"><UsersRound className="h-4 w-4" />{item.active_people_count} personas</span><Button variant="ghost" size="icon" onClick={() => archive(item.ministry_id)} className="text-gray-400"><Archive className="h-4 w-4" /></Button></div></CardContent></Card>)}</div>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent><form onSubmit={create} className="space-y-4"><DialogHeader><DialogTitle>Crear Ministerio</DialogTitle><DialogDescription>Puede existir y recibir Personas aunque todavía no tenga líder.</DialogDescription></DialogHeader><div className="space-y-2"><Label>Nombre</Label><Input value={form.nombre} onChange={(e) => setForm((old) => ({ ...old, nombre: e.target.value }))} required /></div><div className="space-y-2"><Label>Descripción</Label><Textarea value={form.descripcion} onChange={(e) => setForm((old) => ({ ...old, descripcion: e.target.value }))} /></div><DialogFooter><Button variant="outline" type="button" onClick={() => setOpen(false)}>Cancelar</Button><Button className="bg-[#132443]">Crear Ministerio</Button></DialogFooter></form></DialogContent></Dialog>
  </div></div>;
}
