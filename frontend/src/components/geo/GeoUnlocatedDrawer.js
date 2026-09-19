import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, Loader2, MapPinOff, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';

const labels = {
  no_address_or_household: 'Sin dirección ni Hogar', household_without_location: 'Hogar sin dirección válida',
  household_address_conflict: 'Hogar con direcciones en conflicto', incomplete_address: 'Dirección incompleta',
  verification_required: 'Requiere verificación', geocoding_failed: 'Geocodificación fallida', geocoding_pending: 'Geocodificación pendiente',
};

export const GeoUnlocatedDrawer = ({ open, onOpenChange }) => {
  const { API, getAuthHeaders } = useAuth(); const [data, setData] = useState({ items: [], total: 0, reasons: {} }); const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!open) return; setLoading(true);
    axios.get(`${API}/api/geo/unlocated-persons`, getAuthHeaders()).then((response) => setData(response.data)).finally(() => setLoading(false));
  }, [API, getAuthHeaders, open]);
  if (!open) return null;
  return <aside role="dialog" aria-modal="false" aria-label="Personas sin ubicación" className="fixed inset-y-0 right-0 z-50 w-full overflow-y-auto border-l bg-white shadow-2xl sm:max-w-md" data-testid="geo-unlocated-drawer">
    <header className="relative border-b bg-amber-500 p-5 pr-14 text-slate-950"><h2 className="flex items-center gap-2 text-lg font-bold"><MapPinOff className="h-5 w-5" />Personas sin ubicación</h2><p className="mt-1 text-sm">Complete una dirección o asigne un Hogar con domicilio inequívoco.</p><Button variant="ghost" size="icon" className="absolute right-3 top-3" onClick={() => onOpenChange(false)} data-testid="close-geo-unlocated-drawer" aria-label="Cerrar"><X className="h-5 w-5" /></Button></header>
    <div className="space-y-4 p-5">{loading ? <div className="flex justify-center p-8" data-testid="geo-unlocated-loading"><Loader2 className="h-6 w-6 animate-spin" /></div> : <><div className="border border-amber-200 bg-amber-50 p-4" data-testid="geo-unlocated-total"><b className="text-2xl">{data.total}</b><span className="ml-2 text-sm">requieren ubicación</span></div><div className="grid grid-cols-2 gap-2">{Object.entries(data.reasons).map(([reason, count]) => <div key={reason} className="border p-2 text-xs" data-testid={`geo-unlocated-reason-${reason}`}><b className="block text-base">{count}</b>{labels[reason] || reason}</div>)}</div><div className="space-y-2" data-testid="geo-unlocated-list">{data.items.map((item) => <Link key={item.person_id} to={item.profile_path} className="flex items-center justify-between border-l-4 border-amber-500 bg-slate-50 p-3 hover:bg-amber-50" data-testid={`geo-unlocated-person-${item.person_id}`}><span><b className="block text-sm">{item.name}</b><small className="text-slate-500">{item.person_number || 'Persona 360'} · {labels[item.reason] || item.reason}</small></span><AlertTriangle className="h-4 w-4 text-amber-700" /></Link>)}</div></>}</div>
  </aside>;
};