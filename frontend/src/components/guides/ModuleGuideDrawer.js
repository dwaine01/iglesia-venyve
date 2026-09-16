import React from 'react';
import { AlertTriangle, ArrowRight, CheckCircle2, CircleDot, GitBranch, ListChecks, Play, ShieldCheck, Sparkles } from 'lucide-react';
import { Button } from '../ui/button';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '../ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';

const NumberedList = ({ items = [], testId }) => <ol className="space-y-3" data-testid={testId}>{items.map((item, index) => <li key={`${index}-${item}`} className="grid grid-cols-[28px_1fr] gap-3"><span className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0F1A33] font-mono text-[11px] text-[#F0D889]">{index + 1}</span><span className="pt-0.5 text-sm leading-6 text-slate-700">{item}</span></li>)}</ol>;
const BulletList = ({ items = [], tone = 'navy', testId }) => <ul className="space-y-2" data-testid={testId}>{items.map((item, index) => <li key={`${index}-${item}`} className="flex gap-2 text-sm leading-6 text-slate-700"><CircleDot className={`mt-1.5 h-3 w-3 shrink-0 ${tone === 'gold' ? 'text-[#A77913]' : 'text-[#1E3E62]'}`} />{item}</li>)}</ul>;
const Section = ({ icon: Icon, title, children, testId }) => <section className="border-t border-[#E8DFC8] py-5" data-testid={testId}><h3 className="mb-3 flex items-center gap-2 font-['Spectral'] text-xl font-semibold text-[#0B192C]"><Icon className="h-5 w-5 text-[#A77913]" />{title}</h3>{children}</section>;

const Example = ({ example }) => {
  if (!example) return null;
  if (typeof example === 'string') return <p className="text-sm leading-6 text-slate-700">{example}</p>;
  return <div className="space-y-3 text-sm leading-6 text-slate-700"><p><strong>Situación:</strong> {example.situation}</p><p><strong>Acción:</strong> {example.action}</p><p><strong>Resultado:</strong> {example.result}</p></div>;
};

export const ModuleGuideDrawer = ({ open, onOpenChange, guide, moduleKey, loading, error, onStartTour }) => <Sheet open={open} onOpenChange={onOpenChange}>
  <SheetContent side="right" className="box-border flex w-full max-w-full flex-col overflow-x-hidden bg-[#F8FAFC] p-0 sm:max-w-xl" data-testid={`guide-panel-${moduleKey}`}>
    <div className="border-b border-[#D4AF37]/25 bg-[#0B192C] px-5 pb-5 pt-7 text-white sm:px-7">
      <SheetHeader className="pr-8 text-left">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#E4C55A]">Manual contextual · v{guide?.version || '—'}</p>
        <SheetTitle className="font-['Spectral'] text-3xl font-semibold text-white" data-testid={`guide-title-${moduleKey}`}>{guide?.title || 'Cómo funciona este módulo'}</SheetTitle>
        <SheetDescription className="text-sm leading-6 text-slate-300">{guide?.purpose || (error || 'Cargando guía práctica...')}</SheetDescription>
      </SheetHeader>
      {guide?.result && <div className="mt-5 border-l-2 border-[#D4AF37] bg-white/5 p-4" data-testid={`guide-result-${moduleKey}`}><p className="font-mono text-[11px] uppercase tracking-wider text-[#E4C55A]">Resultado esperado</p><p className="mt-1 text-sm leading-6 text-white">{guide.result}</p></div>}
    </div>

    <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-7">
      {loading && <div className="flex min-h-56 items-center justify-center" data-testid={`guide-loading-${moduleKey}`}><div className="h-9 w-9 animate-spin rounded-full border-2 border-slate-200 border-t-[#D4AF37]" /></div>}
      {error && !loading && <div className="border border-red-200 bg-red-50 p-4 text-sm text-red-800" data-testid={`guide-error-${moduleKey}`}>{error}</div>}
      {guide && <Tabs defaultValue="vision" data-testid={`guide-tabs-${moduleKey}`}>
        <TabsList className="grid h-auto grid-cols-4 bg-[#E9EEF4] p-1">
          <TabsTrigger value="vision" data-testid={`guide-tab-vision-${moduleKey}`}>Visión</TabsTrigger>
          <TabsTrigger value="steps" data-testid={`guide-tab-steps-${moduleKey}`}>Pasos</TabsTrigger>
          <TabsTrigger value="impact" data-testid={`guide-tab-impact-${moduleKey}`}>Impacto</TabsTrigger>
          <TabsTrigger value="roles" data-testid={`guide-tab-roles-${moduleKey}`}>Roles</TabsTrigger>
        </TabsList>

        <TabsContent value="vision" className="mt-2">
          <Section icon={GitBranch} title="Flujo operativo" testId={`guide-flow-${moduleKey}`}><NumberedList items={guide.flow} testId={`guide-flow-list-${moduleKey}`} /></Section>
          <div className="grid gap-4 sm:grid-cols-2">
            <Section icon={ArrowRight} title="Información que entra" testId={`guide-inputs-${moduleKey}`}><BulletList items={guide.inputs} /></Section>
            <Section icon={CheckCircle2} title="Resultados que produce" testId={`guide-outputs-${moduleKey}`}><BulletList items={guide.outputs} tone="gold" /></Section>
          </div>
        </TabsContent>

        <TabsContent value="steps" className="mt-2">
          <Section icon={ListChecks} title="Paso a paso" testId={`guide-steps-${moduleKey}`}><NumberedList items={guide.steps} testId={`guide-steps-list-${moduleKey}`} /></Section>
          <Section icon={AlertTriangle} title="Errores frecuentes" testId={`guide-errors-${moduleKey}`}><BulletList items={guide.common_errors} tone="gold" /></Section>
        </TabsContent>

        <TabsContent value="impact" className="mt-2">
          <Section icon={GitBranch} title="Qué cambia en otros módulos" testId={`guide-connections-${moduleKey}`}>
            <div className="space-y-3">{guide.connections.map((connection, index) => <article key={`${index}-${connection.module || connection}`} className="border-l-2 border-[#D4AF37] bg-white p-4 shadow-sm"><p className="text-xs font-semibold uppercase text-[#996515]">{connection.module || 'Sistema conectado'}</p><p className="mt-1 text-sm leading-6 text-slate-700">{connection.impact || connection}</p></article>)}</div>
          </Section>
          <Section icon={Sparkles} title="Ejemplo práctico" testId={`guide-example-${moduleKey}`}><Example example={guide.example} /></Section>
          <Section icon={ArrowRight} title="Qué ocurre después" testId={`guide-next-${moduleKey}`}><p className="text-sm leading-6 text-slate-700">{guide.next}</p></Section>
        </TabsContent>

        <TabsContent value="roles" className="mt-2">
          <div className="mt-5 border border-[#D4AF37]/30 bg-[#FFFDF7] p-4" data-testid={`guide-role-focus-${moduleKey}`}><p className="font-mono text-xs uppercase tracking-wider text-[#996515]">Tu enfoque · {guide.active_role_label}</p><p className="mt-2 text-sm leading-6 text-slate-800">{guide.role_focus}</p></div>
          <Section icon={ShieldCheck} title="Quién hace qué" testId={`guide-roles-${moduleKey}`}><BulletList items={guide.roles} /></Section>
          <Section icon={CircleDot} title="Estados y lógica" testId={`guide-states-${moduleKey}`}><div className="flex flex-wrap gap-2">{guide.states.map((state) => <span key={state} className="border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700">{state}</span>)}</div></Section>
          <Section icon={Sparkles} title="Buenas prácticas" testId={`guide-practices-${moduleKey}`}><BulletList items={guide.good_practices} tone="gold" /></Section>
        </TabsContent>
      </Tabs>}
    </div>

    <div className="sticky bottom-0 flex gap-3 border-t border-slate-200 bg-white px-5 py-4 sm:px-7">
      <Button variant="outline" onClick={() => onOpenChange(false)} className="min-h-11 flex-1" data-testid={`guide-close-${moduleKey}`}>Cerrar</Button>
      <Button onClick={onStartTour} disabled={!guide?.tour_steps?.length} className="min-h-11 flex-1 bg-[#D4AF37] text-[#0B192C] hover:bg-[#C49E24]" data-testid={`guide-tour-start-${moduleKey}`}><Play className="mr-2 h-4 w-4" />Recorrido guiado</Button>
    </div>
  </SheetContent>
</Sheet>;