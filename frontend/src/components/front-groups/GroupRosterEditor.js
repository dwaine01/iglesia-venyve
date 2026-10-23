import React, { useState } from 'react';
import { CheckCircle2, Link2, Loader2, Unlink, UserMinus } from 'lucide-react';

import { Button } from '../ui/button';
import { PersonQuickPicker } from './PersonQuickPicker';

const personName = (person) => person.name || [person.nombre, person.apellido].filter(Boolean).join(' ') || 'Persona';
let keySeed = 0;
const nextKey = () => { keySeed += 1; return `entry-${keySeed}`; };

export const rosterToEntries = (roster) => (roster?.entries || []).map((entry) => ({
  key: nextKey(),
  people: entry.people.map((person) => ({ person_id: person.person_id, name: person.name })),
}));

// ETAPA 5C: arma la lista del grupo con personas existentes de Persona 360,
// como individuos o parejas, y obliga a REVISAR y confirmar antes de guardar.
export function GroupRosterEditor({ groupId, initialEntries = [], excludedIds = [], onSave, onCancel, saveLabel = 'Confirmar y guardar' }) {
  const [entries, setEntries] = useState(initialEntries);
  const [pairingKey, setPairingKey] = useState(null);
  const [reviewing, setReviewing] = useState(false);
  const [saving, setSaving] = useState(false);

  const inList = new Set(entries.flatMap((entry) => entry.people.map((person) => person.person_id)));
  const individuals = entries.filter((entry) => entry.people.length === 1);
  const pairs = entries.filter((entry) => entry.people.length === 2);
  const people = entries.reduce((total, entry) => total + entry.people.length, 0);

  const addPerson = (person) => {
    if (inList.has(person.person_id) || excludedIds.includes(person.person_id)) return;
    setEntries((current) => [...current, { key: nextKey(), people: [{ person_id: person.person_id, name: personName(person) }] }]);
  };
  const remove = (personId) => setEntries((current) => current.flatMap((entry) => {
    const rest = entry.people.filter((person) => person.person_id !== personId);
    return rest.length ? [{ ...entry, people: rest }] : [];
  }));
  const pairWith = (key, partnerKey) => setEntries((current) => {
    const first = current.find((entry) => entry.key === key);
    const second = current.find((entry) => entry.key === partnerKey);
    if (!first || !second) return current;
    return current.filter((entry) => entry.key !== partnerKey).map((entry) => (entry.key === key ? { ...entry, people: [...first.people, ...second.people] } : entry));
  });
  const split = (key) => setEntries((current) => current.flatMap((entry) => (entry.key === key ? entry.people.map((person) => ({ key: nextKey(), people: [person] })) : [entry])));

  const save = async () => {
    setSaving(true);
    try { await onSave(entries.map((entry) => ({ person_ids: entry.people.map((person) => person.person_id) }))); } finally { setSaving(false); }
  };

  const summary = <p className="text-sm text-slate-600" data-testid="roster-editor-summary"><b>{people}</b> {people === 1 ? 'persona' : 'personas'} · <b>{pairs.length}</b> {pairs.length === 1 ? 'pareja' : 'parejas'} · <b>{individuals.length}</b> {individuals.length === 1 ? 'individual' : 'individuales'}</p>;

  if (reviewing) {
    return (
      <section className="space-y-3 rounded-xl border border-amber-300 bg-amber-50 p-4" data-testid="roster-review">
        <h3 className="flex items-center gap-2 font-semibold text-amber-900"><CheckCircle2 className="h-4 w-4" />Revisa la lista antes de guardar</h3>
        {summary}
        <ol className="space-y-1.5 text-sm">
          {entries.map((entry, index) => <li key={entry.key} className="rounded-lg bg-white px-3 py-2" data-testid="roster-review-entry"><span className="mr-2 text-xs text-slate-400">{index + 1}.</span>{entry.people.length === 2 ? <><span className="mr-1 rounded bg-[#F3EBD7] px-1.5 py-0.5 text-[10px] font-semibold uppercase text-[#7A5F22]">Pareja</span>{entry.people.map(personName).join(' y ')}</> : personName(entry.people[0])}</li>)}
          {!entries.length && <li className="text-slate-500">La lista está vacía: se retirarán todos los integrantes.</li>}
        </ol>
        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline" className="h-11" onClick={() => setReviewing(false)} disabled={saving} data-testid="roster-review-back">Volver a editar</Button>
          <Button className="h-11 bg-amber-700 text-white hover:bg-amber-800" onClick={save} disabled={saving} data-testid="roster-review-confirm">{saving && <Loader2 className="h-4 w-4 animate-spin" />}{saveLabel}</Button>
        </div>
      </section>
    );
  }

  return (
    <section className="space-y-3 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid="roster-editor">
      <div>
        <h3 className="font-semibold text-[#101D36]">Agregar personas desde Persona 360</h3>
        <div className="mt-2"><PersonQuickPicker groupId={groupId} assign={false} placeholder="Buscar por nombre…" onPicked={addPerson} /></div>
      </div>
      {summary}
      <ul className="space-y-2">
        {entries.map((entry) => (
          <li key={entry.key} className={`rounded-lg border p-3 ${entry.people.length === 2 ? 'border-[#D9CFB4] bg-[#FBF6EA]' : 'border-[#EEECE6]'}`} data-testid="roster-editor-entry">
            {entry.people.length === 2 && <p className="mb-1 text-[10px] font-semibold uppercase text-[#7A5F22]">Pareja</p>}
            {entry.people.map((person) => (
              <div key={person.person_id} className="flex min-h-10 items-center justify-between gap-2 text-sm">
                <span className="min-w-0 truncate">{personName(person)}</span>
                <button type="button" onClick={() => remove(person.person_id)} className="inline-flex h-9 shrink-0 items-center gap-1 px-2 text-xs text-red-600" aria-label={`Quitar a ${personName(person)}`}><UserMinus className="h-3.5 w-3.5" />Quitar</button>
              </div>
            ))}
            {entry.people.length === 2 && <button type="button" onClick={() => split(entry.key)} className="mt-1 inline-flex h-9 items-center gap-1 text-xs font-semibold text-slate-600"><Unlink className="h-3.5 w-3.5" />Separar pareja</button>}
            {entry.people.length === 1 && individuals.length > 1 && (pairingKey === entry.key ? (
              <div className="mt-2 space-y-1" data-testid="roster-pair-options">
                <p className="text-xs text-slate-500">Formar pareja con:</p>
                {individuals.filter((other) => other.key !== entry.key).map((other) => <button type="button" key={other.key} onClick={() => { pairWith(entry.key, other.key); setPairingKey(null); }} className="block min-h-10 w-full rounded-md border border-[#E8E5DE] px-3 text-left text-sm hover:bg-amber-50">{personName(other.people[0])}</button>)}
                <button type="button" onClick={() => setPairingKey(null)} className="text-xs text-slate-500 underline">Cancelar</button>
              </div>
            ) : <button type="button" onClick={() => setPairingKey(entry.key)} className="mt-1 inline-flex h-9 items-center gap-1 text-xs font-semibold text-[#7A5F22]" data-testid="roster-make-pair"><Link2 className="h-3.5 w-3.5" />Formar pareja</button>)}
          </li>
        ))}
      </ul>
      <div className={`grid gap-2 ${onCancel ? 'grid-cols-2' : 'grid-cols-1'}`}>
        {onCancel && <Button variant="outline" className="h-11" onClick={onCancel}>Cancelar</Button>}
        <Button className="h-11 bg-[#101D36] text-white hover:bg-[#1b2c4f]" onClick={() => setReviewing(true)} data-testid="roster-editor-review">Revisar lista</Button>
      </div>
    </section>
  );
}
