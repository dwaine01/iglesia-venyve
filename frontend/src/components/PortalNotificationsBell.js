import React, { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { Bell } from 'lucide-react';

import { useAuth } from '../context/AuthContext';

// FASE 6: avisos dentro del portal (invitaciones a invasiones, solicitudes,
// cambios). Consulta cada minuto; tocar un aviso lo marca como leído y abre su enlace.
export default function PortalNotificationsBell() {
  const { API, getAuthHeaders, user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState({ items: [], unread: 0 });
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  const load = useCallback(() => {
    if (!user) return;
    axios.get(`${API}/api/notifications`, getAuthHeaders()).then((response) => setData(response.data)).catch(() => {});
  }, [API, getAuthHeaders, user]);

  useEffect(() => { load(); const timer = setInterval(load, 60000); return () => clearInterval(timer); }, [load]);
  useEffect(() => {
    if (!open) return undefined;
    const close = (event) => { if (ref.current && !ref.current.contains(event.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);

  const openItem = async (item) => {
    setOpen(false);
    if (!item.read_at) await axios.post(`${API}/api/notifications/${item.notification_id}/read`, {}, getAuthHeaders()).catch(() => {});
    load();
    if (item.link) navigate(item.link);
  };
  const readAll = async () => { await axios.post(`${API}/api/notifications/read-all`, {}, getAuthHeaders()).catch(() => {}); load(); };

  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((value) => !value)} className="relative grid h-10 w-10 place-items-center rounded-md hover:bg-slate-100" aria-label={`Avisos${data.unread ? `: ${data.unread} sin leer` : ''}`} data-testid="portal-notifications-bell">
        <Bell className="h-5 w-5 text-slate-600" />
        {data.unread > 0 && <span className="absolute right-1 top-1 grid min-w-[1.1rem] place-items-center rounded-full bg-[#b4493d] px-1 text-[0.65rem] font-bold leading-[1.1rem] text-white" data-testid="portal-notifications-count">{data.unread > 9 ? '9+' : data.unread}</span>}
      </button>
      {open && (
        <div className="fixed inset-x-2 top-14 z-50 max-h-[70vh] overflow-y-auto rounded-xl border border-[#E8E5DE] bg-white shadow-xl sm:absolute sm:inset-x-auto sm:right-0 sm:top-11 sm:w-96" data-testid="portal-notifications-panel">
          <div className="flex items-center justify-between border-b border-[#EEECE6] px-3 py-2">
            <p className="text-sm font-semibold text-[#101D36]">Avisos</p>
            {data.unread > 0 && <button type="button" onClick={readAll} className="min-h-9 text-xs font-semibold text-[#7A5F22]">Marcar todo como leído</button>}
          </div>
          {data.items.length ? (
            <ul className="divide-y divide-[#EEECE6]">
              {data.items.map((item) => (
                <li key={item.notification_id}>
                  <button type="button" onClick={() => openItem(item)} className={`block w-full px-3 py-3 text-left hover:bg-slate-50 ${item.read_at ? '' : 'bg-[#FBF6EA]'}`} data-testid={`portal-notification-${item.type}`}>
                    <p className="text-sm font-semibold text-[#101D36]">{item.title}</p>
                    <p className="text-xs text-slate-600">{item.message}</p>
                    <p className="mt-0.5 text-[0.68rem] text-slate-400">{item.created_at ? new Date(item.created_at).toLocaleString('es') : ''}</p>
                  </button>
                </li>
              ))}
            </ul>
          ) : <p className="p-4 text-sm text-slate-500">No tienes avisos.</p>}
        </div>
      )}
    </div>
  );
}
