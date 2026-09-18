import React from 'react';
import { Flame, MapPin, Network } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';

const categoryOptions = [['all', 'Todas las categorías'], ['members', 'Miembros activos'], ['new', 'Personas nuevas'], ['consolidation', 'En Consolidación'], ['discipleship', 'En Discipulado'], ['front_group', 'Con Grupo Frontal'], ['cell', 'En Célula']];

export const GeoFilters = ({ filters, setFilters, catalog, mode, setMode, canViewPrecise }) => {
  const update = (key, value) => setFilters((current) => ({ ...current, [key]: value === 'all' ? '' : value }));
  return <section className="border bg-white p-4" data-testid="geo-filter-panel">
    <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-['Spectral'] text-xl font-semibold">Filtros geográficos</h2><p className="text-xs text-slate-500">La ubicación nunca se consulta nuevamente al abrir el mapa.</p></div><div className="flex border" data-testid="geo-map-mode-control"><Button type="button" size="sm" variant={mode === 'heatmap' ? 'default' : 'ghost'} onClick={() => setMode('heatmap')} data-testid="geo-mode-heatmap"><Flame className="h-4 w-4" />Densidad</Button><Button type="button" size="sm" variant={mode === 'clusters' ? 'default' : 'ghost'} onClick={() => setMode('clusters')} data-testid="geo-mode-clusters"><Network className="h-4 w-4" />Clusters</Button>{canViewPrecise && <Button type="button" size="sm" variant={mode === 'pins' ? 'default' : 'ghost'} onClick={() => setMode('pins')} data-testid="geo-mode-pins"><MapPin className="h-4 w-4" />Pines</Button>}</div></div>
    <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
      <div className="space-y-1"><Label>Categoría</Label><Select value={filters.category || 'all'} onValueChange={(value) => update('category', value)}><SelectTrigger data-testid="geo-category-filter"><SelectValue /></SelectTrigger><SelectContent className="bg-white">{categoryOptions.map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div>
      <div className="space-y-1"><Label>Zona</Label><Select value={filters.zone || 'all'} onValueChange={(value) => update('zone', value)}><SelectTrigger data-testid="geo-zone-filter"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todas</SelectItem><SelectItem value="north">Norte</SelectItem><SelectItem value="east">Este</SelectItem><SelectItem value="south">Sur</SelectItem><SelectItem value="west">Oeste</SelectItem></SelectContent></Select></div>
      <div className="space-y-1"><Label>Etapa</Label><Select value={filters.stage || 'all'} onValueChange={(value) => update('stage', value)}><SelectTrigger data-testid="geo-stage-filter"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todas</SelectItem>{catalog.stages.map((item) => <SelectItem key={item.stage_key} value={item.stage_key}>{item.stage_name}</SelectItem>)}</SelectContent></Select></div>
      <div className="space-y-1"><Label>Grupo Frontal</Label><Select value={filters.front_group_id || 'all'} onValueChange={(value) => update('front_group_id', value)}><SelectTrigger data-testid="geo-front-group-filter"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todos</SelectItem>{catalog.front_groups.map((item) => <SelectItem key={item.front_group_id} value={item.front_group_id}>{item.name}</SelectItem>)}</SelectContent></Select></div>
      <div className="space-y-1"><Label>Célula</Label><Select value={filters.cell_id || 'all'} onValueChange={(value) => update('cell_id', value)}><SelectTrigger data-testid="geo-cell-filter"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="all">Todas</SelectItem>{catalog.cells.map((item) => <SelectItem key={item.cell_id} value={item.cell_id}>{item.name}</SelectItem>)}</SelectContent></Select></div>
      <div className="space-y-1"><Label>Desde</Label><Input type="date" value={filters.period_start} onChange={(event) => update('period_start', event.target.value)} data-testid="geo-period-start-filter" /></div>
    </div>
  </section>;
};