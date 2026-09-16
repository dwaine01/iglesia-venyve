import React, { useState } from 'react';
import { KeyRound, Loader2 } from 'lucide-react';
import { Navigate, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { useAuth } from '../context/AuthContext';
import { translateTechnicalText } from '../lib/displayLabels';

export default function ChangePasswordPage() {
  const { user, loading, changePassword } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ current_password: '', new_password: '', confirmation: '' });
  const [saving, setSaving] = useState(false);

  if (loading) return <div className="flex min-h-screen items-center justify-center" data-testid="password-change-loading"><Loader2 className="h-7 w-7 animate-spin" /></div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.must_change_password) return <Navigate to="/" replace />;

  const submit = async (event) => {
    event.preventDefault();
    if (form.new_password !== form.confirmation) return toast.error('Las claves nuevas no coinciden');
    setSaving(true);
    try {
      await changePassword(form.current_password, form.new_password);
      toast.success('Clave actualizada');
      navigate('/', { replace: true });
    } catch (error) {
      toast.error(translateTechnicalText(error?.response?.data?.detail || 'No se pudo cambiar la clave'));
    } finally { setSaving(false); }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#F4F1E8] px-4" data-testid="change-password-page">
      <section className="w-full max-w-md border border-[#D9D1C3] bg-white p-7 shadow-xl">
        <KeyRound className="h-9 w-9 text-[#9A7A2F]" />
        <h1 className="mt-4 font-['Spectral'] text-3xl font-semibold text-[#101D36]" data-testid="change-password-title">Crea tu clave personal</h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">Por seguridad, reemplaza la clave temporal antes de entrar a tu panel.</p>
        <form className="mt-6 space-y-4" onSubmit={submit}>
          <div><Label htmlFor="current-password">Clave temporal</Label><Input id="current-password" type="password" value={form.current_password} onChange={(event) => setForm((old) => ({ ...old, current_password: event.target.value }))} required data-testid="current-password-input" /></div>
          <div><Label htmlFor="new-password">Nueva clave</Label><Input id="new-password" type="password" minLength={10} value={form.new_password} onChange={(event) => setForm((old) => ({ ...old, new_password: event.target.value }))} required data-testid="new-password-input" /></div>
          <div><Label htmlFor="confirm-password">Confirmar nueva clave</Label><Input id="confirm-password" type="password" minLength={10} value={form.confirmation} onChange={(event) => setForm((old) => ({ ...old, confirmation: event.target.value }))} required data-testid="confirm-password-input" /></div>
          <Button type="submit" disabled={saving} className="w-full bg-[#101D36]" data-testid="change-password-submit-button">{saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />}Guardar mi clave</Button>
        </form>
      </section>
    </main>
  );
}