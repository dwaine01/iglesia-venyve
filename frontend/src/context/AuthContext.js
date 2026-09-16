import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);
const API = process.env.REACT_APP_BACKEND_URL;
if (!API) throw new Error('REACT_APP_BACKEND_URL is required.');

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    if (token) {
      axios.get(`${API}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
        .then(res => {
          setUser(res.data);
          setLoading(false);
        })
        .catch(() => {
          logout();
          setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, [token, logout]);

  const login = async (email, password) => {
    const res = await axios.post(`${API}/api/auth/login`, { email, password });
    localStorage.setItem('token', res.data.token);
    setToken(res.data.token);
    setUser(res.data.user);
    return res.data;
  };

  const register = async (nombre, email, password, invite_code, rol) => {
    const payload = { nombre, email, password };
    if (invite_code && invite_code.trim()) payload.invite_code = invite_code.trim();
    if (rol) payload.rol = rol;
    const res = await axios.post(`${API}/api/auth/register`, payload);
    localStorage.setItem('token', res.data.token);
    setToken(res.data.token);
    setUser(res.data.user);
    return res.data;
  };

  const changePassword = async (current_password, new_password) => {
    const res = await axios.post(`${API}/api/auth/change-password`, { current_password, new_password }, getAuthHeaders());
    localStorage.setItem('token', res.data.token);
    setToken(res.data.token);
    setUser(res.data.user);
    return res.data;
  };

  const refreshUser = async () => {
    const res = await axios.get(`${API}/api/auth/me`, getAuthHeaders());
    setUser(res.data);
    return res.data;
  };

  const getAuthHeaders = () => ({
    headers: { Authorization: `Bearer ${token}` }
  });

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, changePassword, refreshUser, logout, getAuthHeaders, API }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
