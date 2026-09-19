import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { UserPlus, ArrowLeft, AlertTriangle, BadgeCheck, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { canManageDirectMembership } from '../lib/accessControl';

const emptyForm = { nombre: '', apellido: '', telefono: '', email: '', fecha_nacimiento: '', preexisting_active_member: false, existing_member_number: '' };

export default function PersonaNuevaPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState(emptyForm);
  const [step, setStep] = useState('form');
  const [duplicates, setDuplicates] = useState([]);
  const [idempotencyKey, setIdempotencyKey] = useState(null);
  const [checking, setChecking] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const canDirect = canManageDirectMembership(user);

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  const genKey = () =>
    (window.crypto?.randomUUID?.() ||
      `${Date.now()}-${Math.random().toString(36).slice(2)}`);

  const isValid = form.nombre.trim().length >= 2 && form.apellido.trim().length >= 2;

  const handleCheckDuplicates = async () => {
    if (!isValid) {
      setError('Nombre y apellido son obligatorios.');
      return;
    }
    setError('');
    setChecking(true);
    try {
      const res = await axios.post(
        `${API}/api/core/persons/check-duplicates`,
        { nombre: form.nombre.trim(), apellido: form.apellido.trim(), telefono: form.telefono || null },
        getAuthHeaders()
      );
      const found = res.data.possible_duplicates || [];
      setDuplicates(found);
      setIdempotencyKey(genKey());
      setStep('review');
    } catch (err) {
      setError(formatError(err?.response?.data?.detail));
    } finally {
      setChecking(false);
    }
  };

  const handleCreate = async () => {
    setError('');
    setCreating(true);
    try {
      const payload = {
        nombre: form.nombre.trim(),
        apellido: form.apellido.trim(),
        telefono: form.telefono || null,
        email: form.email || null,
        fecha_nacimiento: form.fecha_nacimiento || null,
        idempotency_key: idempotencyKey || genKey(),
        preexisting_active_member: canDirect && form.preexisting_active_member,
        existing_member_number: canDirect && form.preexisting_active_member && form.existing_member_number ? form.existing_member_number.trim() : null,
      };
      const res = await axios.post(`${API}/api/core/persons`, payload, getAuthHeaders());
      if (res.data.membership?.direct) toast.success(`Membresía directa activada · N.º ${res.data.membership.member_number}`);
      navigate(`/personas/${res.data.person_id}`);
    } catch (err) {
      setError(formatError(err?.response?.data?.detail));
    } finally {
      setCreating(false);
    }
  };

  const nombreCompleto = (p) => `${p.nombre || ''} ${p.apellido || ''}`.trim();

  const formatError = (detail) => {
    if (typeof detail === 'string') return detail;
    if (detail?.message) return detail.message;
    if (Array.isArray(detail)) return detail.map((item) => item?.msg).filter(Boolean).join(' ');
    return 'No se pudo crear la persona.';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] p-4 md:p-8">
      <div className="max-w-2xl mx-auto space-y-6">
        <button
          onClick={() => navigate('/personas')}
          className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
          data-testid="new-person-back-button"
        >
          <ArrowLeft className="w-4 h-4" />
          Volver a Personas
        </button>

        <Card className="border-none shadow-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-xl">
              <UserPlus className="w-5 h-5 text-[#C8A951]" />
              Nueva Persona
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            {error && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md p-3" data-testid="new-person-error-alert">
                {error}
              </div>
            )}

            {step === 'form' && (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="nombre">Nombre *</Label>
                    <Input id="nombre" value={form.nombre} onChange={update('nombre')} data-testid="new-person-first-name-input" />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="apellido">Apellido *</Label>
                    <Input id="apellido" value={form.apellido} onChange={update('apellido')} data-testid="new-person-last-name-input" />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="telefono">Teléfono</Label>
                    <Input id="telefono" value={form.telefono} onChange={update('telefono')} data-testid="new-person-phone-input" />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="email">Email</Label>
                    <Input id="email" type="email" value={form.email} onChange={update('email')} data-testid="new-person-email-input" />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="fecha_nacimiento">Fecha de nacimiento</Label>
                    <Input
                      id="fecha_nacimiento"
                      type="date"
                      value={form.fecha_nacimiento}
                      onChange={update('fecha_nacimiento')}
                      data-testid="new-person-birth-date-input"
                    />
                  </div>
                </div>
                {canDirect && <div className="border-l-4 border-emerald-600 bg-emerald-50 p-4" data-testid="direct-membership-section">
                  <div className="flex items-start gap-3">
                    <Checkbox id="preexisting-active-member" checked={form.preexisting_active_member} onCheckedChange={(checked) => setForm((current) => ({ ...current, preexisting_active_member: Boolean(checked), existing_member_number: checked ? current.existing_member_number : '' }))} data-testid="toggle-direct-membership-checkbox" />
                    <div className="min-w-0 flex-1"><Label htmlFor="preexisting-active-member" className="flex items-center gap-2 font-semibold text-emerald-950"><BadgeCheck className="h-4 w-4" />Miembro activo preexistente</Label><p className="mt-1 text-xs leading-5 text-emerald-800">Omite el proceso de nuevos miembros y habilita de inmediato el número, carnet y certificado.</p></div>
                  </div>
                  {form.preexisting_active_member && <div className="mt-4 space-y-1.5"><Label htmlFor="existing-member-number">Número existente (opcional)</Label><Input id="existing-member-number" value={form.existing_member_number} onChange={update('existing_member_number')} placeholder="Déjelo vacío para asignar uno nuevo" maxLength={20} data-testid="input-membership-number" /></div>}
                </div>}
                <Button
                  onClick={handleCheckDuplicates}
                  disabled={!isValid || checking}
                  className="w-full bg-[#C8A951] hover:bg-[#B8964A] text-white"
                  data-testid="new-person-check-duplicates-button"
                >
                  {checking ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : null}
                  Verificar y continuar
                </Button>
              </>
            )}

            {step === 'review' && (
              <div className="space-y-4">
                {form.preexisting_active_member && <div className="border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900" data-testid="direct-membership-review-alert"><b>Alta directa:</b> al crear esta Persona se activará su membresía histórica y sus documentos oficiales.</div>}
                {duplicates.length > 0 ? (
                  <div className="rounded-md border border-amber-300 bg-amber-50 p-4 space-y-3">
                    <div className="flex items-start gap-2 text-amber-800">
                      <AlertTriangle className="w-5 h-5 mt-0.5 shrink-0" />
                      <div>
                        <p className="font-semibold">
                          Encontramos {duplicates.length} persona(s) con datos parecidos.
                        </p>
                        <p className="text-sm text-amber-700">
                          Revisa si alguna ya es esta persona antes de crear un registro nuevo.
                        </p>
                      </div>
                    </div>
                    <div className="space-y-2">
                      {duplicates.map((d) => (
                        <div
                          key={d.person_id}
                          className="flex items-center justify-between bg-white rounded-md border border-amber-200 p-3"
                        >
                          <div>
                            <p className="font-medium text-gray-900">{nombreCompleto(d)}</p>
                            <p className="text-xs text-gray-500">
                              {d.person_number} {d.telefono ? `· ${d.telefono}` : ''}
                            </p>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigate(`/personas/${d.person_id}`)}
                            data-testid={`new-person-open-duplicate-${d.person_id}`}
                          >
                            Ver este perfil
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="rounded-md border border-green-200 bg-green-50 p-4 text-sm text-green-800">
                    No encontramos personas parecidas. Puedes crear el registro con confianza.
                  </div>
                )}

                <div className="flex flex-col sm:flex-row gap-3">
                  <Button variant="outline" onClick={() => setStep('form')} className="sm:w-auto w-full" data-testid="new-person-edit-data-button">
                    Editar datos
                  </Button>
                  {duplicates.length === 0 && <Button onClick={handleCreate} disabled={creating} className="flex-1 bg-[#C8A951] hover:bg-[#B8964A] text-white" data-testid="new-person-create-button">{creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}Crear Persona</Button>}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
