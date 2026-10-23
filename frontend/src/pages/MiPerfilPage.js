import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { Loader2, Mail, MapPin, Network, ShieldCheck, TriangleAlert, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { displayLabel, translateTechnicalText } from '../lib/displayLabels';

// ETAPA 5A: "Mi perfil" — siempre disponible para toda cuenta, sin importar
// qué módulos tenga asignados (no depende de ninguna capability).
export default function MiPerfilPage() {
  const { API, getAuthHeaders } = useAuth();
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    axios.get(`${API}/api/core/me/profile`, getAuthHeaders())
      .then((response) => setProfile(response.data))
      .catch((requestError) => setError(translateTechnicalText(requestError?.response?.data?.detail || 'No se pudo cargar tu perfil.')));
  }, [API, getAuthHeaders]);

  if (error) return <div className="min-h-screen bg-[#F8F6F0] p-4" data-testid="mi-perfil-error"><div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700"><TriangleAlert className="mt-0.5 h-4 w-4" />{error}</div></div>;
  if (!profile) return <div className="flex min-h-[60vh] items-center justify-center" data-testid="mi-perfil-loading"><Loader2 className="h-7 w-7 animate-spin text-[#9A7A2F]" /></div>;

  const { person, contacts, addresses, ministries, front_groups: frontGroups, mentor_badge: mentorBadge, account } = profile;
  const fullName = `${person?.nombre || ''} ${person?.apellido || ''}`.trim();

  return (
    <div className="min-h-screen bg-[#F8F6F0] pb-10" data-testid="mi-perfil-page">
      <motion.header initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="bg-[#101D36] px-4 py-8 text-white sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-3xl items-center gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full border border-[#D4B871]/40 bg-[#0B1428] text-xl font-bold text-[#D4B871]">{fullName.slice(0, 1).toUpperCase() || '?'}</div>
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase text-[#D4B871]">Mi perfil</p>
            <h1 className="mt-1 truncate font-['Spectral'] text-2xl font-bold sm:text-3xl" data-testid="mi-perfil-nombre">{fullName || 'Sin nombre'}</h1>
            <p className="mt-1 text-xs text-white/60">{person?.person_number}{account?.access_title ? ` · ${account.access_title}` : ''}{account?.rol ? ` · ${displayLabel(account.rol)}` : ''}</p>
          </div>
        </div>
      </motion.header>

      <div className="mx-auto max-w-3xl space-y-4 px-4 py-6 sm:px-6 lg:px-8">
        <section className="rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid="mi-perfil-contactos">
          <h2 className="flex items-center gap-2 font-['Spectral'] text-lg font-semibold text-[#101D36]"><Mail className="h-4 w-4 text-[#9A7A2F]" />Contacto</h2>
          {contacts?.length ? <ul className="mt-3 space-y-2 text-sm text-slate-700">{contacts.map((item) => <li key={item.contact_id}>{displayLabel(item.tipo)}: <b>{item.valor}</b>{item.es_principal && <span className="ml-2 text-xs text-[#9A7A2F]">(principal)</span>}</li>)}</ul> : <p className="mt-2 text-sm text-slate-400">Aún no tienes contactos registrados.</p>}
        </section>

        <section className="rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid="mi-perfil-direcciones">
          <h2 className="flex items-center gap-2 font-['Spectral'] text-lg font-semibold text-[#101D36]"><MapPin className="h-4 w-4 text-[#9A7A2F]" />Direcciones</h2>
          {addresses?.length ? <ul className="mt-3 space-y-2 text-sm text-slate-700">{addresses.map((item) => <li key={item.address_id}>{[item.linea1, item.sector, item.ciudad].filter(Boolean).join(', ')}</li>)}</ul> : <p className="mt-2 text-sm text-slate-400">Aún no tienes direcciones registradas.</p>}
        </section>

        <section className="rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid="mi-perfil-ministerios">
          <h2 className="flex items-center gap-2 font-['Spectral'] text-lg font-semibold text-[#101D36]"><User className="h-4 w-4 text-[#9A7A2F]" />Ministerios y cargos</h2>
          {ministries?.length ? <ul className="mt-3 space-y-2 text-sm text-slate-700">{ministries.map((item) => <li key={item.ministry_id}>{item.nombre}{item.rol ? ` · ${displayLabel(item.rol)}` : ''}</li>)}</ul> : <p className="mt-2 text-sm text-slate-400">Aún no tienes ministerios asignados.</p>}
          {mentorBadge?.active && <p className="mt-3 flex items-center gap-1.5 text-sm text-[#9A7A2F]" data-testid="mi-perfil-insignia-mentor"><ShieldCheck className="h-4 w-4" />Insignia de Mentor vigente</p>}
        </section>

        <section className="rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid="mi-perfil-grupos-frontales">
          <h2 className="flex items-center gap-2 font-['Spectral'] text-lg font-semibold text-[#101D36]"><Network className="h-4 w-4 text-[#9A7A2F]" />Grupos Frontales</h2>
          {frontGroups?.length ? <ul className="mt-3 space-y-3 text-sm text-slate-700">{frontGroups.map((group) => <li key={group.front_group_id} data-testid={`mi-perfil-grupo-${group.front_group_id}`}>
            <b className="block">{group.name}</b>
            <span className="text-xs text-slate-500">Perteneces a este Grupo Frontal{group.my_role === 'leader' ? ' como líder' : group.my_role === 'co_leader' ? ' como colíder' : ''}. Líder: {group.leader_name || 'Por definir'}{group.co_leader_name ? ` · Colíder: ${group.co_leader_name}` : ''}</span>
          </li>)}</ul> : <p className="mt-2 text-sm text-slate-400">Aún no perteneces a ningún Grupo Frontal.</p>}
        </section>
      </div>
    </div>
  );
}
