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
  isPastoralAuthority(user) || String(user?.access_level || '').toLowerCase() === 'coordinador_general'
);

export const canViewOperations = (user) => Boolean(user) && (isPastoralAuthority(user) || hasCapability(user, 'operations.view'));
export const canManageOperations = (user) => isPastoralAuthority(user) || hasCapability(user, 'operations.manage');
export const canCheckInOperations = (user) => canManageOperations(user) || hasCapability(user, 'operations.checkin');
export const canViewCare = (user) => Boolean(user) && (isPastoralAuthority(user) || hasAnyCapability(user, ['care.assigned.read', 'care.manage']));
export const canManageCare = (user) => isPastoralAuthority(user) || hasCapability(user, 'care.manage');
export const canReadCareVault = (user) => isPastoralAuthority(user) || hasCapability(user, 'care.confidential.read');