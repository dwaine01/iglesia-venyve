import React from 'react';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

const categoryOptions = [['all', 'Todas'], ['members', 'Miembros activos'], ['new', 'Personas nuevas'], ['consolidation', 'En Consolidación'], ['discipleship', 'En Discipulado'], ['front_group', 'Con Grupo Frontal'], ['cell', 'En Célula']];
const zones = [['all', 'Todas'], ['north', 'Zona 1 · Norte'], ['east', 'Zona 2 · Este'], ['south', 'Zona 3 · Sur'], ['west', 'Zona 4 · Oeste']];

export const GeoFilters = ({ filters, setFilters, catalog }) => {
  const update = (key, value) => setFilters((current) => ({ ...current, [key]: value === 'all' ? '' : value }));
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="geo-filter-panel">
    <div className="space-y-1"><Label>Categoría</Label><Select value={filters.category || 'all'} onValueChange={(value) => update('category', value)}><SelectTrigger data-testid="geo-category-filter"><SelectValue /></SelectTrigger><SelectContent className="bg-white">{categoryOptions.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div>
    <div className="space-y-1"><Label>Zona</Label><Select value={filters.zone || 'all'} onValueChange={(value) => update('zone', value)}><SelectTrigger data-testid="geo-zone-filter"><SelectValue /></SelectTrigger><SelectContent className="bg-white">{zones.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div>
    <div className="space-y-1"><Label>Subzona</Label><Select value={filters.subzone || 'all'} onValueChange={(value) => update('subzone', value)}><SelectTrigger data-testid="geo-subzone-filter"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todas</SelectItem>{[1, 2, 3, 4].flatMap((number) => ['A', 'B', 'C'].map((letter) => <SelectItem key={`${number}-${letter}`} value={`${number}-${letter}`}>{number}-{letter}</SelectItem>))}</SelectContent></Select></div>
    <div className="space-y-1"><Label>Etapa</Label><Select value={filters.stage || 'all'} onValueChange={(value) => update('stage', value)}><SelectTrigger data-testid="geo-stage-filter"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todas</SelectItem>{catalog.stages.map((item) => <SelectItem key={item.stage_key} value={item.stage_key}>{item.stage_name}</SelectItem>)}</SelectContent></Select></div>
    <div className="space-y-1"><Label>Grupo Frontal</Label><Select value={filters.front_group_id || 'all'} onValueChange={(value) => update('front_group_id', value)}><SelectTrigger data-testid="geo-front-group-filter"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todos</SelectItem>{catalog.front_groups.map((item) => <SelectItem key={item.front_group_id} value={item.front_group_id}>{item.name}</SelectItem>)}</SelectContent></Select></div>
    <div className="space-y-1"><Label>Célula</Label><Select value={filters.cell_id || 'all'} onValueChange={(value) => update('cell_id', value)}><SelectTrigger data-testid="geo-cell-filter"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todas</SelectItem>{catalog.cells.map((item) => <SelectItem key={item.cell_id} value={item.cell_id}>{item.name}</SelectItem>)}</SelectContent></Select></div>
    <div className="space-y-1 sm:col-span-2 lg:col-span-3"><Label>Personas registradas desde</Label><Input type="date" value={filters.period_start} onChange={(event) => update('period_start', event.target.value)} data-testid="geo-period-start-filter" /></div>
  </div>;
};