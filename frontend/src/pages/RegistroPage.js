import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Textarea } from '../components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { toast } from 'sonner';
import { Plus, Search, Pencil, Trash2, Users, UserPlus, Phone, MapPin, Filter, ArrowRight, Target, Copy, Check, Share2, Key } from 'lucide-react';
import { motion } from 'framer-motion';

const statusColors = {
  contactado: 'bg-blue-500 text-white',
  visitado: 'bg-amber-500 text-white',
  en_proceso: 'bg-purple-500 text-white',
  graduado: 'bg-emerald-500 text-white',
  inactivo: 'bg-gray-400 text-white',
};
const statusLabels = { contactado: 'Contactado', visitado: 'Visitado', en_proceso: 'En Proceso', graduado: 'Graduado', inactivo: 'Inactivo' };
const relationLabels = { familiar: 'Familiar', amigo: 'Amigo', conocido: 'Conocido', vecino: 'Vecino' };

export default function RegistroPage() {
  const { API, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [people, setPeople] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('todos');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPerson, setEditingPerson] = useState(null);
  const [form, setForm] = useState({ 
    nombre: '', 
    telefono: '', 
    direccion: '', 
    relacion: 'conocido', 
    estado: 'contactado', 
    semana_actual: 1, 
    notas: '',
    foto_url: '',
    edad: '',
    genero: '',
    ocupacion: '',
    estado_civil: '',
    mejor_horario: '',
    fecha_primer_contacto: '',
    como_conocio_iglesia: '',
  });
  const [credencialesModal, setCredencialesModal] = useState(false);
  const [nuevasCredenciales, setNuevasCredenciales] = useState(null);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [resetPasswordModal, setResetPasswordModal] = useState(false);
  const [resetCredenciales, setResetCredenciales] = useState(null);

  const handleResetPassword = async (personId) => {
    if (!window.confirm('¿Estás seguro de resetear la contraseña? Se generará una nueva.')) return;
    try {
      const res = await axios.post(`${API}/api/people/${personId}/reset-password`, {}, getAuthHeaders());
      setResetCredenciales(res.data);
      setResetPasswordModal(true);
      toast.success('Contraseña reseteada exitosamente');
    } catch (err) {
      toast.error('Error al resetear contraseña');
    }
  };

  const handlePhotoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    // Validate file type
    if (!file.type.startsWith('image/')) {
      toast.error('Por favor selecciona una imagen');
      return;
    }
    
    // Validate file size (max 2MB)
    if (file.size > 2 * 1024 * 1024) {
      toast.error('La imagen debe ser menor a 2MB');
      return;
    }
    
    setUploadingPhoto(true);
    
    try {
      // Convert to base64
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result;
        setForm({ ...form, foto_url: base64 });
        toast.success('Foto cargada');
        setUploadingPhoto(false);
      };
      reader.onerror = () => {
        toast.error('Error al cargar foto');
        setUploadingPhoto(false);
      };
      reader.readAsDataURL(file);
    } catch (err) {
      toast.error('Error al procesar foto');
      setUploadingPhoto(false);
    }
  };

  const fetchPeople = useCallback(async () => {
    try { 
      const res = await axios.get(`${API}/api/people`, getAuthHeaders()); 
      setPeople(res.data); 
    } catch (err) { 
      console.error(err); 
      toast.error('Error al cargar personas');
    } finally { 
      setLoading(false); 
    }
  }, [API, getAuthHeaders]);

  useEffect(() => { fetchPeople(); }, [fetchPeople]);

  const resetForm = () => { 
    setForm({ 
      nombre: '', 
      telefono: '', 
      direccion: '', 
      relacion: 'conocido', 
      estado: 'contactado', 
      semana_actual: 1, 
      notas: '',
      foto_url: '',
      edad: '',
      genero: '',
      ocupacion: '',
      estado_civil: '',
      mejor_horario: '',
      fecha_primer_contacto: '',
      como_conocio_iglesia: '',
    }); 
    setEditingPerson(null); 
  };

  const handleSave = async () => {
    if (!form.nombre.trim()) { toast.error('El nombre es requerido'); return; }

    // Sanitizar payload: convertir strings vacíos de campos numéricos a null
    // y normalizar tipos antes de enviar al backend (Pydantic es estricto).
    const payload = { ...form };
    // edad: '' -> null ; si viene, forzar a entero
    if (payload.edad === '' || payload.edad === undefined || payload.edad === null) {
      payload.edad = null;
    } else {
      const n = parseInt(payload.edad, 10);
      payload.edad = Number.isFinite(n) ? n : null;
    }
    // semana_actual: siempre entero válido (fallback 1)
    const sa = parseInt(payload.semana_actual, 10);
    payload.semana_actual = Number.isFinite(sa) && sa > 0 ? sa : 1;

    try {
      if (editingPerson) {
        await axios.put(`${API}/api/people/${editingPerson._id}`, payload, getAuthHeaders());
        toast.success('Persona actualizada');
      } else {
        const res = await axios.post(`${API}/api/people`, payload, getAuthHeaders());
        // Guardar credenciales para mostrar en modal
        setNuevasCredenciales({
          nombre: res.data.nombre,
          username: res.data.username,
          password: res.data.temp_password,
        });
        setCredencialesModal(true);
        toast.success('¡Persona registrada! Ya puedes comenzar su proceso de consolidación');
      }
      setDialogOpen(false);
      resetForm();
      fetchPeople();
    } catch (err) {
      // Extraer mensaje real del backend para facilitar debugging y transparencia al usuario
      let detalle = 'Error al guardar persona';
      const data = err?.response?.data;
      if (typeof data?.detail === 'string') {
        detalle = data.detail;
      } else if (Array.isArray(data?.detail) && data.detail[0]) {
        const d = data.detail[0];
        const campo = Array.isArray(d.loc) ? d.loc.slice(-1)[0] : 'campo';
        detalle = `Campo "${campo}": ${d.msg || 'valor inválido'}`;
      }
      toast.error(detalle);
    }
  };

  const handleEdit = (person) => {
    setEditingPerson(person);
    setForm({ 
      nombre: person.nombre, 
      telefono: person.telefono || '', 
      direccion: person.direccion || '', 
      relacion: person.relacion || 'conocido', 
      estado: person.estado || 'contactado', 
      semana_actual: person.semana_actual || 1, 
      notas: person.notas || '',
      foto_url: person.foto_url || '',
      edad: person.edad || '',
      genero: person.genero || '',
      ocupacion: person.ocupacion || '',
      estado_civil: person.estado_civil || '',
      mejor_horario: person.mejor_horario || '',
      fecha_primer_contacto: person.fecha_primer_contacto || '',
      como_conocio_iglesia: person.como_conocio_iglesia || '',
    });
    setDialogOpen(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('¿Estás seguro de eliminar esta persona? Se perderá todo su progreso.')) return;
    try { 
      await axios.delete(`${API}/api/people/${id}`, getAuthHeaders()); 
      toast.success('Persona eliminada'); 
      fetchPeople(); 
    } catch (err) { 
      toast.error('Error al eliminar'); 
    }
  };

  const handleContinueProcess = (person) => {
    // Navigate to the specific week page for this person
    navigate(`/persona/${person._id}/semana/${person.semana_actual}`);
  };

  const filtered = people.filter(p => {
    const matchSearch = p.nombre.toLowerCase().includes(search.toLowerCase()) || 
                       (p.telefono || '').includes(search) || 
                       (p.direccion || '').toLowerCase().includes(search.toLowerCase());
    const matchStatus = filterStatus === 'todos' || p.estado === filterStatus;
    return matchSearch && matchStatus;
  });

  // Stats
  const statsByStatus = people.reduce((acc, p) => { acc[p.estado] = (acc[p.estado] || 0) + 1; return acc; }, {});

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD]">
      <div className="px-3 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-8 space-y-4 sm:space-y-6">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <div className="relative rounded-2xl bg-gradient-to-r from-[#1B2A4A] to-[#2A3D63] p-6 sm:p-8 overflow-hidden">
            <div className="absolute inset-0 opacity-10">
              <div className="absolute inset-0" style={{
                backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(255,255,255,0.15) 1px, transparent 0)',
                backgroundSize: '32px 32px'
              }}></div>
            </div>
            <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full -translate-y-12 translate-x-12"></div>
            <div className="relative z-10 flex items-start justify-between flex-wrap gap-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Users className="w-5 h-5 text-[#C8A951]" />
                  <span className="text-[#C8A951] text-xs font-semibold uppercase tracking-widest">Gestión de Personas</span>
                </div>
                <h1 className="text-2xl sm:text-3xl font-bold text-white" style={{ fontFamily: 'Spectral, serif' }}>
                  Personas en Consolidación
                </h1>
                <p className="text-white/60 mt-1 text-sm">
                  {people.length} persona{people.length !== 1 ? 's' : ''} bajo tu liderazgo
                </p>
              </div>
              <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) resetForm(); }}>
                <DialogTrigger asChild>
                  <Button className="bg-[#C8A951] text-[#1B2A4A] hover:bg-[#E2CF8A] shadow-lg font-semibold" data-testid="registry-add-person-button">
                    <UserPlus className="w-4 h-4 mr-1.5" /> Nueva Persona
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle style={{ fontFamily: 'Spectral, serif' }}>
                      {editingPerson ? 'Editar Persona' : 'Registrar Nueva Persona'}
                    </DialogTitle>
                  </DialogHeader>
                  <div className="space-y-5 mt-2">
                    {/* Photo */}
                    <div className="space-y-1.5">
                      <Label>Foto de la Persona</Label>
                      <div className="flex gap-3">
                        <div className="flex-1">
                          <Input
                            type="file"
                            accept="image/*"
                            onChange={handlePhotoUpload}
                            disabled={uploadingPhoto}
                            className="cursor-pointer"
                          />
                          <p className="text-xs text-muted-foreground mt-1">O ingresa una URL:</p>
                          <Input
                            value={form.foto_url.startsWith('data:') ? '' : form.foto_url}
                            onChange={e => setForm({ ...form, foto_url: e.target.value })}
                            placeholder="https://ejemplo.com/foto.jpg"
                            className="mt-1"
                          />
                        </div>
                        {form.foto_url && (
                          <div className="shrink-0">
                            <img
                              src={form.foto_url}
                              alt="Preview"
                              className="w-20 h-20 rounded-full object-cover border-2 border-[#C8A951]"
                              onError={(e) => { e.target.style.display = 'none'; }}
                            />
                          </div>
                        )}
                      </div>
                      {uploadingPhoto && <p className="text-xs text-muted-foreground">Procesando foto...</p>}
                    </div>

                    {/* Basic Info */}
                    <div className="border-t pt-4">
                      <h3 className="font-semibold text-sm mb-3 text-[#1B2A4A]">Información Básica</h3>
                      <div className="space-y-3">
                        <div className="space-y-1.5">
                          <Label>Nombre Completo *</Label>
                          <Input value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })} 
                                 placeholder="Ej: María García" data-testid="person-name-input" />
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                          <div className="space-y-1.5">
                            <Label>Edad</Label>
                            <Input type="number" value={form.edad} onChange={e => setForm({ ...form, edad: e.target.value })} 
                                   placeholder="25" min="1" max="120" />
                          </div>
                          <div className="space-y-1.5">
                            <Label>Género</Label>
                            <Select value={form.genero} onValueChange={v => setForm({ ...form, genero: v })}>
                              <SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="masculino">Masculino</SelectItem>
                                <SelectItem value="femenino">Femenino</SelectItem>
                                <SelectItem value="otro">Otro</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-1.5">
                            <Label>Estado Civil</Label>
                            <Select value={form.estado_civil} onValueChange={v => setForm({ ...form, estado_civil: v })}>
                              <SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="soltero">Soltero/a</SelectItem>
                                <SelectItem value="casado">Casado/a</SelectItem>
                                <SelectItem value="divorciado">Divorciado/a</SelectItem>
                                <SelectItem value="viudo">Viudo/a</SelectItem>
                                <SelectItem value="union_libre">Unión Libre</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                        <div className="space-y-1.5">
                          <Label>Ocupación</Label>
                          <Input value={form.ocupacion} onChange={e => setForm({ ...form, ocupacion: e.target.value })} 
                                 placeholder="Ej: Maestro, Ingeniero, Estudiante..." />
                        </div>
                      </div>
                    </div>

                    {/* Contact Info */}
                    <div className="border-t pt-4">
                      <h3 className="font-semibold text-sm mb-3 text-[#1B2A4A]">Información de Contacto</h3>
                      <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                          <div className="space-y-1.5">
                            <Label>Teléfono</Label>
                            <Input value={form.telefono} onChange={e => setForm({ ...form, telefono: e.target.value })} 
                                   placeholder="(787) 555-1234" />
                          </div>
                          <div className="space-y-1.5">
                            <Label>Mejor Horario</Label>
                            <Select value={form.mejor_horario} onValueChange={v => setForm({ ...form, mejor_horario: v })}>
                              <SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="manana">Mañana (6am - 12pm)</SelectItem>
                                <SelectItem value="tarde">Tarde (12pm - 6pm)</SelectItem>
                                <SelectItem value="noche">Noche (6pm - 10pm)</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                        <div className="space-y-1.5">
                          <Label>Dirección</Label>
                          <Input value={form.direccion} onChange={e => setForm({ ...form, direccion: e.target.value })} 
                                 placeholder="Dirección completa" />
                        </div>
                      </div>
                    </div>

                    {/* Relationship & Status */}
                    <div className="border-t pt-4">
                      <h3 className="font-semibold text-sm mb-3 text-[#1B2A4A]">Proceso de Consolidación</h3>
                      <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                          <div className="space-y-1.5">
                            <Label>Relación</Label>
                            <Select value={form.relacion} onValueChange={v => setForm({ ...form, relacion: v })}>
                              <SelectTrigger><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="familiar">Familiar</SelectItem>
                                <SelectItem value="amigo">Amigo</SelectItem>
                                <SelectItem value="conocido">Conocido</SelectItem>
                                <SelectItem value="vecino">Vecino</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-1.5">
                            <Label>¿Cómo conoció la iglesia?</Label>
                            <Select value={form.como_conocio_iglesia} onValueChange={v => setForm({ ...form, como_conocio_iglesia: v })}>
                              <SelectTrigger><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="visiteo">Visiteo puerta a puerta</SelectItem>
                                <SelectItem value="familiar">Invitación de familiar</SelectItem>
                                <SelectItem value="amigo">Invitación de amigo</SelectItem>
                                <SelectItem value="evento">Evento de la iglesia</SelectItem>
                                <SelectItem value="redes">Redes sociales</SelectItem>
                                <SelectItem value="otro">Otro</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                          <div className="space-y-1.5">
                            <Label>Estado Actual</Label>
                            <Select value={form.estado} onValueChange={v => setForm({ ...form, estado: v })}>
                              <SelectTrigger><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="contactado">Contactado</SelectItem>
                                <SelectItem value="visitado">Visitado</SelectItem>
                                <SelectItem value="en_proceso">En Proceso</SelectItem>
                                <SelectItem value="graduado">Graduado</SelectItem>
                                <SelectItem value="inactivo">Inactivo</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-1.5">
                            <Label>Semana Actual</Label>
                            <Select value={String(form.semana_actual)} onValueChange={v => setForm({ ...form, semana_actual: parseInt(v) })}>
                              <SelectTrigger><SelectValue /></SelectTrigger>
                              <SelectContent>
                                {[1,2,3,4,5,6,7].map(n => (
                                  <SelectItem key={n} value={String(n)}>Semana {n}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-1.5">
                            <Label>Fecha Primer Contacto</Label>
                            <Input type="date" value={form.fecha_primer_contacto} 
                                   onChange={e => setForm({ ...form, fecha_primer_contacto: e.target.value })} />
                          </div>
                        </div>
                        <div className="space-y-1.5">
                          <Label>Notas / Necesidades Especiales</Label>
                          <Textarea value={form.notas} onChange={e => setForm({ ...form, notas: e.target.value })} 
                                    placeholder="Necesidades específicas, situación personal, áreas de oración, etc." rows={3} />
                        </div>
                      </div>
                    </div>

                    <Button className="w-full bg-[#1B2A4A] hover:bg-[#2A3D63] font-semibold" 
                            onClick={handleSave} data-testid="person-save-button">
                      {editingPerson ? 'Actualizar Persona' : 'Registrar Persona'}
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>
              
              {/* Modal de Credenciales */}
              <Dialog open={credencialesModal} onOpenChange={setCredencialesModal}>
                <DialogContent className="max-w-md">
                  <DialogHeader>
                    <DialogTitle className="text-center" style={{ fontFamily: 'Spectral, serif' }}>
                      <div className="flex flex-col items-center gap-2 mb-2">
                        <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center">
                          <Check className="w-8 h-8 text-green-600" />
                        </div>
                        <span className="text-xl">¡Persona Creada Exitosamente!</span>
                      </div>
                    </DialogTitle>
                  </DialogHeader>
                  {nuevasCredenciales && (
                    <div className="space-y-4">
                      <div className="bg-[#F5F0E8] rounded-lg p-4 border-2 border-[#C8A951]">
                        <p className="text-sm text-center mb-3 font-medium text-[#1B2A4A]">
                          Dale estas credenciales a <span className="font-bold">{nuevasCredenciales.nombre}</span>:
                        </p>
                        <div className="space-y-2 bg-white rounded-lg p-3">
                          <div>
                            <Label className="text-xs text-muted-foreground">Usuario</Label>
                            <div className="flex items-center gap-2 mt-1">
                              <code className="flex-1 bg-gray-100 px-3 py-2 rounded text-sm font-mono">
                                {nuevasCredenciales.username}
                              </code>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => {
                                  navigator.clipboard.writeText(nuevasCredenciales.username);
                                  toast.success('Usuario copiado');
                                }}
                              >
                                <Copy className="w-4 h-4" />
                              </Button>
                            </div>
                          </div>
                          <div>
                            <Label className="text-xs text-muted-foreground">Contraseña</Label>
                            <div className="flex items-center gap-2 mt-1">
                              <code className="flex-1 bg-gray-100 px-3 py-2 rounded text-sm font-mono">
                                {nuevasCredenciales.password}
                              </code>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => {
                                  navigator.clipboard.writeText(nuevasCredenciales.password);
                                  toast.success('Contraseña copiada');
                                }}
                              >
                                <Copy className="w-4 h-4" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex gap-2">
                        <Button
                          className="flex-1 bg-[#25D366] hover:bg-[#20BA5A] text-white font-semibold"
                          onClick={() => {
                            const mensaje = `¡Hola ${nuevasCredenciales.nombre}! 🎉\n\nTe han registrado en el proceso de consolidación de Casa de Oración Ven y Ve.\n\nTus credenciales de acceso son:\n👤 Usuario: ${nuevasCredenciales.username}\n🔑 Contraseña: ${nuevasCredenciales.password}\n\nIngresa a tu panel para ver tu progreso y ganar estrellas!`;
                            window.open(`https://wa.me/?text=${encodeURIComponent(mensaje)}`, '_blank');
                          }}
                        >
                          <Share2 className="w-4 h-4 mr-2" />
                          Enviar por WhatsApp
                        </Button>
                        <Button
                          variant="outline"
                          onClick={() => {
                            const texto = `Usuario: ${nuevasCredenciales.username}\nContraseña: ${nuevasCredenciales.password}`;
                            navigator.clipboard.writeText(texto);
                            toast.success('Credenciales copiadas al portapapeles');
                          }}
                        >
                          <Copy className="w-4 h-4 mr-2" />
                          Copiar Todo
                        </Button>
                      </div>
                      
                      <Button
                        className="w-full bg-[#1B2A4A] hover:bg-[#2A3D63]"
                        onClick={() => setCredencialesModal(false)}
                      >
                        Cerrar
                      </Button>
                    </div>
                  )}
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </motion.div>

        {/* Status Stats */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} 
                    className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {Object.entries(statusLabels).map(([key, label]) => (
            <motion.div key={key} 
              whileHover={{ y: -2, scale: 1.02 }} 
              onClick={() => setFilterStatus(filterStatus === key ? 'todos' : key)}
              className={`rounded-xl p-4 cursor-pointer transition-all duration-200 border-2 ${
                filterStatus === key ? 'border-[#C8A951] shadow-lg' : 'border-transparent'
              } ${statusColors[key].replace('text-white', '')} text-white shadow-sm hover:shadow-md`}
            >
              <p className="text-2xl font-bold">{statsByStatus[key] || 0}</p>
              <p className="text-xs text-white/80 font-medium mt-0.5">{label}</p>
            </motion.div>
          ))}
        </motion.div>

        {/* Filters */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }} 
                    className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input placeholder="Buscar por nombre, teléfono o dirección..." 
                   value={search} 
                   onChange={e => setSearch(e.target.value)} 
                   className="pl-9 bg-white shadow-sm" 
                   data-testid="registry-search-input" />
          </div>
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-full sm:w-48 bg-white shadow-sm">
              <Filter className="w-3.5 h-3.5 mr-1.5" />
              <SelectValue placeholder="Filtrar" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="todos">Todos los Estados</SelectItem>
              <SelectItem value="contactado">Contactado</SelectItem>
              <SelectItem value="visitado">Visitado</SelectItem>
              <SelectItem value="en_proceso">En Proceso</SelectItem>
              <SelectItem value="graduado">Graduado</SelectItem>
              <SelectItem value="inactivo">Inactivo</SelectItem>
            </SelectContent>
          </Select>
        </motion.div>

        {/* Table */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <div className="bg-white rounded-xl shadow-md border border-[#E7E2D6] overflow-hidden">
            {loading ? (
              <div className="p-8 text-center text-muted-foreground">Cargando personas...</div>
            ) : filtered.length === 0 ? (
              <div className="p-12 text-center">
                <div className="w-20 h-20 mx-auto rounded-full bg-gradient-to-br from-[#1B2A4A] to-[#2A3D63] flex items-center justify-center mb-4">
                  <Users className="w-10 h-10 text-[#C8A951]" />
                </div>
                <p className="text-xl font-bold mb-2" style={{ fontFamily: 'Spectral, serif' }}>
                  {people.length === 0 ? 'Comienza tu lista de 30' : 'No se encontraron resultados'}
                </p>
                <p className="text-muted-foreground text-sm mb-6 max-w-md mx-auto">
                  {people.length === 0 
                    ? 'La primera semana es de GANAR. Registra tu lista de 30 personas (familiares, amigos, conocidos) para comenzar el proceso de consolidación.'
                    : 'Intenta ajustar los filtros de búsqueda para encontrar a la persona que buscas.'}
                </p>
                {people.length === 0 && (
                  <Button className="bg-[#C8A951] text-[#1B2A4A] hover:bg-[#E2CF8A] font-semibold shadow-lg" 
                          onClick={() => setDialogOpen(true)}>
                    <UserPlus className="w-4 h-4 mr-1.5" /> Registrar Primera Persona
                  </Button>
                )}
              </div>
            ) : (
              <>
                {/* Vista mobile: Cards */}
                <div className="md:hidden divide-y divide-[#E7E2D6]">
                  {filtered.map((person, idx) => (
                    <motion.div
                      key={person._id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: idx * 0.03 }}
                      className="p-3 space-y-3 hover:bg-[#F5F0E8]/50 transition-colors"
                      data-testid={`person-card-${person._id}`}
                    >
                      <div className="flex items-start gap-3">
                        {person.foto_url ? (
                          <img src={person.foto_url} alt={person.nombre}
                               className="w-12 h-12 rounded-full object-cover border-2 border-[#C8A951] shrink-0"
                               onError={(e) => { e.target.style.display = 'none'; }} />
                        ) : (
                          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[#1B2A4A] to-[#2A3D63] flex items-center justify-center text-white font-bold shrink-0">
                            {person.nombre.charAt(0)}
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="font-bold text-[#1B2A4A] truncate">{person.nombre}</p>
                              {person.edad && (
                                <p className="text-xs text-muted-foreground truncate">
                                  {person.edad} años{person.ocupacion ? ` • ${person.ocupacion}` : ''}
                                </p>
                              )}
                            </div>
                            <Badge className="bg-[#1B2A4A] text-white font-bold shrink-0">
                              S{person.semana_actual}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                            <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${statusColors[person.estado] || 'bg-gray-200'}`}>
                              {statusLabels[person.estado] || person.estado}
                            </span>
                            <Badge variant="outline" className="capitalize text-[10px] font-medium px-1.5 py-0">
                              {relationLabels[person.relacion] || person.relacion}
                            </Badge>
                          </div>
                          {person.telefono && (
                            <div className="flex items-center gap-1.5 mt-1.5 text-xs text-muted-foreground">
                              <Phone className="w-3 h-3 shrink-0" />
                              <span className="truncate">{person.telefono}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex gap-1.5">
                        <Button
                          size="sm"
                          className="flex-1 bg-[#1FA6A0] text-white hover:bg-[#1FA6A0]/90 font-medium text-xs h-9"
                          onClick={() => handleContinueProcess(person)}
                          data-testid={`continue-process-${person._id}`}
                        >
                          <Target className="w-3.5 h-3.5 mr-1" />
                          Continuar
                          <ArrowRight className="w-3.5 h-3.5 ml-1" />
                        </Button>
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-9 w-9 shrink-0 hover:bg-blue-50 hover:text-blue-600"
                          onClick={() => handleResetPassword(person._id)}
                          title="Resetear Contraseña"
                        >
                          <Key className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-9 w-9 shrink-0 hover:bg-[#C8A951]/10 hover:text-[#C8A951]"
                          onClick={() => handleEdit(person)}
                        >
                          <Pencil className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="icon"
                          className="h-9 w-9 shrink-0 text-destructive hover:bg-red-50"
                          onClick={() => handleDelete(person._id)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </motion.div>
                  ))}
                </div>

                {/* Vista desktop: Tabla */}
                <div className="hidden md:block overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gradient-to-r from-[#F5F0E8] to-[#FAFAF8]">
                      <TableHead className="font-bold text-[#1B2A4A]">Persona</TableHead>
                      <TableHead className="font-bold text-[#1B2A4A]">Contacto</TableHead>
                      <TableHead className="font-bold text-[#1B2A4A]">Info</TableHead>
                      <TableHead className="font-bold text-[#1B2A4A]">Estado</TableHead>
                      <TableHead className="font-bold text-[#1B2A4A]">Semana</TableHead>
                      <TableHead className="text-right font-bold text-[#1B2A4A]">Acciones</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((person, idx) => (
                      <motion.tr 
                        key={person._id} 
                        initial={{ opacity: 0 }} 
                        animate={{ opacity: 1 }} 
                        transition={{ delay: idx * 0.03 }}
                        className="hover:bg-[#F5F0E8]/50 transition-colors border-b border-[#E7E2D6] group" 
                        data-testid={`person-row-${person._id}`}
                      >
                        <TableCell>
                          <div className="flex items-center gap-3">
                            {person.foto_url ? (
                              <img src={person.foto_url} alt={person.nombre} 
                                   className="w-10 h-10 rounded-full object-cover border-2 border-[#C8A951]"
                                   onError={(e) => { e.target.style.display = 'none'; }} />
                            ) : (
                              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#1B2A4A] to-[#2A3D63] flex items-center justify-center text-white font-bold text-sm">
                                {person.nombre.charAt(0)}
                              </div>
                            )}
                            <div>
                              <p className="font-bold text-[#1B2A4A]">{person.nombre}</p>
                              {person.edad && <p className="text-xs text-muted-foreground">{person.edad} años{person.ocupacion ? ` • ${person.ocupacion}` : ''}</p>}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {person.telefono ? (
                            <div className="space-y-0.5">
                              <div className="flex items-center gap-1.5">
                                <Phone className="w-3.5 h-3.5" />
                                {person.telefono}
                              </div>
                              {person.mejor_horario && (
                                <p className="text-xs text-muted-foreground/70">
                                  Mejor: {person.mejor_horario === 'manana' ? 'Mañana' : person.mejor_horario === 'tarde' ? 'Tarde' : 'Noche'}
                                </p>
                              )}
                            </div>
                          ) : '-'}
                        </TableCell>
                        <TableCell>
                          <div className="space-y-1">
                            <Badge variant="outline" className="capitalize text-xs font-medium">
                              {relationLabels[person.relacion] || person.relacion}
                            </Badge>
                            {person.genero && (
                              <p className="text-xs text-muted-foreground">{person.genero === 'masculino' ? 'M' : person.genero === 'femenino' ? 'F' : 'Otro'}</p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className={`text-xs px-3 py-1.5 rounded-full font-semibold ${statusColors[person.estado] || 'bg-gray-200'}`}>
                            {statusLabels[person.estado] || person.estado}
                          </span>
                        </TableCell>
                        <TableCell>
                          <Badge className="bg-[#1B2A4A] text-white font-bold">
                            S{person.semana_actual}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1.5">
                            <Button 
                              size="sm" 
                              className="bg-[#1FA6A0] text-white hover:bg-[#1FA6A0]/90 font-medium text-xs h-8"
                              onClick={() => handleContinueProcess(person)}
                              data-testid={`continue-process-${person._id}`}
                            >
                              <Target className="w-3.5 h-3.5 mr-1" />
                              Continuar Proceso
                              <ArrowRight className="w-3.5 h-3.5 ml-1" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="h-8 w-8 hover:bg-blue-50 hover:text-blue-600"
                              onClick={() => handleResetPassword(person._id)}
                              title="Resetear Contraseña"
                            >
                              <Key className="w-3.5 h-3.5" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="h-8 w-8 hover:bg-[#C8A951]/10 hover:text-[#C8A951]" 
                              onClick={() => handleEdit(person)}
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="h-8 w-8 text-destructive hover:bg-red-50" 
                              onClick={() => handleDelete(person._id)}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </TableCell>
                      </motion.tr>
                    ))}
                  </TableBody>
                </Table>
                </div>
              </>
            )}
          </div>
        </motion.div>
        
        {/* Modal de Contraseña Reseteada */}
        <Dialog open={resetPasswordModal} onOpenChange={setResetPasswordModal}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle style={{ fontFamily: 'Spectral, serif' }}>
                Contraseña Reseteada
              </DialogTitle>
            </DialogHeader>
            {resetCredenciales && (
              <div className="space-y-4">
                <div className="bg-blue-50 rounded-lg p-4 border-2 border-blue-200">
                  <p className="text-sm text-center mb-3 text-blue-900">
                    Nueva contraseña generada:
                  </p>
                  <div className="space-y-2 bg-white rounded-lg p-3">
                    <div>
                      <Label className="text-xs text-muted-foreground">Usuario</Label>
                      <div className="flex items-center gap-2 mt-1">
                        <code className="flex-1 bg-gray-100 px-3 py-2 rounded text-sm font-mono">
                          {resetCredenciales.username}
                        </code>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            navigator.clipboard.writeText(resetCredenciales.username);
                            toast.success('Usuario copiado');
                          }}
                        >
                          <Copy className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground">Nueva Contraseña</Label>
                      <div className="flex items-center gap-2 mt-1">
                        <code className="flex-1 bg-gray-100 px-3 py-2 rounded text-sm font-mono">
                          {resetCredenciales.new_password}
                        </code>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            navigator.clipboard.writeText(resetCredenciales.new_password);
                            toast.success('Contraseña copiada');
                          }}
                        >
                          <Copy className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
                <Button
                  className="w-full bg-[#1B2A4A] hover:bg-[#2A3D63]"
                  onClick={() => setResetPasswordModal(false)}
                >
                  Cerrar
                </Button>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
