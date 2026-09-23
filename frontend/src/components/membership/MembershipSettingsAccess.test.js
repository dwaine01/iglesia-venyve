import { isPastoralAuthority } from '../../lib/accessControl';

test.each([
  [{ rol: 'pastor' }, true],
  [{ rol: 'pastora' }, true],
  [{ rol: 'lider', capabilities: ['membership.documents.manage'] }, false],
  [{ rol: 'persona', privilege_groups: ['board', 'finance'] }, false],
  [null, false],
])('la configuración institucional conserva autoridad pastoral estricta', (user, expected) => {
  expect(isPastoralAuthority(user)).toBe(expected);
});