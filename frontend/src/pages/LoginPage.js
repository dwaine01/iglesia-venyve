import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ArrowRight, Cross, Eye, EyeOff, Quote } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';

import { LOGO_IGLESIA } from '../data/presentationData';

const LOGO_URL = LOGO_IGLESIA;

const loginQuotes = [
  '"La vision no es abstracta, es concreta; y lo concreto produce resultados."',
  '"Si cuidas la planta, le echas agua y la proteges, va a dar fruto."',
  '"La hormiga sabe lo que quiere, cuando lo quiere y donde lo quiere."',
  '"De Persona a Discipulo, de Discipulo a Obrero, de Obrero a Ministro."',
];

const journeySteps = [
  { label: 'Persona', color: '#C8A951', glow: true },
  { label: 'Discipulo', color: '#D4B871', glow: false },
  { label: 'Obrero', color: '#1FA6A0', glow: false },
  { label: 'Ministro', color: '#FFFFFF', glow: false },
];

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
      setQuoteIdx((prev) => (prev + 1) % loginQuotes.length);
    }, 5500);
    return () => clearInterval(interval);
  }, []);

  const activeQuote = useMemo(() => loginQuotes[quoteIdx], [quoteIdx]);

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
      const msg = typeof detail === 'string' ? detail : 'Error al iniciar sesion';
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
    <div className="h-screen w-full relative bg-[#0B1428] overflow-hidden">
      {/* ========================================================= */}
      {/*            FONDO: NAVY UNIFORME + AMBIENTE SUTIL           */}
      {/* ========================================================= */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <div className="absolute inset-0 animated-dots opacity-[0.05]"></div>
        <div className="absolute inset-0 bg-gradient-to-b from-[#0B1428] via-[#0F1A33]/60 to-[#0B1428]"></div>
        {/* Orbes sutiles para atmósfera (no agregan encuadre) */}
        <div className="absolute top-[20%] right-[-8%] w-[600px] h-[600px] bg-gradient-radial from-[#C8A951]/12 to-transparent rounded-full blur-3xl"></div>
        <div className="absolute bottom-[10%] left-[-10%] w-[550px] h-[550px] bg-gradient-radial from-[#1FA6A0]/10 to-transparent rounded-full blur-3xl"></div>
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
                alt="Casa de Oracion Ven y Ve"
                className="relative w-[72px] h-[72px] md:w-[88px] md:h-[88px] object-contain logo-transparent"
                data-testid="login-logo"
              />
            </div>
            <div className="hidden sm:block">
              <p className="text-[#C8A951]/90 text-[10px] md:text-[11px] tracking-[0.35em] uppercase font-semibold" style={{ fontFamily: 'Spectral, serif' }}>
                Casa de Oracion
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
        <main className="flex-1 w-full px-6 sm:px-10 lg:px-16 xl:px-24 flex flex-col justify-center py-4 md:py-6">
          <div className="max-w-[1400px] mx-auto w-full">

            {/* --- Hero + Login lado a lado --- */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-stretch">
              {/* Hero text (izquierda) - con cita rotatoria integrada debajo */}
              <div className="lg:col-span-7 xl:col-span-8 flex flex-col gap-4 justify-center" data-testid="login-hero-text">
                <h1
                  className="text-4xl sm:text-5xl md:text-6xl lg:text-[72px] xl:text-[88px] font-bold text-white leading-[0.95] tracking-tight"
                  style={{ fontFamily: 'Spectral, serif' }}
                >
                  La Ley de las<br />
                  <span className="shimmer-text">7 Semanas</span>
                </h1>
                <p
                  className="text-base md:text-lg lg:text-xl text-white/70 leading-relaxed font-light max-w-2xl"
                  style={{ fontFamily: 'Spectral, serif' }}
                >
                  Un proceso de discipulado y consolidacion ministerial que transforma vidas para el Reino de Dios.
                </p>

                {/* --- Cita rotatoria - a la izquierda, sutilmente debajo del subtitulo --- */}
                <div className="mt-6 md:mt-8 max-w-xl" data-testid="login-rotating-quote">
                  <p
                    key={quoteIdx}
                    className="text-white/70 text-sm md:text-base italic leading-[1.5] fade-in-quote font-light"
                    style={{ fontFamily: 'Spectral, serif' }}
                    data-testid="login-quote-text"
                  >
                    {activeQuote}
                  </p>
                  <div className="flex gap-1.5 mt-3" data-testid="login-quote-indicators">
                    {loginQuotes.map((_, i) => (
                      <div
                        key={i}
                        className={`h-[2px] rounded-full transition-[width,background-color] duration-500 ${
                          i === quoteIdx ? 'w-8 bg-[#C8A951]' : 'w-3 bg-white/15'
                        }`}
                      />
                    ))}
                  </div>
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
                      {isRegister ? 'Crear cuenta' : 'Iniciar sesion'}
                    </h2>
                    <p className="text-white/55 text-xs md:text-sm">
                      {isRegister
                        ? 'Registrate para acceder al manual'
                        : 'Ingresa tus credenciales institucionales'}
                    </p>
                  </div>

                  <form onSubmit={handleSubmit} className="space-y-3.5">
                    {isRegister && (
                      <>
                        <div className="space-y-1.5">
                          <Label htmlFor="invite_code" className={`text-[10px] uppercase tracking-wider font-semibold ${inviteCodeError ? 'text-red-400' : 'text-[#C8A951]'}`}>
                            Codigo de invitacion <span className="text-white/40 normal-case tracking-normal">(opcional)</span>
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
                        Correo electronico
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
                        Contrasena
                      </Label>
                      <div className="relative">
                        <Input
                          id="password"
                          type={showPass ? 'text' : 'password'}
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          placeholder="Tu contrasena"
                          required
                          data-testid="login-password-input"
                          className="bg-transparent border-white/20 text-white placeholder:text-white/30 focus-visible:ring-[#C8A951]/50 focus-visible:border-[#C8A951]/60 h-10 pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPass(!showPass)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-[#C8A951] transition-colors"
                          aria-label={showPass ? 'Ocultar contrasena' : 'Mostrar contrasena'}
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
                      {loading ? 'Procesando...' : isRegister ? 'Crear cuenta' : 'Iniciar sesion'}
                    </Button>
                  </form>

                  <div className="mt-4 text-center">
                    <button
                      onClick={() => setIsRegister(!isRegister)}
                      className="text-xs md:text-sm text-white/45 hover:text-[#C8A951] transition-colors"
                      data-testid="toggle-auth-mode"
                    >
                      {isRegister ? 'Ya tengo cuenta. Iniciar sesion' : 'No tengo cuenta. Registrarme'}
                    </button>
                  </div>
                </div>
              </aside>
            </div>
          </div>
        </main>

        {/* ========================================================= */}
        {/*   FOOTER: CAMINO DEL DISCIPULADO + INFO DE LA IGLESIA      */}
        {/* ========================================================= */}
        <footer
          className="w-full px-6 sm:px-10 lg:px-16 xl:px-24 pt-4 md:pt-6 pb-4 md:pb-6 shrink-0"
          data-testid="login-footer"
        >
          <div className="max-w-[1400px] mx-auto">
            {/* Etiqueta "El Camino del Discipulado" */}
            <div className="flex items-center gap-4 mb-3 md:mb-4">
              <div className="h-px flex-1 bg-gradient-to-r from-transparent via-[#C8A951]/25 to-transparent"></div>
              <span
                className="text-[#C8A951]/90 text-[10px] md:text-xs tracking-[0.4em] uppercase font-semibold whitespace-nowrap shrink-0"
                style={{ fontFamily: 'Spectral, serif' }}
              >
                El Camino del Discipulado
              </span>
              <div className="h-px flex-1 bg-gradient-to-r from-transparent via-[#C8A951]/25 to-transparent"></div>
            </div>

            {/* Journey horizontal a lo largo */}
            <div
              className="flex items-center justify-between gap-3 md:gap-6 flex-wrap md:flex-nowrap mb-3"
              data-testid="login-journey-path"
            >
              {journeySteps.map((step, i) => (
                <React.Fragment key={i}>
                  <div className="flex items-center gap-2.5 md:gap-3 group shrink-0">
                    <div className="relative">
                      {step.glow && (
                        <div
                          className="absolute inset-0 rounded-full blur-lg animate-pulse"
                          style={{ backgroundColor: step.color, opacity: 0.65 }}
                        />
                      )}
                      <div
                        className="relative w-3.5 h-3.5 md:w-4 md:h-4 rounded-full"
                        style={{
                          backgroundColor: step.color,
                          boxShadow: `0 0 18px ${step.color}90`,
                        }}
                      />
                    </div>
                    <span
                      className="text-white text-base md:text-lg lg:text-xl font-semibold tracking-wide"
                      style={{ fontFamily: 'Spectral, serif' }}
                    >
                      {step.label}
                    </span>
                  </div>
                  {i < journeySteps.length - 1 && (
                    <ArrowRight className="w-4 h-4 md:w-5 md:h-5 text-[#C8A951]/55 shrink-0" strokeWidth={2} />
                  )}
                </React.Fragment>
              ))}
            </div>

            {/* Linea divisoria minimal + Hechos 1:8 */}
            <div className="pt-4 border-t border-white/10 flex items-center justify-end">
              <p className="text-white/30 text-[10px] md:text-xs tracking-[0.25em] uppercase">
                Hechos 1:8
              </p>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}
