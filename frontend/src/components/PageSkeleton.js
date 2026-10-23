import React from 'react';

// Esqueleto liviano mientras llega el código del módulo (no usa librerías).
export default function PageSkeleton() {
  return (
    <div className="mx-auto w-full max-w-7xl space-y-5 p-4 sm:p-6 lg:p-8" data-testid="page-skeleton" aria-busy="true" aria-label="Cargando módulo">
      <div className="space-y-2">
        <div className="h-3 w-24 animate-pulse rounded bg-slate-200" />
        <div className="h-7 w-64 max-w-full animate-pulse rounded bg-slate-200" />
        <div className="h-3 w-96 max-w-full animate-pulse rounded bg-slate-100" />
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((item) => <div key={item} className="h-24 animate-pulse border border-slate-100 bg-white" />)}
      </div>
      <div className="h-64 animate-pulse border border-slate-100 bg-white" />
    </div>
  );
}
