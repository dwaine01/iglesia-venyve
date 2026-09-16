import React from 'react';
import { ArrowRight, Compass } from 'lucide-react';
import { BRAND, CAP_JOURNEY, moduleBrand } from '../../config/brand';

export const CapJourney = () => <section className="border border-amber-200 bg-gradient-to-r from-[#FFF9E8] via-white to-[#F2F7F6] p-5 sm:p-7" data-testid="cap-ministerial-journey">
  <p className="font-mono text-xs font-semibold uppercase text-[#8A6818]">{moduleBrand('Servicio y Desarrollo')}</p>
  <div className="mt-2 flex items-start gap-3"><Compass className="mt-1 h-6 w-6 shrink-0 text-amber-700" /><div><h2 className="font-['Spectral'] text-2xl font-semibold text-[#0B192C]">Encuentra tu lugar para servir</h2><p className="mt-2 max-w-4xl text-sm leading-6 text-slate-700">Identificamos los dones, talentos e intereses de cada persona para ayudarla a encontrar la Puerta donde puede servir y desarrollarse. La decisión final siempre la toman la persona y sus líderes.</p></div></div>
  <div className="mt-6 grid gap-2 sm:grid-cols-3 xl:grid-cols-6" data-testid="cap-ministerial-steps">{CAP_JOURNEY.map((step, index) => <div key={step} className="flex min-w-0 items-center gap-2"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#0B192C] font-mono text-xs text-[#F1D471]">{index + 1}</span><span className="text-xs font-semibold leading-5 text-slate-700">{step}</span>{index < CAP_JOURNEY.length - 1 && <ArrowRight className="hidden h-3 w-3 shrink-0 text-amber-500 xl:block" />}</div>)}</div>
  <p className="mt-5 border-l-2 border-amber-500 pl-3 text-xs leading-5 text-slate-600">Las recomendaciones orientan la conversación. Nunca se convierten automáticamente en una decisión pastoral. · {BRAND.slogan}</p>
</section>;