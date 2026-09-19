import React, { useState } from 'react';
import { ArrowLeft, FileSearch, Loader2, ShieldCheck, Upload } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { MembershipImportMapping } from '../components/membership/MembershipImportMapping';
import { MembershipImportResults } from '../components/membership/MembershipImportResults';

export default function MembershipImportPage() {
  const { API, getAuthHeaders } = useAuth(); const navigate = useNavigate();
  const [file, setFile] = useState(null); const [report, setReport] = useState(null);
  const [mapping, setMapping] = useState({}); const [loading, setLoading] = useState(false); const [error, setError] = useState('');

  const run = async (customMapping = null) => {
    if (!file) return setError('Seleccione un archivo CSV o XLSX.');
    setLoading(true); setError('');
    try {
      const body = new FormData(); body.append('file', file);
      if (customMapping) body.append('mapping', JSON.stringify(customMapping));
      const response = await axios.post(`${API}/api/membership/import/dry-run`, body, getAuthHeaders());
      setReport(response.data); setMapping(response.data.mapping || {});
      toast.success(`Análisis completado: ${response.data.summary.total} filas, 0 escrituras`);
    } catch (requestError) { setError(apiErrorMessage(requestError, 'No se pudo analizar el archivo')); }
    finally { setLoading(false); }
  };

  return <main className="min-h-screen bg-[#F4F1EA] px-4 py-6 sm:px-6 lg:px-8" data-testid="membership-import-page"><div className="mx-auto max-w-7xl space-y-6">
    <button type="button" onClick={() => navigate('/personas')} className="flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-950" data-testid="membership-import-back-button"><ArrowLeft className="h-4 w-4" />Volver a Personas</button>
    <header className="border-l-4 border-emerald-600 bg-white p-5 shadow-sm"><p className="flex items-center gap-2 text-xs font-bold uppercase text-emerald-700"><ShieldCheck className="h-4 w-4" />Simulación segura</p><h1 className="mt-2 font-['Spectral'] text-3xl font-semibold text-slate-950 sm:text-4xl">Importar membresía histórica</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Analiza CSV o Excel, detecta posibles duplicados y sugiere hogares. Esta pantalla es 100% DRY-RUN: no crea Personas, membresías ni hogares.</p></header>
    <section className="grid gap-4 border bg-white p-5 lg:grid-cols-[1fr_auto] lg:items-end" data-testid="membership-import-file-section"><div><label htmlFor="membership-import-file" className="mb-2 block text-sm font-semibold">Archivo CSV o XLSX</label><Input id="membership-import-file" type="file" accept=".csv,.xlsx" onChange={(event) => { setFile(event.target.files?.[0] || null); setReport(null); setMapping({}); setError(''); }} data-testid="membership-import-file-input" /><p className="mt-2 text-xs text-slate-500">Máximo 5 MiB y 2,000 filas. Para el padrón actual se esperan aproximadamente 130–150 personas.</p></div><Button onClick={() => run()} disabled={!file || loading} className="h-11 bg-emerald-700 hover:bg-emerald-800" data-testid="btn-dry-run-import">{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSearch className="h-4 w-4" />}Analizar sin guardar</Button></section>
    {error && <div className="border border-red-300 bg-red-50 p-3 text-sm text-red-800" data-testid="membership-import-error-alert">{error}</div>}
    {report && <><MembershipImportMapping columns={report.columns} mapping={mapping} onChange={(field, value) => setMapping((current) => ({ ...current, [field]: value }))} /><div className="flex justify-end"><Button variant="outline" onClick={() => run(mapping)} disabled={loading} data-testid="membership-import-rerun-button"><Upload className="h-4 w-4" />Reanalizar con este mapeo</Button></div><MembershipImportResults report={report} /></>}
  </div></main>;
}