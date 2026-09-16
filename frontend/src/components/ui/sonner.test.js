import { getResponsiveToastPosition } from './sonner';

describe('posición responsive de notificaciones', () => {
  test('mantiene las notificaciones fuera de la cabecera móvil', () => {
    expect(getResponsiveToastPosition('top-right', true)).toBe('bottom-center');
  });

  test('conserva la posición configurada en escritorio', () => {
    expect(getResponsiveToastPosition('top-right', false)).toBe('top-right');
  });
});