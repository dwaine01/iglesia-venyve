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
  'mentor.qualifications.manage',
]);

export const canViewLeadership = (user) => hasAnyCapability(user, [
  'leadership.view',
  'leadership.promote',
  'leadership.requirements.manage',
]);

export const canViewGeo = (user) => hasAnyCapability(user, [
  'geo.view_aggregate',
  'geo.view_precise',
  'geo.manage_locations',
]);