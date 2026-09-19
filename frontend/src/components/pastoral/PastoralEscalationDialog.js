import React, { useState } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';

export const PastoralEscalationDialog = ({ authorities = [], onEscalate, saving }) => {
  const [open, setOpen] = useState(false); const [authority, setAuthority] = useState(''); const [reason, setReason] = useState('');
  const submit = async (event) => { event.preventDefault(); await onEscalate({ authority_person_id: authority, reason }); setOpen(false); setReason(''); };
  return <Dialog open={open} onOpenChange={setOpen}><DialogTrigger asChild><Button variant="destructive" data-testid="pastoral-escalate-case-button"><AlertTriangle className="h-4 w-4" />Escalar urgente</Button></DialogTrigger><DialogContent data-testid="pastoral-escalation-dialog"><DialogHeader><DialogTitle className="font-['Spectral'] text-2xl">Escalamiento pastoral inmediato</DialogTitle></DialogHeader><form onSubmit={submit} className="space-y-4"><div className="space-y-2"><Label>Autoridad pastoral</Label><select value={authority} onChange={(event) => setAuthority(event.target.value)} className="h-10 w-full border bg-white px-3 text-sm" required data-testid="pastoral-escalation-authority-select"><option value="">Seleccione Pastor/Pastora o Coordinación General</option>{authorities.map((item) => <option key={item.person_id} value={item.person_id}>{item.name} · {item.role}</option>)}</select></div><div className="space-y-2"><Label>Motivo obligatorio</Label><Textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={5} required data-testid="pastoral-escalation-reason-input" /></div><Button disabled={saving || !authority || reason.trim().length < 5} className="w-full" variant="destructive" data-testid="pastoral-escalation-confirm-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Escalar y auditar</Button></form></DialogContent></Dialog>;
};