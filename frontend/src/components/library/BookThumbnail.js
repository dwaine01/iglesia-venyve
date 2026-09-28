import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BookOpen } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';

export const BookThumbnail = ({ fileId, size = 40, className = '' }) => {
  const { API, getAuthHeaders } = useAuth();
  const [src, setSrc] = useState(null);

  useEffect(() => {
    let objectUrl;
    if (!fileId) { setSrc(null); return; }
    axios.get(`${API}/api/library/files/${fileId}/download`, { ...getAuthHeaders(), params: { thumbnail: true }, responseType: 'blob' })
      .then((res) => { objectUrl = URL.createObjectURL(res.data); setSrc(objectUrl); })
      .catch(() => setSrc(null));
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [fileId, API]);

  const style = { width: size, height: size };
  if (!fileId || !src) return <div style={style} className={`flex items-center justify-center rounded-md bg-slate-100 text-slate-400 ${className}`} data-testid="book-thumbnail-placeholder"><BookOpen className="h-4 w-4" /></div>;
  return <img src={src} alt="" style={style} className={`rounded-md object-cover ${className}`} data-testid="book-thumbnail-image" />;
};
