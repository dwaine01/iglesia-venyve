import React from 'react';
import { FilterX, Search, SlidersHorizontal } from 'lucide-react';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { DirectoryFilterSelect } from './DirectoryFilterSelect';

const AGE_OPTIONS = [
  { value: 'ninez', label: 'Niñez' },
  { value: 'adolescencia', label: 'Adolescencia' },
  { value: 'adulto', label: 'Adulto' },
];

const GENDER_OPTIONS = [
  { value: 'masculino', label: 'Masculino' },
  { value: 'femenino', label: 'Femenino' },
  { value: 'no_especificado', label: 'No especificado' },
];

export const DirectoryFilters = ({
  filters,
  occupationOptions,
  skillOptions,
  ministries,
  roles,
  activeLabels,
  onChange,
  onClear,
}) => (
  <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-6" data-testid="directory-filters-panel">
    <div className="mb-5 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        <SlidersHorizontal className="h-4 w-4 text-amber-700" />
        <h2 className="font-semibold text-slate-900">Criterios de búsqueda</h2>
      </div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={onClear}
        disabled={activeLabels.length === 0}
        data-testid="directory-clear-filters-button"
      >
        <FilterX className="mr-2 h-4 w-4" />
        Limpiar
      </Button>
    </div>

    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <div className="space-y-2 sm:col-span-2 xl:col-span-3">
        <Label htmlFor="global-search-input" className="text-xs font-semibold uppercase text-slate-500">
          Nombre, VV, talento, ministerio o función
        </Label>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            id="global-search-input"
            data-testid="global-search-input"
            value={filters.q}
            onChange={(event) => onChange('q', event.target.value)}
            placeholder="Ej. Mecánico, sonido, VV-000123..."
            className="h-11 bg-white pl-10"
          />
        </div>
      </div>

      <DirectoryFilterSelect id="filter-occupation-select" label="Ocupación" value={filters.occupationId} placeholder="Todas las ocupaciones" options={occupationOptions} onChange={(value) => onChange('occupationId', value)} />
      <DirectoryFilterSelect id="filter-skill-select" label="Habilidad" value={filters.skillId} placeholder="Todas las habilidades" options={skillOptions} onChange={(value) => onChange('skillId', value)} />
      <DirectoryFilterSelect id="filter-age-select" label="Grupo etario" value={filters.ageGroup} placeholder="Todas las edades" options={AGE_OPTIONS} onChange={(value) => onChange('ageGroup', value)} />
      <DirectoryFilterSelect id="filter-ministry-select" label="Ministerio" value={filters.ministryId} placeholder="Todos los ministerios" options={ministries} onChange={(value) => onChange('ministryId', value)} />
      <DirectoryFilterSelect id="filter-role-select" label="Función ministerial" value={filters.roleId} placeholder="Todas las funciones" options={roles} onChange={(value) => onChange('roleId', value)} />
      <DirectoryFilterSelect id="filter-gender-select" label="Género" value={filters.gender} placeholder="Todos los géneros" options={GENDER_OPTIONS} onChange={(value) => onChange('gender', value)} />
    </div>

    <div className="mt-4 flex flex-wrap items-center gap-2" data-testid="directory-active-filters">
      {activeLabels.map((label) => <Badge key={label} variant="secondary">{label}</Badge>)}
      <Badge variant="outline" className="border-dashed text-slate-500" data-testid="filter-membership-select">
        Membresía · módulo pendiente
      </Badge>
    </div>
  </section>
);