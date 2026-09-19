import React from 'react';
import { Label } from '../ui/label';

const fields = [
  ['first_name', 'Nombre'], ['last_name', 'Apellido'], ['full_name', 'Nombre completo'],
  ['email', 'Correo'], ['phone', 'Teléfono'], ['birth_date', 'Fecha de nacimiento'],
  ['person_number', 'Número VV'], ['member_number', 'Número de miembro'],
  ['address1', 'Dirección'], ['address2', 'Apartamento / unidad'], ['city', 'Ciudad'],
  ['state', 'Estado'], ['zip', 'Código postal'], ['household', 'Hogar / familia'],
];

export const MembershipImportMapping = ({ columns, mapping, onChange }) => (
  <section className="border bg-white p-5" data-testid="membership-import-mapping-section">
    <div className="mb-4"><h2 className="font-['Spectral'] text-2xl font-semibold">Mapeo de columnas</h2><p className="mt-1 text-sm text-slate-500">Confirme qué columna corresponde a cada dato. Ninguna fila será guardada.</p></div>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {fields.map(([field, label]) => <div key={field} className="space-y-1.5"><Label htmlFor={`mapping-${field}`}>{label}</Label><select id={`mapping-${field}`} value={mapping[field] || ''} onChange={(event) => onChange(field, event.target.value || null)} className="h-10 w-full border bg-white px-3 text-sm" data-testid={`membership-import-mapping-${field}`}><option value="">No importar</option>{columns.map((column) => <option key={column} value={column}>{column}</option>)}</select></div>)}
    </div>
  </section>
);