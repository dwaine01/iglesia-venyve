import React from 'react';
import { FlaskConical, Loader2, ShieldAlert } from 'lucide-react';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from './ui/alert-dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';

export const QaDemoCleanupDialog = ({ open, onOpenChange, summary, phrase, setPhrase, busy, error, onConfirm }) => {
  const confirmed = Boolean(summary?.confirmation_phrase) && phrase === summary.confirmation_phrase;
  const collections = Object.entries(summary?.affected_by_collection || {});
  return <AlertDialog open={open} onOpenChange={onOpenChange}><AlertDialogContent className="max-h-[88vh] overflow-y-auto border border-slate-200 bg-white shadow-2xl" data-testid="qa-demo-cleanup-dialog"><AlertDialogHeader>
    <div className="flex h-10 w-10 items-center justify-center bg-red-50 text-red-700"><FlaskConical className="h-5 w-5" /></div>
    <AlertDialogTitle data-testid="qa-demo-cleanup-title">Vista previa obligatoria de limpieza QA</AlertDialogTitle>
    <AlertDialogDescription data-testid="qa-demo-cleanup-description">Se identificaron {summary?.qa_persons || 0} Personas, {summary?.qa_users || 0} cuentas y {summary?.affected_documents || 0} documentos de propiedad directa. Las referencias incidentales en registros reales no se eliminarán.</AlertDialogDescription>
  </AlertDialogHeader>
  <div className="border border-amber-300 bg-amber-50 p-3 text-xs text-amber-950" data-testid="qa-demo-cleanup-safety-alert"><ShieldAlert className="mr-1 inline h-4 w-4" />La vista previa vence en cinco minutos. Si cambia cualquier candidato, la operación será rechazada.</div>
  <div className="max-h-52 overflow-y-auto border" data-testid="qa-demo-cleanup-preview-list">{collections.length === 0 ? <p className="p-3 text-sm text-slate-500">No hay documentos candidatos.</p> : collections.map(([name, count]) => <div key={name} className="flex items-center justify-between border-b px-3 py-2 text-sm last:border-b-0"><code>{name}</code><b data-testid={`qa-demo-preview-count-${name}`}>{count}</b></div>)}</div>
  <div className="space-y-2"><Label htmlFor="qa-confirmation-phrase">Escriba exactamente: <code className="font-bold text-red-700">{summary?.confirmation_phrase || '—'}</code></Label><Input id="qa-confirmation-phrase" value={phrase} onChange={(event) => setPhrase(event.target.value)} autoComplete="off" data-testid="qa-demo-confirmation-input" /></div>
  {error && <p className="border border-red-200 bg-red-50 p-3 text-sm text-red-700" data-testid="qa-demo-cleanup-error-alert">{error}</p>}
  <AlertDialogFooter><AlertDialogCancel disabled={busy} data-testid="qa-demo-cleanup-cancel-button">Cancelar</AlertDialogCancel><AlertDialogAction disabled={busy || !confirmed || !summary?.affected_documents} onClick={(event) => { event.preventDefault(); onConfirm(); }} className="bg-red-700 text-white hover:bg-red-800" data-testid="qa-demo-cleanup-confirm-button">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}Eliminar solo lo previsualizado</AlertDialogAction></AlertDialogFooter>
  </AlertDialogContent></AlertDialog>;
};