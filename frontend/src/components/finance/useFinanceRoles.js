import { useEffect, useState } from 'react';
import axios from 'axios';

import { useAuth } from '../../context/AuthContext';

// Qué puede hacer esta cuenta en Finanzas (el servidor vuelve a validar cada acción). Mientras carga, nada de
// escritura se muestra. La pastora: solo lectura (decisión del dueño).
let cached = null;
let cachedToken = null;

export const useFinanceRoles = () => {
  const { API, getAuthHeaders, token } = useAuth();
  const [roles, setRoles] = useState(cached && cachedToken === token ? cached : {});
  useEffect(() => {
    if (cached && cachedToken === token) return undefined;
    let alive = true;
    axios.get(`${API}/api/finance/my-roles`, getAuthHeaders()).then((response) => {
      cached = response.data || {}; cachedToken = token;
      if (alive) setRoles(cached);
    }).catch(() => { if (alive) setRoles({}); });
    return () => { alive = false; };
  }, [API, token]); // eslint-disable-line react-hooks/exhaustive-deps
  return roles;
};
