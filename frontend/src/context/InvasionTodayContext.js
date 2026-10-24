import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import axios from 'axios';

import { useAuth } from './AuthContext';

// Contexto de invasión del día (barra inferior móvil y "+ Agregar visita"):
// las invasiones activas HOY en las que participa la persona, la más próxima
// y si puede registrar visitas propias. El backend decide todo eso; aquí solo
// se recuerda cuál eligió cuando hay varias activas a la vez.
const CHOICE_KEY = 'venyve_current_invasion';
export const OUTREACH_CHANGED_EVENT = 'venyve:outreach-changed';
export const INVASIONS_CHANGED_EVENT = 'venyve:invasions-changed';

const readChoice = () => { try { return window.localStorage.getItem(CHOICE_KEY) || ''; } catch (error) { return ''; } };
const writeChoice = (value) => { try { window.localStorage.setItem(CHOICE_KEY, value); } catch (error) { /* sin almacenamiento: se vuelve a preguntar */ } };

const InvasionTodayContext = createContext({ data: null, current: null, needsChoice: false, choose: () => {}, refresh: () => {} });

export function InvasionTodayProvider({ children }) {
  const { API, getAuthHeaders, user } = useAuth();
  const [data, setData] = useState(null);
  const [choice, setChoice] = useState(readChoice);
  const refresh = useCallback(() => {
    if (!user) { setData(null); return; }
    axios.get(`${API}/api/invasions/mine/today`, getAuthHeaders()).then((response) => setData(response.data)).catch(() => setData(null));
  }, [API, getAuthHeaders, user]);
  useEffect(() => {
    refresh();
    const onFocus = () => refresh();
    window.addEventListener('focus', onFocus);
    window.addEventListener(INVASIONS_CHANGED_EVENT, onFocus);
    return () => { window.removeEventListener('focus', onFocus); window.removeEventListener(INVASIONS_CHANGED_EVENT, onFocus); };
  }, [refresh]);
  const choose = useCallback((campaignId) => { writeChoice(campaignId); setChoice(campaignId); }, []);
  const value = useMemo(() => {
    const active = data?.active || [];
    const current = active.length === 1 ? active[0] : active.find((item) => item.campaign_id === choice) || null;
    return { data, current, needsChoice: active.length > 1 && !current, choose, refresh };
  }, [data, choice, choose, refresh]);
  return <InvasionTodayContext.Provider value={value}>{children}</InvasionTodayContext.Provider>;
}

export const useInvasionToday = () => useContext(InvasionTodayContext);
