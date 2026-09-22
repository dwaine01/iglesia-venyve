import { useEffect, useState } from 'react';
import axios from 'axios';

import { useAuth } from '../context/AuthContext';
import { isPastoralAuthority } from '../lib/accessControl';

export const useBoardAccess = () => {
  const { API, getAuthHeaders, user } = useAuth();
  const [state, setState] = useState(() => ({ loading: !isPastoralAuthority(user), allowed: isPastoralAuthority(user), full_access: isPastoralAuthority(user), permissions: [] }));
  useEffect(() => {
    let active = true;
    if (!user) { setState({ loading: false, allowed: false, full_access: false, permissions: [] }); return undefined; }
    axios.get(`${API}/api/board/access`, getAuthHeaders())
      .then((response) => { if (active) setState({ loading: false, ...response.data }); })
      .catch(() => { if (active) setState({ loading: false, allowed: false, full_access: false, permissions: [] }); });
    return () => { active = false; };
  }, [API, getAuthHeaders, user]);
  return state;
};

export const hasBoardPermission = (access, permission) => Boolean(access?.full_access || access?.permissions?.includes(permission));