import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { toast } from 'sonner';
import { Eye, EyeOff, Flame, Sparkles } from 'lucide-react';

import { LOGO_IGLESIA } from '../data/presentationData';
const LOGO_URL = LOGO_IGLESIA;
const BG_URL = 'https://images.unsplash.com/photo-1646315026053-27cf64144dd8?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85';

const loginQuotes = [
  '"La vision no es abstracta, es concreta; y lo concreto produce resultados."',
  '"Si cuidas la planta, le echas agua y la proteges, va a dar fruto."',
  '"La hormiga sabe lo que quiere, cuando lo quiere y donde lo quiere."',
  '"De Persona a Discipulo, de Discipulo a Obrero, de Obrero a Ministro."',
];

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [nombre, setNombre] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [quoteIdx, setQuoteIdx] = useState(0);
  const { login, register } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const interval = setInterval(() => {
      setQuoteIdx(prev => (prev + 1) % loginQuotes.length);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (isRegister) {
        await register(nombre, email, password);
        toast.success('Cuenta creada exitosamente');
      } else {
        await login(email, password);
        toast.success('Bienvenido al Manual');
      }
      navigate('/');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al iniciar sesion');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left Panel - Brand - Enhanced */}
      <div className="hidden lg:flex lg:w-1/2 xl:w-[55%] relative overflow-hidden">
        <div className="absolute inset-0 bg-[#0F1A33]">
          <img src={BG_URL} alt="" className="w-full h-full object-cover opacity-15" />
        </div>
        <div className="absolute inset-0 animated-dots opacity-10"></div>
        <div className="absolute inset-0 bg-gradient-to-br from-[#0F1A33] via-[#0F1A33]/90 to-[#1B2A4A]/80"></div>
        <div className="relative z-10 flex flex-col justify-between p-12 xl:p-16 w-full">
          <div>
            <div className="flex items-center gap-3 mb-8">
              <img src={LOGO_URL} alt="Casa de Oracion Ven y Ve" className="w-20 h-20 object-contain logo-transparent" />
              <div className="flex items-center gap-1.5 bg-[#C8A951]/15 px-3 py-1 rounded-full">
                <Sparkles className="w-3.5 h-3.5 text-[#C8A951]" />
                <span className="text-[#C8A951] text-xs font-semibold">Manual Corporativo</span>
              </div>
            </div>
            <h1 className="text-4xl xl:text-5xl font-bold text-white mb-4 leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
              La Ley de las <span className="shimmer-text">7 Semanas</span>
            </h1>
            <p className="text-lg text-white/60 max-w-md leading-relaxed">
              Un proceso de crecimiento y formacion que transforma vidas.
            </p>
          </div>
          <div className="space-y-6">
            <div className="border-t border-white/10 pt-6">
              <div className="flex items-start gap-3 mb-4">
                <Flame className="w-5 h-5 text-[#C8A951] shrink-0 mt-1" />
                <p key={quoteIdx} className="text-white/80 text-base italic max-w-lg leading-relaxed" style={{ transition: 'opacity 0.5s' }}>
                  {loginQuotes[quoteIdx]}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-6">
              {[
                { color: 'bg-[#C8A951]', text: 'Persona a Discipulo' },
                { color: 'bg-[#1FA6A0]', text: 'Discipulo a Obrero' },
                { color: 'bg-white/40', text: 'Obrero a Ministro' },
              ].map((step, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className={`w-2.5 h-2.5 rounded-full ${step.color} ${i === 0 ? 'pulse-gold' : ''}`}></div>
                  <span className="text-white/50 text-xs">{step.text}</span>
                </div>
              ))}
            </div>
            <p className="text-white/30 text-xs">
              Casa de Oracion Ven y Ve &mdash; Primera Iglesia del Nazareno &mdash; Pastora Carmen Garcia
            </p>
          </div>
        </div>
      </div>

      {/* Right Panel - Form */}
      <div className="flex-1 flex items-center justify-center p-4 sm:p-6 md:p-10 bg-background">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-14 h-14 bg-[#0F1A33] rounded-lg p-1 flex items-center justify-center shrink-0">
              <img src={LOGO_URL} alt="Ven y Ve" className="w-full h-full object-contain logo-transparent" />
            </div>
            <div>
              <h2 className="text-lg font-bold" style={{ fontFamily: 'Spectral, serif' }}>Ven y Ve</h2>
              <p className="text-xs text-muted-foreground">Ley de las 7 Semanas</p>
            </div>
          </div>

          <Card className="border shadow-sm">
            <CardHeader className="pb-4">
              <CardTitle className="text-2xl" style={{ fontFamily: 'Spectral, serif' }}>
                {isRegister ? 'Crear Cuenta' : 'Iniciar Sesion'}
              </CardTitle>
              <CardDescription>
                {isRegister
                  ? 'Registrate para acceder al manual de seguimiento'
                  : 'Accede al manual de la Ley de las 7 Semanas'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                {isRegister && (
                  <div className="space-y-2">
                    <Label htmlFor="nombre">Nombre completo</Label>
                    <Input
                      id="nombre"
                      value={nombre}
                      onChange={(e) => setNombre(e.target.value)}
                      placeholder="Ej: Juan Perez"
                      required
                      data-testid="register-name-input"
                    />
                  </div>
                )}
                <div className="space-y-2">
                  <Label htmlFor="email">Correo electronico</Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="correo@ejemplo.com"
                    required
                    data-testid="login-email-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Contrasena</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPass ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Tu contrasena"
                      required
                      data-testid="login-password-input"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPass(!showPass)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
                <Button type="submit" className="w-full" disabled={loading} data-testid="login-submit-button">
                  {loading ? 'Procesando...' : isRegister ? 'Crear Cuenta' : 'Iniciar Sesion'}
                </Button>
              </form>
              <div className="mt-4 text-center">
                <button
                  onClick={() => setIsRegister(!isRegister)}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                  data-testid="toggle-auth-mode"
                >
                  {isRegister ? 'Ya tengo cuenta. Iniciar sesion' : 'No tengo cuenta. Registrarme'}
                </button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
