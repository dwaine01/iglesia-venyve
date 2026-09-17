import React, { useMemo, useState } from 'react';
import {
  BriefcaseBusiness,
  Cake,
  ChevronDown,
  Copy,
  Heart,
  Mail,
  MapPin,
  MoreHorizontal,
  Pencil,
  Phone,
  Trash2,
  UserRound,
  UsersRound,
} from 'lucide-react';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';

const titleCase = (value) => {
  if (!value) return null;
  return value.charAt(0).toUpperCase() + value.slice(1);
};

const formatDate = (iso) => {
  if (!iso) return null;
  try {
    return new Date(`${iso}T12:00:00`).toLocaleDateString('es', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
};

const calculateAge = (iso) => {
  if (!iso) return null;
  const birth = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(birth.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const beforeBirthday =
    today.getMonth() < birth.getMonth() ||
    (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate());
  if (beforeBirthday) age -= 1;
  return age >= 0 ? age : null;
};

function DetailItem({ icon: Icon, label, value, helper }) {
  if (!value) return null;
  return (
    <div className="flex min-w-0 gap-3 border-gray-200 lg:border-r lg:pr-5 last:border-r-0">
      <Icon className="mt-0.5 h-5 w-5 shrink-0 text-[#132443]" />
      <div className="min-w-0">
        <p className="text-xs text-gray-500">{label}</p>
        <p className="truncate text-sm font-semibold text-[#101D36]">{value}</p>
        {helper && <p className="text-xs text-gray-500">{helper}</p>}
      </div>
    </div>
  );
}

export default function PersonProfileHeader({ header, photoSrc, onEdit, onArchive, onSelectTab, onBack }) {
  const [copied, setCopied] = useState(false);
  const age = useMemo(() => calculateAge(header.fecha_nacimiento), [header.fecha_nacimiento]);
  const ageLabel = header.age_category === 'menor' ? 'Menor' : header.age_category === 'adulto' ? 'Adulto' : titleCase(header.age_category);
  const demographicItems = [
    {
      key: 'birth',
      icon: Cake,
      label: 'Fecha de nacimiento',
      value: formatDate(header.fecha_nacimiento),
      helper: age !== null ? `${age} años` : null,
    },
    { key: 'gender', icon: UsersRound, label: 'Género', value: titleCase(header.genero) },
    { key: 'civil', icon: Heart, label: 'Estado civil', value: titleCase(header.estado_civil) },
    {
      key: 'occupation',
      icon: BriefcaseBusiness,
      label: 'Ocupación principal',
      value: header.ocupacion,
      helper: header.habilidades?.map((item) => item.nombre).join(', ') || null,
    },
  ].filter((item) => item.value);

  const copyNumber = async () => {
    await navigator.clipboard.writeText(header.person_number);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <section className="space-y-3" data-testid="person-profile-header">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <button onClick={onBack} className="flex items-center gap-2 text-sm font-medium text-gray-600 transition-colors hover:text-[#132443]" data-testid="person-profile-back-button">
          <span aria-hidden="true">←</span> Volver a Personas
        </button>
        <div className="flex flex-wrap items-center justify-end gap-2 self-end sm:self-auto">
          {onArchive && <Button variant="outline" onClick={onArchive} className="border-red-200 bg-white text-red-700 shadow-sm hover:bg-red-50 hover:text-red-800" data-testid="person-archive-button">
            <Trash2 className="mr-2 h-4 w-4" /> Eliminar Persona
          </Button>}
          <Button variant="outline" onClick={onEdit} disabled={!onEdit} className="bg-white shadow-sm" data-testid="person-profile-edit-button">
            <Pencil className="mr-2 h-4 w-4" /> Editar
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button className="bg-[#132443] text-white shadow-sm hover:bg-[#1C3157]" data-testid="person-profile-actions-button">
                <MoreHorizontal className="mr-2 h-4 w-4" /> Acciones <ChevronDown className="ml-2 h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuItem onSelect={copyNumber} data-testid="person-copy-number-action">
                <Copy /> {copied ? 'VV copiado' : 'Copiar número VV'}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => onSelectTab('contacto')} data-testid="person-view-contact-action">
                <Phone /> Ver contacto
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onSelectTab('direcciones')} data-testid="person-view-addresses-action">
                <MapPin /> Ver direcciones
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-[#E8E5DE] bg-white shadow-[0_12px_35px_rgba(15,26,51,0.07)]">
        <div className="grid lg:grid-cols-[260px_minmax(0,1fr)]">
          <div className="p-3 lg:p-4 lg:pr-0">
            {photoSrc ? (
              <img
                src={photoSrc}
                alt={header.nombre_completo}
                className="h-36 w-36 rounded-lg object-cover shadow-sm sm:h-44 sm:w-44 lg:h-[260px] lg:w-[260px]"
              />
            ) : (
              <div className="flex h-36 w-36 items-center justify-center rounded-lg border border-[#D8C98E] bg-gradient-to-br from-[#F6F0DD] to-[#E8DDB8] text-4xl font-semibold text-[#8A6D2F] shadow-inner sm:h-44 sm:w-44 lg:h-[260px] lg:w-[260px] lg:text-6xl">
                {header.initials}
              </div>
            )}
          </div>

          <div className="flex min-w-0 flex-col px-5 pb-5 pt-2 lg:px-7 lg:py-6">
            <div className="grid flex-1 gap-6 xl:grid-cols-[minmax(0,1fr)_300px]">
              <div className="min-w-0">
                <Badge className="mb-3 bg-[#F2E8C4] font-mono text-[#85671D] hover:bg-[#F2E8C4]">
                  {header.person_number}
                </Badge>
                <h1 className="text-3xl font-bold leading-tight tracking-tight text-[#101D36] sm:text-4xl lg:text-[42px]">
                  {header.nombre_completo}
                </h1>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-gray-600">
                  {ageLabel && (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-3 py-1 font-medium text-gray-700">
                      <UserRound className="h-3.5 w-3.5" /> {ageLabel}
                    </span>
                  )}
                </div>
                <p className="mt-4 max-w-xl text-sm text-gray-500">Perfil único de Persona · Casa de Oración Ven y Ve</p>
              </div>

              {(header.primary_phone || header.primary_email || header.city) && (
                <div className="space-y-4 border-t border-gray-100 pt-5 xl:border-l xl:border-t-0 xl:pl-7 xl:pt-1">
                  {header.primary_phone && (
                    <div className="flex gap-3">
                      <Phone className="mt-0.5 h-5 w-5 shrink-0 text-[#132443]" />
                      <div className="min-w-0"><p className="break-all font-semibold text-[#101D36]">{header.primary_phone}</p><p className="text-xs text-gray-500">Teléfono principal</p></div>
                    </div>
                  )}
                  {header.city && (
                    <div className="flex gap-3">
                      <MapPin className="mt-0.5 h-5 w-5 shrink-0 text-[#132443]" />
                      <div className="min-w-0"><p className="font-semibold text-[#101D36]">{header.city}</p><p className="text-xs text-gray-500">Ubicación actual</p></div>
                    </div>
                  )}
                  {header.primary_email && (
                    <div className="flex gap-3">
                      <Mail className="mt-0.5 h-5 w-5 shrink-0 text-[#132443]" />
                      <div className="min-w-0"><p className="break-all font-semibold text-[#101D36]">{header.primary_email}</p><p className="text-xs text-gray-500">Correo electrónico</p></div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {demographicItems.length > 0 && (
              <div className="mt-6 grid gap-4 border-t border-gray-200 pt-5 sm:grid-cols-2 xl:grid-cols-4">
                {demographicItems.map((item) => <DetailItem key={item.key} {...item} />)}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
