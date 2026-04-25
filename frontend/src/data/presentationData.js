/**
 * Contenido completo de la presentación extraído del Manual oficial.
 *
 * IMPORTANTE — Lógica de las notas (revisada 2026-04-26 v4):
 *  - Lo que ve la AUDIENCIA en pantalla = visual limpio, palabras clave.
 *  - Las NOTAS del pastor / Notas TV = guion para PREDICAR con CORAZÓN.
 *
 *  CONTEXTO PASTORAL CRÍTICO:
 *    Esto NO es un sistema que ya existe. Es un NUEVO MOVER de Dios que
 *    la iglesia va a implementar AHORA por primera vez. Llevamos meses
 *    estudiando esta visión. Hoy se lanza. Se necesita la integración
 *    de toda la iglesia y el compromiso real con la visión de Dios.
 *
 *  REGLA DE ORO: NO DEJAR NADA A LA IMAGINACIÓN DE LA PASTORA.
 *      - Cada frase es una línea LISTA para decir en voz alta.
 *      - Cada ilustración trae conclusión incluida.
 *      - Cada aplicación tiene: NÚMERO + TIEMPO + ACCIÓN + DESTINATARIO.
 *
 *  Estructura de cada nota (6 secciones):
 *      abrir       -> apertura PASTORAL que toca el corazón
 *      decir       -> 3-4 declaraciones cerradas
 *      ilustrar    -> historia/imagen CON conclusión explícita
 *      preguntar   -> pregunta concreta y directa
 *      aplicar     -> acción con número, tiempo y verbo de mando
 *      transicion  -> frase puente cerrada al siguiente slide
 *
 *  REGLA UNIVERSAL:
 *      - SI usar acentos correctos (ñ, á, é, í, ó, ú).
 *      - NO mencionar nombres específicos de personas.
 *      - SI usar lenguaje de "vamos a empezar", "este es el día",
 *        "hoy comenzamos", "se lanza ahora".
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
// Notas pastorales: este es un NUEVO MOVER que se inicia HOY.
// ============================================================================

// Notas pastorales por puerta (slides 12-20)
const NOTAS_PUERTAS = {
  1: {
    abrir: 'Antes de hablar de estrategias… tenemos que hablar del altar. Porque esta puerta… no es un ministerio más… es la base de todo. Es el aire que va a respirar todo lo que estamos construyendo. Si esta puerta está débil… todo lo demás se cae.',
    decir: [
      'La Puerta 1 — Intercesión Profética — tiene una asignación clara: cubrir espiritualmente todo el sistema. Cubrir al pastor. Cubrir a los líderes. Cubrir a los visitantes. Cubrir cada célula. Porque sin cobertura… no hay crecimiento que permanezca.',
      'Tres acciones diarias… que no se negocian: orar por el pastor por nombre. Orar por los visitantes del domingo. Orar por cada célula y su líder. Eso no es opcional… eso es fundamento.',
      'Cuando un equipo ora constantemente… la atmósfera cambia. No en años… en semanas. Porque la oración… no es religiosa… es estratégica.',
    ],
    ilustrar: 'Nehemías comenzó por la Puerta de la Fuente. Porque entendía algo: sin agua… no hay ciudad. Y hoy te lo digo claro: sin oración… no hay iglesia. Puede haber música… puede haber predicación… puede haber actividad… pero no hay vida.',
    preguntar: 'Te hago una pregunta directa: ¿Cuándo fue la última vez que un grupo de esta iglesia se sentó a orar… sin prisa… sin agenda… solo a buscar a Dios? Si no lo recuerdas… ahí está el problema. Pero también… ahí comienza el cambio.',
    aplicar: 'Ahora vamos a hacerlo práctico: esta semana vamos a establecer un día fijo de intercesión. Lunes o jueves. De 7 a 8 PM. Mínimo 5 intercesores. Y con una lista clara: el nombre del pastor, los últimos visitantes, las células activas. Porque aquí no oramos al aire… oramos con dirección.',
    transicion: 'Recuerda esto: donde hay oración… Dios envía personas. Y cuando esas personas llegan… entran por una puerta específica. La siguiente puerta… es la Puerta 2: Bienvenida y Consolidación.',
  },
  2: {
    abrir: 'Vamos a tomar una decisión hoy… En esta casa… nadie entra… y sale igual. Nadie se va… sin que alguien lo haya mirado a los ojos. Eso no es emoción… es cultura.',
    decir: [
      'La Puerta 2 — Bienvenida y Consolidación — no es protocolo… es la primera imagen de Dios que una persona va a experimentar aquí. Porque para muchos… nosotros somos la primera iglesia que conocen. Y lo que vivan aquí… define si regresan… o desaparecen.',
      'Ahora escúchame esto con atención: el primer día… es clave. Ese mismo día… no en una semana… no en un mes… Ese mismo día el visitante debe recibir: un saludo real, una conexión, una tarjeta con sus datos, los materiales (MCD y NPT) y un mentor asignado. Ese mismo día. Porque lo que no se hace rápido… se pierde.',
      'Después de ese primer contacto… viene el proceso completo: se le presenta la visión, se ministra el Espíritu Santo, se integra, entra en LBS, se bautiza, participa en retiro, y recibe seguimiento por 3 meses. Esto no es opcional… esto es el camino completo. Si cortamos una parte… la persona se queda a mitad. Y una persona a mitad… es una persona en riesgo.',
    ],
    ilustrar: 'Te lo explico así: el padre del hijo pródigo… no esperó. No le dijo: "vuelve el domingo". Corrió. Lo abrazó. Lo restauró. El mismo día. Esa es la cultura que estamos estableciendo aquí.',
    preguntar: 'Ahora te hago una pregunta directa: si hoy entra alguien quebrantado por esa puerta… ¿sale con dirección… o solo con un "Dios te bendiga"? Porque eso define la iglesia que somos.',
    aplicar: 'Ahora vamos a hacerlo práctico: antes del próximo culto… el equipo de bienvenida va a preparar kits. Mínimo 10. Cada kit con: libro MCD, libro NPT, tarjeta de bienvenida, bolígrafo. Y dos ujieres entrenados para entregarlos. Aquí nadie se va sin ser atendido. Cero excepciones.',
    transicion: 'Recuerda esto: la bienvenida no es un momento… es el inicio de un proceso. Y cuando ese proceso comienza bien… la vida se transforma. Pero hay personas que no pueden esperar… personas que llegan en crisis… con urgencias… y para ellas… existe la siguiente puerta: la Puerta 3… Cuidado Pastoral Inmediato.',
  },
  3: {
    abrir: 'Hay dolores… que no avisan. No llegan en horario de culto… llegan un martes… a las 3 de la mañana. Y a partir de hoy… esta iglesia va a estar lista para responder en ese momento. No después. No cuando haya tiempo. En ese momento.',
    decir: [
      'La Puerta 3 — Cuidado Pastoral Inmediato — es la primera línea de respuesta cuando alguien entra en crisis. Muerte. Divorcio. Adicción. Pensamientos suicidas. Aquí no reaccionamos tarde… respondemos a tiempo.',
      'Y este equipo tiene cuatro acciones claras: oración personal — incluso por teléfono. Consejería básica — directa, 30 minutos. Canalizar al discipulado. Y acompañamiento por 7 días. Eso es proceso.',
      'Ahora entiende esto bien: este equipo no reemplaza al pastor. Lo que hace… es sostener el alma hasta que el pastor llegue. Para que cuando llegue… encuentre vida… no destrucción. Porque hay momentos… donde una llamada a tiempo… salva una vida.',
    ],
    ilustrar: 'Te lo explico así: una oveja herida… no necesita un programa. Necesita a alguien… que se baje hasta donde está… la cargue… y la traiga de vuelta. Eso es Puerta 3. Eso es amor en acción.',
    preguntar: 'Ahora te hago una pregunta fuerte: si esta noche alguien de tu equipo entra en crisis… ¿sabe a quién llamar? ¿Tiene un número claro? ¿O va a llamar al 911… porque la iglesia no está organizada? Eso define todo.',
    aplicar: 'Ahora vamos a hacerlo práctico: esta semana… vamos a crear una tarjeta de emergencia. Con tres números claros: el líder de Puerta 3 y dos asistentes. Vamos a imprimir mínimo 100. Y cada líder… cada servidor… cada miembro clave… va a tener esa tarjeta. Porque en una crisis… no hay tiempo para buscar contactos.',
    transicion: 'Recuerda esto: una iglesia madura… no solo predica… responde. Y responde rápido. Pero hay heridas… que no se sanan en una llamada. Heridas profundas… que necesitan tiempo con Dios. Y para eso… existe la siguiente puerta: la Puerta 4… Retiros y Encuentros (LBS).',
  },
  4: {
    abrir: 'Hay batallas… que no se ganan en un culto. Hay cadenas… que no se rompen en una prédica. Hay heridas… que no se sanan en una oración rápida. Se rompen… en un encuentro profundo con Dios.',
    decir: [
      'Por eso existe la Puerta 4: Retiros y Encuentros — LBS. Esto no es un evento… es un proceso.',
      'LBS significa: Liberación, Bendición, Sanidad. Tres etapas… 21 días… un antes y un después. Primero: Liberación — se rompen cadenas. Segundo: Bendición — se afirma identidad. Tercero: Sanidad — se restaura el alma.',
      'Y esto es clave: no se salta ninguna. Porque una persona sin liberación… no puede sostener bendición. Y una persona sin sanidad… no puede caminar en propósito. Esto es proceso completo.',
      'Cada retiro debe terminar con evidencia. Testimonios escritos. ¿Qué dejó atrás? ¿Qué recibió? ¿En qué cambió? Porque lo que no se documenta… se olvida. Y lo que se olvida… no se reproduce.',
    ],
    ilustrar: 'Te lo explico con la Biblia: David encontró profundidad en el valle. José fue formado en la prisión. Jesús se preparó en el desierto. Sin valle… no hay autoridad. Sin proceso… no hay transformación real. Por eso el retiro no es opcional… es necesario.',
    preguntar: 'Ahora te hago una pregunta directa: ¿Cuántas personas aquí están cargando cosas que solo se rompen en un retiro… pero nadie las ha invitado? No porque no quieran… sino porque no había sistema. Eso se terminó.',
    aplicar: 'Ahora vamos a hacerlo práctico: antes del próximo domingo… vas a escribir 5 nombres. Cinco personas que necesitan LBS. Y esta semana… las vas a llamar. Personalmente. Y con una frase clara: "Hay un retiro que cambia vidas… y sentí que tu nombre debía estar ahí." Eso es intención. Eso es liderazgo. Eso es Reino.',
    transicion: 'Recuerda esto: el retiro transforma… pero el sistema sostiene. Porque después que una persona cambia… no la podemos dejar sola. Hay que formarla. Y esa es la siguiente puerta: la Puerta 5… Mentores de Discipulado.',
  },
  5: {
    abrir: 'Un nuevo creyente… sin mentor… es como un bebé… en medio del frío. Puede sobrevivir… sí… pero la mayoría… no lo logra. Y nosotros no vamos a perder más almas… por falta de acompañamiento.',
    decir: [
      'La Puerta 5 — Mentores de Discipulado — tiene una misión clara: formar creyentes maduros. Y esto es clave: los primeros 3 meses… deciden todo. Si se queda… o si se va. Si crece… o si se enfría. Si se multiplica… o se estanca. Tres meses… definen 30 años.',
      'Ahora entiende esto: un mentor no es solo alguien que enseña Biblia. Es un puente. Entre el evangelio… y la vida real. El matrimonio. El trabajo. El dinero. Los hijos. Porque discipular… no es solo enseñar… es caminar con alguien.',
      'Y un mentor verdadero tiene tres hábitos claros: se reúne semanalmente. Envía un mensaje cada semana. Ora por su discípulo por nombre. Si no hace eso… no es mentor. Es solo contacto.',
    ],
    ilustrar: 'Te lo explico con la Biblia: Pablo le habló a Timoteo… pero no se quedó ahí. Le dijo: "Lo que recibiste… entrégalo a otros… que enseñen a otros." Cuatro generaciones… Pablo a Timoteo, a hombres fieles, a otros. Eso es multiplicación. Eso es Reino. Eso es sistema.',
    preguntar: 'Ahora te hago una pregunta directa: si Dios te pide cuentas hoy… ¿a quién estás formando? No con palabras… con tu vida. Si la respuesta es "a nadie"… ahí comienza tu asignación.',
    aplicar: 'Ahora vamos a hacerlo práctico: esta semana… vas a escoger UNA persona. Alguien que se haya convertido en los últimos 3 meses. Y mañana… la vas a llamar. Con una frase clara: "Quiero caminar contigo durante las próximas semanas. Una hora a la semana. Mismo día, misma hora." Y antes de colgar… esa primera reunión queda agendada. Eso es discipulado real.',
    transicion: 'Recuerda esto: la iglesia crece cuando evangeliza… pero se sostiene cuando discipula. Y aquí… vamos a hacer ambas cosas. Pero hay personas… que no están presentes… que se alejaron… y no los vamos a dejar perderse. Nosotros vamos a ir hacia ellos. Esa es la siguiente puerta: la Puerta 6… Visitación Pastoral.',
  },
  6: {
    abrir: 'Si solo cuidamos… al que viene el domingo… vamos a perder… al que dejó de venir el lunes. Y muchas veces… la gente no se va haciendo ruido… se va en silencio. Y eso no es casualidad… es falta de sistema.',
    decir: [
      'Por eso existe la Puerta 6: Visitación Pastoral. Esto es la iglesia… saliendo de sus cuatro paredes. Entrando a las casas. Entrando a las realidades. Entrando a donde está la necesidad. Porque el Reino… no se queda en el templo.',
      'Ahora escucha esto: cada semana hay cinco frentes claros: visitar un enfermo, visitar un ausente, visitar un amigo de la iglesia, orar en un hogar, y restaurar a alguien alejado. Eso no es opcional… eso es responsabilidad.',
      'Porque cada visita lleva un mensaje claro: "No estás solo. Tu vida importa. Por eso estoy aquí." Eso es Reino en acción.',
    ],
    ilustrar: 'Te lo explico con Nehemías: la Puerta del Muladar… era el lugar más sucio. Donde nadie quería estar. Pero ahí fue donde reconstruyeron. ¿Por qué? Porque donde hay ruina… ahí es donde Dios quiere restaurar. Y eso es lo que vamos a hacer… ir donde otros no quieren ir.',
    preguntar: 'Ahora te hago una pregunta directa: ¿Cuántas personas se han alejado… sin que nadie las llame? Sin que nadie toque su puerta… sin que nadie diga: "Te extrañamos." Porque esos nombres… Dios nos los va a pedir.',
    aplicar: 'Ahora vamos a hacerlo práctico: antes del próximo culto… vamos a hacer una lista. Siete personas. Ausentes del último mes. Y cada nombre… tiene un responsable. Y cada responsable… hace una llamada. No para juzgar… para conectar. Con una frase simple: "Te extrañamos… solo quería saber cómo estás." Eso cambia todo.',
    transicion: 'Recuerda esto: la gente no se pierde… cuando alguien va por ellos. Se pierde… cuando nadie los busca. Y aquí… nadie se queda atrás. Pero todo lo que Dios está haciendo aquí… no se puede quedar dentro de estas paredes. Tiene que salir… y llegar a más personas. Y para eso… existe la siguiente puerta: la Puerta 7… Multimedia y Comunicación.',
  },
  7: {
    abrir: 'Hoy una persona puede llorar sola a las 2 de la mañana, abrir su teléfono y buscar una palabra. A partir de este mes, esa palabra debe ser la nuestra y debe estar publicada.',
    decir: [
      'Multimedia no es un lujo de iglesia moderna. Es el puente entre el mensaje del altar y la generación que vive en la pantalla.',
      'Esta iglesia ya no cierra el domingo a las 12 del mediodía. Va a vivir 24 horas al día, 7 días a la semana, en cada video, prédica subida y testimonio publicado.',
      'Cada culto debe estar editado y publicado en menos de 48 horas. Cada prédica debe tener miniatura, título y descripción clara. Si no, se pierde el alcance.',
    ],
    ilustrar: 'Nehemías llamó a la suya Puerta de las Aguas, símbolo de la Palabra. Hoy las aguas corren por wifi. Si nuestra señal no está ahí, otros están ocupando ese púlpito digital y formando a nuestra gente con doctrina ajena.',
    preguntar: 'La prédica del domingo pasado... ¿cuántas personas pudo tocar el martes en la noche si hubiera estado publicada? ¿Y cuántas no la verán nunca porque nadie la subió?',
    aplicar: 'Esta semana asignamos por nombre UN responsable fijo de Multimedia. Su acuerdo escrito: cada culto editado y publicado en menos de 48 horas en YouTube + Instagram + Facebook. Sin excepciones. Sin atrasos.',
    transicion: 'Y nada de esto se sostiene sin recursos en mano. La Puerta 8 es la que provee esas herramientas.',
  },
  8: {
    abrir: 'La visión sin recursos termina en frustración y queja. Por eso Dios siempre proveyó logística antes de cada gran movimiento de su pueblo. Y ahora nos toca a nosotros administrar bien lo que Dios va a hacer.',
    decir: [
      'Administración y Recursos no es contar dinero en una oficina. Es abrir camino físico para que cada alma encuentre Biblia, manual y herramienta cuando llega.',
      'Tres inventarios deben estar siempre completos: Biblias para nuevos creyentes, manuales de discipulado para mentores y materiales de las 9 puertas para líderes.',
      'Lo que se administra con orden alcanza al doble de personas. Lo que se administra sin orden se gasta sin fruto y nadie sabe en qué.',
    ],
    ilustrar: 'Nehemías llamó a esta Puerta del Caballo. Los caballos son símbolo de guerra. Y ningún ejército en la historia ha ganado una guerra sin logística detrás. Tampoco la iglesia gana guerra espiritual sin Biblias en mano.',
    preguntar: 'Si mañana llegan 20 nuevos creyentes... ¿hay 20 Biblias listas para entregar? ¿hay 20 manuales? ¿hay 20 bolígrafos? ¿O les vamos a decir "vuelvan la otra semana" y los perdemos en el camino?',
    aplicar: 'Esta semana, Puerta 8 hace inventario físico: cuenta exactamente cuántas Biblias, cuántos manuales y cuántos bolígrafos hay. Lo que falte para llegar a 30 unidades, se compra antes del próximo culto. Reporta el número al pastor el sábado.',
    transicion: 'Y para encender corazones en masa, Dios siempre usó momentos clave. La Puerta 9 los planifica con disciplina.',
  },
  9: {
    abrir: 'Hay momentos que cambian a una iglesia para siempre: un congreso, un retiro de lanzamiento, una noche de gloria. Esos momentos no se improvisan tres semanas antes, y los próximos los vamos a planificar con disciplina espiritual.',
    decir: [
      'Congresos y Eventos Especiales son los puntos de inflexión donde Dios acelera de un solo golpe lo que el sistema construye semana a semana.',
      'Cada evento debe tener cuatro datos por escrito antes de promocionarse: fecha, equipo responsable, presupuesto en números y meta de almas alcanzadas.',
      'En un evento se cruzan todas las puertas: Pastoral predica, Multimedia transmite, Finanzas administra, Cocina alimenta, Ujieres reciben. Es la sinfonía completa.',
    ],
    ilustrar: 'Nehemías llamó a la suya Puerta Oriental, por donde entra el Rey de gloria. Cada congreso nuestro debe abrir cielos sobre la congregación, no solo llenar bancas y vender camisetas. La diferencia se mide en testimonios escritos después del evento.',
    preguntar: 'El próximo evento grande de esta iglesia... ¿va a ser un mover de Dios documentado con testimonios, o un evento más que la gente olvida en una semana porque no se ministró nada profundo?',
    aplicar: 'Esta semana, definimos en una hoja: 1) FECHA del próximo evento grande, 2) NOMBRE del coordinador, 3) PRESUPUESTO en dólares, 4) META de almas. Pegamos esa hoja en la oficina pastoral. Si no está escrito, no existe.',
    transicion: 'Cerramos las nueve puertas. Ahora levantamos la mirada al sistema completo: la estructura general.',
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
      abrir: 'Hay momentos en la vida de una iglesia que no se repiten… y este es uno de ellos. Esto no nació en una reunión, nació en oración, en ayuno, en búsqueda… y hoy no lo presentamos, hoy lo ACTIVAMOS. Lo que tienes delante no es un manual… es una puerta espiritual que Dios está abriendo para esta casa.',
      decir: [
        'Dios no nos llamó a venir los domingos a cumplir… nos llamó a edificar una generación. Y esa generación no se levanta con emoción… se levanta con orden, sistema y obediencia.',
        'Hoy se termina la iglesia espectadora. Hoy comienza la iglesia que trabaja. Hoy comienza la iglesia que entiende que el Reino no se sostiene con asistencia… sino con gente activada.',
        'Hoy vamos a ver tres cosas: el QUÉ, el CÓMO y tu rol. Porque nadie se va de aquí sin saber dónde pertenece y cuál es su próximo paso.',
      ],
      ilustrar: 'Hay gente que lleva años en la iglesia… pero nunca ha entrado en el fuego. Han estado en el ambiente, pero no en la presencia. Han oído la Palabra, pero nunca la activaron. Hoy no te estoy invitando a escuchar… te estoy invitando a encenderte. Acércate tanto al fuego de Dios… que cuando salgas de aquí, los que te conocen noten algo diferente en ti.',
      preguntar: 'Te hago una pregunta directa: ¿Esto será otra capacitación más… o será el día que partió tu vida en dos?',
      aplicar: 'Ahora mismo, escribe tu nombre completo en la primera página del manual y la fecha de hoy. Eso no es un requisito… es un pacto. Y el que firma, se compromete. Hoy no empiezas un curso… entras en un proceso que puede redefinir tu vida espiritual. Y si lo haces con disciplina… vas a ver fruto.',
      transicion: 'Antes de avanzar, vamos a ver el mapa completo. Porque nadie llega lejos sin saber hacia dónde va.',
      tiempoSugerido: '60-75 minutos · "Escribe la visión y declárala…" — Habacuc 2:2',
    },
  },

  // ----- 2. INDICE -----
  {
    id: 'indice',
    type: 'indice',
    title: 'Índice del Manual',
    subtitle: '29 páginas · 9 puertas · 7 semanas',
    notes: {
      abrir: 'Antes de hablar de fruto… hablemos de raíz. Antes de la raíz… miremos el mapa. Y antes del mapa… despertemos el hambre de recorrerlo completo.',
      decir: [
        'Este índice no es decoración… es dirección. Es la ruta que Dios trazó paso a paso para esta iglesia en este nuevo tiempo.',
        'Son 29 páginas, 9 puertas, 7 semanas… pero no es información… es transformación.',
        'Está dividido en 4 partes: Fundamentos, las 9 Puertas, Liderazgo y Estrategia. Nada se salta. Nada sobra. Todo tiene propósito.',
        'Lo que hoy parece nuevo… en pocas semanas será nuestro lenguaje natural. Vamos a hablar de "Puerta 3"… como hablamos de nuestra propia casa.',
      ],
      ilustrar: 'Una iglesia sin dirección escrita… cae en activismo. Mucho movimiento… mucho cansancio… poco fruto. Pero hoy rompemos ese ciclo. Porque lo que no se define… no se multiplica.',
      preguntar: 'Te hago una pregunta: ¿Cuántas veces empezamos algo… sin saber exactamente hacia dónde íbamos? Eso se termina hoy.',
      aplicar: 'Ahora haz algo práctico: pasa tu dedo por las 4 secciones del índice… y marca la que más llama tu atención. Porque muchas veces… lo que despierta tu curiosidad… revela dónde Dios quiere usarte. Esa sección la vas a leer esta semana.',
      transicion: 'Hoy no estamos viendo un índice… estamos viendo un mapa… y el que tiene mapa… llega. Pero antes del sistema… antes del proceso… antes de las puertas… está el llamado. Vamos ahora a la invitación.',
    },
  },

  // ----- 3. UNA INVITACION -----
  {
    id: 'invitacion',
    type: 'invitacion',
    title: 'Una Invitación',
    subtitle: 'Bienvenido a este Manual',
    notes: {
      abrir: 'Lo que tienes en las manos no nació de una idea humana… ni de una reunión administrativa. Nació en oración… en madrugadas… en búsqueda… y en una convicción clara de que Dios quiere hacer algo nuevo.',
      decir: [
        'Hay vidas concretas esperando ser alcanzadas con tu llamada. Hay sueños esperando ser activados con tu mentoría. Hay puertas esperando ser abiertas con tu obediencia.',
        'Esto no es información para guardar en una libreta… es estrategia espiritual para ejecutar esta misma semana.',
        'Porque hacer cosas buenas sin orden… cansa. Pero hacer cosas buenas con orden… multiplica. Produce fruto… y fruto que permanece.',
      ],
      ilustrar: 'La Biblia dice: "Donde no hay visión, el pueblo se desenfrena." Por eso hoy no estás en otra reunión más… estás recibiendo una visión por la que vale la pena vivir… y trabajar los próximos meses sin distracción.',
      preguntar: 'Te hago una pregunta directa: ¿Cuántas cosas buenas hemos estado haciendo… pero sin fruto real? ¿Y cuánto tiempo más vamos a seguir así… sin corregir el rumbo?',
      aplicar: 'Ahora haz algo práctico: saca un bolígrafo. Cada vez que una frase te confronte… subráyala. Porque lo que te confronta… revela lo que Dios quiere trabajar en ti. Y al final del día… lo que subrayaste no es información… es tu primer paso de obediencia.',
      transicion: 'Ahora la pregunta no es solo qué es este manual… la pregunta es: ¿para quién es? Y la respuesta… te incluye a ti.',
    },
  },

  // ----- 4. PARA QUIEN + PROMESA -----
  {
    id: 'para-quien-promesa',
    type: 'para-quien-promesa',
    title: '¿Para quién es este manual?',
    subtitle: 'Cómo leerlo · Nuestra Promesa',
    notes: {
      abrir: 'Si estás aquí hoy… este manual es para ti. No llegó a tus manos por casualidad… Dios te lo está entregando con propósito.',
      decir: [
        'Lo vas a leer de una manera diferente: con lápiz en la mano… con oración en el corazón… y con tu equipo cerca. Porque esa combinación… transforma vidas.',
        'Mientras lees, hay tres acciones obligatorias: subraya lo que te impacta, marca con asterisco lo que vas a implementar, y pon signo de pregunta a lo que te confronte. Esto no es lectura pasiva… esto es activación.',
        'La promesa es clara: si aplicamos con disciplina lo que está aquí… vamos a ver fruto. No por el manual… sino porque Dios honra los principios correctos.',
      ],
      ilustrar: 'El pastor lo lee como pastor… y reorganiza su visión. El líder lo lee como líder… y levanta gente. El mentor lo lee como mentor… y forma vidas. El servidor lo lee… y descubre su lugar. El nuevo creyente lo lee… y entiende su proceso. Aquí nadie queda fuera. Todos encuentran su nombre en estas páginas.',
      preguntar: 'Te hago una pregunta: ¿lo vas a leer como una vez más… o lo vas a usar como herramienta todos los días?',
      aplicar: 'Ahora haz una decisión práctica: define desde qué rol vas a leer este manual. Escríbelo en la primera página, junto a tu nombre: pastor, líder, mentor, servidor o nuevo creyente. Porque la forma en que lo leas… define lo que vas a recibir.',
      transicion: 'Antes de entrar en los detalles… vamos a ver el sistema completo en una sola imagen. Porque el que ve el panorama… entiende el proceso.',
    },
  },

  // ----- 5. INTRO MANUAL -----
  {
    id: 'intro-manual',
    type: 'intro-manual',
    title: 'Introducción del Manual',
    subtitle: 'Una Invitación a ver la iglesia con nuevos ojos',
    notes: {
      abrir: 'Hay dos formas de ver la iglesia… Una vieja… basada en actividades sueltas, eventos, mucho movimiento… pero poco fruto. Y una forma correcta… basada en procesos, personas y propósito. Hoy Dios nos está cambiando la manera de ver Su iglesia.',
      decir: [
        'Esto no es solo un ajuste… es un cambio de mentalidad. Porque no estamos llamados a hacer iglesia… estamos llamados a edificar el Reino.',
        'Este sistema se sostiene sobre cinco pilares claros: el corazón del sistema (visión, misión y valores), la base bíblica que nos da fundamento, el proceso claro que ordena el crecimiento, las herramientas prácticas que facilitan la ejecución, y la estrategia de ganar que mide resultados.',
        'No basta con tener corazón… hay que tener proceso. No basta con tener proceso… hay que tener herramientas. Y nada de eso funciona… si no hay estrategia que produzca fruto.',
        'Cada pilar sostiene al otro. Si uno falla… todo se debilita. Porque Dios no nos dio partes… nos dio un sistema completo.',
      ],
      ilustrar: 'Y ese sistema tiene un propósito claro: alcanzar, formar, activar y enviar personas. Hay vidas esperando ser alcanzadas… sueños esperando ser activados… y puertas esperando ser abiertas. Pero Dios no baja a abrirlas… usa a Su iglesia. Y la iglesia… somos nosotros.',
      preguntar: 'Te hago una pregunta directa: ¿Cuál de estos cinco pilares está más débil en tu vida… o en tu área? No lo pienses mucho… lo primero que vino a tu mente… ahí está el problema. Y también… ahí está tu asignación.',
      aplicar: 'Ahora hazlo práctico: esta semana vas a identificar ese pilar por escrito. Y antes del próximo encuentro… vas a dar UN paso concreto para fortalecerlo. Porque aquí no medimos intención… medimos evidencia.',
      transicion: 'Recuerda esto: no queremos una iglesia ocupada… queremos una iglesia efectiva. Ahora vamos a comenzar por el primer pilar… el corazón del sistema. Nuestra identidad como iglesia.',
    },
  },

  // ----- 6. NUESTRA IDENTIDAD -----
  {
    id: 'identidad',
    type: 'identidad',
    title: 'Nuestra Identidad',
    subtitle: 'Visión · Misión · Valores',
    notes: {
      abrir: 'Antes de leer lo que está en la pantalla… respóndete esto en silencio: ¿Quién eres tú… cuando nadie de la iglesia te está viendo? Porque esa respuesta… define tu verdadera identidad. No lo que dices… no lo que aparentas… sino lo que realmente eres.',
      decir: [
        'Nuestra VISIÓN es clara: levantar discípulos que se conviertan en líderes… a través de un sistema intencional que transforma vidas y se multiplica. Eso significa que aquí no venimos solo a congregarnos… venimos a formarnos… y a multiplicarnos.',
        'Nuestra MISIÓN tiene cuatro pasos… y no se pueden alterar: Evangelizar… Consolidar… Discipular… Y enviar. Si nos saltamos uno… podemos crecer en número… pero nos debilitamos por dentro. Y eso no es crecimiento… eso es apariencia.',
        'Nuestros VALORES son siete: Presencia de Dios, Amor por las almas, Relaciones intencionales, Formación continua, Multiplicación, Orden y Excelencia. Estos no son palabras bonitas… son el estándar de cómo vivimos. Son el filtro de cada decisión… de cada ministerio… de cada líder.',
      ],
      ilustrar: 'Si decimos "presencia de Dios"… pero no oramos… no es valor… es discurso. Si decimos "amor por las almas"… pero no buscamos a nadie… no es amor… es costumbre. Si decimos "orden"… pero vivimos en desorganización… no es identidad… es apariencia. Y Dios no trabaja con apariencia… Dios trabaja con verdad.',
      preguntar: 'Por eso te hago esta pregunta: ¿Cuál de estos valores está más débil en tu vida… o en tu área? No lo pienses mucho… el primero que vino a tu mente… ese es. Y ahí… es donde Dios quiere empezar contigo.',
      aplicar: 'Ahora hazlo práctico: esta semana vas a escribir los 7 valores en una hoja. Y al lado de cada uno vas a poner: SI o NO. Sin excusas. Sin maquillaje. Porque donde hay NO… hay trabajo pendiente. Y donde hay trabajo pendiente… hay oportunidad de crecimiento.',
      transicion: 'Recuerda esto: no estamos construyendo una iglesia con actividades… estamos formando una iglesia con identidad. Porque cuando la identidad es correcta… el sistema funciona. Ahora… vamos a ver de dónde nace todo esto. No nació en una reunión… no nació en una idea moderna… esto está en la Biblia. Vamos a Nehemías capítulo 3.',
    },
  },

  // ----- 7. LEMA · NEHEMIAS -----
  {
    id: 'lema-nehemias',
    type: 'lema-nehemias',
    title: 'Lema del Año',
    subtitle: 'Año de Cosecha y Restitución',
    verse: 'Nehemías 3 - Las 9 Puertas',
    notes: {
      abrir: 'Cosecha y Restitución… Esto no es un lema bonito… no es una frase para motivar… es una palabra profética. Y las palabras proféticas… no se celebran… se obedecen.',
      decir: [
        'Nehemías capítulo 3 nos revela algo poderoso: él no comenzó reconstruyendo casas… ni decorando el templo… comenzó por las puertas. Porque sin puertas… no hay protección. No hay orden. No hay crecimiento seguro. Y eso es exactamente lo que estamos haciendo aquí. Estamos reconstruyendo las puertas.',
        'Nehemías organizó el trabajo por zonas. Cada familia sabía qué le tocaba… qué debía proteger… y cuál era su responsabilidad. Eso no es solo historia… eso es modelo. Eso es sistema. Eso es lo que hoy llamamos las 9 puertas.',
        'Porque una iglesia sin estructura… se desgasta. Pero una iglesia con estructura… avanza.',
        'Dios promete cosecha… pero la cosecha viene después del orden. Dios promete restitución… pero la restitución viene cuando se cierran las brechas.',
      ],
      ilustrar: 'Y muchas de nuestras brechas hoy… no son demonios… son procesos incompletos. Llamadas que no se hicieron. Personas que no se siguieron. Discipulados que se quedaron a mitad. Eso también es puerta rota. Y una puerta rota… siempre deja entrar al enemigo.',
      preguntar: 'Por eso te hago una pregunta directa: ¿Cuántas áreas en tu vida… o en tu ministerio… están abiertas… rotas… sin terminar? Y lo más importante… ¿Cuánto tiempo más vamos a vivir así? Hoy no es un día para identificar problemas… es un día para tomar responsabilidad.',
      aplicar: 'Haz esto práctico: antes del próximo domingo… vas a identificar UNA puerta rota en tu área. Y vas a escribir un plan de 30 días: una meta clara. Una fecha de inicio. Una fecha de cierre. Y tres acciones concretas. Porque aquí no hablamos de intención… hablamos de ejecución.',
      transicion: 'Recuerda esto: las puertas no se reconstruyen con deseos… se reconstruyen con trabajo. Y cuando las puertas se levantan… la ciudad se levanta. Ahora vamos a ver el sistema que nos va a ayudar a hacer esto realidad… La Ley de las 7 Semanas.',
    },
  },

  // ----- 8. LEY DE LAS 7 SEMANAS -----
  {
    id: 'ley-7-semanas',
    type: 'ley-7-semanas',
    title: 'La Ley de las 7 Semanas',
    subtitle: 'Un proceso de crecimiento y formación',
    notes: {
      abrir: 'Siete semanas… No es un calendario… es un proceso. No son ideas… son decisiones. Y cuando estas siete decisiones se ejecutan con disciplina… parten un año en dos. Porque lo que no cambia en meses… puede transformarse en semanas cuando hay orden.',
      decir: [
        'Cada semana tiene un propósito claro: Semana 1 — Preparación y oración profética. Semana 2 — Invasión. Semana 3 — MCD. Semana 4 — NPT. Semana 5 — Liberación. Semana 6 — Bendición. Semana 7 — Sanidad.',
        'Y esto es clave: no se negocian. No se cambian. No se saltan. Porque este proceso funciona como un efecto dominó. Si una semana falla… lo que sigue se debilita.',
        'Esto no es actividad… es formación. Esto no es emoción… es transformación.',
        'Y este sistema está sostenido por principios claros: procesos continuos, eliminar vacíos espirituales, acción no solo teoría, disciplina en la ejecución, y trabajo en equipo. Aquí nadie corre solo… todos avanzamos juntos.',
      ],
      ilustrar: 'Como dice el manual: la visión no es abstracta… es concreta. Y lo concreto… produce resultados. Te lo pongo simple: una semana sin propósito… se convierte en un mes perdido. Pero siete semanas con enfoque… pueden producir lo que muchos no logran en meses.',
      preguntar: 'Ahora te hago una pregunta directa: ¿En qué parte del proceso se nos cae la gente? ¿En la semana 3? ¿En la semana 5? Porque el problema no es el sistema… es lo que no estamos haciendo bien en ese punto. Y esta vez… no podemos repetir el mismo error.',
      aplicar: 'Ahora vamos a hacerlo práctico: antes de salir hoy… vamos a definir la fecha exacta de inicio. Y vamos a marcar las 7 semanas en el calendario. Porque lo que no se agenda… no se ejecuta. Y lo que no se ejecuta… no produce fruto.',
      transicion: 'Recuerda esto: este no es un programa que se prueba… es un proceso que se respeta. Ahora… para que esto funcione correctamente… Dios nos dio un motor que conecta todo esto: el Modelo CAP.',
    },
  },

  // ----- 9. MODELO CAP -----
  {
    id: 'modelo-cap',
    type: 'modelo-cap',
    title: 'Modelo CAP',
    subtitle: 'Consolidación y Activación por Puertas',
    verse: 'Habacuc 2:2 — "Escribe la visión y declárala…"',
    notes: {
      abrir: 'CAP… No es una palabra más… no es un concepto bonito… Es la respuesta de Dios al problema de muchas iglesias: crecen… pero no logran sostener lo que crecen. Porque crecer sin estructura… es perder lo que Dios envía.',
      decir: [
        'CAP significa: Consolidación y Activación por Puertas. Y esto es clave: no solo queremos recibir gente… queremos consolidarla… y activarla. Porque una persona que no se activa… eventualmente se desconecta.',
        'El don es la llave. Dios ya puso algo dentro de cada persona… y ese don… abre su puerta en el Reino. Cuando conectamos a alguien correctamente… algo se abre. Pero cuando no lo hacemos… esa persona se pierde en el sistema.',
        'La iglesia funciona como un cuerpo. No todos hacen lo mismo… pero todos son necesarios. Y lo que tú haces… nadie más lo puede hacer igual que tú. Por eso este sistema no es masivo… es intencional.',
        'Hay tres niveles que sostienen todo: Formación (enseñar), Seguimiento (acompañar) y Crecimiento (multiplicar). Si quitamos uno… en menos de unos meses… todo se cae. Porque no basta con enseñar… hay que acompañar. Y no basta con acompañar… hay que multiplicar.',
      ],
      ilustrar: 'Te lo explico claro: sin CAP… la persona llega… se emociona… pero nadie la asigna… nadie la sigue… y eventualmente… se pierde. Pero con CAP… cada persona tiene un proceso. Tiene un líder. Tiene una puerta. Y tiene un destino. Eso es sistema. Eso es orden. Eso es Reino.',
      preguntar: 'Ahora te hago una pregunta directa: ¿Cuántas personas están entrando hoy… y no tienen quién las está formando realmente? Y más fuerte aún… ¿Quién es responsable de esas vidas? Porque esto no es solo organización… esto es responsabilidad espiritual.',
      aplicar: 'Ahora vamos a hacerlo práctico: esta semana… vas a tomar UNA persona que no tenga proceso claro. Y le vas a asignar tres cosas por escrito: una puerta, un mentor con nombre, y la semana en que comienza. Si no tiene esos tres… no está en discipulado. Está en el aire. Y aquí no vamos a trabajar con gente en el aire.',
      transicion: 'Recuerda esto: no queremos visitas… queremos discípulos. No queremos asistentes… queremos obreros. Ahora… para que este sistema se mueva con velocidad… Dios nos dio un principio que activa todo: el Tiempo 3… La Operación 72.',
    },
  },

  // ----- 10. OPERACION 72 -----
  {
    id: 'operacion-72',
    type: 'operacion-72',
    title: 'Operación 72',
    subtitle: 'Equipo por Puertas · Tiempo 3',
    verse: 'Isaías 61:1-5',
    notes: {
      abrir: 'Tiempo 3… Esto no es un número… es un patrón. No es algo que inventamos… es algo que Dios estableció. Moisés dijo: en tres días. Josué dijo: en tres días. Jesús dijo: en tres días. Dios trabaja en ciclos… y cuando entendemos el ritmo… vemos resultados.',
      decir: [
        'Ahora míralo aplicado al sistema: en 3 días… atendemos al nuevo creyente. En 21 días… se completa el proceso de LBS. En 72 horas… se define si una persona se queda o se va. En 3 meses… consolidamos y formamos.',
        'Esto no es teoría… esto es estrategia espiritual con tiempo definido. Porque el problema de muchas iglesias… no es falta de gente… es falta de respuesta a tiempo.',
        'Ahora mira los 3 meses: Mes 1 — se afirma el llamado. Mes 2 — se entiende el privilegio de servir. Mes 3 — se activa para ganar a otros. Tres meses… una vida transformada. Pero solo… si se ejecuta.',
      ],
      ilustrar: 'Escucha esto: cuando tardamos semanas en llamar a alguien… ya lo perdimos. Porque en 72 horas… la persona decide si vuelve… o no. Así de serio es esto. Por eso este sistema no funciona con intención… funciona con rapidez.',
      preguntar: 'Te hago una pregunta directa: ¿Qué pasaría en esta iglesia… si cada visitante recibe una llamada en menos de 72 horas? No un mensaje frío… una llamada real. ¿Sabes cuántas personas se quedarían? ¿Sabes cuánto creceríamos en 6 meses… solo obedeciendo esto?',
      aplicar: 'Ahora vamos a hacerlo práctico: mañana antes del mediodía… cada líder va a revisar su lista de visitantes de esta semana. Y va a llamar a cada uno en menos de 72 horas. Sin excusas. Y con esta frase clara: "Soy del equipo de la iglesia, solo quería saber cómo estás y orar contigo unos minutos." Eso es Reino. Eso es cuidado. Eso es sistema.',
      transicion: 'Recuerda esto: la gente no se pierde por falta de prédica… se pierde por falta de seguimiento. Y aquí… eso se terminó. Ahora vamos a ver la estructura que sostiene todo esto… las 9 puertas.',
    },
  },

  // ----- 11. LAS 9 PUERTAS (intro) -----
  {
    id: 'las-9-puertas',
    type: 'las-9-puertas',
    title: 'Las 9 Puertas',
    subtitle: 'El sistema completo de activación',
    notes: {
      abrir: 'Las 9 puertas… Esto no es organización… esto es cobertura. Esto no es estructura humana… es diseño de Dios. Cada necesidad que llega a esta casa… ya tiene una puerta asignada. Y cada puerta… tiene una respuesta. Aquí nadie debería perderse… porque el sistema está diseñado para que toda vida sea atendida.',
      decir: [
        'Escucha esto bien: si llega un enfermo va a la Puerta 6. Si hay una crisis, Puerta 3. Si hay una petición urgente, Puerta 1. Si llega un nuevo creyente, Puerta 5. Si llega un visitante, Puerta 2. Si hay un retiro, Puerta 4. Si es comunicación, Puerta 7. Si son recursos, Puerta 8. Si es un evento, Puerta 9. Eso no es improvisación… eso es orden.',
        'Porque el sistema funciona así: las células detectan necesidades… las puertas responden… y el liderazgo supervisa… y Dios transforma vidas. Así funciona el Reino.',
        'Pero hay algo importante: una puerta no es un nombre… es una estructura. Y cada puerta debe tener cuatro cosas claras: un líder con nombre, un asistente con nombre, un equipo mínimo, y metas medibles. Si no tiene eso… no es puerta… es solo un título.',
      ],
      ilustrar: 'Te lo digo claro: una iglesia sin puertas definidas… termina haciendo todo… y no haciendo nada bien. Es como un hospital sin áreas… todos atienden… pero nadie resuelve. Y la gente se pierde… no por falta de amor… sino por falta de orden.',
      preguntar: 'Por eso te hago esta pregunta: si entra alguien nuevo ahora mismo… ¿tú sabes exactamente a dónde dirigirlo en menos de un minuto? ¿O lo vas a dejar caminando sin dirección? Porque eso define si tenemos sistema… o solo intención.',
      aplicar: 'Ahora vamos a hacerlo práctico: antes de la próxima reunión… vas a memorizar las 9 puertas. Su número. Su nombre. Y su función. Porque lo que no conoces… no lo puedes ejecutar. Y lo que no ejecutas… no produce fruto.',
      transicion: 'Recuerda esto: aquí cada miembro tiene un lugar. Cada necesidad tiene una respuesta. Y cada vida tiene un proceso. Ahora vamos a entrar en detalle… porque todo comienza con la base espiritual de este sistema: la Puerta 1… Intercesión Profética.',
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
    subtitle: 'Jerarquía · Células · Cultura',
    notes: {
      abrir: 'Sin estructura clara, todo trabajo se diluye y todo llamado se gasta. Esta página es la columna vertebral del ministerio. Sin esta columna, el cuerpo no se levanta.',
      decir: [
        'La cadena de mando es: Pastor manda al Coordinador. Coordinador supervisa a 9 líderes de puerta. Cada líder dirige su equipo. Cada equipo sirve a la iglesia.',
        'Las CÉLULAS detectan necesidades en la base. Las PUERTAS responden con equipo y proceso. Nunca al revés: la célula no responde, ella solo detecta y reporta.',
        'El flujo natural es: persona llega → Bienvenida la recibe → entra a una célula → toma discipulado → va a retiro → empieza a servir → se forma como líder → abre nueva célula. Así se multiplica.',
      ],
      ilustrar: 'Una iglesia sin jerarquía clara es como un ejército sin oficiales asignados: todos pelean al mismo tiempo, nadie protege la retaguardia y al final se cansan sin saber por qué perdieron.',
      preguntar: '¿Cada líder de esta iglesia sabe a quién reporta sus avances y quiénes le reportan a él? Si la respuesta es "no estoy seguro", ahí hay una grieta y por las grietas se escapa el fruto.',
      aplicar: 'Esta semana, cada líder dibuja en una hoja su línea de mando: arriba, el nombre del coordinador. Al centro, su nombre. Abajo, los nombres de su equipo. Antes del viernes, comparte esa hoja con todo su equipo.',
      transicion: 'En el corazón de toda esta estructura hay una persona clave que decide si funciona o no: el líder de puerta.',
    },
  },

  // ----- 22. EL LIDER DE PUERTA -----
  {
    id: 'lider-puerta',
    type: 'lider',
    title: 'El Líder de Puerta',
    subtitle: 'Cuidar · Ubicar · Activar · Desarrollar',
    notes: {
      abrir: 'Un líder bíblico NO es un jefe que da órdenes. Si tu equipo te tiene miedo de hablarte, no eres líder: eres tirano con título. Y eso aquí no funciona.',
      decir: [
        'CUIDAR significa conocer a tu gente: sabes quién está bien, quién está triste y quién está escondiendo dolor detrás de una sonrisa el domingo.',
        'UBICAR significa ayudar a cada miembro a encontrar su lugar según su don, no usarlos para tus tareas. Hay diferencia entre asignar y explotar.',
        'ACTIVAR Y DESARROLLAR significa formar OTROS líderes que un día te reemplacen. El éxito ministerial se mide por los líderes que dejas formados, no por los aplausos que recibes en el escenario.',
      ],
      ilustrar: 'Lo dijo un líder bíblico bien claro: el verdadero liderazgo no se mide por cuántos te siguen mientras estás en el cargo. Se mide por cuántos líderes dejas formados y operando cuando ya no estás para supervisarlos.',
      preguntar: 'Si revisamos los últimos 12 meses de tu liderazgo... ¿cuántos líderes NUEVOS se formaron bajo tu cobertura con nombre y apellido? La respuesta dolerá, pero ilumina el camino.',
      aplicar: 'Antes del próximo domingo, identifica UNA persona en tu equipo con potencial real de líder futuro. Anota su nombre. Llámala mañana. Frase exacta: "Quiero invertir 30 minutos por semana en formarte como líder, durante los próximos 3 meses. ¿Me lo permites?"',
      transicion: 'Y para formar al nuevo creyente, hace falta otro actor clave que toca corazones uno a uno: el mentor.',
    },
  },

  // ----- 23. MENTOR -----
  {
    id: 'mentor',
    type: 'mentor',
    title: 'Propósito del Mentor',
    subtitle: '2 Timoteo 2:2',
    notes: {
      abrir: 'El mentor no es un maestro de teología que da clases en el templo. Es un puente humano entre el evangelio y la vida real: el matrimonio, el trabajo, las cuentas, los hijos, las decisiones del lunes.',
      decir: [
        'El mentor existe para 4 razones concretas: afirmar la fe del nuevo creyente, ayudarlo a cambiar su estilo de vida, integrarlo a la iglesia y prepararlo para servir.',
        'Perfil obligatorio del mentor: vida de oración diaria, amor visible por las almas, conocimiento bíblico sólido, paciencia, responsabilidad y testimonio limpio público y privado.',
        'Cuatro responsabilidades semanales del mentor: 1) contacto semanal por llamada o mensaje, 2) reunión de discipulado de 1 hora, 3) cuidado espiritual con oración por nombre, 4) integración a célula y a puerta.',
      ],
      ilustrar: 'Un nuevo creyente sin mentor asignado es un bebé sin madre que lo amamante. Puede sobrevivir comiendo lo que encuentre... pero su desarrollo siempre estará incompleto y vulnerable. Esta iglesia no se va a permitir hijos huérfanos.',
      preguntar: '¿A cuántas personas estás formando como mentor en este momento de tu vida? Si la respuesta es CERO... ¿qué vas a hacer al respecto antes del próximo domingo a las 12 del mediodía?',
      aplicar: 'Antes de salir hoy, escribe el nombre de UN nuevo creyente en tu manual. Llámalo mañana. Comprométete por 8 semanas exactas, una hora a la semana, mismo día, misma hora. Pon las 8 reuniones en tu calendario antes de colgar el teléfono.',
      transicion: 'Y todo mentor necesita un mapa para no improvisar cada semana. Ese mapa se llama Discipulado en 8 Semanas.',
    },
  },

  // ----- 24. DISCIPULADO 8 SEMANAS -----
  {
    id: 'discipulado-8-semanas',
    type: 'discipulado-8',
    title: 'Discipulado en 8 Semanas',
    subtitle: 'El mapa del nuevo creyente',
    notes: {
      abrir: 'Las primeras 8 semanas DECIDEN si el nuevo creyente echa raíces que aguantan tormentas o se seca al primer viento fuerte. Aquí no hay plan B. Lo que sembremos aquí, eso vamos a recoger.',
      decir: [
        'Cada una de las 8 semanas tiene UN tema y UN texto bíblico ancla. Semana 1: salvación y seguridad en Cristo (2 Co 5:17). Semana 2: oración y relación con Dios (Jer 33:3). Semana 3: la Biblia y crecimiento. Semana 4: la iglesia y congregarse.',
        'Semana 5: cambio de vida y santidad. Semana 6: visión y propósito. Semana 7: descubrir el don y servir en una puerta. Semana 8: preparación para el liderazgo. Ningún tema al azar.',
        'Las 4 primeras semanas son las RAÍCES. Las 4 últimas son la COSECHA. Sin raíces no hay cosecha. Sin cosecha, no formamos al próximo líder.',
      ],
      ilustrar: 'En 8 semanas exactas, una persona puede pasar de "acabo de aceptar a Cristo el domingo pasado" a "estoy formando a alguien más en su primera semana de discipulado". Esa es la velocidad del Reino cuando hay mapa claro y mentor activo.',
      preguntar: '¿Hay material físico impreso de las 8 semanas LISTO HOY en una caja para entregar a un nuevo creyente que se convierta el próximo domingo? Si la respuesta es no, ya entendemos por qué se nos van.',
      aplicar: 'Esta semana, Puerta 8 manda a imprimir 30 paquetes del Discipulado de 8 Semanas. Cada paquete con 8 hojas anilladas. Antes del próximo domingo, las 30 carpetas están en una caja en la oficina pastoral lista para entregar.',
      transicion: 'Ahora la pregunta clave que muchas iglesias evitan: ¿cuándo decimos que una persona está REALMENTE consolidada?',
    },
  },

  // ----- 25. CONSOLIDADO DE PUERTA -----
  {
    id: 'consolidado-puerta',
    type: 'consolidado',
    title: 'Consolidado de Puerta',
    subtitle: 'No por emoción · Por evidencia',
    notes: {
      abrir: 'Llegó la hora de medir con honestidad brutal. No nos vamos a engañar más con apariencias del domingo, ni a llamar consolidado a quien solo asiste y aplaude.',
      decir: [
        'Como dice el manual: "No queremos solo personas presentes, queremos personas firmes." Esa frase es nuestra brújula desde hoy.',
        'Hay 4 indicadores tangibles para llamar a alguien CONSOLIDADO: Ubicación, Activación, Cobertura y Proceso. Si falta UNO solo de los 4, no está consolidado: está de paso.',
        'Ubicado quiere decir que tiene puerta asignada por escrito. Activo quiere decir que ya está sirviendo en algo concreto. Cubierto quiere decir que un líder lo conoce por nombre. En proceso quiere decir que sigue formándose semana a semana.',
      ],
      ilustrar: 'Cien asistentes que ocupan banca pero no sirven valen menos en el Reino que diez consolidados que multiplican fruto cada mes. Esa es la matemática de Dios, no la nuestra. Por eso Jesús escogió doce, no doscientos.',
      preguntar: 'De toda nuestra lista actual de personas... ¿a cuántas concretamente podemos marcarles HOY los 4 checks completos? Seamos honestos en el equipo. La verdad sana, la mentira mata el ministerio.',
      aplicar: 'Esta semana, cada líder hace una tabla en una hoja con los nombres de su equipo en filas y los 4 indicadores en columnas. Marca SÍ o NO en cada celda. Donde haya "NO", ahí tiene trabajo concreto para los próximos 30 días.',
      transicion: 'Y para mantener todo este sistema en movimiento constante, hace falta UNA herramienta semanal que muchos subestiman.',
    },
  },

  // ----- 26. REUNION DE SUPERVISORES -----
  {
    id: 'reunion-supervisores',
    type: 'reunion',
    title: 'Reunión Mensual de Supervisores',
    subtitle: '30 minutos · Máximo enfoque',
    notes: {
      abrir: 'Esta reunión mensual de 30 minutos NO es para dar reportes bonitos ni para socializar. Es para asegurar que el sistema completo está vivo y avanzando según las metas escritas.',
      decir: [
        'Agenda fija de 30 minutos exactos: 5 min de inicio con oración, ministración y bienvenida; 5 min por supervisor (¿cuántos líderes? ¿quién avanza? ¿quién necesita ayuda?); 10 min de detección de bloqueos; 5 min de ajustes; 5 min de activación final declarando claridad y multiplicación.',
        'Lo que NO se hace: alargar, desviarse, contar historias largas, quejarse sin solución. Lo que SÍ se hace: ir al punto, escuchar al líder, decidir y ejecutar antes del lunes.',
        'Tu rol como coordinadora no es moderadora ni secretaria que toma notas. Eres la persona que ENFOCA al equipo, CORRIGE desviaciones y ACTIVA acciones concretas. Punto final.',
      ],
      ilustrar: 'Tres frases clave que hay que repetir hasta que se vuelvan cultura del equipo: "Vamos al punto." "¿Cuál es el siguiente paso concreto?" "Eso lo resolvemos antes del lunes." Repítelas en cada reunión sin pena.',
      preguntar: '¿Cuántas reuniones del último trimestre terminaron sin un siguiente paso CONCRETO escrito en el grupo de WhatsApp? Esas no son reuniones: son sesiones de desahogo disfrazadas de trabajo ministerial.',
      aplicar: 'En la próxima reunión mensual, ponle un cronómetro visible al teléfono en el centro de la mesa. Si pasa de los 30 minutos, identificamos quién desvió el tema y por qué. Sin pena, con amor, pero sin pena.',
      transicion: 'Y todo este sistema apunta a UNA sola meta medible al final del año: ganar líderes servidores que multipliquen vida.',
    },
  },

  // ----- 27. ESTRATEGIA DE GANAR -----
  {
    id: 'estrategia-ganar',
    type: 'estrategia',
    title: 'Estrategia de Ganar',
    subtitle: '40 líderes · Plan anual',
    notes: {
      abrir: 'No estamos hablando de "más asistencia los domingos" como meta vaga. Estamos hablando de 40 LÍDERES servidores formados, activos y multiplicando antes del cierre del año. Esa es la meta exacta.',
      decir: [
        'Cada 2 semanas debe haber personas concretas haciendo MCD, NPT, Bienvenida y Retiros LBS. Movimiento medible en una hoja, no esperanzas vagas.',
        'Tres discipulados clave en orden: primero "Mi llamado es sobrenatural", luego el segundo discipulado y al final el tercer discipulado. En ese orden estricto, sin saltos.',
        'Cada persona que se inscribe en consolidación recibe reconocimiento PÚBLICO desde el escenario el domingo siguiente. Lo que celebramos en público, eso multiplicamos en privado.',
      ],
      ilustrar: 'El plan de visita pastoral son 4 pasos exactos: 1) Confirmar datos por teléfono, 2) Entregar un regalo en la mano (libro o tarjeta), 3) Ofrecer MCD con fecha de inicio, 4) Conectar con mentor por nombre. Cuatro pasos sencillos que producen un líder en 90 días.',
      preguntar: 'De los 40 líderes que queremos ganar este año... ¿cuántos están ya identificados con NOMBRE Y APELLIDO en una lista escrita de oración? Si no están en lista, no están en el plan.',
      aplicar: 'Antes de salir hoy, escribe en tu manual los primeros 5 nombres con apellido de tu lista personal hacia los 40. Por esos 5 vas a orar cada mañana antes de las 8 am. Por esos 5 vas a llorar. Por esos 5 vas a ayunar el primer viernes del mes.',
      transicion: 'Y ahora cerramos. Todo lo que hemos visto se reduce a UNA sola palabra que define a la iglesia que Dios sueña: cultura.',
    },
  },

  // ----- 28. CULTURA Y LLAMADO FINAL -----
  {
    id: 'cultura-cierre',
    type: 'cierre',
    title: 'Cultura y Llamado Final',
    subtitle: 'Año de Cosecha y Restitución',
    notes: {
      abrir: 'Llegamos al final, y este final es en realidad el principio. Hoy esta iglesia entra en una cultura nueva que vamos a construir juntos, semana tras semana, sin retroceder.',
      decir: [
        'Como lo dice el manual con palabras exactas: hay una puerta para servir, hay una función para cada don, hay una necesidad en cada área y hay una generación que necesita ser cuidada.',
        'Las CÉLULAS detectan la necesidad. Las PUERTAS responden con equipo y proceso. El LIDERAZGO supervisa los resultados. Y solo DIOS transforma. Esa es la cadena exacta del Reino.',
        'Este es el año de cosecha y restitución. Lo que el enemigo robó en años pasados, Dios lo devuelve este año. Lo que parecía tarde, Dios lo acelera. Creemos y avanzamos con disciplina.',
      ],
      ilustrar: 'Una iglesia donde cada miembro tiene un lugar, cada necesidad tiene una respuesta y cada vida tiene un proceso. Esa frase es nuestra firma como casa de oración a partir de hoy. No es lema: es pacto.',
      preguntar: '¿Vas a salir de aquí como observador que aplaude la visión desde la silla... o como protagonista que la ejecuta de lunes a viernes? La cosecha se reparte solo entre los que trabajan en ella, no entre los que la celebran.',
      aplicar: 'Antes de levantarte de tu silla hoy, escribe en tu manual estas tres líneas exactas: 1) PUERTA donde voy a servir el próximo trimestre. 2) NOMBRE Y APELLIDO de la persona que voy a discipular 8 semanas. 3) FECHA exacta del lunes en que comienzo. Sin esas 3 líneas escritas, esto fue solo emoción pasajera.',
      transicion: 'Cerramos declarando juntos en voz alta: "Soy parte de la cosecha de este año. Mi puerta está abierta. Aquí estoy. Señor, envíame."',
      versiculoFinal: '"Porque de la manera que en un cuerpo tenemos muchos miembros, pero no todos los miembros tienen la misma función..." — Romanos 12:4',
    },
  },
];
