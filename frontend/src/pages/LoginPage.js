import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Eye, EyeOff } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';

import { LOGO_IGLESIA } from '../data/presentationData';
import { BRAND, SPIRITUAL_QUOTES } from '../config/brand';

const LOGO_URL = LOGO_IGLESIA;

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [nombre, setNombre] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [inviteCodeError, setInviteCodeError] = useState('');
  const rol = 'persona';
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [quoteIdx, setQuoteIdx] = useState(0);

  const { login, register } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const interval = setInterval(() => {
      setQuoteIdx((prev) => (prev + 1) % SPIRITUAL_QUOTES.length);
    }, 6500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    document.title = `${BRAND.name} | Acceso`;
  }, []);

  const activeQuote = useMemo(() => SPIRITUAL_QUOTES[quoteIdx], [quoteIdx]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setInviteCodeError('');
    setLoading(true);
    try {
      if (isRegister) {
        const codeClean = (inviteCode || '').trim().toUpperCase();
        // Sin código, el alta siempre crea una cuenta Persona de autoservicio.
        await register(nombre, email, password, codeClean || null, codeClean ? null : rol);
        toast.success('Cuenta creada exitosamente');
      } else {
        await login(email, password);
        toast.success('Bienvenido');
      }
      navigate('/');
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : 'No se pudo iniciar sesión';
      // Si el error viene del codigo, resaltar el campo
      if (isRegister && typeof detail === 'string' && detail.toLowerCase().includes('codigo')) {
        setInviteCodeError(detail);
      }
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen w-full overflow-x-hidden bg-[#0B1428] lg:h-screen lg:overflow-hidden" data-testid="ven-y-ve-360-login-page">
      {/* ========================================================= */}
      {/*            FONDO: NAVY UNIFORME + AMBIENTE SUTIL           */}
      {/* ========================================================= */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <div className="absolute inset-0 animated-dots opacity-[0.05]"></div>
        <div className="absolute inset-0 bg-gradient-to-b from-[#0B1428] via-[#0F1A33]/60 to-[#0B1428]"></div>
      </div>

      {/* ========================================================= */}
      {/*       CONTENEDOR PRINCIPAL - TODO EN UNA PANTALLA           */}
      {/* ========================================================= */}
      <div className="relative z-10 h-full w-full flex flex-col">
        {/* -------- HEADER MINIMAL (solo logo + nombre) -------- */}
        <header
          className="w-full px-6 sm:px-10 lg:px-16 xl:px-24 pt-6 md:pt-8 shrink-0"
          data-testid="login-header"
        >
          <div className="flex items-center gap-4">
            {/* LOGO GRANDE */}
            <div className="relative shrink-0">
              <div className="absolute inset-0 bg-[#C8A951]/25 blur-3xl rounded-full scale-110"></div>
              <img
                src={LOGO_URL}
                alt="Casa de Oración Ven y Ve"
                className="relative w-[72px] h-[72px] md:w-[88px] md:h-[88px] object-contain logo-transparent"
                data-testid="login-logo"
              />
            </div>
            <div className="hidden sm:block">
              <p className="text-[#C8A951]/90 text-[10px] md:text-[11px] tracking-[0.35em] uppercase font-semibold" style={{ fontFamily: 'Spectral, serif' }}>
                Casa de Oración
              </p>
              <p className="text-white text-base md:text-lg font-semibold mt-0.5" style={{ fontFamily: 'Spectral, serif' }}>
                Ven y Ve
              </p>
            </div>
          </div>
        </header>

        {/* ========================================================= */}
        {/*   SECCIÓN CENTRAL: HERO + LOGIN + CITA (en el medio)       */}
        {/* ========================================================= */}
        <main className="flex-1 w-full px-6 sm:px-10 lg:px-16 xl:px-24 flex flex-col justify-center py-5 md:py-6">
          <div className="max-w-[1400px] mx-auto w-full">

            {/* --- Hero + Login lado a lado --- */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-stretch">
              {/* Hero text (izquierda) - con cita rotatoria integrada debajo */}
              <div className="lg:col-span-7 xl:col-span-8 flex flex-col justify-center" data-testid="login-hero-text">
                <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.24em] text-[#D7BC65]" data-testid="login-platform-kicker">Plataforma ministerial</p>
                <h1
                  className="mt-3 text-4xl sm:text-5xl md:text-6xl lg:text-[72px] xl:text-[82px] font-bold text-white leading-[0.95]"
                  style={{ fontFamily: 'Spectral, serif' }}
                  data-testid="login-brand-title"
                >
                  VEN Y VE <span className="shimmer-text">360</span>
                </h1>
                <p className="mt-3 text-base font-semibold text-[#E7D28D] md:text-lg" data-testid="login-brand-subtitle">{BRAND.subtitle}</p>
                <p className="mt-2 font-['Spectral'] text-base text-white md:text-lg" data-testid="login-brand-slogan">{BRAND.slogan}</p>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-white/65 md:text-base" data-testid="login-brand-description">{BRAND.description}</p>

                {/* --- Identidad espiritual permanente --- */}
                <div className="mt-6 max-w-2xl border-l border-[#C8A951]/65 pl-4 md:mt-8" data-testid="login-rotating-quote" aria-live="polite">
                  <div className="flex items-center justify-between gap-4">
                    <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-[#D8BC61]" data-testid="login-quote-category">{activeQuote.category}</p>
                    <span className="font-mono text-[10px] text-white/35" data-testid="login-quote-position">{String(quoteIdx + 1).padStart(2, '0')} / {SPIRITUAL_QUOTES.length}</span>
                  </div>
                  <p
                    key={quoteIdx}
                    className="mt-2 text-white/75 text-sm md:text-base italic leading-[1.6] fade-in-quote font-light"
                    style={{ fontFamily: 'Spectral, serif' }}
                    data-testid="login-quote-text"
                  >
                    “{activeQuote.text}”
                  </p>
                  <div className="mt-3 h-px overflow-hidden bg-white/10" data-testid="login-quote-progress"><div key={`progress-${quoteIdx}`} className="h-full origin-left animate-[quoteProgress_6.5s_linear] bg-[#C8A951]" /></div>
                </div>
              </div>

              {/* Login card (derecha) - rectangular alargado, una sola linea dorada */}
              <aside
                className="lg:col-span-5 xl:col-span-4 w-full max-w-md mx-auto lg:mx-0 lg:ml-auto flex"
                data-testid="login-card"
              >
                <div
                  className="relative bg-white/[0.03] backdrop-blur-xl rounded-2xl p-8 md:p-10 shadow-[0_20px_60px_rgba(0,0,0,0.5)] w-full flex flex-col justify-center min-h-[540px] border border-[#C8A951]/45"
                >
                  <div className="mb-5">
                    <h2
                      className="text-2xl md:text-3xl font-bold text-white mb-1 leading-tight"
                      style={{ fontFamily: 'Spectral, serif' }}
                    >
                      {isRegister ? 'Crear cuenta' : 'Iniciar sesión'}
                    </h2>
                    <p className="text-white/55 text-xs md:text-sm">
                      {isRegister
                        ? `Regístrate para acceder a ${BRAND.name}`
                        : `Ingresa a ${BRAND.name} con tus credenciales institucionales`}
                    </p>
                  </div>

                  <form onSubmit={handleSubmit} className="space-y-3.5">
                    {isRegister && (
                      <>
                        <div className="space-y-1.5">
                          <Label htmlFor="invite_code" className={`text-[10px] uppercase tracking-wider font-semibold ${inviteCodeError ? 'text-red-400' : 'text-[#C8A951]'}`}>
                            Código de invitación <span className="text-white/40 normal-case tracking-normal">(opcional)</span>
                          </Label>
                          <Input
                            id="invite_code"
                            value={inviteCode}
                            onChange={(e) => { setInviteCode(e.target.value.toUpperCase()); if (inviteCodeError) setInviteCodeError(''); }}
                            placeholder="Ej: AB3XK7YP (dejar vacio si no tienes)"
                            maxLength={12}
                            aria-invalid={!!inviteCodeError}
                            data-testid="register-invite-code-input"
                            className={`bg-transparent text-white placeholder:text-white/30 h-10 font-mono tracking-[0.2em] uppercase ${
                              inviteCodeError
                                ? 'border-red-500/70 focus-visible:ring-red-500/50 focus-visible:border-red-500'
                                : 'border-[#C8A951]/40 focus-visible:ring-[#C8A951]/50 focus-visible:border-[#C8A951]/80'
                            }`}
                          />
                          {inviteCodeError ? (
                            <p className="text-[11px] text-red-400 leading-tight" data-testid="register-invite-code-error">
                              {inviteCodeError}
                            </p>
                          ) : (
                            <p className="text-[10px] text-white/40 leading-tight">
                              Sin código se crea una cuenta Persona. Los roles institucionales requieren invitación.
                            </p>
                          )}
                        </div>

                        {!inviteCode.trim() && <p className="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/60" data-testid="register-persona-role-notice">Cuenta de autoservicio: Persona</p>}

                        <div className="space-y-1.5">
                          <Label htmlFor="nombre" className="text-white/75 text-[10px] uppercase tracking-wider font-semibold">
                            Nombre completo
                          </Label>
                          <Input
                            id="nombre"
                            value={nombre}
                            onChange={(e) => setNombre(e.target.value)}
                            placeholder="Ej: Juan Perez"
                            required
                            data-testid="register-name-input"
                            className="bg-transparent border-white/20 text-white placeholder:text-white/30 focus-visible:ring-[#C8A951]/50 focus-visible:border-[#C8A951]/60 h-10"
                          />
                        </div>
                      </>
                    )}
                    <div className="space-y-1.5">
                      <Label htmlFor="email" className="text-white/75 text-[10px] uppercase tracking-wider font-semibold">
                        Correo electrónico
                      </Label>
                      <Input
                        id="email"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="correo@ejemplo.com"
                        required
                        data-testid="login-email-input"
                        className="bg-transparent border-white/20 text-white placeholder:text-white/30 focus-visible:ring-[#C8A951]/50 focus-visible:border-[#C8A951]/60 h-10"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="password" className="text-white/75 text-[10px] uppercase tracking-wider font-semibold">
                        Contraseña
                      </Label>
                      <div className="relative">
                        <Input
                          id="password"
                          type={showPass ? 'text' : 'password'}
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          placeholder="Tu contraseña"
                          required
                          data-testid="login-password-input"
                          className="bg-transparent border-white/20 text-white placeholder:text-white/30 focus-visible:ring-[#C8A951]/50 focus-visible:border-[#C8A951]/60 h-10 pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPass(!showPass)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-[#C8A951] transition-colors"
                          aria-label={showPass ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                          data-testid="toggle-password-visibility-button"
                        >
                          {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>

                    <Button
                      type="submit"
                      className="w-full h-11 mt-2 text-base bg-gradient-to-r from-[#C8A951] to-[#B8993F] hover:from-[#B8993F] hover:to-[#A88730] text-[#0B1428] font-bold shadow-lg shadow-[#C8A951]/20"
                      disabled={loading}
                      data-testid="login-submit-button"
                      style={{ fontFamily: 'Spectral, serif' }}
                    >
                      {loading ? 'Procesando...' : isRegister ? 'Crear cuenta' : 'Iniciar sesión'}
                    </Button>
                  </form>

                  <div className="mt-4 text-center">
                    <button
                      onClick={() => setIsRegister(!isRegister)}
                      className="text-xs md:text-sm text-white/45 hover:text-[#C8A951] transition-colors"
                      data-testid="toggle-auth-mode"
                    >
                      {isRegister ? 'Ya tengo cuenta. Iniciar sesión' : 'No tengo cuenta. Registrarme'}
                    </button>
                  </div>
                </div>
              </aside>
            </div>
          </div>
        </main>

        <footer
          className="w-full shrink-0 px-6 pb-5 pt-3 sm:px-10 lg:px-16 xl:px-24"
          data-testid="login-footer"
        >
          <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-4 border-t border-white/10 pt-4 text-[10px] uppercase text-white/35">
            <span className="tracking-[0.18em]">{BRAND.church}</span>
            <span className="tracking-[0.25em]">Hechos 1:8</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
