import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from '../components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { Users, TrendingUp, Award, AlertCircle, ArrowRight, Crown, UserPlus, Trash2, Key, Shield, Presentation, DoorOpen } from 'lucide-react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { StatusBadge, ProgressVsExpected } from '../components/StatusBadge';
import { LOGO_IGLESIA } from '../data/presentationData';
import { BRAND } from '../config/brand';

export default function DashboardGeneralPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  // Gestión de pastores
  const [pastors, setPastors] = useState([]);
  const [loadingPastors, setLoadingPastors] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ nombre: '', email: '', password: '' });
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [createdCreds, setCredentials] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await axios.get(`${API}/api/dashboard/role-based`, getAuthHeaders());
        setData(res.data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    fetchPastors();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [API]);

  const fetchPastors = async () => {
    setLoadingPastors(true);
    try {
      const res = await axios.get(`${API}/api/pastor/pastors`, getAuthHeaders());
      setPastors(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingPastors(false);
    }
  };

  const handleCreate = async () => {
    const { nombre, email, password } = form;
    if (!nombre.trim() || !email.trim() || !password.trim()) {
      toast.error('Completa todos los campos');
      return;
    }
    if (password.length < 6) {
      toast.error('La contraseña debe tener al menos 6 caracteres');
      return;
    }
    setSaving(true);
    try {
      const res = await axios.post(
        `${API}/api/pastor/pastors`,
        { nombre: nombre.trim(), email: email.trim().toLowerCase(), password },
        getAuthHeaders()
      );
      toast.success(`Pastor ${res.data.nombre} creado con éxito`);
      setCredentials({ nombre: res.data.nombre, email: res.data.email, password });
      setForm({ nombre: '', email: '', password: '' });
      setCreateOpen(false);
      fetchPastors();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al crear pastor');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await axios.delete(`${API}/api/pastor/pastors/${deleteTarget._id}`, getAuthHeaders());
      toast.success(`${deleteTarget.nombre} eliminado`);
      setDeleteTarget(null);
      fetchPastors();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al eliminar');
    }
  };

  if (loading) return <div className="p-8 text-center">Cargando...</div>;
  if (!data) return <div className="p-8 text-center">Error al cargar datos</div>;

  const { lideres, total_lideres, total_personas_global } = data;
  const lideresMetaBaja = lideres.filter(l => l.estado?.key === 'meta_baja');
  const lideresExcelente = lideres.filter(l => l.estado?.key === 'excelente');

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD]">
      <div className="px-3 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-8 space-y-4 sm:space-y-6">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <div className="relative rounded-2xl bg-gradient-to-r from-[#14213D] via-[#1B2A4A] to-[#0E5B5A] p-5 sm:p-8 overflow-hidden">
            <div className="absolute inset-0 opacity-10">
              <div className="absolute inset-0" style={{
                backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(255,255,255,0.15) 1px, transparent 0)',
                backgroundSize: '32px 32px'
              }}></div>
            </div>
            <div className="absolute right-4 top-0 h-20 w-20 -translate-y-8 rounded-full bg-white/5"></div>
            <div className="relative z-10">
              <div className="flex items-center gap-3 sm:gap-4 mb-3">
                <div className="w-12 h-12 sm:w-14 sm:h-14 bg-[#0F1A33] rounded-lg p-1 flex items-center justify-center shrink-0 border border-[#C8A951]/30">
                  <img src={LOGO_IGLESIA} alt={BRAND.church}
                    className="w-full h-full object-contain logo-transparent" />
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Crown className="w-4 h-4 sm:w-5 sm:h-5 text-yellow-300" />
                    <span className="text-yellow-300 text-[10px] sm:text-xs font-semibold uppercase tracking-widest">Acceso Maestro</span>
                  </div>
                  <h1 className="text-xl sm:text-3xl font-bold text-white leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
                    {BRAND.name}
                  </h1>
                  <p className="mt-1 text-xs font-semibold text-[#E7D28D] sm:text-sm">Panel General de Pastores · {BRAND.subtitle}</p>
                </div>
              </div>
              <p className="text-white/60 text-xs sm:text-sm">
                {BRAND.slogan} Supervisión ministerial para cuidar personas, líderes y procesos.
              </p>
            </div>
          </div>
        </motion.div>

        {/* Botón: Presentación Sistema Celular */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.08 }}
        >
          <button
            onClick={() => navigate('/presentacion')}
            className="w-full group relative rounded-2xl overflow-hidden shadow-xl border-2 border-[#C8A951]/40 hover:border-[#C8A951] transition-all hover:shadow-2xl"
            data-testid="btn-presentacion-celular"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-[#1B2A4A] via-[#2A3D63] to-purple-900" />
            <div className="absolute inset-0 opacity-20" style={{
              backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(200,169,81,0.4) 1px, transparent 0)',
              backgroundSize: '24px 24px'
            }} />
            <div className="absolute right-4 top-0 h-20 w-20 -translate-y-8 rounded-full bg-[#C8A951]/10 blur-2xl transition-colors group-hover:bg-[#C8A951]/20" />

            <div className="relative z-10 flex items-center gap-4 p-4 sm:p-5 text-left">
              <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-xl bg-gradient-to-br from-[#C8A951] to-[#E2CF8A] flex items-center justify-center shrink-0 shadow-lg group-hover:scale-105 transition-transform">
                <DoorOpen className="w-7 h-7 sm:w-8 sm:h-8 text-[#1B2A4A]" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Presentation className="w-3.5 h-3.5 text-[#C8A951]" />
                  <span className="text-[10px] sm:text-xs text-[#C8A951] font-bold uppercase tracking-widest">Presentación Interactiva</span>
                </div>
                <h3 className="text-lg sm:text-xl font-bold text-white leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
                  Manual - La Ley de las 7 Semanas
                </h3>
                <p className="text-xs sm:text-sm text-white/60 mt-0.5 hidden sm:block">
                  Sistema Celular · 9 Puertas · Presentar / Ver / Imprimir
                </p>
              </div>
              <ArrowRight className="w-5 h-5 sm:w-6 sm:h-6 text-[#C8A951] shrink-0 group-hover:translate-x-1 transition-transform" />
            </div>
          </button>
        </motion.div>

        {/* Stats Cards */}
        <div className="grid grid-cols-3 md:grid-cols-3 gap-2 sm:gap-4">
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <Card className="border-2 border-purple-200 shadow-lg hover:shadow-xl transition-shadow h-full">
              <CardHeader className="pb-2 sm:pb-3 px-3 sm:px-6 pt-3 sm:pt-6">
                <CardTitle className="text-[10px] sm:text-sm font-medium text-muted-foreground leading-tight">Total Líderes</CardTitle>
              </CardHeader>
              <CardContent className="px-3 sm:px-6 pb-3 sm:pb-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-2xl sm:text-3xl font-bold text-purple-600">{total_lideres}</p>
                    <p className="text-[10px] sm:text-xs text-muted-foreground mt-1 hidden sm:block">Líderes activos</p>
                  </div>
                  <Users className="w-8 h-8 sm:w-12 sm:h-12 text-purple-600/20 hidden xs:block" />
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
            <Card className="border-2 border-indigo-200 shadow-lg hover:shadow-xl transition-shadow h-full">
              <CardHeader className="pb-2 sm:pb-3 px-3 sm:px-6 pt-3 sm:pt-6">
                <CardTitle className="text-[10px] sm:text-sm font-medium text-muted-foreground leading-tight">Total Personas</CardTitle>
              </CardHeader>
              <CardContent className="px-3 sm:px-6 pb-3 sm:pb-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-2xl sm:text-3xl font-bold text-indigo-600">{total_personas_global}</p>
                    <p className="text-[10px] sm:text-xs text-muted-foreground mt-1 hidden sm:block">En consolidación</p>
                  </div>
                  <TrendingUp className="w-8 h-8 sm:w-12 sm:h-12 text-indigo-600/20 hidden xs:block" />
                </div>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <Card className="border-2 border-red-200 shadow-lg hover:shadow-xl transition-shadow h-full">
              <CardHeader className="pb-2 sm:pb-3 px-3 sm:px-6 pt-3 sm:pt-6">
                <CardTitle className="text-[10px] sm:text-sm font-medium text-muted-foreground leading-tight">Meta Baja</CardTitle>
              </CardHeader>
              <CardContent className="px-3 sm:px-6 pb-3 sm:pb-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-2xl sm:text-3xl font-bold text-red-600">{lideresMetaBaja.length}</p>
                    <p className="text-[10px] sm:text-xs text-muted-foreground mt-1 hidden sm:block">Requieren atención</p>
                  </div>
                  <AlertCircle className="w-8 h-8 sm:w-12 sm:h-12 text-red-600/20 hidden xs:block" />
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Leaders Table / Card List */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
          <Card className="shadow-xl border border-[#E7E2D6]">
            <CardHeader>
              <CardTitle style={{ fontFamily: 'Spectral, serif' }}>Líderes y su Desempeño</CardTitle>
            </CardHeader>
            <CardContent>
              {/* Vista mobile: Cards */}
              <div className="md:hidden space-y-3">
                {lideres.map((lider, idx) => (
                  <motion.div
                    key={lider._id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.04 }}
                    className="p-4 rounded-xl border border-[#E7E2D6] bg-gradient-to-br from-[#F5F0E8]/40 to-[#FAFAF8] space-y-3"
                    data-testid={`lider-card-${lider._id}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="font-bold text-[#1B2A4A] text-base truncate">{lider.nombre}</p>
                        <p className="text-xs text-muted-foreground truncate">{lider.email}</p>
                      </div>
                      <StatusBadge status={lider.estado} />
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                      <div className="text-center p-2 bg-white rounded-lg border border-[#E7E2D6]">
                        <p className="text-[10px] uppercase text-muted-foreground tracking-wider">Personas</p>
                        <p className="text-lg font-bold text-[#1B2A4A]">{lider.total_personas}</p>
                      </div>
                      <div className="text-center p-2 bg-white rounded-lg border border-[#E7E2D6]">
                        <p className="text-[10px] uppercase text-muted-foreground tracking-wider">Activas</p>
                        <p className="text-lg font-bold text-purple-600">{lider.activas}</p>
                      </div>
                      <div className="text-center p-2 bg-white rounded-lg border border-[#E7E2D6]">
                        <p className="text-[10px] uppercase text-muted-foreground tracking-wider">Grad.</p>
                        <p className="text-lg font-bold text-emerald-600">{lider.graduadas}</p>
                      </div>
                    </div>

                    {lider.estado && lider.total_personas > 0 && (
                      <ProgressVsExpected status={lider.estado} compact={false} />
                    )}

                    <Button
                      size="sm"
                      className="w-full bg-[#1B2A4A] hover:bg-[#2A3D63] text-white font-medium"
                      onClick={() => navigate(`/lider/${lider._id}/dashboard`)}
                    >
                      Entrar al Líder
                      <ArrowRight className="w-3.5 h-3.5 ml-1" />
                    </Button>
                  </motion.div>
                ))}
              </div>

              {/* Vista desktop: Tabla */}
              <div className="hidden md:block overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gradient-to-r from-[#F5F0E8] to-[#FAFAF8]">
                      <TableHead className="font-bold text-[#1B2A4A]">Líder</TableHead>
                      <TableHead className="font-bold text-[#1B2A4A]">Total Personas</TableHead>
                      <TableHead className="font-bold text-[#1B2A4A]">Activas</TableHead>
                      <TableHead className="font-bold text-[#1B2A4A]">Graduadas</TableHead>
                      <TableHead className="font-bold text-[#1B2A4A]">Promedio Semana</TableHead>
                      <TableHead className="font-bold text-[#1B2A4A]">Estado</TableHead>
                      <TableHead className="text-right font-bold text-[#1B2A4A]">Acciones</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {lideres.map((lider, idx) => (
                      <motion.tr
                        key={lider._id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: idx * 0.03 }}
                        className="hover:bg-[#F5F0E8]/50 transition-colors border-b border-[#E7E2D6]"
                      >
                        <TableCell>
                          <div>
                            <p className="font-bold text-[#1B2A4A]">{lider.nombre}</p>
                            <p className="text-xs text-muted-foreground">{lider.email}</p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Users className="w-4 h-4 text-muted-foreground" />
                            <span className="font-semibold">{lider.total_personas}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge className="bg-purple-500 text-white">{lider.activas}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge className="bg-emerald-500 text-white">{lider.graduadas}</Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-gradient-to-r from-indigo-500 to-purple-500"
                                style={{ width: `${(lider.promedio_semana / 7) * 100}%` }}
                              />
                            </div>
                            <span className="text-sm font-semibold">{lider.promedio_semana}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-1 min-w-[140px]">
                            <StatusBadge status={lider.estado} />
                            {lider.estado && lider.total_personas > 0 && (
                              <ProgressVsExpected status={lider.estado} compact={true} />
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            className="bg-[#1B2A4A] hover:bg-[#2A3D63] text-white font-medium"
                            onClick={() => navigate(`/lider/${lider._id}/dashboard`)}
                          >
                            Entrar al Líder
                            <ArrowRight className="w-3.5 h-3.5 ml-1" />
                          </Button>
                        </TableCell>
                      </motion.tr>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Gestión de Pastores */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <Card className="shadow-xl border-2 border-[#C8A951]/40 bg-gradient-to-br from-[#C8A951]/5 via-[#FAFAF8] to-[#E2CF8A]/10">
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Shield className="w-5 h-5 text-[#C8A951]" />
                  <div>
                    <CardTitle style={{ fontFamily: 'Spectral, serif' }}>Gestión de Pastores</CardTitle>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Otorga acceso maestro a otros pastores del ministerio
                    </p>
                  </div>
                </div>
                <Button
                  onClick={() => setCreateOpen(true)}
                  className="bg-[#1B2A4A] hover:bg-[#2A3D63] text-white gap-2"
                  data-testid="btn-crear-pastor"
                >
                  <UserPlus className="w-4 h-4" />
                  Nuevo Pastor
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loadingPastors ? (
                <p className="text-center text-muted-foreground py-4">Cargando...</p>
              ) : pastors.length === 0 ? (
                <p className="text-center text-muted-foreground py-4">No hay pastores registrados</p>
              ) : (
                <div className="space-y-2">
                  {pastors.map((p, idx) => (
                    <motion.div
                      key={p._id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.04 }}
                      className="flex items-center justify-between gap-3 p-3 bg-white rounded-lg border border-[#E7E2D6] hover:border-[#C8A951] transition-colors"
                      data-testid={`pastor-row-${p._id}`}
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <div className="w-11 h-11 rounded-full bg-gradient-to-br from-[#C8A951] to-[#E2CF8A] flex items-center justify-center text-[#1B2A4A] font-bold flex-shrink-0">
                          <Crown className="w-5 h-5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="font-bold text-sm text-[#1B2A4A] truncate">{p.nombre}</p>
                            {p.is_current && (
                              <Badge className="bg-[#1FA6A0] text-white text-[10px] px-1.5 py-0">
                                Tú
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground truncate">{p.email}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge className="bg-[#C8A951] text-[#1B2A4A] font-semibold gap-1">
                          <Crown className="w-3 h-3" />
                          Acceso Maestro
                        </Badge>
                        {!p.is_current && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-600 hover:bg-red-50 hover:text-red-700"
                            onClick={() => setDeleteTarget(p)}
                            data-testid={`btn-eliminar-pastor-${p._id}`}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        )}
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Modal: Crear Pastor */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-[440px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2" style={{ fontFamily: 'Spectral, serif' }}>
              <UserPlus className="w-5 h-5 text-[#C8A951]" />
              Nuevo Pastor con Acceso Maestro
            </DialogTitle>
            <DialogDescription>
              Este pastor tendrá los mismos privilegios que tú: ver a todos los líderes y sus personas.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="pastor-nombre">Nombre completo</Label>
              <Input
                id="pastor-nombre"
                data-testid="input-pastor-nombre"
                value={form.nombre}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
                placeholder="Pastor Juan Pérez"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pastor-email">Email</Label>
              <Input
                id="pastor-email"
                type="email"
                data-testid="input-pastor-email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="juan@venyve.com"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pastor-password">Contraseña inicial</Label>
              <Input
                id="pastor-password"
                type="text"
                data-testid="input-pastor-password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                placeholder="Mínimo 6 caracteres"
              />
              <p className="text-[11px] text-muted-foreground">
                Comparte estas credenciales de forma segura con el nuevo pastor.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={saving}>
              Cancelar
            </Button>
            <Button
              onClick={handleCreate}
              disabled={saving}
              className="bg-[#1B2A4A] hover:bg-[#2A3D63] text-white"
              data-testid="btn-confirmar-crear-pastor"
            >
              {saving ? 'Creando...' : 'Crear Pastor'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal: Credenciales creadas */}
      <Dialog open={!!createdCreds} onOpenChange={(v) => !v && setCredentials(null)}>
        <DialogContent className="sm:max-w-[440px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-[#1FA6A0]" style={{ fontFamily: 'Spectral, serif' }}>
              <Crown className="w-5 h-5" />
              ¡Pastor Creado con Éxito!
            </DialogTitle>
            <DialogDescription>
              Comparte estas credenciales con el nuevo pastor. Esta es la única vez que se muestra la contraseña.
            </DialogDescription>
          </DialogHeader>
          {createdCreds && (
            <div className="space-y-3 py-2">
              <div className="bg-gradient-to-br from-[#1B2A4A] to-[#2A3D63] rounded-lg p-4 space-y-2 text-white">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-white/60">Nombre</p>
                  <p className="font-bold text-lg">{createdCreds.nombre}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-white/60">Email</p>
                  <p className="font-mono text-sm bg-white/10 px-2 py-1 rounded">{createdCreds.email}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-white/60">Contraseña</p>
                  <p className="font-mono text-sm bg-[#C8A951] text-[#1B2A4A] px-2 py-1 rounded font-bold">{createdCreds.password}</p>
                </div>
              </div>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => {
                  navigator.clipboard.writeText(
                    `Acceso a ${BRAND.name} (Acceso Maestro)\nEmail: ${createdCreds.email}\nContraseña: ${createdCreds.password}`
                  );
                  toast.success('Credenciales copiadas');
                }}
                data-testid="btn-copiar-credenciales-pastor"
              >
                Copiar Credenciales
              </Button>
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setCredentials(null)} className="bg-[#1B2A4A] hover:bg-[#2A3D63] text-white">
              Entendido
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Alert: Confirmar eliminación */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(v) => !v && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Eliminar a {deleteTarget?.nombre}?</AlertDialogTitle>
            <AlertDialogDescription>
              Este pastor perderá todo acceso al sistema. Esta acción no se puede deshacer.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-red-600 hover:bg-red-700 text-white"
              data-testid="btn-confirmar-eliminar-pastor"
            >
              Sí, eliminar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
