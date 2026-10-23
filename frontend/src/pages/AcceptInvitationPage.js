import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Eye, EyeOff } from 'lucide-react';

import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { LOGO_IGLESIA } from '../data/presentationData';
import { BRAND } from '../config/brand';

const API = process.env.REACT_APP_BACKEND_URL;

// C5: la persona invitada abre este enlace de un solo uso y define su propia
// contraseña (nunca la escribió quien creó la cuenta).
export default function AcceptInvitationPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [password, setPassword] = useState(''); const [confirm, setConfirm] = useState('');
  const [showPass, setShowPass] = useState(false); const [loading, setLoading] = useState(false); const [done, setDone] = useState(false);
  const navigate = useNavigate();

  const submit = async (event) => {
    event.preventDefault();
    if (password.length < 10) { toast.error('La contraseña debe tener al menos 10 caracteres'); return; }
    if (password !== confirm) { toast.error('Las contraseñas no coinciden'); return; }
    setLoading(true);
    try {
      await axios.post(`${API}/api/auth/accept-invitation`, { token, new_password: password });
      setDone(true);
      toast.success('Contraseña establecida. Ya puede iniciar sesión.');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Invitación inválida o vencida');
    } finally { setLoading(false); }
  };

  return <div className="grid min-h-screen place-items-center bg-[#0B1428] px-6" data-testid="accept-invitation-page">
    <div className="w-full max-w-md border border-[#C8A951]/45 bg-white/[0.03] p-8 backdrop-blur-xl">
      <img src={LOGO_IGLESIA} alt={BRAND.name} className="mx-auto h-16 w-16 object-contain logo-transparent" />
      <h1 className="mt-4 text-center font-['Spectral'] text-2xl font-semibold text-white">Active su acceso</h1>
      {!token ? <p className="mt-4 text-center text-sm text-red-400" data-testid="accept-invitation-missing-token">Enlace de invitación inválido.</p>
        : done ? <div className="mt-6 space-y-4 text-center">
          <p className="text-sm text-emerald-300" data-testid="accept-invitation-success">Su contraseña fue creada correctamente.</p>
          <Button onClick={() => navigate('/login')} className="w-full bg-[#C8A951] text-[#0B1428] hover:bg-[#B8993F]" data-testid="accept-invitation-go-login-button">Iniciar sesión</Button>
        </div>
        : <form onSubmit={submit} className="mt-6 space-y-4">
          <div>
            <Label className="text-xs uppercase text-white/75">Nueva contraseña</Label>
            <div className="relative">
              <Input type={showPass ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} className="border-white/20 bg-transparent pr-10 text-white" data-testid="accept-invitation-password-input" />
              <button type="button" onClick={() => setShowPass(!showPass)} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40" aria-label="Mostrar/ocultar contraseña" data-testid="accept-invitation-toggle-password">
                {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <div>
            <Label className="text-xs uppercase text-white/75">Confirmar contraseña</Label>
            <Input type={showPass ? 'text' : 'password'} value={confirm} onChange={(event) => setConfirm(event.target.value)} className="border-white/20 bg-transparent text-white" data-testid="accept-invitation-confirm-input" />
          </div>
          <Button type="submit" disabled={loading} className="w-full bg-[#C8A951] text-[#0B1428] hover:bg-[#B8993F]" data-testid="accept-invitation-submit-button">{loading ? 'Procesando…' : 'Establecer contraseña'}</Button>
        </form>}
    </div>
  </div>;
}
