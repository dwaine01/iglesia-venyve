import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { LOGO_IGLESIA } from '../data/presentationData';
import { RoleBadge } from '../components/RoleBadge';
import { toast } from 'sonner';
import { ArrowRight, AlertCircle, CheckCircle2, KeyRound, Mail, Lock, User, Phone, Loader2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

/**
 * /registro o /registro/:code — Registro publico solo por invitación.
 * Muestra un preview del codigo (rol asignado + superior) antes de pedir datos.
 */
export default function RegistroConCodigoPage() {
  const { code: codeParam } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { registerWithCode, user } = useAuth();

  const [code, setCode] = useState((codeParam || params.get('code') || '').toUpperCase());
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');

  const [form, setForm] = useState({
    nombre: '',
    apellido: '',
    email: '',
    password: '',
    telefono: '',
  });
  const [showPwd, setShowPwd] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  React.useEffect(() => {
    if (user) navigate('/');
  }, [user, navigate]);

  const fetchPreview = useCallback(async (c) => {
    if (!c || c.length < 6) return;
    setPreviewLoading(true);
    setPreviewError('');
    try {
      const res = await axios.get(`${API}/api/auth/invitations/${c}/preview`);
      setPreview(res.data);
      if (!res.data.valid) {
        setPreviewError(
          res.data.status === 'expired' ? 'Este código ya expiró'
            : res.data.status === 'used' ? 'Este código ya fue usado'
            : res.data.status === 'revoked' ? 'Este código fue revocado'
            : 'Código no válido',
        );
      }
    } catch (err) {
      setPreview(null);
      setPreviewError(err.response?.data?.detail || 'Código no encontrado');
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  // Si el codigo viene en la URL, valida automaticamente
  useEffect(() => {
    if (code && code.length >= 6) {
      fetchPreview(code);
    }
  }, [code, fetchPreview]);

  const handleCodeBlur = () => {
    if (code) fetchPreview(code);
  };

  const updateField = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    if (!preview?.valid) {
      setSubmitError('Valida el código antes de continuar');
      return;
    }
    setSubmitError('');
    setSubmitting(true);
    try {
      await registerWithCode({
        code: code.trim().toUpperCase(),
        nombre: form.nombre.trim(),
        apellido: form.apellido.trim() || undefined,
        email: form.email.trim().toLowerCase(),
        password: form.password,
        telefono: form.telefono.trim() || undefined,
      });
      toast.success('¡Bienvenido! Tu cuenta fue creada');
      navigate('/');
    } catch (err) {
      const msg = err.response?.data?.detail || 'No se pudo registrar';
      setSubmitError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B1428] flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-lg">
        <div className="rounded-3xl border border-[#C8A951]/25 p-1.5">
          <div className="rounded-[22px] border border-white/10 bg-[#0F1A33]/95 backdrop-blur p-7 sm:p-9">
            {/* Header */}
            <div className="flex flex-col items-center text-center mb-6">
              <img
                src={LOGO_IGLESIA}
                alt="Ven y Ve"
                className="w-16 h-16 rounded-full mb-3"
                style={{ mixBlendMode: 'screen' }}
              />
              <p className="text-[10px] uppercase tracking-[0.35em] text-[#C8A951] font-bold">Registro por Invitación</p>
              <h1 className="mt-1 text-2xl font-bold text-white" style={{ fontFamily: 'Spectral, serif' }}>
                Activar mi acceso
              </h1>
              <p className="mt-1 text-xs text-white/50">Casa de Oración Ven y Ve</p>
            </div>

            {/* Codigo + preview */}
            <div className="mb-5">
              <Label className="text-xs uppercase tracking-[0.2em] text-white/70 font-bold">Código de invitación</Label>
              <div className="relative mt-1.5">
                <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <Input
                  value={code}
                  onChange={(e) => { setCode(e.target.value.toUpperCase()); setPreview(null); setPreviewError(''); }}
                  onBlur={handleCodeBlur}
                  placeholder="EJ. A8K3X7QP"
                  required
                  data-testid="register-code-input"
                  className="pl-9 bg-white/5 border-white/15 text-white placeholder:text-white/30 focus-visible:ring-[#C8A951] font-mono uppercase tracking-widest"
                />
              </div>
              {previewLoading && (
                <p className="mt-2 flex items-center gap-2 text-xs text-white/60">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Validando código...
                </p>
              )}
              {preview?.valid && (
                <div className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3" data-testid="register-preview-valid">
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs uppercase tracking-widest text-emerald-300 font-bold">Código válido</span>
                  </div>
                  <p className="text-sm text-white/80">
                    Te registrarás como{' '}
                    <RoleBadge rol={preview.target_role} size="sm" />
                  </p>
                  <p className="text-xs text-white/60 mt-1">
                    Asignado a <strong className="text-white">{preview.superior_nombre}</strong>
                  </p>
                </div>
              )}
              {previewError && (
                <div className="mt-2 flex items-start gap-2 text-xs text-red-300">
                  <AlertCircle className="w-3.5 h-3.5 mt-0.5" />
                  <span>{previewError}</span>
                </div>
              )}
            </div>

            <form onSubmit={submit} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <FieldInput
                  label="Nombre"
                  icon={User}
                  value={form.nombre}
                  onChange={(v) => updateField('nombre', v)}
                  placeholder="María"
                  required
                  testId="register-nombre"
                />
                <FieldInput
                  label="Apellido"
                  icon={User}
                  value={form.apellido}
                  onChange={(v) => updateField('apellido', v)}
                  placeholder="Pérez"
                  testId="register-apellido"
                />
              </div>
              <FieldInput
                label="Correo"
                type="email"
                icon={Mail}
                value={form.email}
                onChange={(v) => updateField('email', v)}
                placeholder="tu@correo.com"
                required
                testId="register-email"
              />
              <FieldInput
                label="Teléfono (opcional)"
                icon={Phone}
                value={form.telefono}
                onChange={(v) => updateField('telefono', v)}
                placeholder="+1 809 555 0000"
                testId="register-telefono"
              />
              <FieldInput
                label="Contraseña"
                type={showPwd ? 'text' : 'password'}
                icon={Lock}
                value={form.password}
                onChange={(v) => updateField('password', v)}
                placeholder="Mínimo 6 caracteres"
                required
                testId="register-password"
                rightAction={
                  <button
                    type="button"
                    onClick={() => setShowPwd((s) => !s)}
                    className="text-white/40 hover:text-white/80 text-xs uppercase tracking-wider"
                  >
                    {showPwd ? 'Ocultar' : 'Mostrar'}
                  </button>
                }
              />

              {submitError && (
                <div className="flex items-start gap-2 text-sm text-red-300 bg-red-900/20 border border-red-500/30 rounded-lg p-3">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{submitError}</span>
                </div>
              )}

              <Button
                type="submit"
                disabled={submitting || !preview?.valid}
                data-testid="register-submit"
                className="w-full bg-gradient-to-r from-[#C8A951] to-[#E2CF8A] text-[#1B2A4A] hover:opacity-95 font-bold uppercase tracking-wider mt-2"
              >
                {submitting ? 'Creando cuenta...' : (
                  <span className="inline-flex items-center gap-2">
                    Activar mi acceso <ArrowRight className="w-4 h-4" />
                  </span>
                )}
              </Button>
            </form>

            <p className="mt-5 text-center text-xs text-white/50">
              ¿Ya tienes cuenta?{' '}
              <button onClick={() => navigate('/login')} className="text-[#C8A951] hover:text-[#E2CF8A] underline-offset-4 hover:underline">
                Iniciar sesión
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function FieldInput({ label, icon: Icon, value, onChange, type = 'text', placeholder, required, testId, rightAction }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs uppercase tracking-[0.2em] text-white/70 font-bold">{label}</Label>
      <div className="relative">
        {Icon && <Icon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />}
        <Input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          required={required}
          data-testid={testId}
          className={`bg-white/5 border-white/15 text-white placeholder:text-white/30 focus-visible:ring-[#C8A951] ${Icon ? 'pl-9' : ''} ${rightAction ? 'pr-20' : ''}`}
        />
        {rightAction && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            {rightAction}
          </div>
        )}
      </div>
    </div>
  );
}
