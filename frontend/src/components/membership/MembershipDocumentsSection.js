/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BadgeCheck, CalendarClock, CreditCard, FileSignature, History, Settings2, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { MembershipDocumentDialog } from './MembershipDocumentDialog';
import { formatMembershipDate } from './MembershipDocumentTemplates';

const today = () => new Date().toISOString().slice(0, 10);

export const MembershipDocumentsSection = ({ personId, photoSrc }) => {
  const { API, getAuthHeaders, user } = useAuth();
  const [status, setStatus] = useState(null);
  const [settings, setSettings] = useState(null);
  const [history, setHistory] = useState([]);
  const [issueDate, setIssueDate] = useState(today());
  const [existingNumber, setExistingNumber] = useState('');
  const [signatureSrc, setSignatureSrc] = useState(null);
  const [signatureFile, setSignatureFile] = useState(null);
  const [preview, setPreview] = useState({ open: false, type: null, data: null });
  const [saving, setSaving] = useState(false);

  const loadSignature = async (currentSettings) => {
    if (!currentSettings?.signature_file_id) { setSignatureSrc(null); return; }
    try {
      const response = await axios.get(`${API}/api/membership/settings/signature`, { ...getAuthHeaders(), responseType: 'blob' });
      setSignatureSrc((previous) => { if (previous) URL.revokeObjectURL(previous); return URL.createObjectURL(response.data); });
    } catch { setSignatureSrc(null); }
  };
  const load = async () => {
    const [statusResponse, settingsResponse, historyResponse] = await Promise.all([
      axios.get(`${API}/api/membership/persons/${personId}`, getAuthHeaders()),
      axios.get(`${API}/api/membership/settings`, getAuthHeaders()),
      axios.get(`${API}/api/membership/persons/${personId}/issuances`, getAuthHeaders()),
    ]);
    setStatus(statusResponse.data); setSettings(settingsResponse.data); setHistory(historyResponse.data.items || []); await loadSignature(settingsResponse.data);
  };
  useEffect(() => { load().catch((error) => toast.error(error?.response?.data?.detail || 'No se pudo cargar Membresía')); return () => { if (signatureSrc) URL.revokeObjectURL(signatureSrc); }; }, [personId]);

  const issue = async (type) => {
    if (type === 'card' && !photoSrc) return toast.error('La Persona 360 necesita fotografía antes de emitir el carnet');
    if (type === 'certificate' && !settings?.signature_file_id) return toast.error('Configure primero la firma autorizada');
    setSaving(true);
    try {
      const response = await axios.post(`${API}/api/membership/persons/${personId}/documents/${type}/issue`, { issue_date: issueDate, existing_member_number: existingNumber || null }, getAuthHeaders());
      setPreview({ open: true, type, data: response.data.data });
      toast.success(response.data.action === 'issued' ? 'Documento emitido' : 'Reimpresión registrada');
      await load();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo emitir'); } finally { setSaving(false); }
  };
  const renew = async () => {
    setSaving(true);
    try {
      const response = await axios.post(`${API}/api/membership/persons/${personId}/card/renew`, { issue_date: issueDate }, getAuthHeaders());
      setPreview({ open: true, type: 'card', data: response.data.data }); toast.success('Vigencia renovada; número conservado'); await load();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo renovar'); } finally { setSaving(false); }
  };
  const saveSettings = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/api/membership/settings`, { expiration_months: Number(settings.expiration_months), authorized_signer_name: settings.authorized_signer_name || '', authorized_signer_title: settings.authorized_signer_title || '', organization_name: settings.organization_name || 'Casa de Oración Ven y Ve' }, getAuthHeaders());
      if (signatureFile) { const body = new FormData(); body.append('file', signatureFile); await axios.post(`${API}/api/membership/settings/signature`, body, getAuthHeaders()); }
      toast.success('Configuración oficial actualizada'); setSignatureFile(null); await load();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo guardar'); } finally { setSaving(false); }
  };

  if (!status || !settings) return <section className="border bg-white p-5" data-testid="membership-documents-loading">Cargando documentos oficiales…</section>;
  const data = status.data || {};
  const membership = data.membership || {};
  const person = data.person || {};
  return <section className="space-y-5" data-testid="membership-documents-section">
    <div className="border bg-white p-5"><div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between"><div><p className="flex items-center gap-2 text-xs font-bold uppercase text-[#0879BE]"><ShieldCheck className="h-4 w-4" />Documentos oficiales</p><h2 className="mt-2 font-['Spectral'] text-3xl font-semibold">Carnet y certificado</h2><p className="mt-1 text-sm text-slate-500">Identidad: {person.full_name} · Cargo desde Persona 360: <b>{person.position || 'MIEMBRO'}</b></p></div>{user?.rol === 'pastor' && <Dialog><DialogTrigger asChild><Button variant="outline" data-testid="open-membership-settings-button"><Settings2 className="h-4 w-4" />Configurar</Button></DialogTrigger><DialogContent className="max-w-xl" data-testid="membership-settings-dialog"><DialogHeader><DialogTitle>Configuración de documentos</DialogTitle></DialogHeader><div className="grid gap-4 sm:grid-cols-2"><div><Label>Vigencia del carnet (meses)</Label><Input type="number" min="1" max="120" value={settings.expiration_months} onChange={(event) => setSettings({ ...settings, expiration_months: event.target.value })} data-testid="membership-expiration-months-input" /></div><div><Label>Nombre institucional</Label><Input value={settings.organization_name || ''} onChange={(event) => setSettings({ ...settings, organization_name: event.target.value })} data-testid="membership-organization-name-input" /></div><div><Label>Firmante autorizado</Label><Input value={settings.authorized_signer_name || ''} onChange={(event) => setSettings({ ...settings, authorized_signer_name: event.target.value })} data-testid="membership-signer-name-input" /></div><div><Label>Cargo del firmante</Label><Input value={settings.authorized_signer_title || ''} onChange={(event) => setSettings({ ...settings, authorized_signer_title: event.target.value })} data-testid="membership-signer-title-input" /></div><div className="sm:col-span-2"><Label>Firma PNG transparente</Label><Input type="file" accept="image/png" onChange={(event) => setSignatureFile(event.target.files?.[0] || null)} data-testid="membership-signature-file-input" /><p className="mt-1 text-xs text-slate-500">PNG transparente, máximo 500 KiB. {settings.signature_file_id ? 'Hay una firma configurada.' : 'Pendiente de configurar.'}</p></div></div><Button onClick={saveSettings} disabled={saving} data-testid="save-membership-settings-button">Guardar configuración</Button></DialogContent></Dialog>}</div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><div className="border bg-slate-50 p-4"><span className="text-xs uppercase text-slate-500">Member No.</span><strong className="mt-1 block text-2xl text-[#0879BE]" data-testid="membership-status-number">{membership.member_number || 'Pendiente'}</strong></div><div className="border bg-slate-50 p-4"><span className="text-xs uppercase text-slate-500">Certificado</span><strong className="mt-1 block">{formatMembershipDate(membership.certificate_issue_date)}</strong></div><div className="border bg-slate-50 p-4"><span className="text-xs uppercase text-slate-500">Carnet emitido</span><strong className="mt-1 block">{formatMembershipDate(membership.card_issue_date)}</strong></div><div className="border bg-slate-50 p-4"><span className="text-xs uppercase text-slate-500">Carnet expira</span><strong className="mt-1 block">{formatMembershipDate(membership.card_expiration_date)}</strong></div></div>
      <div className="mt-5 grid gap-3 md:grid-cols-[180px_1fr_auto]"><div><Label>Fecha de emisión/renovación</Label><Input type="date" value={issueDate} onChange={(event) => setIssueDate(event.target.value)} data-testid="membership-issue-date-input" /></div>{!status.exists && user?.rol === 'pastor' ? <div><Label>Número existente (opcional)</Label><Input value={existingNumber} onChange={(event) => setExistingNumber(event.target.value.replace(/\D/g, '').slice(0, 10))} placeholder="Para migración histórica" data-testid="existing-member-number-input" /></div> : <div />}<div className="flex flex-wrap items-end gap-2"><Button onClick={() => issue('certificate')} disabled={saving || !settings.signature_file_id} data-testid="issue-membership-certificate-button"><FileSignature className="h-4 w-4" />{membership.certificate_issue_date ? 'Reimprimir certificado' : 'Emitir certificado'}</Button><Button onClick={() => issue('card')} disabled={saving || !photoSrc} data-testid="issue-membership-card-button"><CreditCard className="h-4 w-4" />{membership.card_issue_date ? 'Reimprimir carnet' : 'Emitir carnet'}</Button>{membership.card_issue_date && <Button variant="outline" onClick={renew} disabled={saving} data-testid="renew-membership-card-button"><CalendarClock className="h-4 w-4" />Renovar vigencia</Button>}</div></div>
      {!photoSrc && <p className="mt-3 border-l-4 border-amber-500 bg-amber-50 p-3 text-sm" data-testid="membership-photo-required-alert">Añada una fotografía al perfil de Persona 360 para habilitar el carnet.</p>}
    </div>
    <div className="border bg-white p-5" data-testid="membership-issuance-history"><h3 className="flex items-center gap-2 font-['Spectral'] text-xl font-semibold"><History className="h-5 w-5" />Historial de emisión</h3>{history.length ? <div className="mt-3 divide-y">{history.slice(0, 20).map((item) => <div key={item.issuance_id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm"><span className="flex items-center gap-2"><BadgeCheck className="h-4 w-4 text-emerald-600" />{item.document_type === 'card' ? 'Carnet' : 'Certificado'} · {item.action}</span><span className="text-slate-500">{String(item.created_at).slice(0, 19).replace('T', ' ')}</span></div>)}</div> : <p className="mt-3 text-sm text-slate-500">Aún no se han emitido documentos.</p>}</div>
    <MembershipDocumentDialog open={preview.open} onOpenChange={(open) => setPreview({ ...preview, open })} documentType={preview.type} data={preview.data} photoSrc={photoSrc} signatureSrc={signatureSrc} />
  </section>;
};