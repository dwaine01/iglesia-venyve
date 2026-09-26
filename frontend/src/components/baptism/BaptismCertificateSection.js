import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { FileSignature, History } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { BaptismDocumentDialog } from './BaptismDocumentDialog';

export const BaptismCertificateSection = ({ personId, canIssue }) => {
  const { API, getAuthHeaders } = useAuth();
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [signatureSrc, setSignatureSrc] = useState(null);
  const [preview, setPreview] = useState({ open: false, data: null });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let objectUrl = null;
    const load = async () => {
      const [statusResponse, historyResponse] = await Promise.all([
        axios.get(`${API}/api/baptism/persons/${personId}`, getAuthHeaders()),
        axios.get(`${API}/api/baptism/persons/${personId}/issuances`, getAuthHeaders()),
      ]);
      setStatus(statusResponse.data);
      setHistory(historyResponse.data.items || []);
      try {
        const signatureResponse = await axios.get(`${API}/api/membership/settings/signature`, { ...getAuthHeaders(), responseType: 'blob' });
        objectUrl = URL.createObjectURL(signatureResponse.data);
        setSignatureSrc(objectUrl);
      } catch { setSignatureSrc(null); }
    };
    load().catch(() => {});
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [API, getAuthHeaders, personId]);

  const issue = async () => {
    setSaving(true);
    try {
      const response = await axios.post(`${API}/api/baptism/persons/${personId}/certificate/issue`, {}, getAuthHeaders());
      setPreview({ open: true, data: response.data.data });
      toast.success(response.data.action === 'issued' ? 'Certificado de bautismo emitido' : 'Reimpresión registrada');
      const [statusResponse, historyResponse] = await Promise.all([
        axios.get(`${API}/api/baptism/persons/${personId}`, getAuthHeaders()),
        axios.get(`${API}/api/baptism/persons/${personId}/issuances`, getAuthHeaders()),
      ]);
      setStatus(statusResponse.data); setHistory(historyResponse.data.items || []);
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo emitir el certificado'); }
    finally { setSaving(false); }
  };

  if (!status?.exists) return null;
  const baptism = status.data?.baptism || {};
  if (baptism.status !== 'completed') return null;
  return (
    <div className="mt-4 border-t border-[#E8E5DE] pt-4" data-testid="baptism-certificate-section">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-['Spectral'] text-lg font-semibold text-[#101D36]">Certificado de bautismo</h3>
          <p className="text-sm text-slate-500" data-testid="baptism-certificate-status">{baptism.certificate_issue_date ? `Emitido el ${baptism.certificate_issue_date}` : 'Aún no emitido'}</p>
        </div>
        {canIssue && <Button onClick={issue} disabled={saving} className="bg-[#132443]" data-testid="issue-baptism-certificate-button"><FileSignature className="h-4 w-4" />{baptism.certificate_issue_date ? 'Reimprimir certificado' : 'Emitir certificado'}</Button>}
      </div>
      {history.length > 0 && <p className="mt-2 flex items-center gap-1 text-xs text-slate-400" data-testid="baptism-certificate-history-count"><History className="h-3.5 w-3.5" />{history.length} emisión(es) registradas</p>}
      <BaptismDocumentDialog open={preview.open} onOpenChange={(open) => setPreview((old) => ({ ...old, open }))} data={preview.data} signatureSrc={signatureSrc} />
    </div>
  );
};
