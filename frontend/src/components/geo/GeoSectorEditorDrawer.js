import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Edit3, Loader2, Map, Plus, Save, Trash2, Undo2, X } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../ui/alert-dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';
import { closedPolygon } from './geoGeometry';

const blank = { zone_id: 'north', name: '', description: '', color: '#3B82F6' };
const zoneLabels = { north: 'Zona 1 · Norte', east: 'Zona 2 · Este', south: 'Zona 3 · Sur', west: 'Zona 4 · Oeste' };

export const GeoSectorEditorDrawer = ({ open, onOpenChange, sectors, draft, setDraft, selectedVertex, setSelectedVertex, onSaved, onFocusSector, onDrawingChange }) => {
  const { API, getAuthHeaders } = useAuth(); const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(blank); const [busy, setBusy] = useState(false); const [overlap, setOverlap] = useState(null);
  useEffect(() => { if (!open) { setEditing(null); setDraft([]); setSelectedVertex(null); setForm(blank); onDrawingChange(false); } }, [open, setDraft, setSelectedVertex, onDrawingChange]);
  const begin = (sector = null) => {
    setEditing(sector?.sector_id || 'new'); setForm(sector ? { zone_id: sector.zone_id, name: sector.name, description: sector.description || '', color: sector.color } : blank);
    setDraft(sector ? sector.geometry.coordinates[0].slice(0, -1) : []); setSelectedVertex(null); onDrawingChange(true); if (sector) onFocusSector(sector);
  };
  const cancel = () => { setEditing(null); setDraft([]); setSelectedVertex(null); setForm(blank); onDrawingChange(false); };
  const requestSave = async (allowOverlap = false) => {
    if (draft.length < 3) { toast.error('Dibuje al menos tres vértices'); return; }
    const payload = { ...form, name: form.name.trim() || undefined, description: form.description.trim() || undefined, geometry: closedPolygon(draft), allow_overlap: allowOverlap };
    setBusy(true);
    try {
      if (editing === 'new') await axios.post(`${API}/api/geo/sectors`, payload, getAuthHeaders());
      else await axios.put(`${API}/api/geo/sectors/${editing}`, payload, getAuthHeaders());
      toast.success(editing === 'new' ? 'Sector territorial creado' : 'Sector actualizado'); setOverlap(null); cancel(); await onSaved();
    } catch (error) {
      const detail = error.response?.data?.detail;
      if (error.response?.status === 409 && detail?.code === 'SECTOR_OVERLAP') setOverlap({ payload, conflicts: detail.conflicts || [] });
      else toast.error(apiErrorMessage(error, 'No se pudo guardar el sector'));
    } finally { setBusy(false); }
  };
  const deactivate = async (sector) => {
    setBusy(true); try { await axios.delete(`${API}/api/geo/sectors/${sector.sector_id}`, getAuthHeaders()); toast.success('Sector desactivado sin borrar su historial'); if (editing === sector.sector_id) cancel(); await onSaved(); }
    catch (error) { toast.error(apiErrorMessage(error, 'No se pudo desactivar el sector')); } finally { setBusy(false); }
  };
  const removeVertex = () => {
    if (selectedVertex === null) return; setDraft(draft.filter((_, index) => index !== selectedVertex)); setSelectedVertex(null);
  };
  return <>
    {open && <aside role="dialog" aria-modal="false" aria-label="Editor de sectores" className="fixed inset-y-0 right-0 z-50 w-full overflow-y-auto border-l bg-white p-0 shadow-2xl sm:max-w-md" data-testid="geo-sector-editor-drawer">
      <header className="relative border-b bg-slate-950 p-5 pr-14 text-left text-white"><h2 className="flex items-center gap-2 text-lg font-semibold text-white"><Map className="h-5 w-5 text-cyan-400" />Editor de sectores</h2><p className="mt-2 text-sm text-slate-300">Dibuje límites sobre calles reales. El ajuste automático a calles queda opcional.</p><Button variant="ghost" size="icon" className="absolute right-3 top-3 text-white hover:bg-white/10 hover:text-white" onClick={() => onOpenChange(false)} data-testid="close-geo-sector-editor" aria-label="Cerrar editor"><X className="h-5 w-5" /></Button></header>
      <div className="space-y-5 p-5">
        {!editing && <><Button className="w-full bg-cyan-700 text-white hover:bg-cyan-800" onClick={() => begin()} data-testid="create-geo-sector-button"><Plus className="h-4 w-4" />Crear sector</Button>
          <div className="space-y-2" data-testid="geo-sector-list">{sectors.length === 0 && <p className="border border-dashed p-4 text-center text-sm text-slate-500" data-testid="geo-sector-list-empty">Todavía no hay sectores personalizados.</p>}{sectors.map((sector) => <article key={sector.sector_id} className="border-l-4 bg-slate-50 p-3" style={{ borderColor: sector.color }} data-testid={`geo-sector-item-${sector.sector_id}`}><div className="flex items-start justify-between gap-3"><div><b className="block text-sm">{sector.name}</b><small className="text-slate-500">{zoneLabels[sector.zone_id]} · {sector.stats?.households_count || 0} hogares</small></div><div className="flex"><Button variant="ghost" size="icon" onClick={() => begin(sector)} data-testid={`edit-geo-sector-${sector.sector_id}`} aria-label={`Editar ${sector.name}`}><Edit3 className="h-4 w-4" /></Button><Button variant="ghost" size="icon" className="text-red-700" onClick={() => deactivate(sector)} disabled={busy} data-testid={`deactivate-geo-sector-${sector.sector_id}`} aria-label={`Desactivar ${sector.name}`}><Trash2 className="h-4 w-4" /></Button></div></div></article>)}</div></>}
        {editing && <div className="space-y-4" data-testid="geo-sector-form"><div><Label>Zona oficial</Label><Select value={form.zone_id} onValueChange={(value) => setForm((current) => ({ ...current, zone_id: value }))}><SelectTrigger data-testid="geo-sector-zone-select"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(zoneLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div>
          <div><Label htmlFor="geo-sector-name">Nombre</Label><Input id="geo-sector-name" value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} placeholder="Se asigna automáticamente si queda vacío" data-testid="geo-sector-name-input" /></div>
          <div><Label htmlFor="geo-sector-description">Descripción / notas</Label><Textarea id="geo-sector-description" value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} data-testid="geo-sector-description-input" /></div>
          <div><Label htmlFor="geo-sector-color">Color territorial</Label><div className="flex gap-2"><Input id="geo-sector-color" type="color" className="h-10 w-16 p-1" value={form.color} onChange={(event) => setForm((current) => ({ ...current, color: event.target.value }))} data-testid="geo-sector-color-input" /><Input value={form.color} onChange={(event) => setForm((current) => ({ ...current, color: event.target.value }))} data-testid="geo-sector-color-text-input" /></div></div>
          <div className="border border-cyan-200 bg-cyan-50 p-3 text-sm text-cyan-950" data-testid="geo-sector-drawing-status"><b>{draft.length} vértices</b><p>Toque el mapa para agregar puntos. Arrastre un punto para corregir el límite.</p></div>
          <div className="grid grid-cols-3 gap-2"><Button variant="outline" onClick={() => setDraft(draft.slice(0, -1))} disabled={!draft.length} data-testid="undo-geo-sector-vertex"><Undo2 className="h-4 w-4" />Último</Button><Button variant="outline" onClick={removeVertex} disabled={selectedVertex === null} data-testid="remove-geo-sector-vertex"><X className="h-4 w-4" />Punto</Button><Button variant="outline" onClick={() => { setDraft([]); setSelectedVertex(null); }} disabled={!draft.length} data-testid="clear-geo-sector-drawing"><Trash2 className="h-4 w-4" />Limpiar</Button></div>
          <div className="grid grid-cols-2 gap-2"><Button variant="outline" onClick={cancel} data-testid="cancel-geo-sector-edit">Cancelar</Button><Button className="bg-slate-950 text-white" onClick={() => requestSave(false)} disabled={busy || draft.length < 3} data-testid="save-geo-sector-button">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}Guardar</Button></div></div>}
      </div>
    </aside>}
    <AlertDialog open={Boolean(overlap)} onOpenChange={(value) => !value && setOverlap(null)}><AlertDialogContent data-testid="geo-sector-overlap-dialog"><AlertDialogHeader><AlertDialogTitle>Conflicto territorial detectado</AlertDialogTitle><AlertDialogDescription>Este límite se superpone con {overlap?.conflicts?.map((item) => item.name).join(', ')}. Puede cancelar y corregirlo, o guardarlo con una excepción auditada.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel data-testid="cancel-geo-sector-overlap">Corregir límite</AlertDialogCancel><AlertDialogAction onClick={() => requestSave(true)} data-testid="confirm-geo-sector-overlap">Guardar excepción</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </>;
};