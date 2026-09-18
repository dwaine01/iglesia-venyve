import { canViewGeo, hasCapability, isPastoralAuthority } from './accessControl';

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

  test('ordinary person cannot open geo maps', () => {
    expect(canViewGeo({ rol: 'persona', capabilities: [] })).toBe(false);
  });
});