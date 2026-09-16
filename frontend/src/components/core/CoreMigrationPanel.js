import React from 'react';
import { CheckCircle2, Loader2, RefreshCw, Route } from 'lucide-react';
import { Button } from '../ui/button';

export const CoreMigrationPanel = ({ integrity, running, onRun }) => {
  const last = integrity?.last_migration;
  return (
    <section className="border-y border-[#DED8C8] bg-[#F1EEE6]" data-testid="core-migration-panel">
      <div className="grid gap-6 px-4 py-7 sm:px-6 lg:grid-cols-[1fr_auto] lg:items-center lg:px-8">
        <div className="flex items-start gap-4">
          <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-[#101D36] text-[#D4B871]">
            <Route className="h-5 w-5" />
          </div>
          <div>
            <h2 className="font-['Spectral'] text-xl font-bold text-[#101D36]">Migración canónica idempotente</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-gray-600">
              Enlaza cuentas y registros heredados con el Perfil 360, migra contactos y ocupaciones, y conserva los procesos existentes sin duplicar Personas.
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-gray-500" data-testid="core-last-migration">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              {last?.completed_at ? `Última ejecución: ${new Date(last.completed_at).toLocaleString('es-ES')}` : 'Lista para primera ejecución registrada'}
            </div>
          </div>
        </div>
        <Button onClick={onRun} disabled={running} className="bg-[#101D36] text-white hover:bg-[#1B2A4A]" data-testid="core-run-migration-button">
          {running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
          {running ? 'Consolidando núcleo...' : 'Ejecutar consolidación'}
        </Button>
      </div>
    </section>
  );
};