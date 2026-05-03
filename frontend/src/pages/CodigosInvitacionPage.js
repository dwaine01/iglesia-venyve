import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { RoleBadge } from '../components/RoleBadge';
import { toast } from 'sonner';
import {
  KeyRound, Plus, Copy, Check, Clock, Ban, AlertCircle,
  CheckCircle2, X, ArrowLeft, Sparkles, ExternalLink,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const CAN_CREATE = {
  maestro: ['supervisor', 'lider', 'obrero', 'discipulo'],
  supervisor: ['lider'],
  lider: ['obrero'],
  obrero: ['discipulo'],
  discipulo: [],
};
const ROLE_LABEL = {
  supervisor: 'Supervisor',
  lider: 'Líder de Grupo',
  obrero: 'Obrero',
  discipulo: 'Discípulo',
};

function statusInfo(status) {
  switch (status) {
    case 'active':  return { label: 'Activo',    icon: Sparkles, cls: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
    case 'used':    return { label: 'Usado',     icon: CheckCircle2, cls: 'bg-blue-50 text-blue-700 border-blue-200' };
    case 'expired': return { label: 'Expirado',  icon: Clock, cls: 'bg-amber-50 text-amber-700 border-amber-200' };
    case 'revoked': return { label: 'Revocado',  icon: Ban, cls: 'bg-red-50 text-red-700 border-red-200' };
    default:        return { label: status,      icon: AlertCircle, cls: 'bg-slate-50 text-slate-700 border-slate-200' };
  }
}

export default function CodigosInvitacionPage() {
  const { user, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);

  const allowedRoles = CAN_CREATE[user?.rol] || [];

  const reload = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/users/invitations`, getAuthHeaders());
      setItems(res.data.items || []);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'No se pudieron cargar los códigos');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const grouped = {
    active: items.filter((i) => i.status === 'active'),
    used: items.filter((i) => i.status === 'used'),
    expired: items.filter((i) => i.status === 'expired'),
    revoked: items.filter((i) => i.status === 'revoked'),
  };

  return (
    <div className="space-y-6" data-testid="codigos-page">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <Button variant="ghost" size="sm" onClick={() => navigate('/equipo')} className="mb-2 -ml-2 text-muted-foreground hover:text-[#1B2A4A]">
            <ArrowLeft className="w-3.5 h-3.5 mr-1" /> Mi Equipo
          </Button>
          <p className="text-[10px] uppercase tracking-[0.35em] text-[#C8A951] font-bold">Invitaciones</p>
          <h1 className="text-2xl sm:text-3xl font-bold text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>Códigos de Invitación</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Genera códigos para que tus subordinados se registren con su propia contraseña.
          </p>
        </div>
        {allowedRoles.length > 0 && (
          <Button onClick={() => setCreateOpen(true)} className="bg-[#C8A951] hover:bg-[#E2CF8A] text-[#1B2A4A] font-bold" data-testid="create-invitation-button">
            <Plus className="w-4 h-4 mr-2" /> Generar código
          </Button>
        )}
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
        </div>
      ) : (
        <>
          {/* Activos */}
          <Section title={`Activos (${grouped.active.length})`}>
            {grouped.active.length === 0 ? (
              <EmptyState
                hasPermission={allowedRoles.length > 0}
                onCreate={() => setCreateOpen(true)}
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {grouped.active.map((inv) => <ActiveCard key={inv.id} inv={inv} onChange={reload} />)}
              </div>
            )}
          </Section>

          {/* Otros */}
          {(grouped.used.length + grouped.expired.length + grouped.revoked.length) > 0 && (
            <Section title="Historial">
              <div className="space-y-2">
                {[...grouped.used, ...grouped.expired, ...grouped.revoked].map((inv) => (
                  <HistoryRow key={inv.id} inv={inv} />
                ))}
              </div>
            </Section>
          )}
        </>
      )}

      <CreateInvitationDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        allowedRoles={allowedRoles}
        onCreated={reload}
      />
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <h2 className="text-sm font-bold uppercase tracking-widest text-[#C8A951] mb-3">{title}</h2>
      {children}
    </div>
  );
}

function EmptyState({ hasPermission, onCreate }) {
  return (
    <Card className="border-[#E7E2D6]">
      <CardContent className="p-8 text-center">
        <KeyRound className="w-10 h-10 mx-auto text-[#C8A951]/50 mb-3" />
        <p className="text-sm font-semibold text-[#1B2A4A] mb-1">Sin códigos activos</p>
        {hasPermission ? (
          <>
            <p className="text-xs text-muted-foreground mb-4">Genera uno para invitar a alguien a unirse a tu equipo.</p>
            <Button size="sm" onClick={onCreate} className="bg-[#1B2A4A] hover:bg-[#2A3D63] text-white">
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Crear ahora
            </Button>
          </>
        ) : (
          <p className="text-xs text-muted-foreground">Tu rol no genera invitaciones.</p>
        )}
      </CardContent>
    </Card>
  );
}

function ActiveCard({ inv, onChange }) {
  const { getAuthHeaders } = useAuth();
  const [copied, setCopied] = useState(null);
  const [busy, setBusy] = useState(false);

  const fullUrl = `${window.location.origin}/registro/${inv.code}`;
  const expiresIn = (() => {
    const exp = new Date(inv.expires_at);
    const diff = exp - Date.now();
    if (diff <= 0) return 'expirado';
    const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
    return days === 1 ? '1 día' : `${days} días`;
  })();

  const copy = async (kind) => {
    try {
      await navigator.clipboard.writeText(kind === 'code' ? inv.code : fullUrl);
      setCopied(kind);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      toast.error('No se pudo copiar');
    }
  };

  const revoke = async () => {
    if (!window.confirm('¿Revocar este código? La persona ya no podrá usarlo.')) return;
    setBusy(true);
    try {
      await axios.delete(`${API}/api/users/invitations/${inv.id}`, getAuthHeaders());
      toast.success('Código revocado');
      onChange();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'No se pudo revocar');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="border-[#C8A951]/30 bg-gradient-to-br from-[#FBF9F3] to-white" data-testid={`invitation-card-${inv.id}`}>
      <CardContent className="p-5">
        <div className="flex items-center justify-between mb-3">
          <RoleBadge rol={inv.target_role} size="sm" />
          <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold flex items-center gap-1">
            <Clock className="w-3 h-3" /> Expira en {expiresIn}
          </span>
        </div>

        <div className="bg-[#0F1A33] rounded-xl p-4 mb-3 text-center">
          <p className="text-[10px] uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-1">Código</p>
          <p className="text-3xl font-bold text-white font-mono tracking-[0.3em]" data-testid={`code-value-${inv.id}`}>
            {inv.code}
          </p>
        </div>

        <div className="flex flex-col gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => copy('code')}
            className="w-full border-[#1B2A4A]/30 text-[#1B2A4A] hover:bg-[#1B2A4A] hover:text-white"
            data-testid={`copy-code-${inv.id}`}
          >
            {copied === 'code' ? <><Check className="w-3.5 h-3.5 mr-1.5" /> Copiado</> : <><Copy className="w-3.5 h-3.5 mr-1.5" /> Copiar código</>}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => copy('url')}
            className="w-full border-[#1B2A4A]/30 text-[#1B2A4A] hover:bg-[#1B2A4A] hover:text-white"
            data-testid={`copy-url-${inv.id}`}
          >
            {copied === 'url' ? <><Check className="w-3.5 h-3.5 mr-1.5" /> Enlace copiado</> : <><ExternalLink className="w-3.5 h-3.5 mr-1.5" /> Copiar enlace de registro</>}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={revoke}
            disabled={busy}
            className="w-full text-red-600 hover:text-red-700 hover:bg-red-50"
            data-testid={`revoke-${inv.id}`}
          >
            <Ban className="w-3.5 h-3.5 mr-1.5" /> Revocar
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function HistoryRow({ inv }) {
  const info = statusInfo(inv.status);
  const Icon = info.icon;
  return (
    <div className={`flex items-center gap-3 px-4 py-3 rounded-lg border ${info.cls}`} data-testid={`history-row-${inv.id}`}>
      <Icon className="w-4 h-4 shrink-0" />
      <p className="font-mono font-bold tracking-widest min-w-[10ch]">{inv.code}</p>
      <RoleBadge rol={inv.target_role} size="sm" />
      <span className="text-xs uppercase tracking-widest font-bold ml-auto">{info.label}</span>
    </div>
  );
}

function CreateInvitationDialog({ open, onOpenChange, allowedRoles, onCreated }) {
  const { getAuthHeaders } = useAuth();
  const [rol, setRol] = useState(allowedRoles[0] || '');
  const [days, setDays] = useState(7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  React.useEffect(() => {
    if (open) {
      setRol(allowedRoles[0] || '');
      setDays(7);
      setError('');
    }
  }, [open, allowedRoles]);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const res = await axios.post(`${API}/api/users/invitations`, {
        target_role: rol,
        expires_in_days: Number(days),
      }, getAuthHeaders());
      toast.success(`Código ${res.data.code} listo para compartir`);
      onCreated();
      onOpenChange(false);
    } catch (err) {
      setError(err.response?.data?.detail || 'No se pudo generar el código');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-[#C8A951]" />
            Generar código de invitación
          </DialogTitle>
          <DialogDescription>
            La persona se registrará con un correo y contraseña propios y quedará bajo tu supervisión.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label className="text-xs uppercase tracking-widest font-bold text-muted-foreground">Rol del invitado</Label>
            <div className="mt-2 flex flex-wrap gap-2">
              {allowedRoles.map((r) => (
                <button
                  type="button"
                  key={r}
                  onClick={() => setRol(r)}
                  className={`px-3 py-1.5 rounded-full border text-xs font-bold uppercase tracking-wider transition-colors ${
                    rol === r
                      ? 'bg-[#1B2A4A] text-white border-[#1B2A4A]'
                      : 'bg-white text-[#1B2A4A] border-[#1B2A4A]/30 hover:border-[#1B2A4A]'
                  }`}
                  data-testid={`invite-role-${r}`}
                >
                  {ROLE_LABEL[r]}
                </button>
              ))}
            </div>
          </div>

          <div>
            <Label htmlFor="days" className="text-xs uppercase tracking-widest font-bold text-muted-foreground">Vigencia</Label>
            <div className="mt-2 flex gap-2">
              {[3, 7, 14, 30].map((d) => (
                <button
                  type="button"
                  key={d}
                  onClick={() => setDays(d)}
                  className={`flex-1 px-3 py-2 rounded-lg border text-sm font-semibold transition-colors ${
                    days === d
                      ? 'bg-[#C8A951] text-[#1B2A4A] border-[#C8A951]'
                      : 'bg-white text-[#1B2A4A] border-[#E7E2D6] hover:border-[#C8A951]'
                  }`}
                  data-testid={`invite-days-${d}`}
                >
                  {d} {d === 1 ? 'día' : 'días'}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>Cancelar</Button>
            <Button type="submit" disabled={busy || !rol} className="bg-[#C8A951] hover:bg-[#E2CF8A] text-[#1B2A4A] font-bold" data-testid="invite-submit">
              {busy ? 'Generando...' : 'Generar código'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
