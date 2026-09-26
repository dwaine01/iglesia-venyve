const PASTORAL_ROLES = new Set(['pastor', 'pastora', 'admin', 'superadmin']);

export const isPastoralAuthority = (user) => {
  const role = String(user?.rol || user?.role || '').trim().toLowerCase();
  const accessLevel = String(user?.access_level || '').trim().toLowerCase();
  return PASTORAL_ROLES.has(role) || accessLevel === 'pastor';
};

export const hasCapability = (user, capability) => (
  isPastoralAuthority(user) || (user?.capabilities || []).includes(capability)
);

export const hasAnyCapability = (user, capabilities) => (
  isPastoralAuthority(user) || capabilities.some((capability) => hasCapability(user, capability))
);

export const hasPrivilegeGroup = (user, group) => (
  Array.isArray(user?.privilege_groups) && user.privilege_groups.includes(group)
);

export const canViewFinanceModule = (user) => (
  isPastoralAuthority(user)
  || (
    hasPrivilegeGroup(user, 'finance')
    && (user?.capabilities || []).includes('finance.read')
  )
);

export const canViewPrivatePersonFinance = (user) => isPastoralAuthority(user);

export const canViewFormation = (user) => hasCapability(user, 'formation.read');
export const canManageFormationPrograms = (user) => hasCapability(user, 'formation.programs.manage');
export const canManageFormationCohorts = (user) => hasCapability(user, 'formation.cohorts.manage');
export const canRegularizeMembership = (user) => hasCapability(user, 'membership.direct_import');
export const canAccreditHistoricalFormation = (user) => hasCapability(user, 'formation.historical_credit.manage');
export const canEnrollFormation = (user) => hasCapability(user, 'formation.enroll');
export const canWriteBaptism = (user) => hasCapability(user, 'baptism.write');

export const canViewFrontGroups = (user) => hasAnyCapability(user, [
  'front_groups.view',
  'front_groups.manage',
  'front_groups.work.assign',
  'front_groups.rotation.manage',
  'consolidation.assign',
  'mentor.qualifications.manage',
]);

export const canViewLeadership = (user) => hasAnyCapability(user, [
  'leadership.view',
  'leadership.promote',
  'leadership.requirements.manage',
]);

export const canViewGeo = (user) => Boolean(user);

export const canUseTerritorialMap = (user) => hasAnyCapability(user, [
  'geo.view_aggregate', 'geo.view_precise', 'geo.manage_locations',
]);

export const canManageDirectMembership = (user) => (
  isPastoralAuthority(user)
  || ['coordinador_general', 'general_coordinator'].includes(String(user?.access_level || user?.rol || user?.role || '').trim().toLowerCase())
  || (
    String(user?.rol || user?.role || '').trim().toLowerCase() === 'lider'
    && String(user?.access_level || '').trim().toLowerCase() === 'lider'
    && (user?.capabilities || []).includes('core.access.manage')
  )
  || (user?.capabilities || []).includes('membership.direct_import')
);

export const canManageMembershipDocuments = (user) => (
  isPastoralAuthority(user)
  || ['coordinador_general', 'general_coordinator'].includes(String(user?.access_level || user?.rol || user?.role || '').trim().toLowerCase())
  || (user?.capabilities || []).includes('membership.documents.manage')
);

export const canManageBaptismEvents = (user) => (
  isPastoralAuthority(user)
  || ['coordinador_general', 'general_coordinator'].includes(String(user?.access_level || user?.rol || user?.role || '').trim().toLowerCase())
  || (user?.capabilities || []).includes('baptism.events.manage')
);

export const canIssueBaptismCertificates = (user) => (
  isPastoralAuthority(user)
  || ['coordinador_general', 'general_coordinator'].includes(String(user?.access_level || user?.rol || user?.role || '').trim().toLowerCase())
  || (user?.capabilities || []).includes('baptism.certificates.issue')
);

export const canViewOperations = (user) => Boolean(user) && (isPastoralAuthority(user) || hasCapability(user, 'operations.view'));
export const canManageOperations = (user) => isPastoralAuthority(user) || hasCapability(user, 'operations.manage');
export const canCheckInOperations = (user) => canManageOperations(user) || hasCapability(user, 'operations.checkin');
export const canViewCare = (user) => Boolean(user) && (isPastoralAuthority(user) || hasAnyCapability(user, ['care.assigned.read', 'care.manage']));
export const canManageCare = (user) => isPastoralAuthority(user) || hasCapability(user, 'care.manage');
export const canReadCareVault = (user) => isPastoralAuthority(user) || hasCapability(user, 'care.confidential.read');