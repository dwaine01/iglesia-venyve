import React from 'react';
import {
  BookOpen,
  BriefcaseBusiness,
  CalendarCheck2,
  ChevronRight,
  Church,
  ClipboardList,
  Droplets,
  FileClock,
  Handshake,
  HeartHandshake,
  House,
  MapPin,
  Network,
  Phone,
  PlaneTakeoff,
  Sprout,
  UserRound,
  UsersRound,
} from 'lucide-react';
import { Badge } from './ui/badge';

const ICONS = {
  contacto: Phone,
  direcciones: MapPin,
  llegada_origen: PlaneTakeoff,
  membership: UsersRound,
  bautismo: Droplets,
  bienvenida: Handshake,
  consolidacion: Sprout,
  ley7: BookOpen,
  discipulado: UsersRound,
  mentor_acompanamiento: UserRound,
  celula: Network,
  ministerio_servicio: BriefcaseBusiness,
  familia: House,
  household: UsersRound,
  asistencia: CalendarCheck2,
  historial: FileClock,
};

const FALLBACK_ICONS = [Church, HeartHandshake, ClipboardList];

const statusContent = (section) => {
  if (section.status_code === 'has_summary') {
    return { label: 'Registrado', classes: 'bg-emerald-50 text-emerald-700 border-emerald-100' };
  }
  if (section.status_code === 'no_record') {
    return { label: 'Sin registros', classes: 'bg-gray-100 text-gray-600 border-gray-200' };
  }
  if (section.status_code === 'access_restricted') {
    return { label: 'Acceso restringido', classes: 'bg-amber-50 text-amber-700 border-amber-100' };
  }
  return { label: 'No disponible', classes: 'bg-slate-50 text-slate-500 border-slate-200' };
};

export default function Profile360Summary({ sections, available, onSelect }) {
  const modules = sections.filter((section) => section.section_key !== 'core');

  return (
    <section className="rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-[0_10px_30px_rgba(15,26,51,0.05)] sm:p-5" data-testid="profile-360-summary">
      <div className="mb-4">
        <h2 className="text-2xl font-bold tracking-tight text-[#101D36] sm:text-[28px]">Perfil 360°</h2>
        <p className="mt-1 text-sm text-gray-500">Resumen general y acceso a todos los módulos de la persona</p>
      </div>

      <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-3">
        {modules.map((section, index) => {
          const Icon = ICONS[section.section_key] || FALLBACK_ICONS[index % FALLBACK_ICONS.length];
          const targetTab = section.tab_key || section.section_key;
          const canOpen = available.includes(targetTab);
          const status = statusContent(section);
          const unavailable = section.status_code === 'module_unavailable';
          const restricted = section.status_code === 'access_restricted';

          return (
            <button
              key={section.section_key}
              type="button"
              disabled={!canOpen}
              onClick={() => canOpen && onSelect(targetTab)}
              data-testid={`resumen-360-card-${section.section_key}`}
              className={`group min-h-[104px] w-full rounded-lg border p-4 text-left transition-all ${
                canOpen
                  ? 'border-[#DED8C9] bg-white hover:-translate-y-0.5 hover:border-[#C8A951]/70 hover:shadow-md'
                  : 'cursor-default border-gray-200 bg-white'
              } ${section.section_key === 'historial' ? 'xl:col-span-3' : ''}`}
            >
              <div className="flex h-full gap-3">
                <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${canOpen ? 'bg-[#F4EBCF] text-[#785E24]' : 'bg-slate-50 text-[#132443]'}`}>
                  <Icon className="h-5 w-5" strokeWidth={1.8} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-semibold text-[#101D36]">{section.status_label}</h3>
                    <Badge variant="outline" className={`shrink-0 border px-2 py-0.5 text-[10px] font-medium ${status.classes}`}>
                      {status.label}
                    </Badge>
                  </div>
                  <p className={`mt-1 line-clamp-2 text-sm ${unavailable ? 'text-gray-400' : 'text-gray-600'}`}>
                    {section.summary || (unavailable ? 'Módulo aún no disponible' : restricted ? 'Información protegida por permisos' : 'Sin registros todavía')}
                  </p>
                  {!unavailable && (
                    <p className="mt-1 text-xs text-gray-400">{canOpen ? 'Ver información' : 'Fuente protegida'}</p>
                  )}
                </div>
                {canOpen && <ChevronRight className="mt-auto h-4 w-4 shrink-0 text-gray-400 transition-transform group-hover:translate-x-0.5" />}
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
