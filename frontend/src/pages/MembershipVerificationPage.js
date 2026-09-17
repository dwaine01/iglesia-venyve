import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';
import { BadgeCheck, BadgeX, CalendarDays, ShieldCheck } from 'lucide-react';

const statusCopy = {
  active: ['Carnet vigente', 'La membresía fue verificada por VEN Y VE 360.'],
  expired: ['Carnet vencido', 'La identidad existe, pero la vigencia del carnet terminó.'],
  inactive: ['Membresía inactiva', 'El carnet no está activo actualmente.'],
  invalid: ['Verificación inválida', 'El código no corresponde a un carnet emitido.'],
};

export default function MembershipVerificationPage() {
  const { token } = useParams();
  const API = process.env.REACT_APP_BACKEND_URL;
  const [result, setResult] = useState(null);
  useEffect(() => { axios.get(`${API}/api/public/membership/verify/${encodeURIComponent(token)}`).then((response) => setResult(response.data)).catch(() => setResult({ valid: false, status: 'invalid' })); }, [API, token]);
  if (!result) return <main className="flex min-h-screen items-center justify-center bg-[#EAF1F0]" data-testid="membership-verification-loading">Verificando carnet…</main>;
  const valid = result.valid;
  const copy = statusCopy[result.status] || statusCopy.invalid;
  const Icon = valid ? BadgeCheck : BadgeX;
  return <main className="min-h-screen bg-[#EAF1F0] px-4 py-10" data-testid="membership-verification-page"><section className="mx-auto max-w-xl overflow-hidden border border-[#BCD0CC] bg-white shadow-xl"><header className="bg-[#102A2D] px-6 py-8 text-white"><img src="/assets/membership/church-logo.png" alt="Casa de Oración Ven y Ve" className="h-24 w-24 bg-white object-contain" /><p className="mt-5 text-xs font-bold uppercase tracking-widest text-[#6ED17A]">Verificación oficial</p><h1 className="mt-2 font-['Spectral'] text-4xl font-semibold">{copy[0]}</h1><p className="mt-2 text-sm text-white/70">{copy[1]}</p></header><div className="p-6"><Icon className={`h-12 w-12 ${valid ? 'text-emerald-600' : 'text-red-600'}`} /><dl className="mt-5 divide-y text-sm">{result.member_name && <div className="flex justify-between gap-4 py-3"><dt className="text-slate-500">Miembro</dt><dd className="font-semibold text-right" data-testid="verified-member-name">{result.member_name}</dd></div>}{result.member_number && <div className="flex justify-between gap-4 py-3"><dt className="text-slate-500">Member No.</dt><dd className="font-semibold" data-testid="verified-member-number">{result.member_number}</dd></div>}{result.position && <div className="flex justify-between gap-4 py-3"><dt className="text-slate-500">Cargo</dt><dd className="font-semibold text-right">{result.position}</dd></div>}{result.expires && <div className="flex justify-between gap-4 py-3"><dt className="flex items-center gap-1 text-slate-500"><CalendarDays className="h-4 w-4" />Vigencia</dt><dd className="font-semibold">{result.expires}</dd></div>}</dl><p className="mt-6 flex items-center gap-2 border-l-4 border-[#0879BE] bg-[#EEF7FC] p-3 text-xs text-slate-600"><ShieldCheck className="h-5 w-5 shrink-0 text-[#0879BE]" />Esta página confirma únicamente datos públicos de vigencia. No muestra contacto, dirección ni información financiera.</p></div></section></main>;
}