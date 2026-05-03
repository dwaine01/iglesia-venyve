import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { RoleBadge } from '../components/RoleBadge';
import { Crown, Shield, Users, Hammer, Sprout, Users2, KeyRound, ArrowRight, Sparkles } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const ROLE_ICON = { maestro: Crown, supervisor: Shield, lider: Users, obrero: Hammer, discipulo: Sprout };
const ROLE_LABEL = { maestro: 'Maestro', supervisor: 'Supervisor', lider: 'Líder', obrero: 'Obrero', discipulo: 'Discípulo' };

export default function DashboardJerarquicoPage() {
  const { user, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    axios.get(`${API}/api/dashboard/hierarchy`, getAuthHeaders())
      .then((res) => { if (mounted) setData(res.data); })
      .catch(() => { if (mounted) setData(null); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <div className="space-y-6" data-testid="dashboard-loading">
        <Skeleton className="h-32 w-full rounded-2xl" />
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}
        </div>
        <Skeleton className="h-72 w-full rounded-2xl" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-20">
        <p className="text-muted-foreground">No se pudo cargar el dashboard.</p>
      </div>
    );
  }

  const stats = data.stats_by_role || {};
  const isObrero = user?.rol === 'obrero';
  const isDiscipulo = user?.rol === 'discipulo';

  return (
    <div className="space-y-8" data-testid="dashboard-jerarquico">
      {/* Hero personalizado por rol */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#0F1A33] via-[#1B2A4A] to-[#2A3D63] text-white p-6 sm:p-10">
        <div className="absolute inset-0 opacity-[0.06]" style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, white 1px, transparent 0)', backgroundSize: '32px 32px' }} />
        <div className="relative flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-[10px] uppercase tracking-[0.35em] text-[#C8A951] font-bold mb-2">Dashboard</p>
            <h1 className="text-3xl sm:text-4xl font-bold leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
              Hola, {user?.nombre} · <span className="text-[#C8A951]">{ROLE_LABEL[user?.rol]}</span>
            </h1>
            <p className="mt-2 text-sm text-white/70 max-w-xl">
              {isDiscipulo
                ? 'Tus tareas y materiales aparecerán aquí pronto.'
                : isObrero
                ? `Tu equipo: ${data.discipulos_count || 0} de ${data.max_discipulos} discípulos asignados.`
                : `Tienes ${data.team_total} personas en tu árbol y ${data.active_invitations} invitaciones activas.`}
            </p>
          </div>
          {!isDiscipulo && (
            <div className="flex flex-col sm:flex-row gap-2">
              <Button onClick={() => navigate('/equipo')} className="bg-[#C8A951] hover:bg-[#E2CF8A] text-[#1B2A4A] font-bold" data-testid="hero-go-equipo">
                <Users2 className="w-4 h-4 mr-2" /> Mi Equipo
              </Button>
              <Button onClick={() => navigate('/equipo/codigos')} variant="outline" className="border-white/30 text-white hover:bg-white/10 hover:text-white" data-testid="hero-go-codigos">
                <KeyRound className="w-4 h-4 mr-2" /> Generar código
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Stats por rol del subarbol */}
      {!isDiscipulo && (
        <div>
          <h2 className="text-sm font-bold uppercase tracking-widest text-[#C8A951] mb-3">Mi árbol</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {Object.entries(ROLE_LABEL).map(([rol, label]) => {
              const Icon = ROLE_ICON[rol];
              const count = stats[rol] || 0;
              const visible = user?.rol === 'maestro' ? true : count > 0 || rol === 'discipulo';
              if (!visible && rol === 'maestro') return null;
              return (
                <Card key={rol} className="border-[#E7E2D6]" data-testid={`stat-card-${rol}`}>
                  <CardContent className="p-4 flex items-center gap-3">
                    <div className="shrink-0 w-10 h-10 rounded-lg bg-[#1B2A4A] text-[#C8A951] flex items-center justify-center">
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs uppercase tracking-widest text-muted-foreground font-bold">{label}</p>
                      <p className="text-2xl font-bold text-[#1B2A4A] tabular-nums">{count}</p>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* Subordinados directos */}
      {!isDiscipulo && (
        <Card className="border-[#E7E2D6]">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <Users2 className="w-5 h-5 text-[#C8A951]" />
                Subordinados directos
              </CardTitle>
              <Button variant="ghost" size="sm" onClick={() => navigate('/equipo')} className="text-[#1B2A4A] hover:bg-[#1B2A4A]/5">
                Ver todos <ArrowRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {data.direct_subordinates.length === 0 ? (
              <div className="text-center py-10 px-4">
                <Sparkles className="w-10 h-10 mx-auto text-[#C8A951]/40 mb-3" />
                <p className="text-sm font-semibold text-[#1B2A4A] mb-1">Tu equipo está vacío</p>
                <p className="text-xs text-muted-foreground mb-4">Genera un código o crea cuentas directamente desde Mi Equipo.</p>
                <Button onClick={() => navigate('/equipo')} className="bg-[#1B2A4A] hover:bg-[#2A3D63] text-white" data-testid="empty-go-equipo">
                  Ir a Mi Equipo
                </Button>
              </div>
            ) : (
              <ul className="divide-y divide-[#E7E2D6]">
                {data.direct_subordinates.map((u) => (
                  <li key={u.id} className="py-3 flex items-center gap-3" data-testid={`direct-sub-${u.id}`}>
                    <div className="shrink-0 w-9 h-9 rounded-full bg-[#1B2A4A] text-white flex items-center justify-center font-bold uppercase">
                      {u.nombre?.[0] || '?'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-[#1B2A4A] truncate">{u.nombre}{u.apellido ? ` ${u.apellido}` : ''}</p>
                      <p className="text-xs text-muted-foreground truncate">{u.email}</p>
                    </div>
                    <RoleBadge rol={u.rol} size="sm" />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      {/* Vista Discipulo */}
      {isDiscipulo && (
        <Card className="border-[#E7E2D6]">
          <CardContent className="p-8 text-center">
            <Sprout className="w-12 h-12 mx-auto text-[#C8A951] mb-4" />
            <h3 className="text-xl font-bold text-[#1B2A4A] mb-2" style={{ fontFamily: 'Spectral, serif' }}>Bienvenido al proceso</h3>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              Tu obrero te asignará tareas, videos y libros conforme avances en las 7 semanas. Esta sección se activará muy pronto.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
