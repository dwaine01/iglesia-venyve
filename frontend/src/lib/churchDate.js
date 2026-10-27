// La iglesia vive en hora de Nueva York: «hoy» es el día de Nueva York, no el de UTC (toISOString) ni el del
// navegador. Así un formulario abierto a las 8:38 PM del 26 de octubre propone 2026-10-26 y no 2026-10-27.
export const CHURCH_TIME_ZONE = 'America/New_York';

const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: CHURCH_TIME_ZONE, year: 'numeric', month: '2-digit', day: '2-digit' });

/** Día (YYYY-MM-DD) en hora de la iglesia para un instante (por defecto, ahora). */
export const churchToday = (date = new Date()) => {
  const parts = Object.fromEntries(formatter.formatToParts(date).map((part) => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
};
