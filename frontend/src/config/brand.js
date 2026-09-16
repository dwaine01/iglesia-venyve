export const BRAND = Object.freeze({
  name: 'VEN Y VE 360',
  subtitle: 'Sistema Integral de Gestión Ministerial',
  slogan: 'Una iglesia. Una visión. Un solo sistema.',
  church: 'Casa de Oración Ven y Ve',
  description: 'Personas, procesos, células, puertas, ministerios y liderazgo conectados en un mismo lugar.',
});

export const MODULE_BRANDS = Object.freeze({
  general: 'Visión General',
  core: 'Gobierno e Integridad',
  people: 'Personas',
  processes: 'Procesos',
  sevenWeeks: 'Ley de las 7 Semanas',
  cellular: 'Sistema Celular',
  doors: '9 Puertas',
  board: 'Junta Directiva',
  ministries: 'Ministerios',
  finance: 'Finanzas',
});

export const moduleBrand = (area) => `${BRAND.name} | ${area}`;

export const SPIRITUAL_QUOTES = Object.freeze([
  { category: 'PERSONAS', text: 'Cada persona importa en el Reino; ninguna vida queda fuera del cuidado pastoral.' },
  { category: 'CONSOLIDACIÓN', text: 'Consolidar es afirmar los pasos de quien llega para que eche raíces en la fe.' },
  { category: 'SERVICIO', text: 'Sirviendo con amor y excelencia reflejamos el corazón de Cristo en la comunidad.' },
  { category: 'CUIDADO MUTUO', text: 'Unidos en oración y mentoría, cuidamos el alma y fortalecemos la familia.' },
  { category: 'MULTIPLICACIÓN', text: 'Cada célula es una semilla de avivamiento destinada a multiplicarse con fruto.' },
  { category: 'LIDERAZGO', text: 'Formar líderes siervos es asegurar el legado del evangelio para las futuras generaciones.' },
  { category: 'UNIDAD', text: 'Una sola visión nos une, un solo Espíritu nos impulsa a la meta.' },
  { category: 'FRUTO', text: 'El verdadero fruto permanece cuando caminamos en obediencia y discipulado constante.' },
  { category: 'VISIÓN VEN Y VE 360', text: 'Una iglesia. Una visión. Un solo sistema para conectar, cuidar y multiplicar.' },
]);

export const DISCIPLESHIP_JOURNEY = Object.freeze(['Persona', 'Discípulo', 'Obrero', 'Ministro']);

export const CAP_JOURNEY = Object.freeze([
  'Identificar dones',
  'Recomendar Puerta',
  'Confirmar con líder',
  'Activar en servicio',
  'Dar seguimiento',
  'Desarrollar liderazgo',
]);