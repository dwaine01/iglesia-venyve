import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { DatabaseZap, Loader2, ShieldCheck, TriangleAlert } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { CoreAccessTable } from '../components/core/CoreAccessTable';
import { CoreHealthCards } from '../components/core/CoreHealthCards';
import { CoreMigrationPanel } from '../components/core/CoreMigrationPanel';
import { CreateAccessDialog } from '../components/core/CreateAccessDialog';
import { ConfidentialityPolicyPanel } from '../components/core/ConfidentialityPolicyPanel';
import { translateTechnicalText } from '../lib/displayLabels';

export default function CoreGovernancePage() {
  const { API, getAuthHeaders, user } = useAuth();
  const [integrity, setIntegrity] = useState(null);
  const [users, setUsers] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [saving, setSaving] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const requests = [axios.get(`${API}/api/core/governance/users`, getAuthHeaders()), axios.get(`${API}/api/core/governance/access-candidates`, getAuthHeaders())];
      if (user?.rol === 'pastor') requests.push(axios.get(`${API}/api/core/governance/integrity`, getAuthHeaders()));
      const [usersResponse, candidatesResponse, integrityResponse] = await Promise.all(requests);
      setUsers(usersResponse.data.items || []);
      setCandidates(candidatesResponse.data.items || []);
      setIntegrity(integrityResponse?.data || null);
    } catch (requestError) {
      setError(translateTechnicalText(requestError?.response?.data?.detail || 'No se pudo cargar la gestión de accesos.'));
    } finally {
      setLoading(false);
    }
  }, [API, getAuthHeaders, user?.rol]);

  useEffect(() => { load(); }, [load]);

  const runMigration = async () => {
    setRunning(true);
    try {
      const response = await axios.post(`${API}/api/core/governance/migrate`, {}, getAuthHeaders());
      toast.success(`Núcleo consolidado: ${response.data.users_linked + response.data.legacy_people_linked} enlaces actualizados`);
      await load();
    } catch (requestError) {
      toast.error(requestError?.response?.data?.detail || 'No se pudo ejecutar la migración.');
    } finally { setRunning(false); }
  };

  const saveAccess = async (userId, payload) => {
    setSaving(userId);
    try {
      await axios.put(`${API}/api/core/governance/users/${userId}/access`, payload, getAuthHeaders());
      toast.success('Acceso actualizado y sesiones anteriores revocadas');
      await load();
    } catch (requestError) {
      toast.error(requestError?.response?.data?.detail || 'No se pudo actualizar el acceso.');
    } finally { setSaving(null); }
  };

  const createAccess = async (payload) => {
    try {
      await axios.post(`${API}/api/core/governance/users`, payload, getAuthHeaders());
      toast.success('Acceso creado; entregue la clave temporal de forma privada');
      await load();
      return true;
    } catch (requestError) {
      toast.error(translateTechnicalText(requestError?.response?.data?.detail || 'No se pudo crear el acceso.'));
      return false;
    }
  };

  if (loading) return <div className="flex min-h-[60vh] items-center justify-center" data-testid="core-loading-state"><Loader2 className="h-7 w-7 animate-spin text-[#9A7A2F]" /></div>;

  return (
    <div className="min-h-screen bg-[#F8F6F0]" data-testid="core-governance-page">
      <motion.header initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="bg-[#101D36] px-4 py-9 text-white sm:px-6 lg:px-8">
        <div className="flex max-w-5xl flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md border border-[#D4B871]/30 bg-[#0B1428] text-[#D4B871]"><DatabaseZap className="h-6 w-6" /></div>
          <div><p className="text-xs font-semibold uppercase text-[#D4B871]">Acceso controlado</p><h1 className="mt-1 font-['Spectral'] text-3xl font-bold sm:text-4xl" data-testid="core-page-title">Gestión de accesos</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-white/65">Cada cuenta nace desde un Perfil 360 y recibe únicamente el nivel autorizado.</p></div>
          </div>
          <CreateAccessDialog candidates={candidates} currentUser={user} onCreate={createAccess} />
        </div>
      </motion.header>

      {error ? <div className="m-4 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700" data-testid="core-error-alert"><TriangleAlert className="mt-0.5 h-4 w-4" />{error}</div> : (
        <>
          {user?.rol === 'pastor' && integrity && <><div className="px-4 py-6 sm:px-6 lg:px-8"><CoreHealthCards integrity={integrity} /></div><CoreMigrationPanel integrity={integrity} running={running} onRun={runMigration} />{integrity.duplicate_candidates?.length > 0 && <div className="mx-4 mt-6 rounded-md border border-amber-200 bg-amber-50 p-4 sm:mx-6 lg:mx-8" data-testid="core-duplicate-alert"><div className="flex gap-2"><ShieldCheck className="mt-0.5 h-4 w-4 text-amber-700" /><div><p className="font-semibold text-amber-900">Candidatos a duplicado: {integrity.duplicate_candidates.length}</p><p className="mt-1 text-xs text-amber-800">Se mantienen separados hasta una revisión humana; la migración nunca fusiona identidades ambiguas.</p></div></div></div>}</>}
          {user?.rol === 'pastor' && <ConfidentialityPolicyPanel />}
          <CoreAccessTable items={users} currentUser={user} saving={saving} onSave={saveAccess} />
        </>
      )}
    </div>
  );
}