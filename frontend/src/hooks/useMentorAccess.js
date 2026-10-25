import { useEffect, useState } from 'react';
import axios from 'axios';

import { useAuth } from '../context/AuthContext';

export const useMentorAccess = () => {
  const { API, getAuthHeaders, user } = useAuth();
  const [state, setState] = useState({ loading: true, isActiveMentor: false });
  useEffect(() => {
    let active = true;
    if (!user?.person_id) { setState({ loading: false, isActiveMentor: false }); return undefined; }
    // Insignia PROPIA (no exige permiso de perfiles: una cuenta «persona» que es mentor también la lee).
    axios.get(`${API}/api/mentorship/my-badge`, getAuthHeaders())
      .then((response) => { if (active) setState({ loading: false, isActiveMentor: Boolean(response.data?.active) }); })
      .catch(() => { if (active) setState({ loading: false, isActiveMentor: false }); });
    return () => { active = false; };
  }, [API, getAuthHeaders, user]);
  return state;
};
