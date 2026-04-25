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
    abrir: 'Hoy… una persona puede estar llorando sola… a las 2 de la mañana… abrir su teléfono… y buscar una respuesta. Y la pregunta es: ¿qué va a encontrar? Porque si nosotros no estamos ahí… alguien más va a ocupar ese espacio.',
    decir: [
      'Por eso existe la Puerta 7: Multimedia y Comunicación. Esto no es lujo… esto es misión. Esto es el puente… entre el altar y una generación que vive en la pantalla.',
      'Escucha esto bien: la iglesia ya no termina el domingo. La iglesia ahora vive… 24 horas… 7 días a la semana. En cada video. En cada prédica. En cada testimonio publicado. Eso es alcance. Eso es expansión.',
      'Ahora algo práctico: cada culto… debe estar editado y publicado en menos de 48 horas. Con calidad. Con intención. Con un título claro. Una miniatura correcta. Y una descripción que conecte. Porque si no se publica bien… no se ve. Y si no se ve… no transforma.',
    ],
    ilustrar: 'Te lo explico con Nehemías: la Puerta de las Aguas… representaba la Palabra. Hoy… esas aguas corren por internet. Por redes sociales. Por plataformas digitales. Y si nosotros no fluimos ahí… otros lo van a hacer. Y nuestra gente… va a consumir contenido que no está alineado con la visión. Eso es serio.',
    preguntar: 'Ahora te hago una pregunta directa: la prédica del domingo pasado… ¿cuántas personas la pudieron ver el martes? ¿Y cuántas no la verán nunca… porque nadie la subió? Eso es oportunidad perdida.',
    aplicar: 'Ahora vamos a hacerlo práctico: esta semana… asignamos UN responsable. Por nombre. Y con un acuerdo claro: cada culto publicado en menos de 48 horas. En YouTube. En Instagram. En Facebook. Sin excusas. Sin atrasos. Porque esto no es creatividad… es responsabilidad.',
    transicion: 'Recuerda esto: el mensaje no se queda en el altar… se multiplica en la plataforma. Y lo que Dios está hablando aquí… tiene que llegar más lejos. Pero para que todo esto funcione… se necesitan recursos. Orden. Herramientas. Administración. Y eso nos lleva a la siguiente puerta: la Puerta 8… Administración y Recursos.',
  },
  8: {
    abrir: 'La visión… sin recursos… termina en frustración. No porque Dios no quiera hacer algo… sino porque no hay con qué sostenerlo.',
    decir: [
      'Por eso la Puerta 8 existe: Administración y Recursos. Y escúchame bien: esto no es contabilidad… esto es Reino. Esto es preparar el terreno para que cada vida que llegue… encuentre lo que necesita. Una Biblia. Un manual. Una herramienta. Sin retrasos. Sin excusas.',
      'Ahora esto es clave: hay tres inventarios que siempre deben estar completos: Biblias para nuevos creyentes. Manuales de discipulado. Materiales para cada puerta. Siempre. Porque cuando alguien llega… no puede esperar. Lo que no está listo… se pierde.',
      'Te lo digo claro: lo que se administra con orden… alcanza más. Lo que se administra sin orden… se desperdicia. Y nadie sabe en qué.',
    ],
    ilustrar: 'Te lo explico con Nehemías: la Puerta del Caballo… representaba guerra. Y ningún ejército… gana sin logística. Sin armas. Sin provisión. Sin preparación. Y la iglesia… tampoco gana la guerra espiritual… sin recursos en la mano.',
    preguntar: 'Ahora te hago una pregunta directa: si mañana llegan 20 personas nuevas… ¿tenemos 20 Biblias? ¿20 manuales? ¿20 materiales listos? ¿O vamos a decirles… "vuelve la próxima semana"? Porque en el Reino… la demora… cuesta almas.',
    aplicar: 'Ahora vamos a hacerlo práctico: esta semana… la Puerta 8 hace inventario real. No estimado. Real. Cuántas Biblias hay. Cuántos manuales hay. Cuántos materiales hay. Y si no llegamos a 30 unidades… se compra antes del próximo culto. Sin discusión. Y se reporta. Porque lo que no se mide… no se mejora.',
    transicion: 'Recuerda esto: Dios envía la cosecha… pero la iglesia tiene que estar preparada para recibirla. Y cuando todo esto está listo… hay momentos donde Dios no solo toca una persona… sino multitudes. Y esos momentos… no se improvisan. Se planifican. Esa es la siguiente puerta: la Puerta 9… Congresos y Eventos Especiales.',
  },
  9: {
    abrir: 'Hay momentos… que no son normales. Son momentos donde Dios acelera lo que tomó meses… en una sola noche. Un congreso. Un retiro. Una noche de gloria. Pero escúchame bien: esos momentos… no se improvisan. Se planifican. Y se preparan en lo espiritual y en lo práctico.',
    decir: [
      'Por eso existe la Puerta 9: Congresos y Eventos Especiales. Esto no es agenda… esto es impulso espiritual. Esto es donde Dios mete una velocidad nueva al sistema.',
      'Ahora, esto es clave: un evento no empieza cuando se anuncia. Empieza cuando se define. Y todo evento serio debe tener 4 cosas escritas: fecha exacta, equipo responsable, presupuesto en números reales y meta de almas alcanzadas. Si no tiene eso… no es evento. Es intención. Y las intenciones no producen resultados.',
      'Ahora mira esto: en un evento… todas las puertas trabajan juntas. Puerta 3 ministra. Puerta 2 recibe. Puerta 5 discipula. Puerta 7 comunica. Puerta 8 sostiene. Puerta 6 da seguimiento. Es una sinfonía completa. Si una falla… todo se siente. Por eso los eventos no son de un ministerio… son de TODA la iglesia.',
    ],
    ilustrar: 'Ahora te llevo a lo espiritual: Nehemías llamó a esta… la Puerta Oriental. La puerta por donde entra el Rey. Eso significa algo poderoso: cada evento que hagamos… debe abrirle paso a Dios. No solo llenar sillas. No solo hacer ruido. Sino provocar un encuentro real. Y te lo digo claro: la diferencia entre un evento normal y un mover de Dios… se mide después. En testimonios. En vidas cambiadas. En decisiones firmes.',
    preguntar: 'Ahora la pregunta incómoda: el próximo evento de esta iglesia… ¿va a ser inolvidable en el espíritu… o desechable en la memoria? Porque hay eventos que la gente olvida en 7 días… y hay eventos que marcan una vida por años. Y eso no depende de la emoción… depende de la preparación.',
    aplicar: 'Ahora vamos a ejecutar: esta misma semana… se define el próximo evento grande. No "algún día". No "cuando se pueda". Esta semana. Y se escribe en una hoja: fecha, nombre del coordinador, presupuesto, meta de almas. Se pega en la oficina. Porque si no está escrito… no existe.',
    transicion: 'Recuerda esto: Dios se mueve en momentos… pero honra la preparación. Y cuando todo esto se alinea… las puertas dejan de ser ideas… y se convierten en un sistema vivo. Ya no estamos improvisando iglesia… estamos construyendo Reino con orden. Cerramos las nueve puertas. Ahora levantamos la mirada… y vemos el sistema completo funcionando.',
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
      abrir: 'Míralo bien… porque esto no es un dibujo bonito. Esto es la estructura que va a sostener todo lo que Dios quiere hacer aquí. Y te lo digo claro: sin estructura… todo se diluye. Sin orden… todo se desgasta. Sin jerarquía… todo se confunde. Por eso esta página… es la columna vertebral del ministerio.',
      decir: [
        'Ahora escúchalo simple: aquí hay una cadena clara. El Pastor principal dirige la visión. El Coordinador general la baja a operación. Los 9 líderes de puerta ejecutan por área. Los equipos sirven. Y la iglesia recibe, crece y se multiplica. Eso es orden. Eso es gobierno. Eso es sistema.',
        'Ahora esto es CLAVE: las células… NO resuelven. Las células DETECTAN. Las puertas… NO observan. Las puertas RESPONDEN. Si mezclamos eso… el sistema se rompe. La célula no es hospital. La célula es radar. Detecta necesidades, y las envía al lugar correcto. Y las puertas sí tienen el equipo, la estructura y el proceso… para responder bien.',
        'Ahora mira el flujo completo: la persona llega. Puerta 2 la recibe. Entra a una célula. Recibe discipulado. Va a retiro. Empieza a servir. Se forma como líder. Y abre una nueva célula. Eso es multiplicación real. No teoría. Sistema.',
      ],
      ilustrar: 'Ahora te lo aterrizo: una iglesia sin estructura clara… es como un ejército sin rangos. Todos corren. Todos hacen algo. Pero nadie sabe qué le toca. Y al final… se cansan… sin saber por qué no avanzaron. No fue falta de unción. Fue falta de orden.',
      preguntar: 'Ahora la pregunta directa: ¿Tú sabes a quién le rindes cuentas? ¿Y quién te rinde cuentas a ti? Porque si eso no está claro… hay fuga. Y donde hay fuga… se pierde el fruto.',
      aplicar: 'Ahora vamos a ejecutar: esta semana… cada líder va a hacer algo simple pero poderoso. Toma una hoja. Arriba escribe el nombre de tu coordinador. En el centro, tu nombre. Abajo, los nombres de tu equipo. Eso es tu línea de mando. Eso es tu responsabilidad. Y antes del viernes… lo compartes con tu equipo. Para que todos sepan: quién dirige, quién ejecuta y quién responde. Porque donde hay claridad… hay avance. Y donde hay orden… Dios respalda.',
      transicion: 'Ahora escúchame esto para cerrar: el sistema no falla por falta de gente… falla por falta de liderazgo claro. Y en el centro de toda esta estructura… hay una pieza clave. Una persona que define si esto funciona o no. El líder de puerta. Ahí vamos ahora.',
    },
  },

  // ----- 22. EL LIDER DE PUERTA -----
  {
    id: 'lider-puerta',
    type: 'lider',
    title: 'El Líder de Puerta',
    subtitle: 'Cuidar · Ubicar · Activar · Desarrollar',
    notes: {
      abrir: 'Mírame bien esto… porque aquí se define si este sistema vive… o se queda en papel. El problema de muchas iglesias no es falta de gente… es falta de líderes correctos. Y por eso Dios diseñó esto: el líder de puerta.',
      decir: [
        'Ahora escúchame claro desde el inicio: un líder bíblico… NO es un jefe. No es alguien que manda, grita y controla. Si tu equipo tiene miedo de hablarte… no eres líder. Eres presión con título. Y eso aquí no funciona. Aquí estamos formando otra cosa.',
        'Un líder de puerta tiene 4 funciones claras: Cuidar, Ubicar, Activar, Desarrollar. CUIDAR no es preguntar "¿todo bien?" los domingos. Es conocer a tu gente de verdad. Tú sabes quién está firme… quién está débil… y quién está sonriendo… pero por dentro está roto. Si no conoces a tu gente… no la puedes liderar.',
        'UBICAR es ayudar a cada persona a encontrar su lugar correcto. Según su don. No según lo que tú necesitas. Asignar no es lo mismo que usar. Un líder sano conecta propósito. Un líder incorrecto explota gente. Y eso rompe el sistema.',
        'ACTIVAR es dar el siguiente paso. No dejar gente sentada meses. No dejarlos mirando. Es decir: "Ven, te toca." Dar oportunidades. Abrir puertas. Empujar hacia adelante. Porque nadie crece esperando. Y DESARROLLAR es lo más importante de todo: formar líderes. No seguidores. No ayudantes. Líderes. Gente que un día pueda hacer lo mismo que tú haces… sin depender de ti.',
      ],
      ilustrar: 'Te lo digo directo: el éxito de tu liderazgo… no se mide por cuántos te aplauden. Se mide por cuántos líderes dejas formados cuando ya no estás. Eso es Reino. Eso es multiplicación. Un líder verdadero… no crea dependencia. Crea capacidad. Porque el día que tú no estés… el sistema no debe caer. Debe seguir creciendo.',
      preguntar: 'Ahora la pregunta fuerte: en los últimos 12 meses… ¿cuántos líderes nuevos formaste? Con nombre. Con proceso. Con resultado. Si la respuesta es "ninguno"… no es condenación. Pero sí es revelación. Ahí está el ajuste.',
      aplicar: 'Ahora vamos a ejecutar: antes del próximo domingo… cada líder hace esto: identifica UNA persona con potencial real. No la más simpática. No la más disponible. La correcta. Anota su nombre. Y mañana mismo la llamas. Y le dices EXACTAMENTE esto: "Quiero invertir 30 minutos por semana contigo, durante los próximos 3 meses, para formarte como líder. ¿Me lo permites?" Y no cuelgas… hasta que haya fecha en el calendario. Porque formar líderes no es intención… es agenda.',
      transicion: 'Ahora escúchame esto para cerrar: no solo queremos consolidar personas… queremos consolidarlas EN UNA PUERTA. Con propósito. Con función. Con crecimiento. Y para que ese proceso funcione… hay otra pieza clave. Una que toca vidas uno a uno… cara a cara… semana a semana. El mentor. Ahí entramos ahora.',
    },
  },

  // ----- 23. MENTOR -----
  {
    id: 'mentor',
    type: 'mentor',
    title: 'Propósito del Mentor',
    subtitle: '2 Timoteo 2:2',
    notes: {
      abrir: 'Escucha esto con atención… porque aquí es donde el sistema deja de ser estructura… y se vuelve humano. El mentor. El mentor no es un maestro de Biblia. No es alguien que da clases y se va. El mentor… es un puente. Un puente entre el evangelio… y la vida real. Entre lo que se predica el domingo… y lo que se vive el lunes. El matrimonio. El trabajo. Las cuentas. Las decisiones. Ahí entra el mentor.',
      decir: [
        'Ahora, el mentor existe para 4 cosas claras: Primero… AFIRMAR la fe. El nuevo creyente viene inseguro, con dudas, con preguntas. El mentor le dice: "Vas bien. Dios está contigo." Segundo… CAMBIAR su estilo de vida. No solo información… transformación. Hábitos nuevos. Decisiones nuevas. Tercero… INTEGRARLO. A la iglesia. A la célula. A una puerta. Porque nadie crece aislado. Y cuarto… PREPARARLO para servir. Porque el objetivo no es que se quede sentado. Es que se convierta en alguien útil en el Reino.',
        'Ahora escúchame esto fuerte: no cualquiera puede ser mentor. Hay un perfil. Vida de oración diaria. Amor real por las almas. Base bíblica sólida. Paciencia. Responsabilidad. Y testimonio limpio… en público y en privado. Porque el discípulo no copia lo que dices… copia lo que eres.',
        'Ahora las 4 responsabilidades semanales: Número uno… Contacto. Llamada o mensaje. No desaparecer. Número dos… Reunión. Una hora. Una vez por semana. No negociable. Número tres… Cuidado espiritual. Orar por esa persona por nombre. Escucharla. Acompañarla. Y número cuatro… Integración. A célula. Y a una puerta. Porque si no entra al sistema… se pierde.',
      ],
      ilustrar: 'Ahora te lo ilustro claro: un nuevo creyente sin mentor… es un bebé sin madre. Puede sobrevivir… pero va a crecer débil. Inestable. Vulnerable. Y esta iglesia tomó una decisión: aquí no vamos a tener hijos huérfanos.',
      preguntar: 'Ahora la pregunta directa: ¿A cuántas personas estás formando ahora mismo? No "algún día". Ahora. Si la respuesta es cero… no te excuses. Actúa. Porque el problema no es capacidad… es decisión.',
      aplicar: 'Ahora vamos a ejecutar: antes de salir hoy… vas a escribir un nombre. UNO. No diez. Uno. Un nuevo creyente. Mañana lo llamas. Y le dices EXACTAMENTE esto: "Quiero comprometerme contigo 8 semanas. Una hora a la semana, mismo día, misma hora." Y no cuelgas… hasta que estén las 8 reuniones puestas en el calendario. Porque discipulado sin agenda… no es discipulado. Es intención. Y la intención no transforma vidas.',
      transicion: 'Ahora escúchame esto para cerrar: el mentor no improvisa. El mentor no inventa cada semana. El mentor sigue un camino. Un mapa claro. Un proceso probado. Ese mapa ya está diseñado. Se llama… Discipulado en 8 Semanas. Ahí entramos ahora.',
    },
  },

  // ----- 24. DISCIPULADO 8 SEMANAS -----
  {
    id: 'discipulado-8-semanas',
    type: 'discipulado-8',
    title: 'Discipulado en 8 Semanas',
    subtitle: 'El mapa del nuevo creyente',
    notes: {
      abrir: 'Escucha esto con mucha atención… porque aquí se decide todo. No en el culto. No en la emoción. Aquí. En las primeras 8 semanas. Porque estas 8 semanas… no son un programa. Son un filtro. O la persona echa raíces… o se seca. Así de claro. Aquí no hay plan B. Lo que sembremos aquí… eso vamos a cosechar después.',
      decir: [
        'Ahora, esto es clave: el discipulado no es improvisado. No es "vamos a ver qué hablamos hoy". No. Hay un mapa. Un orden. Un proceso claro. Cada semana tiene un propósito específico.',
        'Semana 1… Salvación y seguridad en Cristo. La persona entiende quién es ahora. Nueva criatura. Semana 2… Oración. Aprende a hablar con Dios. No religión… relación. Semana 3… Biblia. Empieza a alimentarse correctamente. Semana 4… Iglesia. Entiende que no camina solo. Es familia. Ahora escúchame esto: estas primeras 4 semanas… son las RAÍCES. Si aquí fallamos… todo lo demás se cae.',
        'Ahora las siguientes 4: Semana 5… Cambio de vida. La fe se vuelve práctica. Semana 6… Visión. Descubre para qué vive. Semana 7… Don. Empieza a servir. Entra a una puerta. Semana 8… Liderazgo. Ya no solo recibe… empieza a formar.',
        'Esto es poderoso: las últimas 4 semanas… son la COSECHA. Raíces primero. Cosecha después. Porque sin raíces… no hay fruto. Y sin fruto… no hay multiplicación.',
      ],
      ilustrar: 'Ahora te lo aterrizo: en 8 semanas… una persona puede pasar de: "Me convertí el domingo pasado…" a… "Estoy formando a alguien más." Eso es Reino. Eso es velocidad espiritual. Eso es sistema funcionando.',
      preguntar: 'Ahora la pregunta incómoda: si HOY se convierte alguien… ¿tenemos el material listo? ¿O vamos a improvisar? Porque ahí es donde se pierden. No por falta de amor… por falta de preparación.',
      aplicar: 'Ahora ejecutamos: esta semana… Puerta 8 tiene una tarea clara. Se imprimen 30 paquetes. Treinta. No cinco. No diez. Treinta. Cada uno con las 8 semanas completas. Ordenadas. Listas. Y se colocan en una caja… en la oficina pastoral. ¿Para qué? Para que cuando alguien se convierta… no haya excusa. Ese mismo día… sale con su material. Y con su mentor. Y con su proceso activo. Porque aquí no reaccionamos tarde… aquí estamos preparados antes.',
      transicion: 'Ahora escúchame esto para cerrar: el discipulado no empieza cuando hay tiempo… empieza cuando hay decisión. Y una iglesia que tiene mapa… no pierde gente. Forma discípulos. Pero ahora viene la pregunta más importante… la que muchas iglesias evitan responder: ¿cuándo una persona realmente… está consolidada? Ahí vamos ahora.',
    },
  },

  // ----- 25. CONSOLIDADO DE PUERTA -----
  {
    id: 'consolidado-puerta',
    type: 'consolidado',
    title: 'Consolidado de Puerta',
    subtitle: 'No por emoción · Por evidencia',
    notes: {
      abrir: 'Escucha esto… porque aquí es donde muchas iglesias se mienten. Y nosotros no vamos a hacer eso. Llegó el momento de medir… con honestidad brutal. No emoción. No percepción. No "yo creo que sí". EVIDENCIA. Porque desde hoy… no vamos a llamar consolidado… al que solo viene los domingos. Eso se terminó.',
      decir: [
        'Como dice el sistema: "No queremos solo personas presentes… queremos personas firmes." Esa frase… no es bonita. Es una regla.',
        'Ahora escúchame esto bien claro: solo hay 4 indicadores. No diez. No veinte. Cuatro. Y si falta UNO… esa persona NO está consolidada. Está de paso.',
        'Indicador número 1: UBICACIÓN. Tiene una puerta asignada. No "está viendo dónde encaja". Ya sabe dónde sirve. Y está escrito. Indicador número 2: ACTIVACIÓN. Ya está haciendo algo. No "quiere ayudar". No "está dispuesto". Está sirviendo. Con responsabilidad. Con horario. Con función. Indicador número 3: COBERTURA. Alguien lo conoce. Por nombre. Por vida. Por situación. No es un rostro más. Tiene un líder. Indicador número 4: PROCESO. Sigue formándose. No se quedó en el culto. Está en discipulado. Está creciendo. Semana tras semana.',
        'Ahora escúchame esto… sin suavizarlo: si una persona viene pero no sirve, no está consolidada. Si sirve pero nadie lo cubre, no está consolidada. Si tiene líder pero no está en proceso, no está consolidada. Si está en proceso pero no tiene lugar, no está consolidada. Los cuatro… o ninguno. Así de simple.',
      ],
      ilustrar: 'Ahora te lo aterrizo fuerte: cien personas sentadas… no hacen una iglesia fuerte. Diez personas consolidadas… sí. Porque esas diez… multiplican. Forman. Crecen. Impactan. Jesús no levantó una multitud… levantó doce. Y cambió el mundo.',
      preguntar: 'Ahora la pregunta incómoda: si hoy revisamos la lista de la iglesia… nombre por nombre… ¿cuántos tienen los 4 checks? No cuántos vienen. Cuántos están firmes. Porque esa diferencia… es la salud real del ministerio.',
      aplicar: 'Ahora ejecutamos: esta semana… cada líder toma una hoja. Hace una tabla. Filas: nombres de su gente. Columnas: Ubicación, Activación, Cobertura, Proceso. Y marca SÍ o NO. Sin maquillaje. Sin excusas. Donde haya un NO… ahí hay trabajo. Eso no es fracaso… eso es dirección clara. Y ese será el plan de acción… para los próximos 30 días. Porque aquí no diagnosticamos… para quedarnos igual. Diagnosticamos… para corregir. Y crecer.',
      transicion: 'Ahora te preparo para lo siguiente: porque un sistema como este… no se mantiene solo. Necesita ritmo. Necesita seguimiento. Necesita una herramienta semanal… que muchos subestiman… pero que decide si todo esto funciona o se cae. Y eso… es lo próximo.',
    },
  },

  // ----- 26. REUNION DE SUPERVISORES -----
  {
    id: 'reunion-supervisores',
    type: 'reunion',
    title: 'Reunión Mensual de Supervisores',
    subtitle: '30 minutos · Máximo enfoque',
    notes: {
      abrir: 'Escúchame bien… porque aquí es donde el sistema vive… o se muere. Esta reunión mensual de 30 minutos… no es opcional. No es decorativa. No es "cuando se pueda". Es el corazón de control del sistema. Si esto se hace bien… todo avanza. Si esto se hace mal… todo se frena. Así de simple.',
      decir: [
        'Ahora te lo dejo claro: esta NO es una reunión para impresionar. No es para decir "todo va bien". No es para hablar bonito. Es para decir la VERDAD… y tomar decisiones. La agenda no se negocia. Se respeta.',
        '5 minutos de inicio. No 10. No 15. 5. Oración. Enfoque. Arrancamos. Luego… 5 minutos por supervisor. Y aquí no vienes a contar historias. Vienes a responder 3 cosas: ¿Cuántos líderes tienes? ¿Quién está avanzando? ¿Quién necesita ayuda? Nada más. Si no puedes responder eso claro… no estás supervisando. Estás observando.',
        'Después vienen 10 minutos… los más importantes: DETECCIÓN. Aquí se revela todo. ¿Dónde se está cayendo la gente? ¿En qué puerta se están perdiendo? ¿Dónde está el cuello de botella? Aquí no se justifica. Aquí se identifica. Porque lo que no se identifica… no se corrige.',
        'Luego… 5 minutos de AJUSTES. Aquí no se habla mucho. Aquí se decide. ¿Qué se corrige? ¿Quién lo corrige? ¿Para cuándo? Si no hay responsable… no hay cambio. Si no hay fecha… no existe. Y cerramos con 5 minutos de ACTIVACIÓN. Oramos. Declaramos. Pero no emocional. Con dirección. Con claridad. Con enfoque en multiplicación.',
      ],
      ilustrar: 'Ahora escúchame esto fuerte: lo que NO se hace en esta reunión: no se alarga. No se desvía. No se cuentan historias largas. No se queja sin solución. Eso mata el sistema. Lo que SÍ se hace: se va al punto. Se escucha. Se decide. Se ejecuta. Antes del lunes. Siempre antes del lunes. Y aquí está tu rol… porque esto es clave: tú no eres moderadora. Tú no eres secretaria. Tú no estás ahí para "dejar que todos hablen". No. Tú estás ahí para: ENFOCAR, CORREGIR, ACTIVAR. Si alguien se desvía… lo traes. Si alguien habla mucho… lo cortas. Si alguien no tiene claridad… lo confrontas. Con respeto… pero con firmeza. Tres frases que deben volverse cultura: "Vamos al punto." "¿Cuál es el siguiente paso concreto?" "Eso lo resolvemos antes del lunes."',
      preguntar: 'Ahora la pregunta incómoda: ¿Cuántas reuniones en los últimos meses… terminaron sin una acción concreta? Sin responsable. Sin fecha. Sin seguimiento. Esas reuniones… no fueron reuniones. Fueron desahogo. Y eso se acabó.',
      aplicar: 'Ahora ejecutamos: próxima reunión. Pones el teléfono en la mesa. Cronómetro visible. 30 minutos exactos. Si alguien rompe el tiempo… se identifica. No para avergonzar… para corregir. Porque el tiempo revela… quién está enfocado… y quién no.',
      transicion: 'Y cierro con esto… porque esto es lo que define TODO: este sistema… no existe para llenar reuniones. No existe para organizar gente. No existe para verse bonito. Existe para una sola cosa: formar líderes… que multipliquen vida. Esa es la meta. Todo lo demás… es herramienta. Si al final del año… no hay más líderes formados… no importa cuántas reuniones hicimos. Fallamos. Pero si hay líderes nuevos… sirviendo… multiplicando… levantando a otros… entonces sí. Entonces el sistema está vivo. Y hacia ahí vamos.',
    },
  },

  // ----- 27. ESTRATEGIA DE GANAR -----
  {
    id: 'estrategia-ganar',
    type: 'estrategia',
    title: 'Estrategia de Ganar',
    subtitle: '40 líderes · Plan anual',
    notes: {
      abrir: 'Escúchame bien… porque aquí se define todo. No estamos construyendo un sistema… estamos estableciendo una CULTURA. Y cultura… no es lo que dices. Es lo que haces… repetidamente. Día tras día. Semana tras semana. Sin emoción. Sin excusas. Sin pausa.',
      decir: [
        'Ahora te lo digo claro: no queremos una iglesia que "intenta". Queremos una iglesia que EJECUTA. No queremos gente motivada… queremos gente disciplinada. Porque la motivación sube y baja… pero la disciplina sostiene el fruto.',
        'La meta está clara: 40 líderes. No 39. No "casi". Formados. Activos. Sirviendo. Multiplicando. Y eso no se logra orando solamente. Se logra ejecutando un plan.',
        'Ahora grábate esto: cada 2 semanas… tiene que haber movimiento. Personas entrando. Personas avanzando. Personas siendo asignadas. Si pasan 2 semanas… y no hay nombres nuevos… el sistema está fallando. No es percepción. Es evidencia.',
        'Tres discipulados. En orden. Sin saltos. Sin inventos. Primero uno. Luego dos. Luego tres. El que se salta el proceso… se cae después. Siempre. Y aquí no improvisamos. Aquí formamos. Y lo que se forma bien… permanece. Ahora escucha esto… porque esto multiplica todo: lo que celebras en público… crece en privado. Cada persona que entra… se reconoce. Se nombra. Se honra. Porque lo visible… se vuelve aspiración para otros. Y eso acelera el sistema.',
      ],
      ilustrar: 'Ahora te aterrizo el plan en una frase: una persona… bien atendida… bien asignada… bien discipulada… en 90 días… puede ser un líder. Pero si fallas en uno de esos pasos… la pierdes. Así de sencillo.',
      preguntar: 'Ahora la pregunta directa: los 40 líderes que dijimos… ¿dónde están? ¿Ya tienen nombre? ¿Ya están escritos? ¿Ya están en oración? ¿O son solo una meta bonita? Porque si no tienen nombre… no existen. Si no están escritos… no están en el plan. Y lo que no está en el plan… no se cumple.',
      aplicar: 'Ahora ejecutamos: antes de salir hoy… no mañana… hoy… escribe 5 nombres. Nombre y apellido. Personas reales. No ideas. No "Dios traerá". Personas que tú conoces. Por esos 5… vas a orar todos los días. Por esos 5… vas a trabajar. Por esos 5… vas a insistir. Porque los líderes… no aparecen. Se forman.',
      transicion: 'Ahora cierro con esto… y esto es lo más importante de todo: este sistema no funciona… si no se vuelve cultura. Y cultura es: orar aunque no sientas. Llamar aunque estés cansado. Discipular aunque no te respondan. Visitar aunque no te abran la puerta. Persistir… hasta ver fruto. Eso es cultura. Y la iglesia que Dios levanta… no es la más grande. Es la más consistente. La que no se rinde. La que no negocia el proceso. La que hace lo correcto… aunque nadie la esté viendo. Si logramos eso… los 40 no son el techo. Son el comienzo. Porque cuando una iglesia entra en cultura… ya no crece por eventos… crece por ADN. Y ese ADN… es el que vamos a establecer. Desde hoy.',
    },
  },

  // ----- 28. CULTURA Y LLAMADO FINAL -----
  {
    id: 'cultura-cierre',
    type: 'cierre',
    title: 'Cultura y Llamado Final',
    subtitle: 'Año de Cosecha y Restitución',
    notes: {
      abrir: 'Escúchame bien… porque este no es un cierre. Es un comienzo. Hoy… esta iglesia cruza una línea. No regresamos a lo mismo. No regresamos a lo cómodo. No regresamos a lo improvisado. Hoy entramos en CULTURA. Y cultura… es lo que haces cuando nadie te está mirando. Es lo que repites… aunque estés cansado. Es lo que sostienes… aunque no veas resultados inmediatos.',
      decir: [
        'Ahora grábate esto: aquí hay una puerta para servir. Aquí hay una función para cada don. Aquí hay una necesidad en cada área. Y aquí hay una generación… que necesita ser cuidada. Y si esa generación no es cuidada… no es porque Dios falló. Es porque nosotros no respondimos. Así de claro.',
        'Ahora te lo ordeno en una sola línea: las células detectan. Las puertas responden. El liderazgo supervisa. Y Dios transforma. Ese es el sistema. Ese es el Reino. Ese es el orden. Y cuando ese orden se respeta… la cosecha llega.',
        'Ahora escucha esto con fe… pero también con responsabilidad: este es el año de cosecha… y de restitución. Lo que se perdió… vuelve. Lo que se detuvo… se activa. Lo que se atrasó… se acelera. Pero no por emoción. Por disciplina. Por obediencia. Por ejecución. Porque Dios no bendice intenciones… bendice estructuras alineadas.',
      ],
      ilustrar: 'Ahora te lo dejo como identidad: somos una iglesia… donde cada persona tiene un lugar. Donde cada necesidad tiene una respuesta. Y donde cada vida tiene un proceso. Eso no es un lema. Eso es un pacto. Y un pacto… no se negocia. Se cumple.',
      preguntar: 'Ahora la pregunta final: ¿Vas a salir de aquí… como alguien que escuchó? ¿O como alguien que responde? Porque el Reino no necesita espectadores. Necesita obreros. La cosecha no se reparte entre los que aplauden. Se reparte entre los que trabajan.',
      aplicar: 'Ahora ejecutamos… aquí mismo: antes de levantarte… escribe. No lo pienses. No lo pospongas. Escribe. Tres líneas: 1) La PUERTA donde vas a servir este próximo trimestre. 2) El NOMBRE Y APELLIDO de la persona que vas a discipular por 8 semanas. 3) La FECHA exacta en que comienzas. Si eso no está escrito… esto fue emoción. Y nosotros no estamos construyendo emoción. Estamos construyendo destino.',
      transicion: 'Ahora todos juntos… declaramos: "Soy parte de la cosecha de este año. Mi puerta está abierta. Aquí estoy. Señor… envíame." Y cerramos con la Palabra. Y desde hoy… cada uno de nosotros… encuentra su función. Y la ejecuta. Sin excusas. Sin retrasos. Sin miedo. Porque la cosecha… ya comenzó.',
      versiculoFinal: '"Porque de la manera que en un cuerpo tenemos muchos miembros, pero no todos los miembros tienen la misma función…" — Romanos 12:4',
    },
  },
];

// ============================================================================
// RESÚMENES EXPRESS — Versión corta de cada slide (1-2 minutos por slide)
// Se activan con el toggle "Express" en la laptop pastora y en el teleprompter TV.
// Cada resumen: 1 idea central + 3 puntos accionables + 1 transición.
// ============================================================================

export const RESUMENES_NOTAS = {
  'portada': {
    idea: 'Hoy esta iglesia cruza una línea: del espectador al obrero.',
    puntos: [
      'Dios no nos llamó a venir los domingos a cumplir — nos llamó a edificar una generación.',
      'Hoy se termina la iglesia espectadora. Hoy comienza la iglesia que trabaja.',
      'Vamos a ver tres cosas: el QUÉ, el CÓMO y tu rol.',
    ],
    transicion: 'Antes de avanzar, vamos a ver el mapa completo.',
  },
  'indice': {
    idea: 'El índice no es decoración, es dirección.',
    puntos: [
      '29 páginas, 9 puertas, 7 semanas — todo con propósito.',
      '4 partes: Fundamentos, Puertas, Liderazgo, Estrategia. Nada se salta.',
      'Lo que despierta tu curiosidad revela dónde Dios quiere usarte.',
    ],
    transicion: 'Antes del sistema, está el llamado.',
  },
  'invitacion': {
    idea: 'Esto nació en oración y madrugadas — no es información, es estrategia.',
    puntos: [
      'Hay vidas, sueños y puertas esperando que tú obedezcas.',
      'Cosas buenas sin orden cansan; con orden multiplican.',
      'Subraya lo que te confronte — eso revela tu primer paso.',
    ],
    transicion: '¿Para quién es este manual? La respuesta te incluye a ti.',
  },
  'para-quien-promesa': {
    idea: 'Léelo con lápiz, oración y equipo — desde tu rol.',
    puntos: [
      'Tres acciones: subraya impacto, asterisco lo que harás, signo de pregunta lo que confronta.',
      'Si aplicamos con disciplina, vamos a ver fruto.',
      'Define hoy desde qué rol lo lees: pastor, líder, mentor, servidor o nuevo creyente.',
    ],
    transicion: 'Veamos el sistema completo en una sola imagen.',
  },
  'intro-manual': {
    idea: 'Pasamos de iglesia de actividades a iglesia de procesos.',
    puntos: [
      '5 pilares: corazón, base bíblica, proceso, herramientas, estrategia.',
      'Si falla un pilar, todo se debilita — Dios nos dio sistema completo.',
      'No queremos iglesia ocupada, queremos iglesia efectiva.',
    ],
    transicion: 'Ahora el primer pilar: nuestra identidad.',
  },
  'identidad': {
    idea: 'Tu identidad es lo que eres cuando nadie te ve.',
    puntos: [
      'Visión: levantar discípulos que se conviertan en líderes.',
      'Misión: 4 pasos en orden — evangelizar, consolidar, discipular, enviar.',
      '7 valores: Presencia de Dios, Amor por las almas, Relaciones, Formación, Multiplicación, Orden, Excelencia.',
    ],
    transicion: 'Esto no nació en una junta — está en Nehemías 3.',
  },
  'lema-nehemias': {
    idea: 'Cosecha y Restitución no es lema — es palabra profética.',
    puntos: [
      'Nehemías comenzó por las puertas — sin puertas no hay protección.',
      'Trabajo por zonas: cada quien sabía qué proteger.',
      'Las brechas no son demonios — son procesos incompletos.',
    ],
    transicion: 'Ahora el sistema concreto: la Ley de las 7 Semanas.',
  },
  'ley-7-semanas': {
    idea: 'Siete decisiones con disciplina parten un año en dos.',
    puntos: [
      'S1 Preparación · S2 Invasión · S3 MCD · S4 NPT · S5 Liberación · S6 Bendición · S7 Sanidad.',
      'No se negocian, no se cambian, no se saltan — efecto dominó.',
      '"La visión no es abstracta, es concreta. Lo concreto produce resultados."',
    ],
    transicion: 'Ahora el motor: el Modelo CAP.',
  },
  'modelo-cap': {
    idea: 'Crecer sin estructura es perder lo que Dios envía.',
    puntos: [
      'CAP = Consolidación y Activación por Puertas. El don es la llave.',
      '3 niveles: Formación, Seguimiento, Crecimiento.',
      'Sin CAP se pierden. Con CAP cada uno tiene proceso, líder, puerta y destino.',
    ],
    transicion: 'Ahora el ritmo que activa todo: Tiempo 3, Operación 72.',
  },
  'operacion-72': {
    idea: 'Tiempo 3 es el patrón de Dios — 72 horas deciden todo.',
    puntos: [
      '3 días al nuevo creyente · 21 días LBS · 72 horas decide · 3 meses consolida.',
      'El problema no es falta de gente — es falta de respuesta a tiempo.',
      'Mes 1 afirma llamado · Mes 2 entiende servicio · Mes 3 activa para ganar.',
    ],
    transicion: 'Ahora la columna vertebral: las 9 puertas.',
  },
  'las-9-puertas': {
    idea: '9 puertas = diseño de Dios. Cada necesidad tiene una respuesta.',
    puntos: [
      'Enfermo→P6 · Crisis→P3 · Petición→P1 · Nuevo creyente→P5 · Visitante→P2 · Retiro→P4 · Comunicación→P7 · Recursos→P8 · Evento→P9.',
      'Cada puerta requiere 4: líder, asistente, equipo, metas.',
      'Cada miembro un lugar, cada necesidad una respuesta, cada vida un proceso.',
    ],
    transicion: 'Empezamos con la base: Puerta 1.',
  },
  'puerta-1': {
    idea: 'Sin oración no hay iglesia — solo edificio.',
    puntos: [
      'Cubrir: pastor, líderes, visitantes, células.',
      '3 acciones diarias: pastor por nombre, visitantes, células con su líder.',
      'La oración no es religiosa — es estratégica.',
    ],
    transicion: 'Donde hay oración, llegan personas. La Puerta 2.',
  },
  'puerta-2': {
    idea: 'Aquí nadie entra y sale igual.',
    puntos: [
      'El primer día: saludo, tarjeta, MCD+NPT, mentor — ese mismo día.',
      'Proceso: visión, Espíritu Santo, LBS, bautismo, retiro, 3 meses.',
      'El padre del pródigo no esperó al lunes — corrió.',
    ],
    transicion: 'Para crisis urgentes: Puerta 3.',
  },
  'puerta-3': {
    idea: 'Hay dolores que llegan un martes a las 3 AM. Aquí responderemos.',
    puntos: [
      'Crisis: muerte, divorcio, adicción, suicidio.',
      '4 acciones: oración, consejería 30 min, canalizar, acompañar 7 días.',
      'No reemplaza al pastor — sostiene al alma hasta que llegue.',
    ],
    transicion: 'Heridas profundas necesitan retiro: Puerta 4.',
  },
  'puerta-4': {
    idea: 'Hay batallas que se ganan en encuentro profundo, no en un culto.',
    puntos: [
      'LBS: Liberación rompe cadenas · Bendición afirma identidad · Sanidad restaura alma — 21 días.',
      'No se salta ninguna fase — proceso completo.',
      'Sin valle no hay autoridad. Sin proceso no hay transformación.',
    ],
    transicion: 'Después del retiro hay que formar. Puerta 5.',
  },
  'puerta-5': {
    idea: '3 meses deciden 30 años.',
    puntos: [
      'Mentor = puente entre evangelio y vida real.',
      '3 hábitos: reunión semanal, mensaje semanal, oración por nombre.',
      'Pablo a Timoteo a hombres fieles a otros — 4 generaciones.',
    ],
    transicion: 'A los que se alejaron, vamos por ellos. Puerta 6.',
  },
  'puerta-6': {
    idea: 'Si solo cuidamos al que viene el domingo, perdemos al que dejó de venir el lunes.',
    puntos: [
      '5 frentes semanales: enfermo, ausente, amigo, hogar nuevo, alejado.',
      'Mensaje: "No estás solo. Tu vida importa."',
      'La gente no se pierde cuando alguien va por ellos.',
    ],
    transicion: 'El mensaje debe salir del templo. Puerta 7.',
  },
  'puerta-7': {
    idea: 'Una persona puede llorar a las 2 AM y abrir su teléfono. ¿Qué encontrará?',
    puntos: [
      'Multimedia no es lujo — es misión.',
      'Cada culto editado y publicado en menos de 48 horas.',
      'Si no fluimos en lo digital, otros ocuparán ese púlpito.',
    ],
    transicion: 'Para sostenerlo necesitamos recursos. Puerta 8.',
  },
  'puerta-8': {
    idea: 'Visión sin recursos termina en frustración.',
    puntos: [
      '3 inventarios siempre completos: Biblias, manuales, materiales.',
      'Si llegan 20 personas, ¿hay 20 Biblias? La demora cuesta almas.',
      'Lo que se administra con orden alcanza más.',
    ],
    transicion: 'Para multitudes, planificación: Puerta 9.',
  },
  'puerta-9': {
    idea: 'Los momentos de Dios no se improvisan, se planifican.',
    puntos: [
      '4 datos por escrito: fecha, equipo, presupuesto, meta de almas.',
      'En un evento todas las puertas trabajan — sinfonía completa.',
      'La diferencia con un mover de Dios se mide en testimonios después.',
    ],
    transicion: 'Cerramos las 9 puertas. Ahora el sistema completo.',
  },
  'estructura-general': {
    idea: 'Sin estructura todo se diluye.',
    puntos: [
      'Pastor → Coordinador → 9 líderes → Equipos → Iglesia.',
      'Células DETECTAN (radar). Puertas RESPONDEN (equipo).',
      'Flujo: llega → P2 recibe → célula → discipulado → retiro → sirve → líder → abre célula.',
    ],
    transicion: 'En el centro: el líder de puerta.',
  },
  'lider-puerta': {
    idea: 'Tu liderazgo se mide por los líderes que dejas formados.',
    puntos: [
      'NO es jefe que manda y grita — si te tienen miedo, eres presión con título.',
      '4 funciones: Cuidar, Ubicar, Activar, Desarrollar.',
      'Un líder verdadero crea capacidad, no dependencia.',
    ],
    transicion: 'Para formar al nuevo creyente: el mentor.',
  },
  'mentor': {
    idea: 'El mentor es puente entre el evangelio y la vida real.',
    puntos: [
      '4 propósitos: afirmar fe, cambiar estilo, integrar, preparar para servir.',
      'Perfil: oración, amor por almas, base bíblica, paciencia, testimonio limpio.',
      '4 responsabilidades semanales: contacto, reunión 1h, oración por nombre, integración.',
    ],
    transicion: 'El mentor sigue un mapa: Discipulado en 8 Semanas.',
  },
  'discipulado-8-semanas': {
    idea: 'Las primeras 8 semanas deciden si echa raíces o se seca.',
    puntos: [
      'Raíces (S1-S4): Salvación, Oración, Biblia, Iglesia.',
      'Cosecha (S5-S8): Cambio de vida, Visión, Don, Liderazgo.',
      'En 8 semanas: "Me convertí el domingo" → "Estoy formando a alguien más."',
    ],
    transicion: '¿Cuándo está realmente consolidado?',
  },
  'consolidado-puerta': {
    idea: 'No queremos personas presentes — queremos personas firmes.',
    puntos: [
      '4 indicadores: Ubicación, Activación, Cobertura, Proceso.',
      'Si falta UNO, no está consolidado — está de paso.',
      'Jesús no levantó una multitud, levantó doce. Y cambió el mundo.',
    ],
    transicion: 'Para sostener el sistema: la reunión mensual.',
  },
  'reunion-supervisores': {
    idea: '30 minutos donde el sistema vive o se muere.',
    puntos: [
      'Agenda: 5+5+10+5+5 (inicio, supervisor, detección, ajustes, activación).',
      'Tu rol: ENFOCAR, CORREGIR, ACTIVAR. No moderadora, no secretaria.',
      '3 frases cultura: "Vamos al punto", "¿Cuál es el siguiente paso?", "Antes del lunes."',
    ],
    transicion: 'Una sola meta: formar líderes que multipliquen.',
  },
  'estrategia-ganar': {
    idea: 'No queremos iglesia que intenta — queremos iglesia que ejecuta.',
    puntos: [
      'Meta: 40 líderes formados, activos, multiplicando.',
      'Cada 2 semanas debe haber movimiento medible.',
      'Una persona bien atendida → 90 días → líder.',
    ],
    transicion: 'Cuando entra en cultura, ya no crece por eventos — crece por ADN.',
  },
  'cultura-cierre': {
    idea: 'Hoy esta iglesia cruza una línea — entramos en CULTURA.',
    puntos: [
      'Células detectan, Puertas responden, Liderazgo supervisa, Dios transforma.',
      'Año de Cosecha y Restitución — no por emoción, por disciplina.',
      'Cultura es lo que haces cuando nadie te está mirando.',
    ],
    transicion: 'Escribe 3 líneas: PUERTA · NOMBRE+APELLIDO · FECHA. La cosecha ya comenzó.',
  },
};
