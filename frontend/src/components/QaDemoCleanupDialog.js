import React from 'react';
import { FlaskConical, Loader2 } from 'lucide-react';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './ui/alert-dialog';

export const QaDemoCleanupDialog = ({ open, onOpenChange, summary, busy, error, onConfirm }) => (
  <AlertDialog open={open} onOpenChange={onOpenChange}>
    <AlertDialogContent className="max-h-[85vh] overflow-y-auto border border-slate-200 bg-white shadow-2xl" data-testid="qa-demo-cleanup-dialog">
      <AlertDialogHeader>
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-red-50 text-red-700">
          <FlaskConical className="h-5 w-5" />
        </div>
        <AlertDialogTitle data-testid="qa-demo-cleanup-title">¿Eliminar todas las muestras QA?</AlertDialogTitle>
        <AlertDialogDescription data-testid="qa-demo-cleanup-description">
          Se eliminarán permanentemente {summary?.qa_persons || 0} Personas y {summary?.qa_users || 0} cuentas identificadas estrictamente como QA/demo, junto con sus artefactos relacionados. Las Personas reales y configuraciones institucionales se preservarán.
        </AlertDialogDescription>
      </AlertDialogHeader>
      {error && <p className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700" data-testid="qa-demo-cleanup-error-alert">{error}</p>}
      <AlertDialogFooter>
        <AlertDialogCancel disabled={busy} data-testid="qa-demo-cleanup-cancel-button">Cancelar</AlertDialogCancel>
        <AlertDialogAction
          disabled={busy}
          onClick={(event) => { event.preventDefault(); onConfirm(); }}
          className="bg-red-700 text-white hover:bg-red-800"
          data-testid="qa-demo-cleanup-confirm-button"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
          Eliminar muestras
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
);