import React, { useState } from 'react';
import { Crosshair, Loader2, MapPin } from 'lucide-react';

import { LOW_ACCURACY_M, accuracyLabel, getCurrentLocation } from '../../lib/geolocation';

// "Usar mi ubicación actual" + referencia escrita. `value` = { latitude, longitude, accuracy_m } o null.
export function LocationCapture({ value, onChange, reference, onReferenceChange, testId = 'location-capture' }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const capture = async () => {
    setBusy(true); setError('');
    try { onChange(await getCurrentLocation()); } catch (captureError) { setError(captureError.message); } finally { setBusy(false); }
  };
  const low = value?.accuracy_m > LOW_ACCURACY_M;
  return (
    <div className="space-y-2" data-testid={testId}>
      <button type="button" onClick={capture} disabled={busy} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg border border-[#101D36] bg-white px-4 text-base font-semibold text-[#101D36] disabled:opacity-60" data-testid={`${testId}-gps`}>
        {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <Crosshair className="h-5 w-5" />}{value ? 'Volver a tomar mi ubicación' : 'Usar mi ubicación actual'}
      </button>
      {value && <p className={`flex items-start gap-2 rounded-lg p-2 text-sm ${low ? 'bg-amber-50 text-amber-900' : 'bg-[#eef5f0] text-[#2f6e47]'}`} data-testid={`${testId}-result`}>
        <MapPin className="mt-0.5 h-4 w-4 shrink-0" />
        <span>Ubicación tomada: {accuracyLabel(value.accuracy_m)}.{low ? ' Es poco precisa: acércate a la casa e intenta de nuevo, o agrega una referencia escrita.' : ''}{' '}<button type="button" onClick={() => onChange(null)} className="font-semibold underline">Quitar</button></span>
      </p>}
      {error && <p className="rounded-lg bg-[#f8ecea] p-2 text-sm text-[#8f382f]" role="alert" data-testid={`${testId}-error`}>{error}</p>}
      {onReferenceChange && <label className="block space-y-1"><span className="text-sm font-semibold text-[#101D36]">Referencia (opcional)</span>
        <input value={reference || ''} onChange={(event) => onReferenceChange(event.target.value)} placeholder="Ej.: casa azul junto a la bodega" className="h-12 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 text-base" data-testid={`${testId}-reference`} />
      </label>}
    </div>
  );
}
