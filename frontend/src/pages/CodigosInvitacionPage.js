import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Copy, KeyRound, Plus, RotateCcw, Shield, Trash2, UserPlus, CheckCircle2, Clock, XCircle,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from '../components/ui/dialog';
import { Badge } from '../components/ui/badge';
import { Card, CardContent } from '../components/ui/card';
import { useAuth } from '../context/AuthContext';

const estadoMap = {
  activo: { label: 'Activo', icon: CheckCircle2, className: 'bg-[#1FA6A0]/15 text-[#1FA6A0] border-[#1FA6A0]/40' },
  usado: { label: 'Usado', icon: Shield, className: 'bg-[#C8A951]/15 text-[#C8A951] border-[#C8A951]/40' },
  vencido: { label: 'Vencido', icon: XCircle, className: 'bg-red-500/15 text-red-400 border-red-500/40' },
};

export default function CodigosInvitacionPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const [codes, setCodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openDialog, setOpenDialog] = useState(false);
  const [destNombre, setDestNombre] = useState('');
  const [destEmail, setDestEmail] = useState('');
  const [creating, setCreating] = useState(false);
  const [newCode, setNewCode] = useState(null);

  const isPastor = user?.rol === 'pastor';
  const roleCreates = isPastor ? 'lider' : 'persona';

  const load = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/invite-codes`, getAuthHeaders());
      setCodes(res.data || []);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error cargando codigos');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleGenerate = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      const res = await axios.post(
        `${API}/api/invite-codes`,
        { destinatario_nombre: destNombre, destinatario_email: destEmail },
        getAuthHeaders(),
      );
      setNewCode(res.data);
      setDestNombre('');
      setDestEmail('');
      toast.success('Codigo generado');
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error generando codigo');
    } finally {
      setCreating(false);
    }
  };

  const handleCopy = async (code) => {
    try {
      await navigator.clipboard.writeText(code);
      toast.success(`Codigo ${code} copiado`);
    } catch {
      toast.error('No se pudo copiar');
    }
  };

  const handleRevoke = async (codeId) => {
    if (!window.confirm('¿Seguro que quieres revocar este codigo? No se podra usar despues.')) return;
    try {
      await axios.delete(`${API}/api/invite-codes/${codeId}`, getAuthHeaders());
      toast.success('Codigo revocado');
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error revocando codigo');
    }
  };

  const formatDate = (iso) => {
    if (!iso) return '-';
    try {
      return new Date(iso).toLocaleDateString('es-DO', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch {
      return iso;
    }
  };

  return (
    <div className="max-w-6xl mx-auto py-6 md:py-10 px-4 md:px-6" data-testid="codigos-page">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2 text-[#C8A951] text-xs uppercase tracking-[0.3em] font-semibold mb-2">
            <KeyRound className="w-4 h-4" />
            <span>Gestion de Acceso</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-bold text-[#0B1428] dark:text-white" style={{ fontFamily: 'Spectral, serif' }}>
            Codigos de Invitacion
          </h1>
          <p className="text-muted-foreground text-sm md:text-base mt-1 max-w-2xl">
            Genera codigos unicos para que tus {roleCreates === 'lider' ? 'lideres' : 'discipulos'} se registren y queden vinculados directamente contigo.
          </p>
        </div>

        <Dialog open={openDialog} onOpenChange={(o) => { setOpenDialog(o); if (!o) setNewCode(null); }}>
          <DialogTrigger asChild>
            <Button
              className="bg-gradient-to-r from-[#C8A951] to-[#B8993F] hover:from-[#B8993F] hover:to-[#A88730] text-[#0B1428] font-semibold"
              data-testid="open-generate-dialog-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              Generar codigo
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            {newCode ? (
              <>
                <DialogHeader>
                  <DialogTitle>Codigo generado</DialogTitle>
                  <DialogDescription>
                    Copialo y enviaselo por correo o mensaje. Vence el {formatDate(newCode.expires_at)}.
                  </DialogDescription>
                </DialogHeader>
                <div className="py-4 text-center">
                  <div className="inline-block bg-[#0B1428] text-[#C8A951] rounded-xl px-6 py-5 font-mono text-3xl tracking-[0.3em] font-bold border-2 border-[#C8A951]/50" data-testid="new-code-display">
                    {newCode.code}
                  </div>
                </div>
                <DialogFooter className="flex gap-2 sm:justify-between">
                  <Button variant="outline" onClick={() => { setNewCode(null); }}>
                    <Plus className="w-4 h-4 mr-2" />
                    Generar otro
                  </Button>
                  <Button
                    onClick={() => handleCopy(newCode.code)}
                    className="bg-[#1B2A4A] text-white hover:bg-[#0F1A33]"
                    data-testid="copy-new-code-btn"
                  >
                    <Copy className="w-4 h-4 mr-2" />
                    Copiar codigo
                  </Button>
                </DialogFooter>
              </>
            ) : (
              <form onSubmit={handleGenerate}>
                <DialogHeader>
                  <DialogTitle>Nuevo codigo de invitacion</DialogTitle>
                  <DialogDescription>
                    Se generara un codigo valido por 30 dias. {isPastor ? 'Al usarse creara un lider bajo tu jerarquia.' : 'Al usarse creara una persona vinculada a ti como su lider.'}
                  </DialogDescription>
                </DialogHeader>
                <div className="py-4 space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="dest-nombre">Destinatario (opcional)</Label>
                    <Input
                      id="dest-nombre"
                      value={destNombre}
                      onChange={(e) => setDestNombre(e.target.value)}
                      placeholder={isPastor ? 'Ej: Juan Perez (lider)' : 'Ej: Maria Gomez'}
                      data-testid="dest-nombre-input"
                    />
                    <p className="text-xs text-muted-foreground">
                      Solo para que te acuerdes a quien lo enviaste.
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="dest-email">Correo del destinatario (opcional)</Label>
                    <Input
                      id="dest-email"
                      type="email"
                      value={destEmail}
                      onChange={(e) => setDestEmail(e.target.value)}
                      placeholder="correo@ejemplo.com"
                      data-testid="dest-email-input"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setOpenDialog(false)}>
                    Cancelar
                  </Button>
                  <Button
                    type="submit"
                    disabled={creating}
                    className="bg-gradient-to-r from-[#C8A951] to-[#B8993F] text-[#0B1428]"
                    data-testid="confirm-generate-btn"
                  >
                    {creating ? 'Generando...' : 'Generar'}
                  </Button>
                </DialogFooter>
              </form>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {/* Info banner */}
      <Card className="mb-6 border-[#C8A951]/30 bg-[#C8A951]/5">
        <CardContent className="pt-6">
          <div className="flex gap-3">
            <UserPlus className="w-5 h-5 text-[#C8A951] shrink-0 mt-0.5" />
            <div className="text-sm text-muted-foreground">
              <p className="font-semibold text-foreground mb-1">Como funciona</p>
              <p>
                Generas un codigo, lo envias por correo o mensaje al {roleCreates === 'lider' ? 'nuevo lider' : 'discipulo'}, y esa persona se registra en el login con su nombre, correo, contrasena y ese codigo. Al registrarse queda automaticamente {roleCreates === 'lider' ? 'como lider' : 'vinculada a ti como tu discipulo'}.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Lista de codigos */}
      {loading ? (
        <div className="text-center py-12 text-muted-foreground">Cargando...</div>
      ) : codes.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <KeyRound className="w-12 h-12 mx-auto text-muted-foreground/50 mb-3" />
            <p className="text-muted-foreground">Aun no has generado ningun codigo.</p>
            <p className="text-xs text-muted-foreground mt-1">Haz click en "Generar codigo" para empezar.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3" data-testid="codes-list">
          {codes.map((c) => {
            const estadoInfo = estadoMap[c.estado] || estadoMap.activo;
            const Icon = estadoInfo.icon;
            return (
              <Card key={c.id} className="overflow-hidden" data-testid={`code-row-${c.code}`}>
                <CardContent className="py-4 px-4 md:px-6">
                  <div className="flex flex-col md:flex-row md:items-center gap-3 md:gap-6">
                    {/* Codigo */}
                    <div className="font-mono text-xl md:text-2xl font-bold tracking-[0.2em] text-[#0B1428] dark:text-white shrink-0">
                      {c.code}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge className={`${estadoInfo.className} border text-xs font-semibold`}>
                          <Icon className="w-3 h-3 mr-1" />
                          {estadoInfo.label}
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          Rol: {c.role_to_assign}
                        </Badge>
                      </div>
                      <div className="mt-2 text-xs md:text-sm text-muted-foreground space-y-0.5">
                        {c.destinatario_nombre && (
                          <p><span className="font-semibold">Para:</span> {c.destinatario_nombre}{c.destinatario_email ? ` (${c.destinatario_email})` : ''}</p>
                        )}
                        <p>
                          <Clock className="inline w-3 h-3 mr-1 -mt-0.5" />
                          Creado {formatDate(c.created_at)}
                          {c.estado === 'activo' && ` · Vence ${formatDate(c.expires_at)}`}
                          {c.estado === 'usado' && ` · Usado ${formatDate(c.used_at)}`}
                          {c.estado === 'vencido' && ` · Vencio`}
                        </p>
                      </div>
                    </div>

                    {/* Acciones */}
                    <div className="flex gap-2 shrink-0">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleCopy(c.code)}
                        data-testid={`copy-${c.code}-btn`}
                      >
                        <Copy className="w-4 h-4 mr-1" />
                        Copiar
                      </Button>
                      {c.estado === 'activo' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleRevoke(c.id)}
                          className="text-red-500 hover:text-red-600 border-red-200"
                          data-testid={`revoke-${c.code}-btn`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Refresh button */}
      <div className="mt-6 text-center">
        <Button variant="ghost" size="sm" onClick={load} data-testid="refresh-codes-btn">
          <RotateCcw className="w-4 h-4 mr-2" />
          Actualizar
        </Button>
      </div>
    </div>
  );
}
