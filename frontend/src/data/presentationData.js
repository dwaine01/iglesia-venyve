/**
 * Contenido completo de la presentación extraído de 13 documentos.
 *
 * IMPORTANTE — Lógica de las notas (revisada 2026-04-25):
 *  - Lo que ve la AUDIENCIA en pantalla = visual limpio, palabras clave.
 *  - Las NOTAS del pastor / Notas TV = guion para PREDICAR, NO repetición
 *    del slide. Cada nota tiene 6 secciones puntuales y directas:
 *      abrir       -> frase corta de apertura
 *      decir       -> 3-4 puntos directos para hablar (no copiar slide)
 *      ilustrar    -> anecdota / ejemplo / dato
 *      preguntar   -> 1 pregunta retorica al auditorio
 *      aplicar     -> accion concreta para esta semana
 *      transicion  -> puente al siguiente slide
 */

// URLs de las imágenes oficiales
export const LOGO_IGLESIA = 'https://customer-assets.emergentagent.com/job_cool-kare-8/artifacts/7lfcbcyw_logo%20casa%20e%20oracion%20ven%20y%20ve.png';
export const IMAGEN_INTRODUCCION = 'https://customer-assets.emergentagent.com/job_cool-kare-8/artifacts/i5szritp_12%20introducion%20del%20manual%20de%20la%20ley%20de%20la%207%20semanas.png';
export const IMAGEN_LEY_7_SEMANAS = 'https://customer-assets.emergentagent.com/job_cool-kare-8/artifacts/xfnntujy_13%20la%20ley%20de%20las%207%20semanas.png';

export const LAS_9_PUERTAS = [
  {
    num: 1,
    nombre: 'Intercesión Profética',
    resumen: 'Cobertura espiritual del sistema celular',
    color: 'from-purple-600 to-indigo-700',
    accent: '#7c3aed',
    icon: 'HandHeart',
    nehemias: 'Puerta de la Fuente (Neh 3:15)',
    proposito: 'Cubrir espiritualmente todo el sistema celular.',
    funciones: [
      'Orar por el pastor y los líderes',
      'Orar por visitantes y nuevos creyentes',
      'Orar por las células',
      'Guerra espiritual por barrios',
    ],
    actividades: ['Reuniones de oración', 'Vigilias', 'Cadenas de oración', 'Intercesión antes de los cultos', 'Ayunos'],
    estructura: ['Coordinador de intercesión', 'Intercesores asignados por células'],
    ministerios: ['Grupo pastoral', 'Intercesores', 'SUAD', 'Líderes', 'Alabanza', 'Danza'],
    indicadores: ['Ambiente espiritual fuerte', 'Crecimiento espiritual en las células', 'Testimonios de respuesta a la oración'],
  },
  {
    num: 2,
    nombre: 'Bienvenida / Consolidación',
    resumen: 'Fiesta de bienvenida al Reino',
    color: 'from-[#C8A951] to-[#E2CF8A]',
    accent: '#C8A951',
    icon: 'DoorOpen',
    nehemias: 'Puerta del Pescado (Neh 3:3)',
    proposito: 'Integrar y afirmar a los nuevos creyentes en la iglesia.',
    proceso: [
      'Se realiza después de la conversión mediante los libros MCD y NPT',
      'Se presenta la visión de la iglesia',
      'Se ministra el Espíritu Santo',
      'Se formaliza la membresía',
      'Inicia LBS en grupo pequeño (casa)',
      'Es bautizado',
      'Participa en un retiro espiritual',
      'Recibe discipulado de consolidación (3 meses)',
    ],
    bienvenida: ['Transporte', 'Recepción en la puerta con amor', 'Entrega de tarjeta de información', 'Conexión con el equipo de bienvenida', 'Entrega de obsequios (libros MCD y NPT)'],
    ministerios: ['Ujieres', 'Transporte', 'Mentores de MCD y NPT', 'Mentores de 3 meses', 'Ejecutiva de retiros LBS', 'Multimedia'],
  },
  {
    num: 3,
    nombre: 'Cuidado Pastoral Inmediato',
    resumen: 'Atención, consejería y acompañamiento',
    color: 'from-rose-500 to-pink-600',
    accent: '#e11d48',
    icon: 'Heart',
    nehemias: 'Puerta de las Ovejas (Neh 3:1-2)',
    proposito: 'Atender personas que necesitan apoyo espiritual urgente.',
    responsabilidades: ['Oración personal', 'Consejería básica', 'Canalizar a discipulado', 'Acompañamiento espiritual'],
    actividades: ['Reuniones de cuidado pastoral', 'Seguimiento espiritual', 'Oración personalizada'],
    ministerios: ['Grupo pastoral', 'Ministerio de misiones'],
  },
  {
    num: 4,
    nombre: 'Retiros y Encuentros (LBS)',
    resumen: 'Liberación, bendición y sanidad',
    color: 'from-emerald-600 to-teal-700',
    accent: '#059669',
    icon: 'Mountain',
    nehemias: 'Puerta del Valle (Neh 3:13)',
    proposito: 'Facilitar encuentros profundos con Dios.',
    actividades: ['Retiros espirituales', 'Encuentros de restauración', 'Jornadas de oración', 'Talleres espirituales'],
    responsabilidades: ['Organización logística', 'Preparación espiritual', 'Seguimiento de participantes'],
    ministerios: ['Grupo pastoral', 'Ujieres', 'Maestros de niños', 'Cocina', 'Multimedia'],
    tiempo: 'LBS: tratamiento de 3 semanas (21 días) - liberación, bendición y sanidad.',
  },
  {
    num: 5,
    nombre: 'Mentores de Discipulado',
    resumen: 'Formar creyentes maduros',
    color: 'from-blue-600 to-cyan-700',
    accent: '#2563eb',
    icon: 'BookOpen',
    nehemias: 'Puerta Vieja (Neh 3:6) - Fundamento y sana doctrina',
    proposito: 'Formar creyentes maduros durante los primeros 3 meses.',
    responsabilidades: ['Discipulado uno a uno', 'Formación bíblica', 'Seguimiento espiritual'],
    actividades: ['Grupos de discipulado', 'Estudios bíblicos'],
    ministerios: ['Mentores MCD y NPT', 'Mentores de 3 meses', 'Mentores LBS', 'Líderes de células', 'Maestros de niños', 'Maestros de discipulado', 'Maestros de liderazgo'],
  },
  {
    num: 6,
    nombre: 'Visitación Pastoral',
    resumen: 'Cuidado fuera del templo',
    color: 'from-orange-500 to-amber-600',
    accent: '#f97316',
    icon: 'HouseIcon',
    nehemias: 'Puerta del Muladar (Neh 3:14) - Limpieza y santidad',
    proposito: 'Extender el cuidado pastoral fuera del templo y conquistar territorios para Cristo.',
    responsabilidades: ['Visitar enfermos', 'Visitar ausentes', 'Visitar amigos de la iglesia', 'Orar en los hogares', 'Restaurar miembros alejados'],
    actividades: ['Visitas pastorales', 'Oración en hogares', 'Acompañamiento familiar'],
    ministerios: ['Ministerio de bienvenida', 'Parejas mentoras', 'Ministerio pastoral'],
    operacion72: 'Llamadas, visitas a personas nuevas, enfermos, seguimiento a no comprometidos, restaurar ausentes, orar por familias.',
  },
  {
    num: 7,
    nombre: 'Multimedia y Comunicación',
    resumen: 'Tecnología, redes sociales, teatro',
    color: 'from-fuchsia-600 to-pink-700',
    accent: '#c026d3',
    icon: 'Megaphone',
    nehemias: 'Puerta de las Aguas (Neh 3:26) - La Palabra',
    proposito: 'Apoyar la comunicación y enseñanza del ministerio.',
    responsabilidades: ['Transmisión de cultos', 'Manejo de redes sociales', 'Producción audiovisual', 'Apoyo a células digitales', 'Discipulado en línea (Zoom)'],
    actividades: ['Grabación de enseñanzas', 'Publicación de contenido', 'Comunicación digital'],
    ministerios: ['Teatro', 'Fotografía y video'],
  },
  {
    num: 8,
    nombre: 'Administración y Recursos',
    resumen: 'Finanzas y material de discipulado',
    color: 'from-slate-600 to-gray-800',
    accent: '#475569',
    icon: 'Wallet',
    nehemias: 'Puerta del Caballo (Neh 3:28) - Guerra espiritual',
    proposito: 'Proveer materiales para el crecimiento espiritual.',
    responsabilidades: ['Venta de Biblias', 'Materiales de discipulado', 'Recursos de liderazgo', 'Manuales ministeriales'],
    ministerios: ['Finanzas', 'Evangelismo'],
  },
  {
    num: 9,
    nombre: 'Congresos y Eventos Especiales',
    resumen: 'Impulso espiritual, entrenamientos',
    color: 'from-red-600 to-orange-700',
    accent: '#dc2626',
    icon: 'Calendar',
    nehemias: 'Puerta Oriental (Neh 3:29) - Expectativa del mover de Dios',
    proposito: 'Generar impulso espiritual en la iglesia.',
    responsabilidades: ['Organizar congresos', 'Planificar conferencias', 'Coordinar eventos anuales', 'Capacitación ministerial'],
    actividades: ['Congresos anuales', 'Seminarios de liderazgo', 'Eventos especiales', 'Retiros de lanzamiento', 'Mantenimiento', 'Pro-templo'],
    ministerios: ['Grupo pastoral', 'Multimedia', 'Mantenimiento', 'Secretarias', 'Finanzas', 'Mentores y maestros', 'Ujieres', 'Cocina'],
  },
];

export const LAS_7_SEMANAS = [
  { num: 1, titulo: 'Preparación - Oración Profética', sub: 'Organización', color: 'from-green-500 to-emerald-600' },
  { num: 2, titulo: 'Invasión', sub: 'Contactados', color: 'from-teal-600 to-cyan-700' },
  { num: 3, titulo: 'MCD', sub: 'Mi Carácter Deseado · Asistencia', color: 'from-blue-500 to-indigo-600' },
  { num: 4, titulo: 'Nací Para Triunfar', sub: 'NPT', color: 'from-yellow-500 to-amber-600' },
  { num: 5, titulo: 'Liberación', sub: 'LBS 1', color: 'from-orange-500 to-red-500' },
  { num: 6, titulo: 'Bendición', sub: 'LBS 2', color: 'from-amber-700 to-orange-800' },
  { num: 7, titulo: 'Sanidad', sub: 'LBS 3', color: 'from-indigo-600 to-purple-700' },
];

// ============================================================================
// SLIDES — 28 slides alineados al manual impreso
// Cada nota es GUION PARA PREDICAR, no repeticion del slide.
// ============================================================================

// Notas pastorales por puerta (slides 12-20)
const NOTAS_PUERTAS = {
  1: {
    abrir: 'Sin oración, ninguna puerta abre. Esta es la primera por una razón.',
    decir: [
      'Intercesión Profética = cobertura ESPIRITUAL del sistema entero, no solo un grupo de oración.',
      'Tres frentes diarios: pastor + líderes, visitantes + nuevos, células enteras.',
      'Vigilias, cadenas, ayunos, oración antes del culto. Sin esto, todo lo demás es show.',
    ],
    ilustrar: 'Nehemías reconstruyó la Puerta de la Fuente. Sin agua, no hay vida. Sin oración, no hay ministerio.',
    preguntar: '¿Cuántas horas semanales DEDICADAS a interceder por tu equipo? Si la respuesta es ninguna, ahí está tu fuga.',
    aplicar: 'Esta semana abre 1 cadena de oración de 7 días con 7 personas — una hora cada una.',
    transicion: 'Y después de la oración, la primera persona que ve el visitante: la Bienvenida.',
  },
  2: {
    abrir: 'La primera impresión define la permanencia. Aquí ganamos o perdemos al visitante.',
    decir: [
      'Bienvenida = FIESTA al Reino, no protocolo frío. Ujieres con sonrisa, transporte real, regalo en mano.',
      'Proceso: MCD + NPT → visión → ministración → membresía → LBS → bautismo → retiro → 3 meses.',
      'Si saltamos un paso, perdemos al nuevo. La secuencia no es opcional.',
    ],
    ilustrar: 'Una visitante que recibe un libro y un mentor en su primer día tiene 4x más probabilidades de quedarse que una que solo recibió "buenos días".',
    preguntar: '¿En tu última visita, qué llevó a casa el visitante: solo un saludo, o un proceso?',
    aplicar: 'Prepara esta semana 5 kits de bienvenida (MCD + NPT + tarjeta) listos para entregar el domingo.',
    transicion: 'Cuando hay crisis personal, no esperamos al lunes. Ahí entra la Puerta 3.',
  },
  3: {
    abrir: 'Crisis no espera. Si tu iglesia tarda 3 días en responder a un dolor, ya es tarde.',
    decir: [
      'Cuidado Pastoral Inmediato = primera línea de respuesta espiritual urgente.',
      'Cuatro acciones: oración personal, consejería básica, canalizar a discipulado, acompañar.',
      'No reemplaza al pastor; ABRE camino al pastor cuando él no llega primero.',
    ],
    ilustrar: 'Puerta de las Ovejas en Nehemías 3:1. Las ovejas heridas necesitan refugio inmediato.',
    preguntar: '¿Tu equipo sabe a quién llamar ANTES que al pastor cuando hay una emergencia?',
    aplicar: 'Esta semana define quién es el responsable de Puerta 3 de guardia cada día. Pásale los teléfonos.',
    transicion: 'Para ir más profundo, salimos del templo: los Retiros LBS.',
  },
  4: {
    abrir: 'Hay heridas que solo se curan en un retiro. La iglesia las identifica; aquí las sana.',
    decir: [
      'LBS = Liberación, Bendición, Sanidad. Tratamiento de 21 días en 3 fases.',
      'No es "evento": es proceso ESTRUCTURADO con preparación, ejecución y seguimiento.',
      'Logística (cocina, niños, multimedia) + preparación espiritual + seguimiento. Tres pilares.',
    ],
    ilustrar: 'Puerta del Valle de Nehemías. Es en el valle donde Dios hace lo más profundo del corazón.',
    preguntar: '¿Cuándo fue la última vez que tu retiro produjo testimonios concretos de liberación, no solo "buena experiencia"?',
    aplicar: 'Inscribe esta semana a 3 personas concretas para el próximo LBS. Llámalas tú misma.',
    transicion: 'El que viene del retiro necesita formación. Ahí entra el Mentor de Discipulado.',
  },
  5: {
    abrir: 'El nuevo creyente es como tierra recién arada. Si no se siembra rápido, se endurece.',
    decir: [
      'Mentores = formar creyentes maduros en los primeros 3 MESES. Tiempo crítico.',
      'Discipulado uno a uno + formación bíblica + seguimiento espiritual cada semana.',
      'Sin mentor, el discípulo se queda en bebé. Con mentor, en 90 días puede formar a otro.',
    ],
    ilustrar: 'Puerta Vieja: fundamento y sana doctrina. Lo viejo es lo eterno; lo nuevo se construye sobre eso.',
    preguntar: '¿Cuántos mentores activos tienes en tu equipo HOY? Si tienes más discípulos que mentores, hay déficit.',
    aplicar: 'Esta semana invita a 3 personas maduras a entrar al equipo de mentores. Pónles fecha de entrenamiento.',
    transicion: 'Y para los que no llegan al templo, vamos NOSOTROS a ellos. Visitación Pastoral.',
  },
  6: {
    abrir: 'Si solo cuidamos al que viene, perdemos al que se ausenta. Hay que SALIR a buscarlos.',
    decir: [
      'Visitación = cuidado pastoral fuera del templo. Conquistar territorios para Cristo, casa por casa.',
      'Cinco frentes: enfermos, ausentes, amigos de la iglesia, hogares, miembros alejados.',
      'Operación 72 aplicada: llamadas + visitas + restauración + oración por familias.',
    ],
    ilustrar: 'Puerta del Muladar — donde estaba la basura, hoy hay limpieza y santidad. Eso es lo que llevamos a cada hogar.',
    preguntar: '¿Cuántos miembros se han alejado y NADIE los ha llamado en los últimos 90 días?',
    aplicar: 'Lista 5 ausentes esta semana. Llámalos antes del domingo. Ofrece visita.',
    transicion: 'Para multiplicar el alcance, usamos las herramientas de hoy: Multimedia.',
  },
  7: {
    abrir: 'Si tu mensaje no llega al teléfono de la gente, no llega a su corazón.',
    decir: [
      'Multimedia = comunicación + enseñanza digital. Transmisiones, redes, producción audiovisual.',
      'Apoyo a células digitales y discipulado por Zoom. La iglesia opera 24/7, no solo el domingo.',
      'Teatro y video también: el evangelio comunicado con todas las herramientas posibles.',
    ],
    ilustrar: 'Puerta de las Aguas — la Palabra. Hoy las aguas corren por internet. Donde haya señal, debe haber Palabra.',
    preguntar: '¿Tu enseñanza dominical está editada y subida en menos de 48 horas? Si no, perdimos el 80% del alcance.',
    aplicar: 'Esta semana asigna a alguien específico a editar y publicar el contenido de cada culto en 48h.',
    transicion: 'Y para que todo funcione, alguien tiene que administrar los recursos. Puerta 8.',
  },
  8: {
    abrir: 'Sin recursos, la visión muere en buenas intenciones. Aquí los provemos.',
    decir: [
      'Administración = recursos para el crecimiento espiritual.',
      'Biblias, materiales de discipulado, recursos de liderazgo, manuales ministeriales en mano de cada quien.',
      'Finanzas + evangelismo trabajan juntos: lo que se administra bien, alcanza más almas.',
    ],
    ilustrar: 'Puerta del Caballo — guerra espiritual. Ningún ejército va a la guerra sin logística.',
    preguntar: '¿Cuántas Biblias y manuales tienes disponibles HOY para entregar a un nuevo creyente?',
    aplicar: 'Inventario esta semana. Cuenta exactamente qué tienes y qué falta. Repórtaselo a la coordinadora.',
    transicion: 'Y para impulsar el ministerio entero, llegamos a la última puerta: Congresos.',
  },
  9: {
    abrir: 'Cada año necesita momentos de impulso. Aquí los planificamos.',
    decir: [
      'Congresos y Eventos Especiales = generan IMPULSO espiritual a la iglesia entera.',
      'Congresos anuales, seminarios, retiros de lanzamiento, capacitación ministerial.',
      'Coordinación: pastoral + multimedia + secretarías + cocina + ujieres + finanzas. Todos necesarios.',
    ],
    ilustrar: 'Puerta Oriental — expectativa del mover de Dios. Cada congreso debe abrir el cielo, no solo llenar agenda.',
    preguntar: '¿Tu próximo congreso ya tiene fecha, equipo, presupuesto y meta de almas? Si falta uno, falta todo.',
    aplicar: 'Esta semana define o confirma la fecha del próximo evento grande. Conforma el equipo en 7 días.',
    transicion: 'Cerramos con las 9 puertas presentadas. Ahora subimos a la mirada general: la estructura.',
  },
};

export const SLIDES = [
  // ----- 1. PORTADA -----
  {
    id: 'portada',
    type: 'portada',
    title: 'La Ley de las 7 Semanas',
    subtitle: 'Sistema Celular y las 9 Puertas',
    description: 'Modelo integral de cuidado, consolidación, discipulado y multiplicación',
    notes: {
      abrir: 'No estamos aquí para repasar un programa. Estamos aquí para entender un SISTEMA que Dios mismo está activando entre nosotros.',
      decir: [
        'Esto no es teoría. Es una estrategia profética para 12 meses.',
        'Vamos a recorrer juntos el QUÉ, el CÓMO y el TU ROL.',
        'Cada uno saldrá hoy con una puerta clara y una semana clara para servir.',
      ],
      ilustrar: 'En enero éramos un grupo. Hoy somos un movimiento. La diferencia no fue el entusiasmo: fue el ORDEN.',
      preguntar: '¿Estás dispuesta a salir de esta sala con un compromiso concreto, no con una emoción pasajera?',
      aplicar: 'Toma tu manual y tu pluma. Lo que escribas hoy se convertirá en ejecución esta misma semana.',
      transicion: 'Antes de comenzar, abramos el índice — vamos a ver el mapa completo del manual.',
      tiempoSugerido: '60-75 minutos · Texto base: Habacuc 2:2',
    },
  },

  // ----- 2. ÍNDICE -----
  {
    id: 'indice',
    type: 'indice',
    title: 'Índice del Manual',
    subtitle: '29 páginas · 9 puertas · 7 semanas',
    notes: {
      abrir: 'Este es nuestro mapa. Lo que vamos a recorrer hoy.',
      decir: [
        'Cuatro partes: Fundamentos, Las 9 Puertas, Liderazgo y Estrategia.',
        'No vamos a saltar nada. Cada parte se construye sobre la anterior.',
        'Si te pierdes, regresas a esta página y te ubicas.',
      ],
      ilustrar: 'Una iglesia sin índice es como un ministerio sin metas: todos hablan, nadie sabe dónde va.',
      preguntar: '¿Estás dispuesta a recorrer el camino completo, o te quedas en la primera parte como otros años?',
      aplicar: 'Esta semana revisas con tu equipo qué parte del manual ya dominan y cuál necesitan estudiar primero.',
      transicion: 'Ahora vamos a la invitación. Antes del sistema, está el llamado.',
    },
  },

  // ----- 3. UNA INVITACIÓN -----
  {
    id: 'invitacion',
    type: 'invitacion',
    title: 'Una Invitación',
    subtitle: 'Bienvenido a este Manual',
    notes: {
      abrir: 'Lo que tienes en las manos NO nació de mí. Nació de una convicción profética.',
      decir: [
        'Hay vidas esperando ser alcanzadas, sueños esperando ser activados, puertas esperando ser abiertas.',
        'Esto no es información: es una estrategia espiritual.',
        'Durante años hicimos cosas buenas SIN orden. Hoy se acabó eso.',
      ],
      ilustrar: '"Donde no hay visión, el pueblo perece. Pero donde hay orden, hay crecimiento; donde hay propósito, hay multiplicación."',
      preguntar: '¿Cuántas cosas buenas estás haciendo que NO producen fruto medible?',
      aplicar: 'Hoy mismo subraya en tu manual lo que más impacta tu corazón. Eso será tu primer paso.',
      transicion: 'Ahora la pregunta no es solo qué hace este manual — sino para QUIÉN está escrito.',
    },
  },

  // ----- 4. ¿PARA QUIÉN? + PROMESA -----
  {
    id: 'para-quien-promesa',
    type: 'para-quien-promesa',
    title: '¿Para quién es este manual?',
    subtitle: 'Cómo leerlo · Nuestra Promesa',
    notes: {
      abrir: 'Si estás aquí, este manual es para TI. Pero hay una manera correcta de leerlo.',
      decir: [
        'No lo leas como un libro: léelo con LÁPIZ EN MANO, con oración, con tu equipo al lado.',
        'Subraya lo que impacta. Marca lo que vas a implementar. Regresa a lo que te desafía.',
        'La promesa: si lo aplicas con disciplina, VERÁS FRUTO. No por el manual; por los principios de Dios.',
      ],
      ilustrar: 'Pastor lee como pastor. Mentor lee como mentor. Servidor descubre su puerta. Nuevo creyente entiende su proceso.',
      preguntar: '¿Vas a leer este manual una sola vez o lo vas a usar como herramienta de trabajo todo el año?',
      aplicar: 'Esta semana define en qué rol vas a leerlo: ¿pastor, líder, mentor, servidor o nuevo creyente?',
      transicion: 'Antes de los detalles, mira la fotografía completa del sistema en una sola página.',
    },
  },

  // ----- 5. INTRO MANUAL (infografía) -----
  {
    id: 'intro-manual',
    type: 'intro-manual',
    title: 'Introducción del Manual',
    subtitle: 'Un Proceso de Crecimiento y Formación',
    notes: {
      abrir: 'Esta infografía resume todo el manual en una sola imagen. Apréndela.',
      decir: [
        'No es una actividad religiosa: es un proceso intencional y CONTINUO.',
        'La transformación es progresiva: PERSONA → DISCÍPULO → OBRERO → LÍDER → MINISTRO.',
        'Siete semanas con propósito específico cada una. Ningún tiempo perdido.',
      ],
      ilustrar: 'En 7 semanas pasamos de "te invito a la iglesia" a "estás formando otro líder". Eso es el sistema funcionando.',
      preguntar: '¿En qué etapa están la mayoría de las personas a tu cargo? ¿Persona, discípulo, obrero o líder?',
      aplicar: 'Haz una lista esta semana: cada persona en tu célula y su nivel actual. Ese es tu mapa real.',
      transicion: 'Ahora el corazón del sistema. Empezamos por nuestra identidad.',
    },
  },

  // ----- 6. NUESTRA IDENTIDAD -----
  {
    id: 'identidad',
    type: 'identidad',
    title: 'Nuestra Identidad',
    subtitle: 'Visión · Misión · Valores',
    notes: {
      abrir: 'Antes de leer la pantalla, pregúntense: ¿quiénes somos cuando NADIE nos ve? Eso es identidad real.',
      decir: [
        'No buscamos más gente. Buscamos más LÍDERES. La diferencia es multiplicación, no presencia.',
        'Misión: evangelizar, consolidar, discipular y enviar. En ese orden, sin saltarse pasos.',
        'Los valores no son decorativos. Cada puerta se EVALÚA con ellos.',
      ],
      ilustrar: 'Si decimos que valoramos el orden y nuestra área es un caos, los valores son solo papel.',
      preguntar: '¿Tu área refleja Orden? ¿Refleja Amor por las almas? Si no, ese es tu punto de partida.',
      aplicar: 'Esta semana cada líder evalúa su área frente a los 7 valores y escribe 1 que necesita mejorar.',
      transicion: 'La razón por la que ESTE año es diferente está escrita en Nehemías 3.',
    },
  },

  // ----- 7. LEMA · NEHEMÍAS -----
  {
    id: 'lema-nehemias',
    type: 'lema-nehemias',
    title: 'Lema del Año',
    subtitle: 'Año de Cosecha y Restitución',
    verse: 'Nehemías 3 - Las 9 Puertas',
    notes: {
      abrir: 'Año de Cosecha y Restitución. No es un slogan: es un mandato profético.',
      decir: [
        'Nehemías reconstruyó PRIMERO las puertas. ¿Por qué? Sin puertas: no hay protección, ni orden, ni crecimiento seguro.',
        'Asignó el trabajo POR ZONAS. Eso es consolidación. Estrategia organizacional, no improvisación.',
        'Dios está devolviéndonos lo perdido y recoge fruto abundante este año.',
      ],
      ilustrar: 'Cuando Nehemías llegó, el muro estaba roto. Hoy nuestro "muro" son los procesos sin terminar. Vamos a reconstruirlos.',
      preguntar: '¿Cuántas "puertas" en tu vida y tu área están sin reconstruir? Hoy es el día.',
      aplicar: 'Identifica esta semana 1 área de tu ministerio que está "rota" y traza un plan de 30 días para repararla.',
      transicion: 'Ahora bajamos al sistema concreto: la Ley de las 7 Semanas.',
    },
  },

  // ----- 8. LEY DE LAS 7 SEMANAS -----
  {
    id: 'ley-7-semanas',
    type: 'ley-7-semanas',
    title: 'La Ley de las 7 Semanas',
    subtitle: 'Un proceso de crecimiento y formación',
    notes: {
      abrir: 'Siete semanas. Un calendario sagrado. No siete deseos.',
      decir: [
        'Cada semana tiene un OBJETIVO concreto. Si saltas una, comprometes todo el proceso.',
        'Disciplina en la ejecución es lo que separa fruto real de actividad religiosa.',
        'Trabajamos en equipo con un mismo objetivo. La unidad acelera el sistema.',
      ],
      ilustrar: 'Una semana sin propósito = un mes perdido. En 7 semanas hacemos lo que otros hacen en 7 meses.',
      preguntar: '¿En qué semana del proceso fallaste el año pasado? Ahí mismo es donde Dios quiere que tengas victoria este año.',
      aplicar: 'Define HOY la semana en la que vas a comenzar tu primer ciclo completo. Ponle fecha al calendario.',
      transicion: 'Ahora el motor que conecta las puertas con el proceso: el Modelo CAP.',
    },
  },

  // ----- 9. MODELO CAP -----
  {
    id: 'modelo-cap',
    type: 'modelo-cap',
    title: 'Modelo CAP',
    subtitle: 'Consolidación y Activación por Puertas',
    verse: 'Habacuc 2:2 — "Escribe la visión y declárala..."',
    notes: {
      abrir: 'CAP no es una sigla: es la respuesta al problema de toda iglesia que crece y se queda sin estructura.',
      decir: [
        'EL DON = LA LLAVE. Tu don es lo que abre tu puerta en el Reino.',
        'La iglesia es un cuerpo. No todos hacen lo mismo, pero todos son necesarios.',
        'Tres niveles de crecimiento: Formación · Seguimiento · Crecimiento. Sin uno, los otros se derrumban.',
      ],
      ilustrar: 'Sin CAP, la gente entra por una puerta y se cae por otra. Con CAP, cada persona tiene un proceso, un líder y un destino.',
      preguntar: '¿Cuántas personas se han ido este año por falta de un sistema sólido de integración?',
      aplicar: 'Identifica esta semana 1 persona que llegó sin proceso. Asígnale puerta, mentor y semana.',
      transicion: 'Y para activar todo eso, Dios nos da el principio del Tiempo 3 — la Operación 72.',
    },
  },

  // ----- 10. OPERACIÓN 72 -----
  {
    id: 'operacion-72',
    type: 'operacion-72',
    title: 'Operación 72',
    subtitle: 'Equipo por Puertas · Tiempo 3',
    verse: 'Isaías 61:1-5',
    notes: {
      abrir: 'Tiempo 3. Tres días. Es el principio profético de operación de Dios.',
      decir: [
        'Moisés "en tres días". Josué "en tres días poseeremos". Jesús "en tres días resucitaré". El patrón es claro.',
        'Aplicación 72: en 3 días atendemos al nuevo creyente. LBS en 3 semanas. Seguimiento de 3 meses.',
        'Mes 1: el llamado. Mes 2: el privilegio de servir. Mes 3: "Predestinado para ganar".',
      ],
      ilustrar: 'Si esperamos 30 días para llamar a un nuevo creyente, ya lo perdimos. En 72 horas decidimos su destino.',
      preguntar: '¿Cuántos visitantes nuevos perdiste este año por NO contactarlos en 72 horas?',
      aplicar: 'Cada líder revisa esta semana su lista de visitantes del mes y los contacta en las próximas 72 horas.',
      transicion: 'Ahora entramos a la columna vertebral del sistema: las 9 Puertas.',
    },
  },

  // ----- 11. LAS 9 PUERTAS (intro) -----
  {
    id: 'las-9-puertas',
    type: 'las-9-puertas',
    title: 'Las 9 Puertas',
    subtitle: 'El sistema completo de activación',
    notes: {
      abrir: 'Cada necesidad tiene una puerta. Cada puerta tiene una respuesta.',
      decir: [
        'Enfermo → Puerta 6. Crisis → Puerta 3. Petición urgente → Puerta 1. Nuevo creyente → Puerta 5.',
        'Visitante → Puerta 2. Evento → Puerta 9. Difusión → Puerta 7. Material → Puerta 8. Encuentro profundo → Puerta 4.',
        'Cada puerta tiene LÍDER, ASISTENTE, EQUIPO y METAS ANUALES. Sin esos 4, la puerta NO existe.',
      ],
      ilustrar: 'Iglesia sin puertas = ambulancia sin departamentos. Todos atienden a todos, nadie atiende a nadie.',
      preguntar: 'Si llega un visitante nuevo HOY a tu célula, ¿sabes exactamente a qué puerta lo conectas?',
      aplicar: 'Memoriza esta semana las 9 puertas con sus colores. La próxima reunión te las pregunto.',
      transicion: 'Ahora vamos puerta por puerta. La Puerta 1 es la base de todo: la cobertura espiritual.',
    },
  },

  // ----- 12-20. PUERTAS INDIVIDUALES (P1-P9) — generadas con notas pastorales por puerta -----
  ...LAS_9_PUERTAS.map((p, idx) => ({
    id: `puerta-${p.num}`,
    type: 'puerta-individual',
    puertaIdx: idx,
    title: `Puerta ${p.num}: ${p.nombre}`,
    subtitle: p.resumen || '',
    notes: NOTAS_PUERTAS[p.num],
  })),

  // ----- 21. ESTRUCTURA GENERAL -----
  {
    id: 'estructura-general',
    type: 'estructura',
    title: 'Estructura General del Sistema',
    subtitle: 'Jerarquía · Células · Cultura',
    notes: {
      abrir: 'Sin estructura, todo trabajo se diluye. Esta es la columna vertebral del ministerio.',
      decir: [
        'Pastor → Coordinador → 9 Líderes de Puerta → Equipos → Iglesia. Cada nivel tiene autoridad y rendición de cuentas.',
        'Las CÉLULAS detectan necesidades. Las PUERTAS responden con equipo y proceso. No al revés.',
        'Flujo: persona llega → Bienvenida → célula → discipulado + retiro → sirve → se forma → abre célula. Multiplicación natural.',
      ],
      ilustrar: 'Una iglesia sin jerarquía clara es como un ejército sin oficiales: todos pelean, nadie gana.',
      preguntar: '¿Sabes a quién reportas tú, y a quién te reportan a ti? Si no lo tienes claro, hay una grieta.',
      aplicar: 'Esta semana dibuja en una hoja TU línea de mando: arriba quién, abajo quiénes. Compártela con tu equipo.',
      transicion: 'En el corazón de la estructura está la persona del Líder de Puerta. Vamos a verlo.',
    },
  },

  // ----- 22. EL LÍDER DE PUERTA -----
  {
    id: 'lider-puerta',
    type: 'lider',
    title: 'El Líder de Puerta',
    subtitle: 'Cuidar · Ubicar · Activar · Desarrollar',
    notes: {
      abrir: 'Un líder NO es un jefe. Si tu equipo te tiene miedo, no eres líder; eres jefe.',
      decir: [
        'CUIDAR: conoce a tu gente. Sabe quién está bien, quién está triste, quién está perdido.',
        'UBICAR: ayuda a cada uno a encontrar su lugar. No los uses para tus tareas, ÚBICALOS en su don.',
        'ACTIVAR y DESARROLLAR: forma OTROS líderes. El éxito se mide en los líderes que levantas, no en los seguidores.',
      ],
      ilustrar: '"El verdadero liderazgo no se mide por cuántos te siguen, sino por cuántos LÍDERES levantas."',
      preguntar: '¿Cuántos líderes nuevos has formado en los últimos 12 meses? Si son cero, hay que cambiar algo.',
      aplicar: 'Identifica esta semana a UNA persona en tu equipo con potencial de líder. Empieza a formarla en 7 días.',
      transicion: 'Para formar al nuevo creyente necesitamos al actor clave: el Mentor.',
    },
  },

  // ----- 23. PROPÓSITO DEL MENTOR -----
  {
    id: 'mentor',
    type: 'mentor',
    title: 'Propósito del Mentor',
    subtitle: '2 Timoteo 2:2',
    notes: {
      abrir: 'El mentor NO es un maestro de teología. Es un PUENTE entre el evangelio y la vida real.',
      decir: [
        'Existe para 4 cosas: afirmar la fe, cambiar el estilo de vida, integrar a la iglesia, preparar para servir.',
        'Perfil: vida de oración + amor por las almas + conocimiento bíblico básico + buen testimonio. No se necesita perfección, se necesita CARÁCTER.',
        'Responsabilidades: contacto SEMANAL, reunión semanal, oración por su discípulo, llevarlo a la célula y a su puerta.',
      ],
      ilustrar: 'Un nuevo creyente sin mentor es como un bebé sin madre: puede sobrevivir, pero no se desarrolla bien.',
      preguntar: '¿A cuántas personas estás formando como mentora HOY mismo? Si son cero, ahí hay un mandato pendiente.',
      aplicar: 'Esta semana ofrécete a ser mentora de UN nuevo creyente y comprométete por 8 semanas con él.',
      transicion: 'Y todo mentor necesita un MAPA. Ese mapa es el Discipulado en 8 Semanas.',
    },
  },

  // ----- 24. DISCIPULADO EN 8 SEMANAS -----
  {
    id: 'discipulado-8-semanas',
    type: 'discipulado-8',
    title: 'Discipulado en 8 Semanas',
    subtitle: 'El mapa del nuevo creyente',
    notes: {
      abrir: 'Las primeras 8 semanas DECIDEN si el nuevo creyente se queda o se pierde. Aquí no hay plan B.',
      decir: [
        'Cada semana tiene un tema y un texto bíblico ancla. Ningún tema al azar.',
        'S1-S4: salvación, oración, Biblia, iglesia. Las raíces. Sin raíces, todo se cae.',
        'S5-S8: santidad, propósito, don y liderazgo. La cosecha. Aquí formamos al próximo líder.',
      ],
      ilustrar: 'En 8 semanas un nuevo creyente puede pasar de "acabo de aceptar a Cristo" a "estoy formando a otra persona".',
      preguntar: '¿Tienes ya el material físico de las 8 semanas listo para entregar HOY a un nuevo creyente?',
      aplicar: 'Esta semana imprime y arma 5 carpetas con el plan de 8 semanas. Ténlas listas para entregar.',
      transicion: 'Ahora la pregunta clave: ¿cuándo decimos que una persona está REALMENTE consolidada?',
    },
  },

  // ----- 25. CONSOLIDADO DE PUERTA -----
  {
    id: 'consolidado-puerta',
    type: 'consolidado',
    title: 'Consolidado de Puerta',
    subtitle: 'No por emoción · Por evidencia',
    notes: {
      abrir: 'Llegó la hora de medir. No nos vamos a engañar más con apariencias.',
      decir: [
        'Cuatro indicadores tangibles: UBICACIÓN, ACTIVACIÓN, COBERTURA, PROCESO. Si falta uno, NO está consolidado.',
        'Ubicado = tiene puerta. Activo = ya sirve. Cubierto = un líder lo conoce. En proceso = sigue formándose.',
        'No queremos asistentes; queremos consolidados. No queremos presencia; queremos firmeza.',
      ],
      ilustrar: 'Cien asistentes que no sirven valen menos que diez consolidados que multiplican. La aritmética del Reino.',
      preguntar: 'De toda tu lista, ¿a cuántos puedes marcar HOY con los 4 checks? Sé honesta.',
      aplicar: 'Esta semana hace una tabla de tu equipo con los 4 indicadores. Marca SÍ o NO a cada uno.',
      transicion: 'Para mantener todo esto en movimiento, hace falta una herramienta clave: la Reunión de Supervisores.',
    },
  },

  // ----- 26. REUNIÓN MENSUAL DE SUPERVISORES -----
  {
    id: 'reunion-supervisores',
    type: 'reunion',
    title: 'Reunión Mensual de Supervisores',
    subtitle: '30 minutos · Máximo enfoque',
    notes: {
      abrir: 'Esta reunión NO es para dar reportes. Es para asegurar que el SISTEMA está avanzando.',
      decir: [
        'Agenda fija de 30 minutos: Inicio 5 · Evaluación 5 c/u · Bloqueos 10 · Ajustes 5 · Activación 5.',
        'NO se hace: alargar, desviarse, contar historias largas. SÍ se hace: ir al punto, escuchar, decidir.',
        'Tu rol NO es moderadora ni secretaria. Eres la que ENFOCA, CORRIGE y ACTIVA.',
      ],
      ilustrar: 'Frases clave: "Vamos al punto". "¿Cuál es el siguiente paso?". "Eso lo resolvemos esta semana". Repítelas hasta que se vuelvan cultura.',
      preguntar: '¿Cuántas reuniones del año pasado terminaron sin un siguiente paso CONCRETO? Esas no fueron reuniones, fueron desahogos.',
      aplicar: 'En tu próxima reunión cronométrala. Si pasa de 30 minutos, identifica QUIÉN te desvió y por qué.',
      transicion: 'Y todo este sistema apunta a una sola cosa medible: ganar 40 líderes este año.',
    },
  },

  // ----- 27. ESTRATEGIA DE GANAR -----
  {
    id: 'estrategia-ganar',
    type: 'estrategia',
    title: 'Estrategia de Ganar',
    subtitle: '40 líderes · Plan anual',
    notes: {
      abrir: 'No hablamos de "más asistencia". Hablamos de 40 LÍDERES SERVIDORES. Esa es la meta.',
      decir: [
        'Cada 2 semanas: personas haciendo MCD, NPT, Bienvenida y Retiros LBS. Movimiento medible.',
        'Discipulados clave: "Mi llamado es sobrenatural" + 2do y 3er discipulado. En ese orden.',
        'Quien se inscriba en consolidación recibirá una reseña ESPECIAL en su carnet. Reconocimiento público al servicio.',
      ],
      ilustrar: 'Damaris hará la 2da visita. Ese día: confirma datos, entrega regalo, ofrece MCD, conecta con mentor. Cuatro pasos que producen un líder.',
      preguntar: '¿Cuántos de tus 40 ya están identificados con nombre y apellido? Si no llegan a 10, hay trabajo urgente.',
      aplicar: 'Esta semana escribe los 5 primeros nombres de tu lista personal de oración para los 40 líderes.',
      transicion: 'Y ahora cerramos. Todo lo que hemos visto se reduce a una palabra: cultura.',
    },
  },

  // ----- 28. CULTURA Y LLAMADO FINAL -----
  {
    id: 'cultura-cierre',
    type: 'cierre',
    title: 'Cultura y Llamado Final',
    subtitle: 'Año de Cosecha y Restitución',
    notes: {
      abrir: 'Cinco palabras que definen nuestra cultura: Amor · Orden · Oración · Servicio · Unidad.',
      decir: [
        'Las CÉLULAS detectan. Las PUERTAS responden. El LIDERAZGO supervisa. DIOS transforma. Esa es la cadena.',
        'Hay una puerta para servir, una función para cada don, una respuesta para cada necesidad.',
        'Este es el año de cosecha. Las pérdidas se convierten en multiplicación.',
      ],
      ilustrar: '"Aquí cada miembro tiene un lugar, cada necesidad tiene una respuesta, y cada vida tiene un proceso." Esa frase es nuestra firma.',
      preguntar: '¿Vas a salir de esta sala como observadora, o como protagonista de esta cosecha?',
      aplicar: 'Antes de irte, escribe en tu manual: la PUERTA donde vas a servir, la PERSONA a quien vas a discipular, la SEMANA en que comienzas.',
      transicion: 'Vamos a cerrar declarando: "Soy parte de la cosecha. Mi puerta está abierta. Aquí estoy."',
      versiculoFinal: '"Porque de la manera que en un cuerpo tenemos muchos miembros, pero no todos los miembros tienen la misma función..." — Romanos 12:4',
    },
  },
];
