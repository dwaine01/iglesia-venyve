/**
 * Contenido completo de la presentación extraído de 13 documentos:
 * 1. Visión, misión, valores
 * 2. Las 9 Puertas en Nehemías 3
 * 3. Visión Operación 72 – Equipo por Puertas
 * 4. Modelo de Activación por Puertas (CAP)
 * 5. Propósito de las 9 Puertas del Ministerio
 * 6. Estructuras de las 9 Puertas
 * 7. Estructura General del Modelo CAP
 * 8. Entrenamiento de Líderes por Puerta
 * 9. Reunión Mensual de Supervisores
 * 10. Propósito de un mentor
 * 11. Estrategia de Ganar
 * 12. Introducción del Manual de la Ley de las 7 Semanas
 * 13. La Ley de las 7 Semanas
 *
 * Cada slide tiene:
 *  - id, title, subtitle, theme
 *  - audience: lo que se muestra en la pantalla grande (visual, limpio)
 *  - notes: notas detalladas para el presentador (explicativos completos)
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

export const SLIDES = [
  // ============================================================
  // 1. PORTADA (manual pág 1)
  // ============================================================
  {
    id: 'portada',
    type: 'portada',
    title: 'La Ley de las 7 Semanas',
    subtitle: 'Sistema Celular y las 9 Puertas',
    description: 'Modelo integral de cuidado, consolidación, discipulado y multiplicación',
    notes: {
      introduccion: 'Esta presentación unifica los fundamentos bíblicos, el modelo CAP (Consolidación y Activación por Puertas), la Operación 72, y la Ley de las 7 Semanas.',
      objetivo: 'Al final de esta presentación cada líder debe entender: QUÉ es el sistema, CÓMO se implementa, y CUÁL es su rol dentro del mismo.',
      tiempoSugerido: '60-75 minutos totales',
      leer: '"Escribe la visión y declárala en tablas, para que corra el que leyere en ella." — Habacuc 2:2',
    },
  },

  // ============================================================
  // 2. ÍNDICE (manual pág 2 - movido aquí en encuadernación)
  // ============================================================
  {
    id: 'indice',
    type: 'indice',
    title: 'Índice del Manual',
    subtitle: '29 páginas · 9 puertas · 7 semanas',
    notes: {
      introduccion: 'Este índice es la guía maestra del manual. La primera página después de la portada permite a la pastora ubicarse rápido y a la audiencia ver el panorama completo.',
      partes: [
        'Parte I (Fundamentos): Introducción y secciones 01-06',
        'Parte II (Las 9 Puertas del Sistema): P1-P9 explicadas una por una',
        'Parte III (Liderazgo y Formación): secciones 16-19',
        'Parte IV (Estrategia y Ejecución): secciones 20-22 + Llamado Final',
      ],
      tiempoSugerido: '2-3 minutos',
      indicacion: 'Mostrar el índice da seguridad. La audiencia entiende que esto es serio, ordenado, y que cada tema se va a tratar a fondo.',
    },
  },

  // ============================================================
  // 3. UNA INVITACIÓN (manual pág 3)
  // ============================================================
  {
    id: 'invitacion',
    type: 'invitacion',
    title: 'Una Invitación',
    subtitle: 'Bienvenido a este Manual',
    notes: {
      mensaje: 'Hay vidas esperando ser alcanzadas, sueños esperando ser activados, y puertas esperando ser abiertas. Este manual no nació de una idea humana; nació de una convicción profética: que Dios quiere hacer algo nuevo, y lo hará a través de personas dispuestas a servir con excelencia.',
      noEsSoloInformacion: 'Lo que tienes en tus manos NO es solo información. Es un mapa. Es una estrategia espiritual diseñada para transformar tu manera de ver la iglesia, el ministerio y tu propio llamado.',
      cita: '"Donde no hay visión, el pueblo perece. Pero donde hay visión clara, hay dirección; donde hay orden, hay crecimiento; y donde hay propósito, hay multiplicación."',
      queEncontraran: [
        'El corazón del sistema (visión, misión, valores)',
        'Una base bíblica sólida (Nehemías 3 y Tiempo 3)',
        'Un proceso claro de transformación (7 semanas)',
        'Herramientas prácticas (mentores, líderes, supervisores)',
        'Una estrategia de ganar (metas medibles)',
      ],
      enfoque: 'Durante demasiado tiempo hemos hecho cosas buenas sin orden. Hoy es diferente. Hoy tenemos un SISTEMA, una RUTA, y un PROPÓSITO que se puede medir.',
    },
  },

  // ============================================================
  // 4. ¿PARA QUIÉN? + PROMESA (manual pág 4)
  // ============================================================
  {
    id: 'para-quien-promesa',
    type: 'para-quien-promesa',
    title: '¿Para quién es este manual?',
    subtitle: 'Cómo leerlo · Nuestra Promesa',
    notes: {
      paraQuien: 'Para el PASTOR que quiere levantar un equipo fuerte. Para el LÍDER que sueña con ver a su gente crecer. Para el MENTOR que desea formar vidas con propósito. Para el SERVIDOR que aún no sabe cuál es su puerta. Y para el NUEVO CREYENTE que está dando sus primeros pasos.',
      comoLeerlo: 'No lo leas como un libro más. Léelo CON LÁPIZ EN MANO, con oración, con tu equipo al lado. Subraya lo que impacta tu corazón. Marca lo que quieres implementar. Regresa a las secciones que te desafían. Está diseñado para ser USADO, no solo guardado.',
      promesa: 'Si aplicas con disciplina lo que aquí está escrito, VERÁS FRUTO. No porque este manual sea mágico, sino porque está alineado con los principios que Dios mismo estableció para edificar Su casa.',
      llamadoFinal: 'Hoy comienza algo nuevo. Gira la página.',
    },
  },

  // ============================================================
  // 5. INTRO-MANUAL (Infografía oficial - manual pág 5)
  // ============================================================
  {
    id: 'intro-manual',
    type: 'intro-manual',
    title: 'Introducción del Manual',
    subtitle: 'Un Proceso de Crecimiento y Formación',
    notes: {
      proposito: 'Esta es la infografía oficial que resume TODO el manual. Guía al lector por lo que va a encontrar.',
      puntosClave: [
        'No es una simple actividad religiosa: es un proceso estructurado, intencional y continuo',
        'La visión no es abstracta, es concreta; y lo concreto produce resultados',
        'Sistema progresivo: De Persona → Discípulo → Obrero → Líder o Ministro',
        'Organizado en 7 semanas con propósito específico en cada fase',
      ],
      fundamentos: [
        'La importancia de los procesos continuos',
        'La necesidad de eliminar vacíos espirituales',
        'El enfoque en la acción, no solo en la teoría',
        'La disciplina en la ejecución',
        'El trabajo en equipo con un mismo objetivo',
      ],
      cierre: 'Más que un programa, este sistema es una ESTRATEGIA DE TRANSFORMACIÓN. Si se sigue con disciplina, unidad y compromiso, produce IMPACTO REAL Y DURADERO.',
    },
  },

  // ============================================================
  // 6. NUESTRA IDENTIDAD (manual sección 01, pág 6)
  // ============================================================
  {
    id: 'identidad',
    type: 'identidad',
    title: 'Nuestra Identidad',
    subtitle: 'Visión · Misión · Valores',
    notes: {
      vision: 'Visión: Levantar discípulos que se conviertan en líderes, a través de un sistema intencional que transforma vidas y se multiplica.',
      mision: 'Misión: Evangelizar, consolidar, discipular y enviar personas, a través de un sistema de puertas ministeriales que garantiza su crecimiento espiritual y multiplicación.',
      declaracion: 'Formamos discípulos, levantamos líderes, multiplicamos el Reino.',
      valores: 'Presencia de Dios · Amor por las almas · Relaciones intencionales · Formación continua · Multiplicación · Orden · Excelencia',
      explicacion: 'Explicar que ESTOS valores no son decorativos. Cada puerta se evalúa con ellos. Preguntar: "¿Mi área refleja Orden? ¿Tengo Amor por las almas?"',
    },
  },

  // ============================================================
  // 7. LEMA · NEHEMÍAS (manual sección 02, pág 7)
  // ============================================================
  {
    id: 'lema-nehemias',
    type: 'lema-nehemias',
    title: 'Lema del Año',
    subtitle: 'Año de Cosecha y Restitución',
    verse: 'Nehemías 3 - Las 9 Puertas',
    notes: {
      lema: 'Año de cosecha y restitución. Dios está devolviendo lo perdido, y recoge fruto abundante.',
      contexto: 'Nehemías asignó el trabajo por zonas: eso es consolidación. No es solo construcción, es estrategia organizacional.',
      porqueReconstruirPuertas: 'Nehemías reconstruyó primero las puertas porque: (1) sin puertas no hay protección, (2) sin puertas no hay orden, (3) sin puertas no hay crecimiento seguro, (4) sin puertas no hay una ciudad estable.',
      aplicacion: 'Hoy la iglesia también necesita puertas reconstruidas para recibir, cuidar y multiplicar.',
    },
  },

  // ============================================================
  // 8. LEY DE LAS 7 SEMANAS (manual sección 03, pág 8)
  // ============================================================
  {
    id: 'ley-7-semanas',
    type: 'ley-7-semanas',
    title: 'La Ley de las 7 Semanas',
    subtitle: 'Un proceso de crecimiento y formación',
    notes: {
      queEs: 'Un proceso estructurado, intencional y continuo para producir resultados reales y medibles. La visión no es abstracta, es concreta; y lo concreto produce resultados.',
      principios: [
        'La importancia de los procesos continuos',
        'La necesidad de eliminar vacíos espirituales',
        'El enfoque en la acción, no solo en la teoría',
        'La disciplina en la ejecución',
        'El trabajo en equipo con un mismo objetivo',
      ],
      transformacion: 'Sistema progresivo: DE PERSONA A DISCÍPULO → DE DISCÍPULO A OBRERO → DE OBRERO A LÍDER O MINISTRO.',
      proposito: 'Facilitar la comprensión · Guiar la implementación · Alinear equipos · Garantizar resultados sostenibles.',
      cierre: 'Más que un programa, este sistema es una ESTRATEGIA DE TRANSFORMACIÓN. Si se sigue con disciplina, unidad y compromiso, produce IMPACTO REAL Y DURADERO.',
    },
  },

  // ============================================================
  // 9. MODELO CAP (manual sección 04, pág 10)
  // ============================================================
  {
    id: 'modelo-cap',
    type: 'modelo-cap',
    title: 'Modelo CAP',
    subtitle: 'Consolidación y Activación por Puertas',
    verse: 'Habacuc 2:2 — "Escribe la visión y declárala..."',
    notes: {
      fundamento: 'La visión debe ser clara, visible y aplicable. Un sistema bien definido permite orden, crecimiento y multiplicación.',
      principio: 'EL DON = LA LLAVE. Cuando conectamos a una persona correctamente, algo se abre. Tu don es la llave que abre tu puerta en el Reino.',
      elCuerpo: 'La iglesia funciona como un cuerpo: no todos hacen lo mismo, pero todos son necesarios. Cada miembro tiene una función específica.',
      niveles: 'El crecimiento se da en 3 niveles: Formación · Seguimiento · Crecimiento.',
      problemaQueResuelve: 'Evita que las personas se pierdan por falta de un sistema sólido de integración.',
    },
  },

  // ============================================================
  // 10. OPERACIÓN 72 (manual sección 05, pág 11)
  // ============================================================
  {
    id: 'operacion-72',
    type: 'operacion-72',
    title: 'Operación 72',
    subtitle: 'Equipo por Puertas · Tiempo 3',
    verse: 'Isaías 61:1-5',
    notes: {
      baseProfetica: 'El propósito por el cual el Padre envía al Hijo al mundo: predicar las buenas noticias, ministrar sanidad al corazón herido, proclamar libertad a cautivos, año de la buena voluntad de Jehová.',
      nuevosTiempos: 'Son NUEVOS TIEMPOS: Tiempo de consolidación completa · Tiempo de sanidad · Tiempo de prosperidad integral.',
      principioTiempo3: 'El PRINCIPIO DE OPERACIÓN es el TIEMPO 3: Moisés "en tres días"; Josué "en tres días poseeremos"; Jesús "en tres días resucitaré".',
      aplicacion72: [
        'En 3 días atenderemos con firmeza a los nuevos creyentes',
        'LBS: tratamiento de 3 semanas (21 días)',
        'Operación 72 se desarrolla en 3 días',
        'Luego, 3 meses de seguimiento con cada nuevo creyente',
      ],
      procesoFormacion: 'Mes 1: profundizar en el llamado. Mes 2: profundizar en el privilegio de servir. Mes 3: enseñar el devocional "Predestinado para ganar".',
      enfoqueMensaje: 'El mensaje debe ser sobre el Evangelio del Reino (Lucas 4:6-19). Enfocarnos en el que tiene sed.',
    },
  },

  // ============================================================
  // 11. LAS 9 PUERTAS (intro - manual sección 06, pág 12)
  // ============================================================
  {
    id: 'las-9-puertas',
    type: 'las-9-puertas',
    title: 'Las 9 Puertas',
    subtitle: 'El sistema completo de activación',
    notes: {
      introduccion: 'El sistema de puertas organiza el ministerio para que cada persona pueda: ser recibida, ser cuidada, ser discipulada, servir, convertirse en líder.',
      ejemplosPracticos: [
        'Enfermo → Puerta 6 (Visitación)',
        'Nuevo creyente → Puerta 5 (Discipulado)',
        'Petición urgente → Puerta 1 (Intercesión)',
        'Crisis → Puerta 3 (Atención pastoral)',
        'Evento → Puerta 9 (Congresos y eventos)',
        'Visitante primera vez → Puerta 2 (Bienvenida)',
        'Difusión digital → Puerta 7 (Multimedia)',
        'Material didáctico → Puerta 8 (Administración)',
        'Encuentro profundo → Puerta 4 (Retiros LBS)',
      ],
      cadaPuerta: 'Cada puerta tiene: un líder responsable, un asistente, un equipo de apoyo, y metas anuales.',
      indicacion: 'Después de esta vista panorámica vamos a entrar puerta por puerta — 9 slides individuales con propósito, funciones, responsabilidades y estructura de cada una.',
    },
  },

  // ============================================================
  // 12-20. PUERTAS INDIVIDUALES (P1-P9, manual págs 13-21)
  // ============================================================
  ...LAS_9_PUERTAS.map((p, idx) => ({
    id: `puerta-${p.num}`,
    type: 'puerta-individual',
    puertaIdx: idx,
    title: `Puerta ${p.num}: ${p.nombre}`,
    subtitle: p.resumen || '',
    notes: {
      proposito: p.proposito,
      ...(p.nehemias ? { nehemias: p.nehemias } : {}),
      ...(p.funciones ? { funciones: p.funciones } : {}),
      ...(p.responsabilidades ? { responsabilidades: p.responsabilidades } : {}),
      ...(p.actividades ? { actividades: p.actividades } : {}),
      ...(p.proceso ? { proceso: p.proceso } : {}),
      ...(p.bienvenida ? { procesoBienvenida: p.bienvenida } : {}),
      ...(p.estructura ? { estructura: p.estructura } : {}),
      ...(p.indicadores ? { indicadores: p.indicadores } : {}),
      ...(p.ministerios ? { ministeriosApoyo: p.ministerios.join(' · ') } : {}),
      ...(p.tiempo ? { tiempoSugerido: p.tiempo } : {}),
      ...(p.operacion72 ? { operacion72: p.operacion72 } : {}),
      compromiso: `"Cada puerta tiene su tiempo; cada tiempo tiene su puerta. Servir aquí es edificar el Reino." — Compromiso · Puerta ${p.num}`,
    },
  })),

  // ============================================================
  // 21. ESTRUCTURA GENERAL (manual sección 16, pág 22)
  // ============================================================
  {
    id: 'estructura-general',
    type: 'estructura',
    title: 'Estructura General del Sistema',
    subtitle: 'Jerarquía · Células · Cultura',
    notes: {
      jerarquia: [
        'Pastor Principal — Visión y dirección del ministerio',
        'Coordinador General del Ministerio Celular',
        'Junta Directiva (9 líderes) + Líderes de cada Puerta',
        'Equipos de servidores por puerta',
        'Iglesia / Miembros / Células',
      ],
      relacionCelulas: 'Las puertas NO funcionan separadas de las células. Las células DETECTAN necesidades → Las puertas RESPONDEN.',
      flujoCompleto: [
        'La persona llega',
        'Puerta 2: Bienvenida',
        'Se conecta a una célula',
        'Puerta 5 (Discipulado) + Puerta 4 (Retiro)',
        'Sirve en una puerta',
        'Se forma como líder',
        'Abre su célula',
      ],
      cultura: 'No somos una iglesia que solo hace reuniones; somos una iglesia que se organiza para cuidar vidas. Las células cuidan personas · Las puertas atienden necesidades.',
      declaracion: 'Aquí cada miembro tiene un lugar, cada necesidad tiene una respuesta, y cada vida tiene un proceso.',
    },
  },

  // ============================================================
  // 22. EL LÍDER DE PUERTA (manual sección 17, pág 23)
  // ============================================================
  {
    id: 'lider-puerta',
    type: 'lider',
    title: 'El Líder de Puerta',
    subtitle: 'Cuidar · Ubicar · Activar · Desarrollar',
    notes: {
      queEs: 'Un líder NO es un jefe. Un líder es: un FORMADOR (invierte en el crecimiento de otros), un CUIDADOR (se preocupa genuinamente por las personas), un ACTIVADOR (motiva y genera movimiento).',
      cuidar: 'CUIDAR: conocer a su gente, saber cómo están emocional, espiritual y personalmente; estar presente y disponible.',
      ubicar: 'UBICAR: ayudar a cada persona a encontrar su lugar, identificar dones/talentos/pasiones, conectar con oportunidades adecuadas.',
      activar: 'ACTIVAR: dar oportunidades para servir, impulsar a dar el siguiente paso, generar participación y compromiso.',
      desarrollar: 'DESARROLLAR: formar nuevos líderes, acompañar procesos de crecimiento, multiplicar el liderazgo.',
      enfoque: 'No solo queremos CONSOLIDAR personas, queremos consolidarlas EN UNA PUERTA.',
      ley: '"El verdadero liderazgo no se mide por cuántos te siguen, sino por cuántos líderes levantas."',
    },
  },

  // ============================================================
  // 23. PROPÓSITO DEL MENTOR (manual sección 18, pág 24)
  // ============================================================
  {
    id: 'mentor',
    type: 'mentor',
    title: 'Propósito del Mentor',
    subtitle: '2 Timoteo 2:2',
    notes: {
      existePara: 'Afirmar la fe del nuevo creyente · Ayudarlo a cambiar su estilo de vida · Integrarlo a la iglesia · Prepararlo para servir.',
      perfilEspiritual: 'Vida de oración constante · Amor genuino por las personas · Conocimiento bíblico básico · Llenura del Espíritu.',
      perfilCaracter: 'Paciencia con el proceso · Responsabilidad y puntualidad · Buen testimonio público · Humildad y servicio.',
      responsabilidades: [
        'Contacto semanal (llamada o mensaje personal)',
        'Reunión de discipulado (1 vez por semana, cara a cara)',
        'Cuidado espiritual (orar, escuchar sin juzgar, aconsejar)',
        'Integración (acompañar a la célula y a su puerta)',
      ],
      metas: 'Que la persona: se mantenga en la iglesia · entre a una célula · descubra su don · comience a servir.',
      errores: 'Abandonar el seguimiento · ser muy duro o muy pasivo · no escuchar · no orar.',
      exito: 'El discipulado fue exitoso cuando la persona: permanece en la iglesia · tiene hábitos espirituales · sirve en un ministerio · comienza a discipular a otros.',
      declaracion: '"Señor, me comprometo a formar vidas, a cuidar personas y a levantar discípulos para tu Reino."',
    },
  },

  // ============================================================
  // 24. DISCIPULADO EN 8 SEMANAS (manual sección 19, pág 25)
  // ============================================================
  {
    id: 'discipulado-8-semanas',
    type: 'discipulado-8',
    title: 'Discipulado en 8 Semanas',
    subtitle: 'El mapa del nuevo creyente',
    notes: {
      contexto: 'Las primeras 8 semanas son DECISIVAS. Determinan si el nuevo creyente se queda o se pierde. Este plan semanal te da estructura clara — ningún tema al azar, ninguna semana sin propósito.',
      semanas: [
        'S1: Salvación y seguridad en Cristo (2 Co 5:17 · Ser nueva criatura)',
        'S2: Oración y relación con Dios (Jer 33:3 · Aprender a hablar con Él)',
        'S3: La Biblia y crecimiento espiritual (alimento diario del alma)',
        'S4: La iglesia y congregarse (no piedras sueltas, somos familia)',
        'S5: Cambio de vida y santidad (el evangelio transforma lo práctico)',
        'S6: Visión y propósito (descubrir para qué fuimos creados)',
        'S7: Descubrir el don · servir en una puerta (activar lo de Dios)',
        'S8: Preparación para el liderazgo (de discípulo a formador)',
      ],
      enfoque: 'Cada semana tiene un objetivo concreto y un texto bíblico ancla. El mentor lleva al discípulo paso a paso, sin saltarse ninguna fase.',
    },
  },

  // ============================================================
  // 25. CONSOLIDADO DE PUERTA (manual sección 20, pág 26)
  // ============================================================
  {
    id: 'consolidado-puerta',
    type: 'consolidado',
    title: 'Consolidado de Puerta',
    subtitle: 'No por emoción · Por evidencia',
    notes: {
      definicion: 'Una persona consolidada de puerta: ya fue UBICADA en su ministerio · está siendo FORMADA · está ACTIVA dentro de su área.',
      indicadores: [
        'UBICACIÓN: Tiene una puerta definida',
        'ACTIVACIÓN: Ya está sirviendo',
        'COBERTURA: Tiene un líder que lo conoce y supervisa',
        'PROCESO: Está en formación (discipulado, enseñanza, crecimiento)',
      ],
      enfoque: 'No vamos a ASUMIR quién está consolidado. LO VAMOS A MEDIR. No queremos solo personas presentes, queremos personas FIRMES.',
    },
  },

  // ============================================================
  // 26. REUNIÓN MENSUAL DE SUPERVISORES (manual sección 21, pág 27)
  // ============================================================
  {
    id: 'reunion-supervisores',
    type: 'reunion',
    title: 'Reunión Mensual de Supervisores',
    subtitle: '30 minutos · Máximo enfoque',
    notes: {
      enfoque: '"Esta reunión no es para dar reportes... es para asegurar que el SISTEMA está avanzando."',
      agenda: [
        'Inicio (5 min): Oración · Ministración · Bienvenida',
        'Evaluación por supervisor (5 min c/u): ¿Cuántos líderes tienes? ¿Quién avanza? ¿Quién necesita ayuda?',
        'Detección de bloqueos (10 min): ¿Dónde se detiene la gente? ¿Qué puerta falla?',
        'Ajustes (5 min): ¿Qué se corrige? ¿Qué puerta reforzar? ¿A quién apoyar?',
        'Activación (5 min): orar y declarar claridad, multiplicación, movimiento.',
      ],
      nunca: 'Alargar · Desviarse · Contar historias largas.',
      siHacer: 'Ir al punto · Escuchar · Decidir.',
      rol: 'NO eres moderadora ni secretaria. ERES: la que enfoca · la que corrige · la que activa.',
      frases: ['"Vamos al punto"', '"¿Cuál es el siguiente paso?"', '"Eso lo resolvemos esta semana"'],
      ejemplosBloqueos: ['No llegan al encuentro', 'No terminan discipulado', 'No hay seguimiento'],
    },
  },

  // ============================================================
  // 27. ESTRATEGIA DE GANAR (manual sección 22, pág 28) — MOVIDA
  // ============================================================
  {
    id: 'estrategia-ganar',
    type: 'estrategia',
    title: 'Estrategia de Ganar',
    subtitle: '40 líderes · Plan anual',
    notes: {
      meta: '40 líderes servidores (primera etapa de consolidación).',
      en2semanas: ['Personas que hacen MCD y NPT', 'Personas en Bienvenida (2 veces al mes)', 'Personas en retiros LBS (cada 2 meses)'],
      discipulados: [
        'Primer discipulado: "Mi llamado es sobrenatural"',
        'Segundo y tercer discipulado',
      ],
      planAbril: 'Quien desee estar en el ministerio de consolidación tendrá una reseña especial en su carnet.',
      proceso: 'Toda la iglesia que se inscriba para trabajar en una puerta comenzará con MCD y NPT (aunque haya leído los libros).',
      visita: 'Damaris (coordinadora) visitará por segunda vez. Ese día: confirma datos · entrega regalo · ofrece MCD · conecta con mentor.',
      invasiones: 'La iglesia sirviendo está invitada a las 5 invasiones del año. Cada persona trabajará con su lista de oración.',
    },
  },

  // ============================================================
  // 28. CULTURA Y LLAMADO FINAL (manual pág 29)
  // ============================================================
  {
    id: 'cultura-cierre',
    type: 'cierre',
    title: 'Cultura y Llamado Final',
    subtitle: 'Año de Cosecha y Restitución',
    notes: {
      culturaPuertas: 'Cada puerta debe operar con: Amor · Orden · Oración · Servicio · Unidad.',
      claveEspiritual: 'Las células DETECTAN · Las puertas RESPONDEN · El liderazgo SUPERVISA · Dios TRANSFORMA vidas.',
      llamado: [
        'Hay una puerta para servir',
        'Hay una función para cada don',
        'Hay una necesidad en cada área',
        'Hay una generación que necesita ser cuidada',
      ],
      declaracionFinal: 'Este es el año de cosecha y restitución. Las pérdidas se convierten en multiplicación. Aquí cada miembro tiene un lugar, cada necesidad tiene una respuesta, y cada vida tiene un proceso.',
      versiculoFinal: '"Porque de la manera que en un cuerpo tenemos muchos miembros, pero no todos los miembros tienen la misma función..." — Romanos 12:4',
    },
  },
];
