import { churchToday } from './churchDate';

test('8:38 PM del 26 de octubre en Nueva York sigue siendo el 26 (en UTC ya es el 27)', () => {
  expect(churchToday(new Date('2026-10-27T00:38:00Z'))).toBe('2026-10-26');
});

test('de día coincide con la fecha de UTC', () => {
  expect(churchToday(new Date('2026-10-26T15:00:00Z'))).toBe('2026-10-26');
});

test('respeta el cambio de horario (invierno, UTC-5)', () => {
  expect(churchToday(new Date('2026-12-01T04:30:00Z'))).toBe('2026-11-30');
});
