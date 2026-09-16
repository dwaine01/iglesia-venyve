import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BookOpenText } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { GuideTourOverlay } from './GuideTourOverlay';
import { ModuleGuideDrawer } from './ModuleGuideDrawer';

const guideCache = new Map();

export const ContextGuideButton = ({ moduleKey, compact = false }) => {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);
  const [guide, setGuide] = useState(() => guideCache.get(moduleKey) || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [attempted, setAttempted] = useState(false);

  useEffect(() => {
    setGuide(guideCache.get(moduleKey) || null);
    setError('');
    setAttempted(false);
  }, [moduleKey]);

  useEffect(() => {
    if (!open || guide || loading || attempted) return;
    setAttempted(true);
    setLoading(true);
    axios.get(`${API}/api/guides/${moduleKey}`, getAuthHeaders())
      .then((response) => {
        guideCache.set(moduleKey, response.data);
        setGuide(response.data);
      })
      .catch(() => setError('No se pudo cargar el manual contextual.'))
      .finally(() => setLoading(false));
  }, [API, attempted, getAuthHeaders, guide, loading, moduleKey, open]);

  const openGuide = () => {
    if (error) { setError(''); setAttempted(false); }
    setOpen(true);
  };

  const startTour = () => {
    setOpen(false);
    window.setTimeout(() => setTourOpen(true), 180);
  };

  return <>
    <Button
      variant="outline"
      size={compact ? 'sm' : 'default'}
      onClick={openGuide}
      className="min-h-10 border-[#C8A951]/60 bg-white text-[#1B2A4A] shadow-sm transition-[transform,background-color,border-color] hover:-translate-y-0.5 hover:border-[#C8A951] hover:bg-[#FFFDF7]"
      data-testid={`open-guide-${moduleKey}`}
      aria-label={`Cómo funciona: ${guide?.title || moduleKey}`}
    >
      <BookOpenText className="h-4 w-4 sm:mr-2" />
      <span className={compact ? 'hidden xl:inline' : ''}>¿Cómo funciona?</span>
    </Button>
    <ModuleGuideDrawer open={open} onOpenChange={setOpen} guide={guide} moduleKey={moduleKey} loading={loading} error={error} onStartTour={startTour} />
    <GuideTourOverlay open={tourOpen} steps={guide?.tour_steps || []} title={guide?.title} onClose={() => setTourOpen(false)} />
  </>;
};