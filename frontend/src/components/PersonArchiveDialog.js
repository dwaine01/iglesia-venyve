import React from 'react';
import { Archive, Loader2 } from 'lucide-react';

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

export const PersonArchiveDialog = ({ open, onOpenChange, personName, busy, error, onConfirm }) => (
  <AlertDialog open={open} onOpenChange={onOpenChange}>
    <AlertDialogContent className="max-h-[85vh] overflow-y-auto border border-slate-200 bg-white shadow-2xl" data-testid="person-archive-dialog">
      <AlertDialogHeader>
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-red-50 text-red-700">
          <Archive className="h-5 w-5" />
        </div>
        <AlertDialogTitle data-testid="person-archive-dialog-title">
          ¿Eliminar a {personName} del directorio?
        </AlertDialogTitle>
        <AlertDialogDescription data-testid="person-archive-dialog-description">
          La Persona dejará de aparecer en búsquedas y su cuenta vinculada será desactivada. El historial ministerial, pastoral y financiero se conservará para auditoría.
        </AlertDialogDescription>
      </AlertDialogHeader>
      {error && <p className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700" data-testid="person-archive-error-alert">{error}</p>}
      <AlertDialogFooter>
        <AlertDialogCancel disabled={busy} data-testid="person-archive-cancel-button">Cancelar</AlertDialogCancel>
        <AlertDialogAction
          disabled={busy}
          onClick={(event) => { event.preventDefault(); onConfirm(); }}
          className="bg-red-700 text-white hover:bg-red-800"
          data-testid="person-archive-confirm-button"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Archive className="h-4 w-4" />}
          Eliminar del directorio
        </AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
);