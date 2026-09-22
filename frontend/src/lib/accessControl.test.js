import { canCheckInOperations, canManageDirectMembership, canManageMembershipDocuments, canManageOperations, canUseTerritorialMap, canViewFinanceModule, canViewGeo, canViewOperations, canViewPrivatePersonFinance, hasCapability, isPastoralAuthority } from './accessControl';

describe('geo access control', () => {
  test('pastoral authority receives map access', () => {
    expect(isPastoralAuthority({ rol: 'pastor' })).toBe(true);
    expect(isPastoralAuthority({ rol: 'pastora' })).toBe(true);
    expect(canViewGeo({ rol: 'pastor', capabilities: [] })).toBe(true);
  });

  test('delegated aggregate access does not imply precise access', () => {
    const user = { rol: 'lider', capabilities: ['geo.view_aggregate'] };
    expect(canViewGeo(user)).toBe(true);
    expect(hasCapability(user, 'geo.view_precise')).toBe(false);
  });

  test('ordinary person can open the evangelism map without territorial data', () => {
    const user = { rol: 'persona', capabilities: [] };
    expect(canViewGeo(user)).toBe(true);
    expect(canUseTerritorialMap(user)).toBe(false);
  });

  test('direct membership is limited to pastor and general coordinator', () => {
    expect(canManageDirectMembership({ rol: 'pastor' })).toBe(true);
    expect(canManageDirectMembership({ rol: 'lider', access_level: 'coordinador_general' })).toBe(true);
    expect(canManageDirectMembership({ rol: 'general_coordinator' })).toBe(true);
    expect(canManageDirectMembership({ rol: 'lider', access_level: 'lider', capabilities: ['core.access.manage'] })).toBe(true);
    expect(canManageDirectMembership({ rol: 'lider', access_level: 'director', capabilities: ['core.access.manage'] })).toBe(false);
    expect(canManageDirectMembership({ rol: 'lider', access_level: 'lider', capabilities: ['membership.direct_import'] })).toBe(true);
    expect(canManageDirectMembership({ rol: 'lider' })).toBe(false);
  });

  test('direct import does not grant official membership documents', () => {
    expect(canManageMembershipDocuments({ rol: 'lider', capabilities: ['membership.direct_import'] })).toBe(false);
    expect(canManageMembershipDocuments({ rol: 'lider', capabilities: ['membership.documents.manage'] })).toBe(true);
    expect(canManageMembershipDocuments({ rol: 'lider', access_level: 'coordinador_general', capabilities: [] })).toBe(true);
  });

  test('operations separates viewing, check-in and management', () => {
    expect(canViewOperations({ rol: 'persona', capabilities: ['operations.view'] })).toBe(true);
    expect(canCheckInOperations({ rol: 'lider', capabilities: ['operations.view', 'operations.checkin'] })).toBe(true);
    expect(canManageOperations({ rol: 'lider', capabilities: ['operations.checkin'] })).toBe(false);
    expect(canManageOperations({ rol: 'pastor', capabilities: [] })).toBe(true);
  });

  test('finance module requires the restricted group and private finance stays pastoral', () => {
    expect(canViewFinanceModule({ rol: 'lider', capabilities: ['finance.read'], privilege_groups: [] })).toBe(false);
    expect(canViewFinanceModule({ rol: 'lider', capabilities: ['finance.read'], privilege_groups: ['finance'] })).toBe(true);
    expect(canViewPrivatePersonFinance({ rol: 'lider', capabilities: ['finance.read'], privilege_groups: ['finance'] })).toBe(false);
    expect(canViewPrivatePersonFinance({ rol: 'pastora', capabilities: [] })).toBe(true);
  });
});