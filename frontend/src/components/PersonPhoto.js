import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';

export default function PersonPhoto({ personId, available, name, className = 'h-12 w-12' }) {
  const { API, getAuthHeaders } = useAuth();
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url;
    if (!available) { setSrc(null); return undefined; }
    axios.get(`${API}/api/core/persons/${personId}/photo`, { ...getAuthHeaders(), responseType: 'blob' })
      .then((response) => { url = URL.createObjectURL(response.data); setSrc(url); })
      .catch(() => setSrc(null));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [API, available, getAuthHeaders, personId]);
  if (src) return <img src={src} alt={name} data-testid={`person-photo-${personId}`} className={`${className} rounded-lg object-cover`} />;
  const initials = (name || '?').split(' ').map((part) => part[0]).slice(0, 2).join('');
  return <div data-testid={`person-photo-fallback-${personId}`} className={`${className} flex items-center justify-center rounded-lg bg-[#F3EACD] font-semibold text-[#755B21]`}>{initials}</div>;
}
