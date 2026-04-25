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
// REGLA CRITICA: las notas son UNIVERSALES.
//   - NO usar fechas (enero, este ano, hace 6 meses, etc.)
//   - NO asumir historias propias (cuando llegamos, antes eramos, etc.)
//   - NO mencionar nombres especificos (Damaris, Pastor X)
//   - SI usar principios biblicos, preguntas confrontativas, aplicaciones
//     concretas pero genericas. La pastora aterriza el ejemplo cuando
//     predica.
// ============================================================================

// Notas pastorales por puerta (slides 12-20)
const NOTAS_PUERTAS = {
  1: {
    abrir: 'Sin oracion, ninguna puerta abre. Esta es la primera por una razon.',
    decir: [
      'Intercesion Profetica = cobertura ESPIRITUAL del sistema entero, no solo un grupo de oracion.',
      'Tres frentes diarios: pastor + lideres, visitantes + nuevos creyentes, celulas enteras.',
      'Vigilias, cadenas, ayunos, oracion antes del culto. Sin esto, todo lo demas es show religioso.',
    ],
    ilustrar: 'Nehemias reconstruyo la Puerta de la Fuente. Sin agua, no hay vida. Sin oracion, no hay ministerio.',
    preguntar: 'Cuando se mide el ministerio en horas de oracion antes que en numero de actividades, las cosas cambian. Donde estamos parados?',
    aplicar: 'Activa una cadena de oracion concreta esta semana — un horario, una lista, un proposito.',
    transicion: 'Y despues de la oracion, la primera persona que ve el visitante: la Bienvenida.',
  },
  2: {
    abrir: 'La primera impresion define la permanencia. Aqui se gana o se pierde al visitante.',
    decir: [
      'Bienvenida = FIESTA al Reino, no protocolo frio. Sonrisa real, transporte resuelto, regalo en mano.',
      'Proceso completo: MCD + NPT, vision, ministracion, membresia, LBS, bautismo, retiro, 3 meses de seguimiento.',
      'Si se salta un paso, se pierde al nuevo. La secuencia no es opcional.',
    ],
    ilustrar: 'Un visitante que recibe libro y mentor en su primer dia tiene mucha mas probabilidad de quedarse que uno que solo recibio "buenos dias".',
    preguntar: 'Que se lleva HOY un visitante de tu iglesia: solo un saludo, o un proceso?',
    aplicar: 'Prepara kits de bienvenida fisicos (libros + tarjeta) listos para entregar antes del proximo culto.',
    transicion: 'Cuando hay crisis personal, no se espera al lunes. Ahi entra la Puerta 3.',
  },
  3: {
    abrir: 'La crisis no espera. Si una iglesia tarda dias en responder a un dolor, ya es tarde.',
    decir: [
      'Cuidado Pastoral Inmediato = primera linea de respuesta espiritual urgente.',
      'Cuatro acciones: oracion personal, consejeria basica, canalizar a discipulado, acompanar.',
      'No reemplaza al pastor; ABRE camino al pastor cuando el no llega primero.',
    ],
    ilustrar: 'Puerta de las Ovejas en Nehemias 3:1. Las ovejas heridas necesitan refugio inmediato.',
    preguntar: 'Sabe el equipo a quien llamar ANTES que al pastor cuando hay una emergencia?',
    aplicar: 'Define un responsable de Puerta 3 de guardia para cada dia. Que sus telefonos esten visibles.',
    transicion: 'Para ir mas profundo, salimos del templo: los Retiros LBS.',
  },
  4: {
    abrir: 'Hay heridas que solo se curan en un retiro. La iglesia las identifica; aqui las sana.',
    decir: [
      'LBS = Liberacion, Bendicion, Sanidad. Tratamiento de 21 dias en 3 fases.',
      'No es "evento": es proceso ESTRUCTURADO con preparacion, ejecucion y seguimiento.',
      'Logistica + preparacion espiritual + seguimiento. Tres pilares irrenunciables.',
    ],
    ilustrar: 'Puerta del Valle de Nehemias. Es en el valle donde Dios hace lo mas profundo del corazon.',
    preguntar: 'Un retiro debe producir testimonios concretos de liberacion, no solo "buena experiencia". Eso esta pasando?',
    aplicar: 'Identifica nombres concretos para el proximo LBS. No promueves al aire — invitas persona por persona.',
    transicion: 'Quien viene del retiro necesita formacion. Ahi entra el Mentor de Discipulado.',
  },
  5: {
    abrir: 'Un nuevo creyente es como tierra recien arada. Si no se siembra rapido, se endurece.',
    decir: [
      'Mentores = formar creyentes maduros en los primeros 3 MESES. Tiempo critico.',
      'Discipulado uno a uno + formacion biblica + seguimiento espiritual cada semana.',
      'Sin mentor, el discipulo se queda en bebe. Con mentor, en 90 dias puede formar a otro.',
    ],
    ilustrar: 'Puerta Vieja: fundamento y sana doctrina. Lo viejo es lo eterno; lo nuevo se construye sobre eso.',
    preguntar: 'Hay mas mentores que discipulos, o mas discipulos sin mentor? Esa relacion define el futuro.',
    aplicar: 'Invita a personas maduras a entrar al equipo de mentores. Pon fecha de entrenamiento.',
    transicion: 'Y para los que no llegan al templo, vamos NOSOTROS a ellos. Visitacion Pastoral.',
  },
  6: {
    abrir: 'Si solo se cuida al que viene, se pierde al que se ausenta. Hay que SALIR a buscarlos.',
    decir: [
      'Visitacion = cuidado pastoral fuera del templo. Conquistar territorios para Cristo, casa por casa.',
      'Cinco frentes: enfermos, ausentes, amigos de la iglesia, hogares, miembros alejados.',
      'Operacion 72 aplicada: llamadas + visitas + restauracion + oracion por familias.',
    ],
    ilustrar: 'Puerta del Muladar — donde estaba la basura, hoy hay limpieza y santidad. Eso es lo que llevamos a cada hogar.',
    preguntar: 'Cuantos miembros se alejan sin que nadie los busque? Ahi se mide el corazon pastoral del equipo.',
    aplicar: 'Lista los ausentes activos esta semana. Llamadas antes del proximo culto. Ofrecer visita.',
    transicion: 'Para multiplicar el alcance, usamos las herramientas de hoy: Multimedia.',
  },
  7: {
    abrir: 'Si el mensaje no llega al telefono de la gente, no llega a su corazon.',
    decir: [
      'Multimedia = comunicacion + ensenanza digital. Transmisiones, redes, produccion audiovisual.',
      'Apoyo a celulas digitales y discipulado por Zoom. La iglesia opera 24/7, no solo el domingo.',
      'Teatro y video: el evangelio comunicado con todas las herramientas posibles.',
    ],
    ilustrar: 'Puerta de las Aguas — la Palabra. Hoy las aguas corren por internet. Donde haya senal, debe haber Palabra.',
    preguntar: 'La ensenanza dominical sale editada y publicada en 48 horas, o se pierde?',
    aplicar: 'Asigna un responsable concreto: editar y publicar el contenido de cada culto en menos de 48h.',
    transicion: 'Y para que todo funcione, alguien tiene que administrar los recursos. Puerta 8.',
  },
  8: {
    abrir: 'Sin recursos, la vision muere en buenas intenciones. Aqui se proveen.',
    decir: [
      'Administracion = recursos para el crecimiento espiritual.',
      'Biblias, materiales de discipulado, recursos de liderazgo, manuales en mano de cada quien.',
      'Finanzas + evangelismo trabajan juntos: lo que se administra bien, alcanza mas almas.',
    ],
    ilustrar: 'Puerta del Caballo — guerra espiritual. Ningun ejercito va a la guerra sin logistica.',
    preguntar: 'Cuantas Biblias y manuales hay disponibles HOY para entregar a un nuevo creyente?',
    aplicar: 'Hagan inventario esta semana. Cuenten exactamente que hay y que falta.',
    transicion: 'Y para impulsar el ministerio entero, llegamos a la ultima puerta: Congresos.',
  },
  9: {
    abrir: 'Cada ano necesita momentos de impulso. Aqui se planifican.',
    decir: [
      'Congresos y Eventos Especiales = generan IMPULSO espiritual a la iglesia entera.',
      'Congresos, seminarios, retiros de lanzamiento, capacitacion ministerial.',
      'Coordinacion: pastoral + multimedia + secretarias + cocina + ujieres + finanzas. Todos necesarios.',
    ],
    ilustrar: 'Puerta Oriental — expectativa del mover de Dios. Cada congreso debe abrir el cielo, no solo llenar agenda.',
    preguntar: 'El proximo evento grande tiene fecha, equipo, presupuesto y meta de almas? Si falta uno, falta todo.',
    aplicar: 'Define o confirma fecha del proximo evento grande. Conformen el equipo en una semana.',
    transicion: 'Cerramos las 9 puertas. Ahora subimos a la mirada general: la estructura.',
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
      abrir: 'No estamos aqui para repasar un programa. Estamos aqui para entender un SISTEMA que Dios mismo activa cuando hay orden.',
      decir: [
        'Esto no es teoria. Es una estrategia profetica con resultados medibles.',
        'Vamos a recorrer juntos el QUE, el COMO y el CUAL es tu rol.',
        'Cada uno debe salir hoy con una puerta clara y una semana clara para servir.',
      ],
      ilustrar: 'Una iglesia con buena gente y sin orden produce actividad sin fruto. Una iglesia con orden produce fruto que permanece.',
      preguntar: 'Estas dispuesta a salir de aqui con un compromiso concreto, o solamente con una emocion pasajera?',
      aplicar: 'Toma tu manual y tu pluma. Lo que escribas hoy se convierte en ejecucion esta misma semana.',
      transicion: 'Antes de comenzar, abramos el indice — vamos a ver el mapa completo del manual.',
      tiempoSugerido: '60-75 minutos · Texto base: Habacuc 2:2',
    },
  },

  // ----- 2. INDICE -----
  {
    id: 'indice',
    type: 'indice',
    title: 'Indice del Manual',
    subtitle: '29 paginas · 9 puertas · 7 semanas',
    notes: {
      abrir: 'Este es el mapa. Si saben donde van, no se pierden en el camino.',
      decir: [
        'Cuatro partes: Fundamentos, Las 9 Puertas, Liderazgo, Estrategia.',
        'No vamos a saltar nada. Cada parte se construye sobre la anterior.',
        'Si en cualquier momento se sienten perdidos, regresen aqui y se reubican.',
      ],
      ilustrar: 'Una iglesia sin indice es como un ministerio sin metas: todos hablan, nadie sabe donde va.',
      preguntar: 'Estas dispuesta a recorrer el camino completo, o te quedas en la primera parte como muchos?',
      aplicar: 'Despues de hoy, revisa con tu equipo que parte del manual ya manejan y cual hay que estudiar primero.',
      transicion: 'Ahora vamos a la invitacion. Antes del sistema, esta el llamado.',
    },
  },

  // ----- 3. UNA INVITACION -----
  {
    id: 'invitacion',
    type: 'invitacion',
    title: 'Una Invitacion',
    subtitle: 'Bienvenido a este Manual',
    notes: {
      abrir: 'Lo que tienes en las manos NO nacio de una idea humana. Nacio de una conviccion profetica.',
      decir: [
        'Hay vidas esperando ser alcanzadas, suenos esperando ser activados, puertas esperando ser abiertas.',
        'Esto no es informacion: es una estrategia espiritual.',
        'Hacer cosas buenas SIN orden produce cansancio. Hacer cosas buenas CON orden produce fruto.',
      ],
      ilustrar: '"Donde no hay vision, el pueblo perece. Donde hay orden, hay crecimiento; donde hay proposito, hay multiplicacion."',
      preguntar: 'Cuantas cosas buenas pueden estar haciendose que NO producen fruto medible?',
      aplicar: 'Subraya en este manual lo que mas impacta tu corazon. Eso sera tu primer paso.',
      transicion: 'Ahora la pregunta no es solo que hace este manual — sino para QUIEN esta escrito.',
    },
  },

  // ----- 4. PARA QUIEN + PROMESA -----
  {
    id: 'para-quien-promesa',
    type: 'para-quien-promesa',
    title: 'Para quien es este manual?',
    subtitle: 'Como leerlo · Nuestra Promesa',
    notes: {
      abrir: 'Si estas aqui, este manual es para TI. Pero hay una manera correcta de leerlo.',
      decir: [
        'Lealo con LAPIZ EN MANO, con oracion, con su equipo al lado.',
        'Subrayen lo que impacta. Marquen lo que van a implementar. Regresen a lo que les desafia.',
        'La promesa: si lo aplican con disciplina, VEN FRUTO. No por el manual; por los principios de Dios.',
      ],
      ilustrar: 'Pastor lee como pastor. Mentor lee como mentor. Servidor descubre su puerta. Nuevo creyente entiende su proceso.',
      preguntar: 'Lo van a leer una sola vez, o lo van a usar como herramienta de trabajo todo el ano?',
      aplicar: 'Define hoy en que rol vas a leerlo: pastor, lider, mentor, servidor o nuevo creyente.',
      transicion: 'Antes de los detalles, miren la fotografia completa del sistema en una sola pagina.',
    },
  },

  // ----- 5. INTRO MANUAL — Una Invitacion a ver la iglesia con nuevos ojos -----
  {
    id: 'intro-manual',
    type: 'intro-manual',
    title: 'Introduccion del Manual',
    subtitle: 'Una Invitacion a ver la iglesia con nuevos ojos',
    notes: {
      abrir: 'Hay una forma vieja de ver la iglesia. Y hay una forma NUEVA. Esta pagina les invita a abrir los ojos.',
      decir: [
        'Cinco pilares definen el sistema: el corazon (vision/mision/valores), la base biblica, el proceso claro, las herramientas practicas y la estrategia de ganar.',
        'No basta con tener corazon: hay que tener proceso. No basta con tener proceso: hay que tener herramientas.',
        'Cada pilar sostiene a los demas. Si quitas uno, el sistema se cae.',
      ],
      ilustrar: 'Hay vidas esperando ser ALCANZADAS, suenos esperando ser ACTIVADOS, puertas esperando ser ABIERTAS. La iglesia es la mano que abre.',
      preguntar: 'Cual de los cinco pilares esta mas debil hoy: el corazon, la base, el proceso, las herramientas o la estrategia?',
      aplicar: 'Identifica el pilar mas debil de tu area. Esta semana das un paso concreto para fortalecerlo.',
      transicion: 'Y empezamos por el primer pilar — el corazon del sistema. Nuestra Identidad.',
    },
  },

  // ----- 6. NUESTRA IDENTIDAD -----
  {
    id: 'identidad',
    type: 'identidad',
    title: 'Nuestra Identidad',
    subtitle: 'Vision · Mision · Valores',
    notes: {
      abrir: 'Antes de leer la pantalla, preguntense: quienes somos cuando NADIE nos ve? Eso es identidad real.',
      decir: [
        'No buscamos mas gente. Buscamos mas LIDERES. La diferencia es multiplicacion, no presencia.',
        'Mision: evangelizar, consolidar, discipular y enviar. En ese orden, sin saltarse pasos.',
        'Los valores no son decorativos. Cada puerta se EVALUA con ellos.',
      ],
      ilustrar: 'Si decimos que valoramos el orden y nuestra area es un caos, los valores son solo papel.',
      preguntar: 'Tu area refleja Orden? Refleja Amor por las almas? Si no, ahi esta el punto de partida.',
      aplicar: 'Cada lider evalua su area frente a los 7 valores y escribe 1 que necesita mejorar.',
      transicion: 'La razon profunda detras de todo este sistema esta escrita en Nehemias 3.',
    },
  },

  // ----- 7. LEMA · NEHEMIAS -----
  {
    id: 'lema-nehemias',
    type: 'lema-nehemias',
    title: 'Lema del Ano',
    subtitle: 'Ano de Cosecha y Restitucion',
    verse: 'Nehemias 3 - Las 9 Puertas',
    notes: {
      abrir: 'Ano de Cosecha y Restitucion. No es un slogan: es un mandato profetico.',
      decir: [
        'Nehemias reconstruyo PRIMERO las puertas. Sin puertas no hay proteccion, ni orden, ni crecimiento seguro.',
        'Asigno el trabajo POR ZONAS. Eso es consolidacion. Estrategia organizacional, no improvisacion.',
        'Dios devuelve lo perdido y recoge fruto abundante cuando hay puertas reconstruidas.',
      ],
      ilustrar: 'En tiempos de Nehemias el muro estaba roto. Hoy las "puertas rotas" son los procesos sin terminar. Toca reconstruirlos.',
      preguntar: 'Cuantas "puertas" en tu vida y tu area estan sin reconstruir? Hoy es el dia.',
      aplicar: 'Identifica 1 area de tu ministerio que esta "rota" y traza un plan de 30 dias para repararla.',
      transicion: 'Ahora bajamos al sistema concreto: la Ley de las 7 Semanas.',
    },
  },

  // ----- 8. LEY DE LAS 7 SEMANAS -----
  {
    id: 'ley-7-semanas',
    type: 'ley-7-semanas',
    title: 'La Ley de las 7 Semanas',
    subtitle: 'Un proceso de crecimiento y formacion',
    notes: {
      abrir: 'Siete semanas. Un calendario sagrado. No siete deseos.',
      decir: [
        'Cada semana tiene un OBJETIVO concreto. Si saltas una, comprometes todo el proceso.',
        'Disciplina en la ejecucion separa el fruto real de la actividad religiosa.',
        'Trabajamos en equipo con un mismo objetivo. La unidad acelera el sistema.',
      ],
      ilustrar: 'Una semana sin proposito = un mes perdido. En 7 semanas se hace lo que muchos hacen en 7 meses.',
      preguntar: 'En que semana del proceso suele caerse la gente, y que vamos a hacer distinto esta vez?',
      aplicar: 'Define HOY la semana en la que vas a comenzar tu primer ciclo completo. Calendario en mano.',
      transicion: 'Ahora el motor que conecta las puertas con el proceso: el Modelo CAP.',
    },
  },

  // ----- 9. MODELO CAP -----
  {
    id: 'modelo-cap',
    type: 'modelo-cap',
    title: 'Modelo CAP',
    subtitle: 'Consolidacion y Activacion por Puertas',
    verse: 'Habacuc 2:2 — "Escribe la vision y declarala..."',
    notes: {
      abrir: 'CAP no es una sigla: es la respuesta al problema de toda iglesia que crece y se queda sin estructura.',
      decir: [
        'EL DON = LA LLAVE. Tu don es lo que abre tu puerta en el Reino.',
        'La iglesia es un cuerpo. No todos hacen lo mismo, pero todos son necesarios.',
        'Tres niveles de crecimiento: Formacion · Seguimiento · Crecimiento. Sin uno, los otros se derrumban.',
      ],
      ilustrar: 'Sin CAP, la gente entra por una puerta y se cae por otra. Con CAP, cada persona tiene proceso, lider y destino.',
      preguntar: 'Cuantas personas pueden estar entrando sin un sistema solido de integracion?',
      aplicar: 'Identifica una persona que llego sin proceso. Asignale puerta, mentor y semana.',
      transicion: 'Y para activar todo eso, Dios nos da el principio del Tiempo 3 — la Operacion 72.',
    },
  },

  // ----- 10. OPERACION 72 -----
  {
    id: 'operacion-72',
    type: 'operacion-72',
    title: 'Operacion 72',
    subtitle: 'Equipo por Puertas · Tiempo 3',
    verse: 'Isaias 61:1-5',
    notes: {
      abrir: 'Tiempo 3. Tres dias. Es el principio profetico de operacion de Dios.',
      decir: [
        'Moises "en tres dias". Josue "en tres dias poseeremos". Jesus "en tres dias resucitare". El patron es claro.',
        'Aplicacion: en 3 dias se atiende al nuevo creyente. LBS en 3 semanas. Seguimiento de 3 meses.',
        'Mes 1: el llamado. Mes 2: el privilegio de servir. Mes 3: "Predestinado para ganar".',
      ],
      ilustrar: 'Cuando se espera 30 dias para llamar a un nuevo creyente, ya se perdio. En 72 horas se decide su destino.',
      preguntar: 'Que pasaria si todo visitante recibiera contacto en menos de 72 horas, sin excepcion?',
      aplicar: 'Cada lider revisa su lista de visitantes recientes y los contacta en las proximas 72 horas.',
      transicion: 'Ahora entramos a la columna vertebral del sistema: las 9 Puertas.',
    },
  },

  // ----- 11. LAS 9 PUERTAS (intro) -----
  {
    id: 'las-9-puertas',
    type: 'las-9-puertas',
    title: 'Las 9 Puertas',
    subtitle: 'El sistema completo de activacion',
    notes: {
      abrir: 'Cada necesidad tiene una puerta. Cada puerta tiene una respuesta.',
      decir: [
        'Enfermo → Puerta 6. Crisis → Puerta 3. Peticion urgente → Puerta 1. Nuevo creyente → Puerta 5.',
        'Visitante → Puerta 2. Evento → Puerta 9. Difusion → Puerta 7. Material → Puerta 8. Encuentro profundo → Puerta 4.',
        'Cada puerta tiene LIDER, ASISTENTE, EQUIPO y METAS ANUALES. Sin esos 4, la puerta NO existe.',
      ],
      ilustrar: 'Iglesia sin puertas = ambulancia sin departamentos. Todos atienden a todos, nadie atiende a nadie.',
      preguntar: 'Si llega un visitante nuevo HOY, alguien sabe exactamente a que puerta lo conecta?',
      aplicar: 'Memoriza las 9 puertas con sus colores. La proxima reunion el equipo se las pregunta.',
      transicion: 'Ahora puerta por puerta. La Puerta 1 es la base de todo: la cobertura espiritual.',
    },
  },

  // ----- 12-20. PUERTAS INDIVIDUALES (P1-P9) -----
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
    subtitle: 'Jerarquia · Celulas · Cultura',
    notes: {
      abrir: 'Sin estructura, todo trabajo se diluye. Esta es la columna vertebral del ministerio.',
      decir: [
        'Pastor → Coordinador → 9 Lideres de Puerta → Equipos → Iglesia. Cada nivel con autoridad y rendicion de cuentas.',
        'Las CELULAS detectan necesidades. Las PUERTAS responden con equipo y proceso. No al reves.',
        'Flujo: persona llega → Bienvenida → celula → discipulado + retiro → sirve → se forma → abre celula. Multiplicacion natural.',
      ],
      ilustrar: 'Una iglesia sin jerarquia clara es como un ejercito sin oficiales: todos pelean, nadie gana.',
      preguntar: 'Cada quien sabe a quien reporta y quienes le reportan? Si no, ahi hay una grieta.',
      aplicar: 'Dibuja TU linea de mando: arriba quien, abajo quienes. Compartelo con tu equipo.',
      transicion: 'En el corazon de la estructura esta la persona del Lider de Puerta. Vamos a verlo.',
    },
  },

  // ----- 22. EL LIDER DE PUERTA -----
  {
    id: 'lider-puerta',
    type: 'lider',
    title: 'El Lider de Puerta',
    subtitle: 'Cuidar · Ubicar · Activar · Desarrollar',
    notes: {
      abrir: 'Un lider NO es un jefe. Si tu equipo te tiene miedo, no eres lider; eres jefe.',
      decir: [
        'CUIDAR: conoce a tu gente. Sabe quien esta bien, quien esta triste, quien esta perdido.',
        'UBICAR: ayuda a cada uno a encontrar su lugar. No los uses para tus tareas, UBICALOS en su don.',
        'ACTIVAR y DESARROLLAR: forma OTROS lideres. El exito se mide en los lideres que levantas.',
      ],
      ilustrar: '"El verdadero liderazgo no se mide por cuantos te siguen, sino por cuantos LIDERES levantas."',
      preguntar: 'Si revisamos los ultimos meses, cuantos lideres nuevos se han formado realmente?',
      aplicar: 'Identifica UNA persona en tu equipo con potencial de lider. Empieza a formarla esta semana.',
      transicion: 'Para formar al nuevo creyente necesitamos al actor clave: el Mentor.',
    },
  },

  // ----- 23. MENTOR -----
  {
    id: 'mentor',
    type: 'mentor',
    title: 'Proposito del Mentor',
    subtitle: '2 Timoteo 2:2',
    notes: {
      abrir: 'El mentor NO es un maestro de teologia. Es un PUENTE entre el evangelio y la vida real.',
      decir: [
        'Existe para 4 cosas: afirmar la fe, cambiar el estilo de vida, integrar a la iglesia, preparar para servir.',
        'Perfil: vida de oracion + amor por las almas + conocimiento biblico basico + buen testimonio.',
        'Responsabilidades: contacto SEMANAL, reunion semanal, oracion por su discipulo, llevarlo a la celula y a su puerta.',
      ],
      ilustrar: 'Un nuevo creyente sin mentor es como un bebe sin madre: puede sobrevivir, pero no se desarrolla bien.',
      preguntar: 'A cuantas personas estas formando como mentor en este momento?',
      aplicar: 'Ofrecete a ser mentor de UN nuevo creyente y comprometete por 8 semanas con el.',
      transicion: 'Y todo mentor necesita un MAPA. Ese mapa es el Discipulado en 8 Semanas.',
    },
  },

  // ----- 24. DISCIPULADO 8 SEMANAS -----
  {
    id: 'discipulado-8-semanas',
    type: 'discipulado-8',
    title: 'Discipulado en 8 Semanas',
    subtitle: 'El mapa del nuevo creyente',
    notes: {
      abrir: 'Las primeras 8 semanas DECIDEN si el nuevo creyente se queda o se pierde. Aqui no hay plan B.',
      decir: [
        'Cada semana tiene un tema y un texto biblico ancla. Ningun tema al azar.',
        'S1-S4: salvacion, oracion, Biblia, iglesia. Las raices. Sin raices, todo se cae.',
        'S5-S8: santidad, proposito, don y liderazgo. La cosecha. Aqui formamos al proximo lider.',
      ],
      ilustrar: 'En 8 semanas un nuevo creyente puede pasar de "acabo de aceptar a Cristo" a "estoy formando a otra persona".',
      preguntar: 'Hay material fisico de las 8 semanas listo HOY para entregar a un nuevo creyente?',
      aplicar: 'Imprime y arma carpetas con el plan de 8 semanas. Listas para entregar.',
      transicion: 'Ahora la pregunta clave: cuando decimos que una persona esta REALMENTE consolidada?',
    },
  },

  // ----- 25. CONSOLIDADO DE PUERTA -----
  {
    id: 'consolidado-puerta',
    type: 'consolidado',
    title: 'Consolidado de Puerta',
    subtitle: 'No por emocion · Por evidencia',
    notes: {
      abrir: 'Llego la hora de medir. No nos vamos a enganar mas con apariencias.',
      decir: [
        'Cuatro indicadores tangibles: UBICACION, ACTIVACION, COBERTURA, PROCESO. Si falta uno, NO esta consolidado.',
        'Ubicado = tiene puerta. Activo = ya sirve. Cubierto = un lider lo conoce. En proceso = sigue formandose.',
        'No queremos asistentes; queremos consolidados. No queremos presencia; queremos firmeza.',
      ],
      ilustrar: 'Cien asistentes que no sirven valen menos que diez consolidados que multiplican. La aritmetica del Reino.',
      preguntar: 'De toda tu lista, a cuantos puedes marcar HOY con los 4 checks? Sean honestos.',
      aplicar: 'Hagan una tabla del equipo con los 4 indicadores. Marca SI o NO a cada uno.',
      transicion: 'Para mantener todo esto en movimiento, hace falta una herramienta clave: la Reunion de Supervisores.',
    },
  },

  // ----- 26. REUNION DE SUPERVISORES -----
  {
    id: 'reunion-supervisores',
    type: 'reunion',
    title: 'Reunion Mensual de Supervisores',
    subtitle: '30 minutos · Maximo enfoque',
    notes: {
      abrir: 'Esta reunion NO es para dar reportes. Es para asegurar que el SISTEMA esta avanzando.',
      decir: [
        'Agenda fija de 30 minutos: Inicio 5 · Evaluacion 5 c/u · Bloqueos 10 · Ajustes 5 · Activacion 5.',
        'NO se hace: alargar, desviarse, contar historias largas. SI se hace: ir al punto, escuchar, decidir.',
        'Tu rol NO es moderadora ni secretaria. Eres la que ENFOCA, CORRIGE y ACTIVA.',
      ],
      ilustrar: 'Frases clave: "Vamos al punto". "Cual es el siguiente paso?". "Eso lo resolvemos esta semana". Repitanlas hasta que se vuelvan cultura.',
      preguntar: 'Cuantas reuniones suelen terminar sin un siguiente paso CONCRETO? Esas no son reuniones, son desahogos.',
      aplicar: 'En la proxima reunion cronometrenla. Si pasa de 30 minutos, identifiquen QUIEN desvio y por que.',
      transicion: 'Y todo este sistema apunta a una sola cosa medible: ganar lideres servidores.',
    },
  },

  // ----- 27. ESTRATEGIA DE GANAR -----
  {
    id: 'estrategia-ganar',
    type: 'estrategia',
    title: 'Estrategia de Ganar',
    subtitle: '40 lideres · Plan anual',
    notes: {
      abrir: 'No hablamos de "mas asistencia". Hablamos de 40 LIDERES SERVIDORES. Esa es la meta.',
      decir: [
        'Cada 2 semanas: personas haciendo MCD, NPT, Bienvenida y Retiros LBS. Movimiento medible.',
        'Discipulados clave: "Mi llamado es sobrenatural" + el segundo y tercer discipulado. En ese orden.',
        'Quien se inscriba en consolidacion debe recibir un reconocimiento claro. Reconocimiento publico al servicio.',
      ],
      ilustrar: 'Plan de visita: confirma datos, entrega regalo, ofrece MCD, conecta con mentor. Cuatro pasos que producen un lider.',
      preguntar: 'De los 40 que queremos ganar, cuantos ya estan identificados con nombre y apellido?',
      aplicar: 'Escribe los primeros 5 nombres de tu lista personal de oracion para los 40 lideres.',
      transicion: 'Y ahora cerramos. Todo lo que hemos visto se reduce a una palabra: cultura.',
    },
  },

  // ----- 28. CULTURA Y LLAMADO FINAL -----
  {
    id: 'cultura-cierre',
    type: 'cierre',
    title: 'Cultura y Llamado Final',
    subtitle: 'Ano de Cosecha y Restitucion',
    notes: {
      abrir: 'Cinco palabras que definen nuestra cultura: Amor · Orden · Oracion · Servicio · Unidad.',
      decir: [
        'Las CELULAS detectan. Las PUERTAS responden. El LIDERAZGO supervisa. DIOS transforma. Esa es la cadena.',
        'Hay una puerta para servir, una funcion para cada don, una respuesta para cada necesidad.',
        'Este es el ano de cosecha. Las perdidas se convierten en multiplicacion.',
      ],
      ilustrar: '"Aqui cada miembro tiene un lugar, cada necesidad tiene una respuesta, y cada vida tiene un proceso." Esa frase es nuestra firma.',
      preguntar: 'Vas a salir de aqui como observadora, o como protagonista de esta cosecha?',
      aplicar: 'Antes de irte, escribe en tu manual: la PUERTA donde vas a servir, la PERSONA a quien vas a discipular, la SEMANA en que comienzas.',
      transicion: 'Cerramos declarando: "Soy parte de la cosecha. Mi puerta esta abierta. Aqui estoy."',
      versiculoFinal: '"Porque de la manera que en un cuerpo tenemos muchos miembros..." — Romanos 12:4',
    },
  },
];
