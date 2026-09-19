import { canManageDirectMembership, canUseTerritorialMap, canViewGeo, hasCapability, isPastoralAuthority } from './accessControl';

describe('geo access control', () => {
  test('pastoral authority receives map access', () => {
    expect(isPastoralAuthority({ rol: 'pastor' })).toBe(true);
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
    expect(canManageDirectMembership({ rol: 'lider' })).toBe(false);
  });
});