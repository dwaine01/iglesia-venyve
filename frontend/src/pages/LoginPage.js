import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Eye, EyeOff, KeyRound, AlertCircle, Mail, Lock, User, ArrowRight, Sparkles } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { LOGO_IGLESIA } from '../data/presentationData';
import { toast } from 'sonner';

/**
 * /login — pantalla de acceso a la plataforma jerarquica.
 * No incluye registro abierto: el registro siempre es por invitacion.
 */
export default function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const inviteFromUrl = params.get('codigo') || '';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  React.useEffect(() => {
    if (user) navigate('/');
  }, [user, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
      toast.success('Bienvenido de vuelta');
      navigate('/');
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al iniciar sesión';
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B1428] flex items-center justify-center px-4 py-10 relative overflow-hidden">
      {/* halo de fondo */}
      <div className="absolute inset-0 bg-gradient-to-br from-[#1B2A4A]/40 via-transparent to-[#0B1428]" />
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: 'radial-gradient(circle at 1px 1px, white 1px, transparent 0)',
          backgroundSize: '32px 32px',
        }}
      />

      <div className="relative w-full max-w-md">
        {/* Marco hairline doble */}
        <div className="rounded-3xl border border-[#C8A951]/25 p-1.5">
          <div className="rounded-[22px] border border-white/10 bg-[#0F1A33]/95 backdrop-blur p-8 sm:p-10">
            {/* Sello / logo */}
            <div className="flex flex-col items-center text-center mb-7">
              <div className="relative">
                <div className="absolute inset-0 bg-[#C8A951]/30 blur-2xl rounded-full" />
                <img
                  src={LOGO_IGLESIA}
                  alt="Casa de Oración Ven y Ve"
                  className="relative w-20 h-20 rounded-full"
                  style={{ mixBlendMode: 'screen' }}
                />
              </div>
              <p className="mt-4 text-[11px] uppercase tracking-[0.35em] text-[#C8A951] font-bold">Casa de Oración</p>
              <h1
                className="mt-1 text-3xl font-bold text-white"
                style={{ fontFamily: 'Spectral, serif' }}
              >
                Ven y Ve
              </h1>
              <p className="mt-1 text-xs text-white/50 italic">Primera Iglesia del Nazareno</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="email" className="text-xs uppercase tracking-[0.2em] text-white/70 font-bold">Correo</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="tu@correo.com"
                    required
                    autoComplete="email"
                    data-testid="login-email-input"
                    className="pl-9 bg-white/5 border-white/15 text-white placeholder:text-white/30 focus-visible:ring-[#C8A951]"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password" className="text-xs uppercase tracking-[0.2em] text-white/70 font-bold">Contraseña</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <Input
                    id="password"
                    type={showPwd ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••"
                    required
                    autoComplete="current-password"
                    data-testid="login-password-input"
                    className="pl-9 pr-10 bg-white/5 border-white/15 text-white placeholder:text-white/30 focus-visible:ring-[#C8A951]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd((s) => !s)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/80 transition-colors"
                    data-testid="toggle-password-visibility"
                    aria-label={showPwd ? 'Ocultar' : 'Mostrar'}
                  >
                    {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {error && (
                <div className="flex items-start gap-2 text-sm text-red-300 bg-red-900/20 border border-red-500/30 rounded-lg p-3">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <Button
                type="submit"
                disabled={loading}
                data-testid="login-submit-button"
                className="w-full bg-gradient-to-r from-[#C8A951] to-[#E2CF8A] text-[#1B2A4A] hover:opacity-95 font-bold uppercase tracking-wider"
              >
                {loading ? 'Entrando...' : (
                  <span className="inline-flex items-center gap-2">
                    Iniciar sesión <ArrowRight className="w-4 h-4" />
                  </span>
                )}
              </Button>
            </form>

            {/* Registro por invitacion */}
            <div className="mt-7 pt-5 border-t border-white/10">
              <div className="flex items-start gap-3">
                <div className="shrink-0 mt-0.5">
                  <Sparkles className="w-4 h-4 text-[#C8A951]" />
                </div>
                <div className="flex-1">
                  <p className="text-xs uppercase tracking-[0.2em] text-[#C8A951] font-bold mb-1">¿Tienes un código?</p>
                  <p className="text-xs text-white/60 mb-3">El acceso es por invitación. Pide tu código a tu superior y regístrate.</p>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => navigate(inviteFromUrl ? `/registro/${inviteFromUrl}` : '/registro')}
                    className="w-full border-[#C8A951]/40 text-[#C8A951] hover:bg-[#C8A951]/10 hover:text-[#E2CF8A]"
                    data-testid="go-to-register"
                  >
                    <KeyRound className="w-4 h-4 mr-2" />
                    Registrarme con código
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <p className="mt-6 text-center text-[10px] uppercase tracking-[0.3em] text-white/30">
          Casa de Oración Ven y Ve · Primera Iglesia del Nazareno
        </p>
      </div>
    </div>
  );
}
