import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import {
  NotebookPen, Home, Users, Heart, Sparkles, CalendarDays,
  Save, Loader2, Trash2, Pencil, X, CheckCircle2, TrendingUp
} from 'lucide-react';

// ==================== helpers ====================
const todayIso = () => new Date().toISOString().slice(0, 10);

const formatFechaLarga = (iso) => {
  if (!iso) return '';
  try {
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString('es-DO', {
      weekday: 'long', day: '2-digit', month: 'long', year: 'numeric',
    });
  } catch {
    return iso;
  }
};

const METRICS = [
  { key: 'casas_visitadas',     label: 'Casas visitadas',     icon: Home,      accent: 'from-[#1FA6A0] to-[#3FB8AF]', text: '#1FA6A0' },
  { key: 'personas_contactadas',label: 'Personas contactadas',icon: Users,     accent: 'from-[#3B5BA5] to-[#5578C2]', text: '#3B5BA5' },
  { key: 'personas_ganadas',    label: 'Personas ganadas',    icon: Heart,     accent: 'from-[#C8A951] to-[#E2CF8A]', text: '#C8A951' },
  { key: 'oraciones_realizadas',label: 'Oraciones realizadas',icon: Sparkles,  accent: 'from-[#7C5DB8] to-[#A688D4]', text: '#7C5DB8' },
];

// ==================== subcomponentes ====================
const StatCard = ({ label, value, tone = 'default', icon: Icon, hint }) => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    className="relative overflow-hidden rounded-2xl border border-[#C8A951]/20 bg-gradient-to-br from-[#0F1A33] to-[#1B2A4A] p-5 shadow-lg"
    data-testid={`stat-${tone}`}
  >
    <div className="pointer-events-none absolute right-2 top-0 h-20 w-20 -translate-y-8 rounded-full bg-[#C8A951]/10 blur-2xl" />
    <div className="flex items-start justify-between relative z-10">
      <div>
        <p className="text-[10px] uppercase tracking-[0.25em] text-[#C8A951] font-bold">{label}</p>
        <p className="text-4xl font-bold text-white mt-1.5" style={{ fontFamily: 'Spectral, serif' }}>{value}</p>
        {hint && <p className="text-[11px] text-white/50 mt-1">{hint}</p>}
      </div>
      {Icon && (
        <div className="p-2 rounded-lg bg-[#C8A951]/15 border border-[#C8A951]/30">
          <Icon className="w-4 h-4 text-[#C8A951]" />
        </div>
      )}
    </div>
  </motion.div>
);

const MiniBarChart = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="text-center py-10 text-white/40 text-sm italic">
        Aún no hay registros diarios. Empieza hoy y mira cómo crece el fruto.
      </div>
    );
  }
  const max = Math.max(
    ...data.map((d) => d.casas + d.contactadas + d.ganadas + d.oraciones),
    1
  );
  return (
    <div className="flex items-end gap-1.5 h-32 pt-2" data-testid="mini-bar-chart">
      {data.map((d) => {
        const total = d.casas + d.contactadas + d.ganadas + d.oraciones;
        const h = Math.max(4, Math.round((total / max) * 100));
        const dd = new Date(d.fecha + 'T00:00:00');
        const label = dd.toLocaleDateString('es-DO', { day: '2-digit', month: 'short' });
        return (
          <div key={d.fecha} className="flex-1 flex flex-col items-center gap-1 min-w-0">
            <div className="w-full rounded-t-md bg-gradient-to-t from-[#C8A951] via-[#E2CF8A] to-[#C8A951]/60 transition-[height] duration-500"
                 style={{ height: `${h}%` }}
                 title={`${label}: ${total} actividades`} />
            <span className="text-[9px] text-white/50 truncate w-full text-center">{label}</span>
          </div>
        );
      })}
    </div>
  );
};

// ==================== página principal ====================
export default function BitacoraPage() {
  const { API, getAuthHeaders, user } = useAuth();

  const [entries, setEntries] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);

  const emptyForm = {
    fecha: todayIso(),
    casas_visitadas: '',
    personas_contactadas: '',
    personas_ganadas: '',
    oraciones_realizadas: '',
    notas: '',
  };
  const [form, setForm] = useState(emptyForm);

  // ---- API ----
  const fetchAll = useCallback(async () => {
    try {
      const [entriesRes, statsRes] = await Promise.all([
        axios.get(`${API}/api/journal`, getAuthHeaders()),
        axios.get(`${API}/api/journal/stats`, getAuthHeaders()),
      ]);
      setEntries(entriesRes.data || []);
      setStats(statsRes.data);
    } catch (err) {
      toast.error('No se pudo cargar la bitácora');
    } finally {
      setLoading(false);
    }
  }, [API, getAuthHeaders]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // ---- handlers ----
  const sanitizePayload = (f) => {
    const toInt = (v) => {
      if (v === '' || v === null || v === undefined) return 0;
      const n = parseInt(v, 10);
      return Number.isFinite(n) && n >= 0 ? n : 0;
    };
    return {
      fecha: f.fecha || todayIso(),
      casas_visitadas: toInt(f.casas_visitadas),
      personas_contactadas: toInt(f.personas_contactadas),
      personas_ganadas: toInt(f.personas_ganadas),
      oraciones_realizadas: toInt(f.oraciones_realizadas),
      notas: (f.notas || '').trim(),
    };
  };

  const handleSave = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    const payload = sanitizePayload(form);
    // Pequeña validación UX: pide al menos 1 dato o nota
    const total = payload.casas_visitadas + payload.personas_contactadas + payload.personas_ganadas + payload.oraciones_realizadas;
    if (total === 0 && !payload.notas) {
      toast.warning('Agrega al menos un número o una nota para guardar esta jornada.');
      return;
    }
    setSaving(true);
    try {
      if (editingId) {
        await axios.put(`${API}/api/journal/${editingId}`, payload, getAuthHeaders());
        toast.success('Jornada actualizada');
      } else {
        await axios.post(`${API}/api/journal`, payload, getAuthHeaders());
        toast.success('¡Jornada registrada! Dios honra tu trabajo.');
      }
      setForm(emptyForm);
      setEditingId(null);
      await fetchAll();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Error al guardar la jornada');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (entry) => {
    setEditingId(entry.id);
    setForm({
      fecha: entry.fecha,
      casas_visitadas: String(entry.casas_visitadas ?? ''),
      personas_contactadas: String(entry.personas_contactadas ?? ''),
      personas_ganadas: String(entry.personas_ganadas ?? ''),
      oraciones_realizadas: String(entry.oraciones_realizadas ?? ''),
      notas: entry.notas || '',
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setForm(emptyForm);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('¿Eliminar esta jornada de la bitácora?')) return;
    try {
      await axios.delete(`${API}/api/journal/${id}`, getAuthHeaders());
      toast.success('Jornada eliminada');
      await fetchAll();
    } catch {
      toast.error('No se pudo eliminar');
    }
  };

  // ---- render ----
  return (
    <div className="min-h-full bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] px-4 sm:px-6 py-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* HERO */}
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#0F1A33] via-[#1B2A4A] to-[#2A3D63] text-white p-6 sm:p-8 shadow-xl"
          data-testid="bitacora-hero"
        >
          <div className="absolute inset-0 opacity-[0.08] pointer-events-none" style={{
            backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(200,169,81,0.6) 1px, transparent 0)',
            backgroundSize: '28px 28px'
          }} />
          <div className="pointer-events-none absolute right-0 top-0 h-56 w-56 -translate-y-24 rounded-full bg-[#C8A951]/10 blur-3xl" />
          <div className="relative z-10 flex items-start gap-4">
            <div className="p-3 rounded-2xl bg-[#C8A951]/15 border border-[#C8A951]/40 shrink-0">
              <NotebookPen className="w-6 h-6 text-[#C8A951]" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-[0.3em] text-[#C8A951] font-bold">Registro Ministerial</p>
              <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold mt-1 leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
                Bitácora <span className="text-[#C8A951] italic">Evangelística</span>
              </h1>
              <p className="text-sm sm:text-base text-white/70 mt-2 max-w-2xl leading-relaxed">
                Registra el fruto de cada jornada en el campo: casas visitadas, personas contactadas,
                decisiones por Cristo y oraciones elevadas. Aquí queda escrito lo que Dios está haciendo a través de {user?.nombre || 'ti'}.
              </p>
            </div>
          </div>
        </motion.div>

        {/* STATS CARDS */}
        {stats && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4" data-testid="stats-grid">
            <StatCard
              label="Hoy"
              value={stats.hoy?.entradas || 0}
              hint={`${stats.hoy?.casas_visitadas || 0} casas · ${stats.hoy?.personas_contactadas || 0} contactos`}
              icon={CalendarDays}
              tone="today"
            />
            <StatCard
              label="Esta semana"
              value={(stats.semana?.casas_visitadas || 0) + (stats.semana?.personas_contactadas || 0)}
              hint={`${stats.semana?.personas_ganadas || 0} personas ganadas`}
              icon={TrendingUp}
              tone="week"
            />
            <StatCard
              label="Este mes"
              value={stats.mes?.personas_contactadas || 0}
              hint={`${stats.mes?.entradas || 0} jornadas registradas`}
              icon={Users}
              tone="month"
            />
            <StatCard
              label="Total acumulado"
              value={stats.total?.personas_ganadas || 0}
              hint={`personas ganadas (${stats.total?.oraciones_realizadas || 0} oraciones)`}
              icon={Heart}
              tone="total"
            />
          </div>
        )}

        {/* FORMULARIO + LISTA */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 sm:gap-6">
          {/* FORMULARIO */}
          <motion.form
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            onSubmit={handleSave}
            className="lg:col-span-2 relative overflow-hidden rounded-2xl bg-white border border-[#1B2A4A]/10 shadow-md p-5 sm:p-6 space-y-4"
            data-testid="bitacora-form"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[10px] uppercase tracking-[0.25em] text-[#C8A951] font-bold">
                  {editingId ? 'Editando jornada' : 'Registrar jornada'}
                </p>
                <h2 className="text-xl font-bold text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>
                  {editingId ? 'Actualizar datos del día' : 'Hoy salí al campo'}
                </h2>
              </div>
              {editingId && (
                <button
                  type="button"
                  onClick={handleCancelEdit}
                  className="p-1.5 rounded-lg hover:bg-[#1B2A4A]/5 text-[#1B2A4A]/60 hover:text-[#1B2A4A] transition-colors"
                  aria-label="Cancelar edición"
                  data-testid="btn-cancelar-edicion"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            <div>
              <Label htmlFor="fecha" className="text-xs font-semibold text-[#1B2A4A]/70">Fecha de la jornada</Label>
              <Input
                id="fecha"
                type="date"
                value={form.fecha}
                onChange={(e) => setForm({ ...form, fecha: e.target.value })}
                max={todayIso()}
                className="mt-1"
                data-testid="input-fecha"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              {METRICS.map(({ key, label, icon: Icon, text }) => (
                <div key={key}>
                  <Label htmlFor={key} className="text-xs font-semibold text-[#1B2A4A]/70 flex items-center gap-1.5">
                    <Icon className="w-3.5 h-3.5" style={{ color: text }} /> {label}
                  </Label>
                  <Input
                    id={key}
                    type="number"
                    min="0"
                    inputMode="numeric"
                    placeholder="0"
                    value={form[key]}
                    onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                    className="mt-1 text-lg font-semibold"
                    data-testid={`input-${key}`}
                  />
                </div>
              ))}
            </div>

            <div>
              <Label htmlFor="notas" className="text-xs font-semibold text-[#1B2A4A]/70">Notas (opcional)</Label>
              <Textarea
                id="notas"
                placeholder="Ej: Salí con Juan al barrio El Paraíso; sembramos en 3 familias; testimonios poderosos..."
                value={form.notas}
                onChange={(e) => setForm({ ...form, notas: e.target.value })}
                rows={3}
                className="mt-1 resize-none"
                data-testid="input-notas"
              />
            </div>

            <Button
              type="submit"
              disabled={saving}
              className="w-full bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] hover:from-[#0F1A33] hover:to-[#1B2A4A] text-white font-bold py-5 shadow-md"
              data-testid="btn-guardar-jornada"
            >
              {saving ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Guardando…</>
              ) : editingId ? (
                <><CheckCircle2 className="w-4 h-4 mr-2" /> Actualizar Jornada</>
              ) : (
                <><Save className="w-4 h-4 mr-2" /> Registrar Jornada</>
              )}
            </Button>
          </motion.form>

          {/* GRÁFICO + LISTA */}
          <div className="lg:col-span-3 space-y-4 sm:space-y-6">
            {/* Gráfico actividad 14 días */}
            {stats && (
              <motion.div
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#0F1A33] to-[#1B2A4A] p-5 sm:p-6 shadow-lg text-white"
                data-testid="chart-card"
              >
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.25em] text-[#C8A951] font-bold">Últimos 14 días</p>
                    <h3 className="text-lg font-bold" style={{ fontFamily: 'Spectral, serif' }}>Ritmo de tu jornada</h3>
                  </div>
                  <Badge className="bg-[#C8A951]/15 text-[#C8A951] border border-[#C8A951]/40 font-mono text-[10px]">
                    {stats.daily_last_14?.length || 0} días
                  </Badge>
                </div>
                <MiniBarChart data={stats.daily_last_14} />
              </motion.div>
            )}

            {/* Lista de entradas */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-2xl bg-white border border-[#1B2A4A]/10 shadow-md overflow-hidden"
              data-testid="entries-list"
            >
              <div className="px-5 py-4 border-b border-[#1B2A4A]/10 flex items-center justify-between">
                <h3 className="text-base font-bold text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>
                  Jornadas registradas
                </h3>
                <Badge variant="outline" className="text-xs border-[#C8A951]/40 text-[#C8A951]">
                  {entries.length} {entries.length === 1 ? 'entrada' : 'entradas'}
                </Badge>
              </div>

              {loading ? (
                <div className="p-10 text-center text-[#1B2A4A]/40 text-sm flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Cargando bitácora…
                </div>
              ) : entries.length === 0 ? (
                <div className="p-10 text-center" data-testid="empty-state">
                  <div className="w-14 h-14 rounded-full bg-[#C8A951]/15 border border-[#C8A951]/30 flex items-center justify-center mx-auto mb-3">
                    <NotebookPen className="w-6 h-6 text-[#C8A951]" />
                  </div>
                  <p className="text-[#1B2A4A] font-bold" style={{ fontFamily: 'Spectral, serif' }}>Tu bitácora espera la primera página</p>
                  <p className="text-sm text-[#1B2A4A]/60 mt-1 max-w-md mx-auto">
                    Usa el formulario para registrar tu jornada de hoy. Cada visita cuenta.
                  </p>
                </div>
              ) : (
                <ul className="divide-y divide-[#1B2A4A]/5">
                  <AnimatePresence initial={false}>
                    {entries.map((entry) => (
                      <motion.li
                        key={entry.id}
                        layout
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        className={`px-5 py-4 transition-colors ${editingId === entry.id ? 'bg-[#C8A951]/10' : 'hover:bg-[#F5F0E8]/50'}`}
                        data-testid={`entry-${entry.id}`}
                      >
                        <div className="flex items-start justify-between gap-3 flex-wrap">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <p className="text-sm font-bold text-[#1B2A4A] capitalize">
                                {formatFechaLarga(entry.fecha)}
                              </p>
                              {entry.fecha === todayIso() && (
                                <Badge className="bg-[#1FA6A0] text-white text-[9px] uppercase tracking-widest">Hoy</Badge>
                              )}
                            </div>
                            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
                              {METRICS.map(({ key, label, icon: Icon, text }) => {
                                const v = entry[key] || 0;
                                if (v === 0) return null;
                                return (
                                  <span key={key} className="inline-flex items-center gap-1.5 text-xs text-[#1B2A4A]/80">
                                    <Icon className="w-3.5 h-3.5" style={{ color: text }} />
                                    <strong style={{ color: text }}>{v}</strong>
                                    <span className="text-[#1B2A4A]/60">{label.toLowerCase()}</span>
                                  </span>
                                );
                              })}
                            </div>
                            {entry.notas && (
                              <p className="text-sm italic text-[#1B2A4A]/70 mt-2 border-l-2 border-[#C8A951]/40 pl-3" style={{ fontFamily: 'Spectral, serif' }}>
                                “{entry.notas}”
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            <button
                              onClick={() => handleEdit(entry)}
                              className="p-2 rounded-lg hover:bg-[#C8A951]/15 text-[#1B2A4A]/50 hover:text-[#C8A951] transition-colors"
                              aria-label="Editar jornada"
                              data-testid={`btn-editar-${entry.id}`}
                            >
                              <Pencil className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleDelete(entry.id)}
                              className="p-2 rounded-lg hover:bg-red-50 text-[#1B2A4A]/50 hover:text-red-600 transition-colors"
                              aria-label="Eliminar jornada"
                              data-testid={`btn-eliminar-${entry.id}`}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </motion.li>
                    ))}
                  </AnimatePresence>
                </ul>
              )}
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  );
}
