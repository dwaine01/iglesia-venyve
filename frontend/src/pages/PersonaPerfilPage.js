import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import PersonAddressSection from '../components/PersonAddressSection';
import PersonContactSection from '../components/PersonContactSection';
import PersonProfileHeader from '../components/PersonProfileHeader';
import PersonProfileEditor from '../components/PersonProfileEditor';
import Profile360Summary from '../components/Profile360Summary';
import CanonicalFamilySection from '../components/CanonicalFamilySection';
import {
  AttendanceSection,
  HistorySection,
  HouseholdSection,
  ProcessesSection,
} from '../components/ProfileDataSections';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { displayLabel } from '../lib/displayLabels';
import { PersonFinanceSection } from '../components/finance/PersonFinanceSection';
import { MembershipDocumentsSection } from '../components/membership/MembershipDocumentsSection';
import { PersonArchiveDialog } from '../components/PersonArchiveDialog';
import { PersonJourneyStatusStrip } from '../components/PersonJourneyStatusStrip';
import { toast } from 'sonner';
import { canManageDirectMembership } from '../lib/accessControl';

// P-001 Slice 2A - Person Profile 360 (shell full-screen).
// Consume unicamente el read-model /api/core/persons/{id}/profile.
// No inventa estados: si un dominio no tiene datos reales, se muestra tal
// como el backend lo declara (module_unavailable / no_record / has_summary).
const SECTION_LABELS = {
  resumen: 'Resumen',
  contacto: 'Contacto',
  direcciones: 'Direcciones',
  household: 'Hogar',
  familia: 'Familia',
  procesos: 'Procesos',
  asistencia: 'Asistencia',
  historial: 'Historial',
  finanzas: 'Finanzas',
  membresia: 'Carnet y certificado',
};

export default function PersonaPerfilPage() {
  const { personId } = useParams();
  const { API, getAuthHeaders, user } = useAuth();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('resumen');
  const [editorOpen, setEditorOpen] = useState(false);
  const [photoSrc, setPhotoSrc] = useState(null);
  const [photoVersion, setPhotoVersion] = useState(0);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [archiveError, setArchiveError] = useState('');

  const refreshProfile = async () => {
    const response = await axios.get(
      `${API}/api/core/persons/${personId}/profile`,
      getAuthHeaders()
    );
    setProfile(response.data);
    setPhotoVersion((value) => value + 1);
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    axios
      .get(`${API}/api/core/persons/${personId}/profile`, getAuthHeaders())
      .then((res) => {
        if (active) setProfile(res.data);
      })
      .catch((err) => {
        if (active) setError(err?.response?.data?.detail || 'No se pudo cargar el perfil.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [API, getAuthHeaders, personId]);

  useEffect(() => {
    let objectUrl;
    if (!profile?.header?.photo_available) {
      setPhotoSrc(null);
      return undefined;
    }
    axios
      .get(`${API}/api/core/persons/${personId}/photo`, {
        ...getAuthHeaders(),
        responseType: 'blob',
      })
      .then((response) => {
        objectUrl = URL.createObjectURL(response.data);
        setPhotoSrc(objectUrl);
      })
      .catch(() => setPhotoSrc(null));
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [API, getAuthHeaders, personId, photoVersion, profile?.header?.photo_available]);


  const header = profile?.header;
  const sections = profile?.sections || [];
  const available = profile?.sections_available || ['resumen'];
  const planned = profile?.sections_planned || [];
  const canViewFinance = user?.rol === 'pastor' || (user?.capabilities || []).includes('finance.read');
  const canManageMembershipDocuments = canManageDirectMembership(user) || (user?.capabilities || []).includes('membership.documents.manage');
  const canArchive = user?.rol === 'pastor' && user?.person_id !== personId && profile?.identity?.account_role !== 'pastor';
  const allSections = [
    'resumen', 'contacto', 'direcciones', 'household',
    'familia', 'procesos', 'asistencia', 'historial', ...(canViewFinance ? ['finanzas'] : []), ...(canManageMembershipDocuments ? ['membresia'] : []),
  ];

  const archivePerson = async () => {
    setArchiving(true);
    setArchiveError('');
    try {
      await axios.delete(`${API}/api/core/persons/${personId}`, getAuthHeaders());
      toast.success('Persona eliminada del directorio; su historial quedó conservado');
      setArchiveOpen(false);
      navigate('/personas', { replace: true });
    } catch (requestError) {
      setArchiveError(requestError?.response?.data?.detail || 'No se pudo eliminar la Persona del directorio.');
    } finally {
      setArchiving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] p-4 md:p-8">
        <div className="max-w-5xl mx-auto space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (error || !header) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD] p-4 md:p-8">
        <div className="max-w-5xl mx-auto space-y-4">
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md p-3">
            {error || 'Persona no encontrada.'}
          </div>
          <Button variant="outline" onClick={() => navigate('/personas')}>
            Volver a Personas
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F7F5EF] px-3 py-4 sm:px-5 lg:px-7 lg:py-6">
      <div className="mx-auto max-w-[1380px] space-y-4">
        <PersonProfileHeader
          header={header}
          photoSrc={photoSrc}
          onEdit={profile.profile_can_write ? () => setEditorOpen(true) : undefined}
          onArchive={canArchive ? () => { setArchiveError(''); setArchiveOpen(true); } : undefined}
          onSelectTab={setActiveTab}
          onBack={() => navigate('/personas')}
        />
        <PersonArchiveDialog
          open={archiveOpen}
          onOpenChange={setArchiveOpen}
          personName={header.nombre_completo}
          busy={archiving}
          error={archiveError}
          onConfirm={archivePerson}
        />
        <PersonJourneyStatusStrip status={profile.journey_status} />
        {profile.profile_can_write && (
          <PersonProfileEditor
            open={editorOpen}
            onOpenChange={setEditorOpen}
            personId={personId}
            header={header}
            talents={profile.talentos}
            canEditTalents={profile.permissions?.talentos?.write}
            API={API}
            getAuthHeaders={getAuthHeaders}
            onChanged={refreshProfile}
          />
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <div className="overflow-hidden rounded-xl border border-[#E8E5DE] bg-[#EEECE6] p-1 shadow-sm">
            <TabsList className="grid h-auto w-full grid-cols-4 gap-1 bg-transparent p-0 lg:grid-cols-10">
              {allSections.map((section) => (
                <TabsTrigger
                  key={section}
                  value={section}
                  data-testid={`profile-tab-${section}`}
                  disabled={!available.includes(section) && section !== 'finanzas' && section !== 'membresia'}
                  className="min-h-9 rounded-lg px-2 text-xs font-medium text-gray-600 data-[state=active]:bg-white data-[state=active]:text-[#101D36] data-[state=active]:shadow-sm sm:text-sm"
                >
                  {SECTION_LABELS[section] || displayLabel(section, 'Sección')}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>

          <TabsContent value="resumen" className="mt-0">
            <Profile360Summary
              sections={sections}
              available={available}
              onSelect={setActiveTab}
            />
          </TabsContent>

          {profile.contacto && (
            <TabsContent value="contacto" className="mt-0 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm sm:p-6">
              <PersonContactSection
                personId={personId}
                domain={profile.contacto}
                API={API}
                getAuthHeaders={getAuthHeaders}
                onChanged={refreshProfile}
              />
            </TabsContent>
          )}

          {profile.direcciones && (
            <TabsContent value="direcciones" className="mt-0 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm sm:p-6">
              <PersonAddressSection
                personId={personId}
                domain={profile.direcciones}
                API={API}
                getAuthHeaders={getAuthHeaders}
                onChanged={refreshProfile}
              />
            </TabsContent>
          )}

          {available.includes('household') && (
            <TabsContent value="household" className="mt-0 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm sm:p-6">
              <HouseholdSection personId={personId} record={profile.household} canWrite={profile.permissions?.household?.write} API={API} getAuthHeaders={getAuthHeaders} onChanged={refreshProfile} />
            </TabsContent>
          )}

          {available.includes('familia') && (
            <TabsContent value="familia" className="mt-0 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm sm:p-6">
              <CanonicalFamilySection personId={personId} items={profile.familia} canWrite={profile.permissions?.familia?.write} API={API} getAuthHeaders={getAuthHeaders} onChanged={refreshProfile} />
            </TabsContent>
          )}

          {available.includes('procesos') && (
            <TabsContent value="procesos" className="mt-0 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm sm:p-6">
              <ProcessesSection personId={personId} arrival={profile.llegada_origen} processes={profile.procesos} ministries={profile.ministerios} canWrite={profile.permissions?.procesos?.write} canWriteMinistries={profile.permissions?.ministerios?.write} API={API} getAuthHeaders={getAuthHeaders} onChanged={refreshProfile} />
            </TabsContent>
          )}

          {available.includes('asistencia') && (
            <TabsContent value="asistencia" className="mt-0 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm sm:p-6">
              <AttendanceSection personId={personId} items={profile.asistencia} canWrite={profile.permissions?.asistencia?.write} API={API} getAuthHeaders={getAuthHeaders} onChanged={refreshProfile} />
            </TabsContent>
          )}

          {available.includes('historial') && (
            <TabsContent value="historial" className="mt-0 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm sm:p-6">
              <HistorySection personId={personId} notes={profile.notas} activity={profile.historial} canWrite={profile.permissions?.notas?.write} canPastoral={profile.permissions?.notas?.pastoral} API={API} getAuthHeaders={getAuthHeaders} onChanged={refreshProfile} />
            </TabsContent>
          )}

          {canViewFinance && (
            <TabsContent value="finanzas" className="mt-0 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm sm:p-6">
              <PersonFinanceSection personId={personId} />
            </TabsContent>
          )}

          {canManageMembershipDocuments && (
            <TabsContent value="membresia" className="mt-0">
              <MembershipDocumentsSection personId={personId} photoSrc={photoSrc} />
            </TabsContent>
          )}

          {planned.map((section) => (
            <TabsContent key={section} value={section} className="mt-0 rounded-xl border border-[#E8E5DE] bg-white px-6 py-16 text-center shadow-sm">
              <p className="font-medium text-[#101D36]">{SECTION_LABELS[section] || displayLabel(section, 'Sección')}</p>
              <p className="mt-1 text-sm text-gray-500">Módulo aún no disponible.</p>
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </div>
  );
}
