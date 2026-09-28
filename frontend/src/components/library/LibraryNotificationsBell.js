import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Bell } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';

export const LibraryNotificationsBell = () => {
  const { API, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const boxRef = useRef(null);

  const refresh = async () => {
    const { data } = await axios.get(`${API}/api/library/notifications`, getAuthHeaders());
    setItems(data.items || []); setUnread(data.unread_count || 0);
  };

  useEffect(() => { refresh(); }, [API]);
  useEffect(() => {
    const onClickOutside = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  const openNotification = async (item) => {
    if (!item.read_at) await axios.patch(`${API}/api/library/notifications/${item.notification_id}/read`, {}, getAuthHeaders()).catch(() => {});
    await refresh();
    setOpen(false);
    if (item.link) navigate(item.link);
  };

  return <div className="relative" ref={boxRef}>
    <button type="button" onClick={() => setOpen((v) => !v)} className="relative rounded-lg border border-[#132443] p-2 text-[#132443]" data-testid="library-notifications-bell">
      <Bell className="h-5 w-5" />
      {unread > 0 && <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-600 text-xs text-white" data-testid="library-notifications-unread-count">{unread}</span>}
    </button>
    {open && <div className="absolute right-0 z-50 mt-2 w-80 rounded-xl border border-slate-200 bg-white p-2 shadow-lg" data-testid="library-notifications-panel">
      {items.length === 0 ? <p className="p-3 text-sm text-slate-500" data-testid="library-notifications-empty">Sin notificaciones.</p> : <ul className="max-h-80 divide-y overflow-y-auto">
        {items.map((item) => <li key={item.notification_id} onClick={() => openNotification(item)} className={`cursor-pointer p-2 text-sm hover:bg-slate-50 ${!item.read_at ? 'font-medium' : 'text-slate-500'}`} data-testid={`library-notification-item-${item.notification_id}`}>
          <p>{item.title}</p><p className="text-xs text-slate-400">{item.message}</p>
        </li>)}
      </ul>}
    </div>}
  </div>;
};
