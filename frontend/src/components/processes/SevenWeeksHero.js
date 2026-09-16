import React from 'react';
import { ArrowRight } from 'lucide-react';
import { BRAND, DISCIPLESHIP_JOURNEY, moduleBrand, MODULE_BRANDS } from '../../config/brand';

export const SevenWeeksHero = () => <section className="relative overflow-hidden border border-[#384762] bg-[#0B1428] px-5 py-7 text-white shadow-lg sm:px-8 sm:py-9" data-testid="seven-weeks-identity-hero">
  <div className="absolute inset-0 opacity-[.06] [background-image:linear-gradient(rgba(255,255,255,.7)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.7)_1px,transparent_1px)] [background-size:30px_30px]" aria-hidden="true" />
  <div className="relative">
    <p className="font-mono text-xs font-semibold uppercase text-[#E2C66D]" data-testid="seven-weeks-brand-line">{moduleBrand(MODULE_BRANDS.sevenWeeks)}</p>
    <h2 className="mt-3 font-['Spectral'] text-4xl font-semibold leading-none sm:text-5xl" data-testid="seven-weeks-hero-title">La Ley de las<br /><span className="text-[#D8BA55]">7 Semanas</span></h2>
    <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-300 sm:text-base">Un proceso de acompañamiento, consolidación y discipulado que ayuda a cada persona a crecer con dirección, cuidado y propósito.</p>
    <div className="mt-6 flex flex-wrap items-center gap-2" data-testid="seven-weeks-journey">
      {DISCIPLESHIP_JOURNEY.map((step, index) => <React.Fragment key={step}><span className="border border-white/15 bg-white/5 px-3 py-2 font-['Spectral'] text-sm font-semibold">{step}</span>{index < DISCIPLESHIP_JOURNEY.length - 1 && <ArrowRight className="h-4 w-4 text-[#D8BA55]" />}</React.Fragment>)}
    </div>
    <p className="mt-5 text-xs text-slate-400">{BRAND.slogan}</p>
  </div>
</section>;