import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useParams } from 'react-router-dom';
import { BadgeCheck, BadgeX, CalendarDays, MapPin, ShieldCheck, UserRound } from 'lucide-react';

const statusCopy = {
  active: ['Bautismo verificado', 'El certificado fue verificado por VEN Y VE 360.'],
  invalid: ['Verificación inválida', 'El código no corresponde a un certificado emitido.'],
};

export default function BaptismVerificationPage() {
  const { token } = useParams();
  const API = process.env.REACT_APP_BACKEND_URL;
  const [result, setResult] = useState(null);
  useEffect(() => { axios.get(`${API}/api/public/baptism/verify/${encodeURIComponent(token)}`).then((response) => setResult(response.data)).catch(() => setResult({ valid: false, status: 'invalid' })); }, [API, token]);
  if (!result) return <main className="flex min-h-screen items-center justify-center bg-[#EAF1F0]" data-testid="baptism-verification-loading">Verificando certificado…</main>;
  const valid = result.valid;
  const copy = statusCopy[result.status] || statusCopy.invalid;
  const Icon = valid ? BadgeCheck : BadgeX;
  return <main className="min-h-screen bg-[#EAF1F0] px-4 py-10" data-testid="baptism-verification-page"><section className="mx-auto max-w-xl overflow-hidden border border-[#BCD0CC] bg-white shadow-xl"><header className="bg-[#102A2D] px-6 py-8 text-white"><img src="/assets/membership/church-logo.png" alt="Casa de Oración Ven y Ve" className="h-24 w-24 bg-white object-contain" /><p className="mt-5 text-xs font-bold uppercase tracking-widest text-[#6ED17A]">Verificación oficial</p><h1 className="mt-2 font-['Spectral'] text-4xl font-semibold">{copy[0]}</h1><p className="mt-2 text-sm text-white/70">{copy[1]}</p></header><div className="p-6"><Icon className={`h-12 w-12 ${valid ? 'text-emerald-600' : 'text-red-600'}`} /><dl className="mt-5 divide-y text-sm">{result.member_name && <div className="flex justify-between gap-4 py-3"><dt className="text-slate-500">Bautizado(a)</dt><dd className="font-semibold text-right" data-testid="verified-baptism-name">{result.member_name}</dd></div>}{result.baptism_date && <div className="flex justify-between gap-4 py-3"><dt className="flex items-center gap-1 text-slate-500"><CalendarDays className="h-4 w-4" />Fecha</dt><dd className="font-semibold" data-testid="verified-baptism-date">{result.baptism_date}</dd></div>}{result.location && <div className="flex justify-between gap-4 py-3"><dt className="flex items-center gap-1 text-slate-500"><MapPin className="h-4 w-4" />Lugar</dt><dd className="font-semibold text-right">{result.location}</dd></div>}{result.officiant_name && <div className="flex justify-between gap-4 py-3"><dt className="flex items-center gap-1 text-slate-500"><UserRound className="h-4 w-4" />Ministro</dt><dd className="font-semibold text-right">{result.officiant_name}</dd></div>}</dl><p className="mt-6 flex items-center gap-2 border-l-4 border-[#0879BE] bg-[#EEF7FC] p-3 text-xs text-slate-600"><ShieldCheck className="h-5 w-5 shrink-0 text-[#0879BE]" />Esta página confirma únicamente el registro público del certificado. No muestra contacto, dirección ni información financiera.</p></div></section></main>;
}
