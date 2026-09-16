import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BookOpenText, CheckCircle2, Route, ShieldCheck, Sparkles } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '../ui/sheet';

const GuideSection = ({ icon: Icon, title, children, testId }) => (
  <section className="border-t border-[#E2D9CC] py-4" data-testid={testId}>
    <h3 className="flex items-center gap-2 text-base font-semibold text-[#0F1A33]"><Icon className="h-4 w-4 text-[#9E8232]" />{title}</h3>
    <div className="mt-2 text-sm leading-6 text-[#4A5568]">{children}</div>
  </section>
);

export const ContextGuideButton = ({ moduleKey }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false); const [guide, setGuide] = useState(null); const [error, setError] = useState('');
  useEffect(() => { if (open && !guide) axios.get(`${API}/api/guides/${moduleKey}`, getAuthHeaders()).then((r) => setGuide(r.data)).catch(() => setError('No se pudo cargar el manual contextual.')); }, [API, getAuthHeaders, guide, moduleKey, open]);
  const list = (items) => <ol className="space-y-2">{(items || []).map((item, index) => <li key={item} className="flex gap-2"><span className="font-mono text-xs text-[#9E8232]">{String(index + 1).padStart(2, '0')}</span><span>{item}</span></li>)}</ol>;
  return <Sheet open={open} onOpenChange={setOpen}><SheetTrigger asChild><Button variant="outline" className="border-[#C8A951]/60 bg-white text-[#1B2A4A]" data-testid={`open-guide-${moduleKey}`}><BookOpenText className="mr-2 h-4 w-4" />¿Cómo funciona?</Button></SheetTrigger><SheetContent side="right" className="w-[calc(100vw-16px)] max-w-[calc(100vw-16px)] overflow-y-auto bg-[#F8F6F0] p-5 sm:max-w-md" data-testid={`guide-panel-${moduleKey}`}><SheetHeader className="pr-8 text-left"><p className="font-mono text-xs uppercase text-[#9E8232]">Manual v{guide?.version || '—'}</p><SheetTitle className="font-['Spectral'] text-2xl text-[#0F1A33]">{guide?.title || 'Manual contextual'}</SheetTitle><SheetDescription>{guide?.purpose || (error ? error : 'Cargando guía práctica...')}</SheetDescription></SheetHeader>{guide && <div className="mt-5"><GuideSection icon={Route} title="Flujo" testId="guide-flow">{list(guide.flow)}</GuideSection><GuideSection icon={ShieldCheck} title="Roles y estados" testId="guide-roles"><ul className="space-y-1">{guide.roles.map((item) => <li key={item}>• {item}</li>)}</ul><p className="mt-3 font-medium text-[#0F1A33]">Estados</p><p>{guide.states.join(' · ')}</p></GuideSection><GuideSection icon={CheckCircle2} title="Pasos operativos" testId="guide-steps">{list(guide.steps)}</GuideSection><GuideSection icon={Sparkles} title="Buenas prácticas" testId="guide-practices"><ul className="space-y-1">{guide.good_practices.map((item) => <li key={item}>• {item}</li>)}</ul><div className="mt-4 border-l-2 border-[#C8A951] bg-white p-3"><strong className="text-[#0F1A33]">¿Qué ocurre después?</strong><p className="mt-1">{guide.next}</p></div></GuideSection></div>}</SheetContent></Sheet>;
};