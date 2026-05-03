import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { RoleBadge } from '../components/RoleBadge';
import { toast } from 'sonner';
import {
  Users2, KeyRound, UserPlus, Search, AlertCircle, ArrowRight, Trash2,
  Sparkles, Mail, Lock, User, ChevronDown, ChevronRight
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const CAN_CREATE = {
  maestro: ['supervisor', 'lider', 'obrero', 'discipulo'],
  supervisor: ['lider'],
  lider: ['obrero'],
  obrero: ['discipulo'],
  discipulo: [],
};
const ROLE_LABEL = { supervisor: 'Supervisor', lider: 'Líder de Grupo', obrero: 'Obrero', discipulo: 'Discípulo' };

export default function MiEquipoPage() {
  const { user, getAuthHeaders } = useAuth();
  const navigate = useNavigate();

  const [team, setTeam] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [createOpen, setCreateOpen] = useState(false);

  const allowedRoles = CAN_CREATE[user?.rol] || [];

  const reload = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/users/my-team?recursive=true`, getAuthHeaders());
      setTeam(res.data.items || []);
      setStats(res.data.stats || {});
    } catch (err) {
      toast.error(err.response?.data?.detail || 'No se pudo cargar el equipo');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = team.filter((u) => {
    if (filter !== 'all' && u.rol !== filter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        u.nombre?.toLowerCase().includes(q) ||
        u.email?.toLowerCase().includes(q) ||
        (u.apellido || '').toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6" data-testid="mi-equipo-page">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-[0.35em] text-[#C8A951] font-bold">Gestión de equipo</p>
          <h1 className="text-2xl sm:text-3xl font-bold text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>Mi Equipo</h1>
          <p className="text-sm text-muted-foreground mt-1">{team.length} {team.length === 1 ? 'persona' : 'personas'} bajo tu supervisión</p>
        </div>
        {allowedRoles.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => navigate('/equipo/codigos')} variant="outline" className="border-[#1B2A4A]/30 text-[#1B2A4A] hover:bg-[#1B2A4A] hover:text-white" data-testid="go-codigos">
              <KeyRound className="w-4 h-4 mr-2" /> Códigos
            </Button>
            <Button onClick={() => setCreateOpen(true)} className="bg-[#1B2A4A] hover:bg-[#2A3D63] text-white" data-testid="open-create-dialog">
              <UserPlus className="w-4 h-4 mr-2" /> Crear cuenta directa
            </Button>
          </div>
        )}
      </div>

      {/* Filtros */}
      <Card className="border-[#E7E2D6]">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar por nombre o correo..."
                className="pl-9"
                data-testid="team-search"
              />
            </div>
            <Tabs value={filter} onValueChange={setFilter}>
              <TabsList>
                <TabsTrigger value="all" data-testid="filter-all">Todos</TabsTrigger>
                {Object.entries(stats).map(([rol, count]) => count > 0 && (
                  <TabsTrigger key={rol} value={rol} data-testid={`filter-${rol}`}>
                    {ROLE_LABEL[rol] || rol} ({count})
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
        </CardContent>
      </Card>

      {/* Tabla */}
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
        </div>
      ) : filtered.length === 0 ? (
        <Card className="border-[#E7E2D6]">
          <CardContent className="p-12 text-center">
            <Sparkles className="w-10 h-10 mx-auto text-[#C8A951]/50 mb-3" />
            <p className="text-sm font-semibold text-[#1B2A4A] mb-1">
              {team.length === 0 ? 'Tu equipo está vacío' : 'Sin resultados'}
            </p>
            {team.length === 0 && allowedRoles.length > 0 && (
              <>
                <p className="text-xs text-muted-foreground mb-4">Crea una cuenta directa o genera un código de invitación.</p>
                <div className="flex justify-center gap-2">
                  <Button size="sm" onClick={() => setCreateOpen(true)} className="bg-[#1B2A4A] hover:bg-[#2A3D63] text-white">
                    Crear cuenta
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => navigate('/equipo/codigos')}>
                    Generar código
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card className="border-[#E7E2D6] overflow-hidden">
          <ul className="divide-y divide-[#E7E2D6]">
            {filtered.map((u) => (
              <TeamRow key={u.id} user={u} onChange={reload} />
            ))}
          </ul>
        </Card>
      )}

      {/* Dialog crear directo */}
      <CreateUserDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        allowedRoles={allowedRoles}
        onCreated={reload}
      />
    </div>
  );
}

function TeamRow({ user: u, onChange }) {
  const { getAuthHeaders, user: me } = useAuth();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  const handleDeactivate = async () => {
    setBusy(true);
    try {
      await axios.delete(`${API}/api/users/${u.id}`, getAuthHeaders());
      toast.success(`${u.nombre} desactivado`);
      onChange();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'No se pudo desactivar');
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  };

  const canDelete = me?.rol === 'maestro' || u.superior_id === me?.id;

  return (
    <li className="px-4 sm:px-6 py-3 flex items-center gap-3 hover:bg-[#FBF9F3] transition-colors" data-testid={`team-row-${u.id}`}>
      <div className="shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-[#1B2A4A] to-[#2A3D63] text-white flex items-center justify-center font-bold uppercase">
        {u.nombre?.[0] || '?'}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-[#1B2A4A] truncate">{u.nombre}{u.apellido ? ` ${u.apellido}` : ''}</p>
        <p className="text-xs text-muted-foreground truncate">{u.email}</p>
      </div>
      <RoleBadge rol={u.rol} size="sm" className="shrink-0" />
      {canDelete && (
        <Button
          size="icon"
          variant="ghost"
          onClick={() => setConfirming(true)}
          className="shrink-0 text-red-600 hover:text-red-700 hover:bg-red-50"
          data-testid={`deactivate-${u.id}`}
          aria-label="Desactivar"
        >
          <Trash2 className="w-4 h-4" />
        </Button>
      )}

      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>¿Desactivar a {u.nombre}?</DialogTitle>
            <DialogDescription>
              No podrá iniciar sesión. Esta acción se puede revertir luego marcándolo como activo.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirming(false)} disabled={busy}>Cancelar</Button>
            <Button onClick={handleDeactivate} disabled={busy} className="bg-red-600 hover:bg-red-700 text-white" data-testid={`confirm-deactivate-${u.id}`}>
              {busy ? 'Desactivando...' : 'Desactivar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </li>
  );
}

function CreateUserDialog({ open, onOpenChange, allowedRoles, onCreated }) {
  const { getAuthHeaders } = useAuth();
  const [form, setForm] = useState({
    nombre: '', apellido: '', email: '', password: '', telefono: '', rol: allowedRoles[0] || '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  React.useEffect(() => {
    if (!open) {
      setForm({ nombre: '', apellido: '', email: '', password: '', telefono: '', rol: allowedRoles[0] || '' });
      setError('');
    } else if (allowedRoles.length > 0 && !allowedRoles.includes(form.rol)) {
      setForm((f) => ({ ...f, rol: allowedRoles[0] }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await axios.post(`${API}/api/users/create-direct`, {
        nombre: form.nombre.trim(),
        apellido: form.apellido.trim() || undefined,
        email: form.email.trim().toLowerCase(),
        password: form.password,
        telefono: form.telefono.trim() || undefined,
        rol: form.rol,
      }, getAuthHeaders());
      toast.success(`${form.nombre} creado correctamente`);
      onCreated();
      onOpenChange(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'No se pudo crear el usuario');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserPlus className="w-5 h-5 text-[#C8A951]" />
            Crear cuenta directa
          </DialogTitle>
          <DialogDescription>
            La cuenta queda asignada automáticamente a ti como superior.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          {/* Rol */}
          <div>
            <Label className="text-xs uppercase tracking-widest font-bold text-muted-foreground">Rol</Label>
            <div className="mt-2 flex flex-wrap gap-2">
              {allowedRoles.map((r) => (
                <button
                  type="button"
                  key={r}
                  onClick={() => setForm((f) => ({ ...f, rol: r }))}
                  className={`px-3 py-1.5 rounded-full border text-xs font-bold uppercase tracking-wider transition-colors ${
                    form.rol === r
                      ? 'bg-[#1B2A4A] text-white border-[#1B2A4A]'
                      : 'bg-white text-[#1B2A4A] border-[#1B2A4A]/30 hover:border-[#1B2A4A]'
                  }`}
                  data-testid={`role-option-${r}`}
                >
                  {ROLE_LABEL[r]}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="cu-nombre" className="text-xs uppercase tracking-widest font-bold text-muted-foreground">Nombre</Label>
              <Input id="cu-nombre" value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} required data-testid="create-nombre" />
            </div>
            <div>
              <Label htmlFor="cu-apellido" className="text-xs uppercase tracking-widest font-bold text-muted-foreground">Apellido</Label>
              <Input id="cu-apellido" value={form.apellido} onChange={(e) => setForm((f) => ({ ...f, apellido: e.target.value }))} data-testid="create-apellido" />
            </div>
          </div>
          <div>
            <Label htmlFor="cu-email" className="text-xs uppercase tracking-widest font-bold text-muted-foreground">Correo</Label>
            <Input id="cu-email" type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} required data-testid="create-email" />
          </div>
          <div>
            <Label htmlFor="cu-password" className="text-xs uppercase tracking-widest font-bold text-muted-foreground">Contraseña temporal</Label>
            <Input id="cu-password" type="text" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} required minLength={6} placeholder="Mínimo 6 caracteres" data-testid="create-password" />
            <p className="text-[10px] text-muted-foreground mt-1">Compártela con la persona para que entre por primera vez.</p>
          </div>
          <div>
            <Label htmlFor="cu-telefono" className="text-xs uppercase tracking-widest font-bold text-muted-foreground">Teléfono (opcional)</Label>
            <Input id="cu-telefono" value={form.telefono} onChange={(e) => setForm((f) => ({ ...f, telefono: e.target.value }))} data-testid="create-telefono" />
          </div>

          {error && (
            <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>Cancelar</Button>
            <Button type="submit" disabled={busy || !form.rol} className="bg-[#1B2A4A] hover:bg-[#2A3D63] text-white" data-testid="create-submit">
              {busy ? 'Creando...' : 'Crear cuenta'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
