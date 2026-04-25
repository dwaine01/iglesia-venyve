/**
 * Contenido completo de la presentacion extraido de 13 documentos.
 *
 * IMPORTANTE - Logica de las notas (revisada 2026-04-26 v3):
 *  - Lo que ve la AUDIENCIA en pantalla = visual limpio, palabras clave.
 *  - Las NOTAS del pastor / Notas TV = guion para PREDICAR con CORAZON.
 *    Cada nota busca CONECTAR, REFLEXIONAR, IMPACTAR y MOVER.
 *
 *  REGLA DE ORO: NO DEJAR NADA A LA IMAGINACION DE LA PASTORA.
 *      - Cada frase es una linea LISTA para decir en voz alta.
 *      - Cada ilustracion trae conclusion incluida (no es solo "Pablo a Timoteo").
 *      - Cada aplicacion tiene: NUMERO + TIEMPO + ACCION + DESTINATARIO.
 *        NO: "Comprometete con un tiempo de oracion".
 *        SI: "Manana antes de las 7am, ora 15 minutos por 3 nombres concretos."
 *
 *  Estructura de cada nota (6 secciones):
 *      abrir       -> linea de apertura COMPLETA, lista para leer
 *      decir       -> 3-4 declaraciones cerradas (no ideas abiertas)
 *      ilustrar    -> historia/imagen CON conclusion explicita
 *      preguntar   -> pregunta concreta y directa
 *      aplicar     -> accion con numero, tiempo y verbo de mando
 *      transicion  -> frase puente cerrada al siguiente slide
 *
 *  REGLA UNIVERSAL (mantener):
 *      - NO usar fechas (enero, este ano, hace 6 meses)
 *      - NO mencionar nombres especificos
 *      - SI usar tiempos genericos pero concretos:
 *          "esta semana", "antes del proximo culto",
 *          "en menos de 72 horas", "manana en la manana".
 */

// URLs de las imagenes oficiales
export const LOGO_IGLESIA = 'https://customer-assets.emergentagent.com/job_cool-kare-8/artifacts/7lfcbcyw_logo%20casa%20e%20oracion%20ven%20y%20ve.png';
export const IMAGEN_INTRODUCCION = 'https://customer-assets.emergentagent.com/job_cool-kare-8/artifacts/i5szritp_12%20introducion%20del%20manual%20de%20la%20ley%20de%20la%207%20semanas.png';
export const IMAGEN_LEY_7_SEMANAS = 'https://customer-assets.emergentagent.com/job_cool-kare-8/artifacts/xfnntujy_13%20la%20ley%20de%20las%207%20semanas.png';

export const LAS_9_PUERTAS = [
  {
    num: 1,
    nombre: 'Intercesion Profetica',
    resumen: 'Cobertura espiritual del sistema celular',
    color: 'from-purple-600 to-indigo-700',
    accent: '#7c3aed',
    icon: 'HandHeart',
    nehemias: 'Puerta de la Fuente (Neh 3:15)',
    proposito: 'Cubrir espiritualmente todo el sistema celular.',
    funciones: [
      'Orar por el pastor y los lideres',
      'Orar por visitantes y nuevos creyentes',
      'Orar por las celulas',
      'Guerra espiritual por barrios',
    ],
    actividades: ['Reuniones de oracion', 'Vigilias', 'Cadenas de oracion', 'Intercesion antes de los cultos', 'Ayunos'],
    estructura: ['Coordinador de intercesion', 'Intercesores asignados por celulas'],
    ministerios: ['Grupo pastoral', 'Intercesores', 'SUAD', 'Lideres', 'Alabanza', 'Danza'],
    indicadores: ['Ambiente espiritual fuerte', 'Crecimiento espiritual en las celulas', 'Testimonios de respuesta a la oracion'],
  },
  {
    num: 2,
    nombre: 'Bienvenida / Consolidacion',
    resumen: 'Fiesta de bienvenida al Reino',
    color: 'from-[#C8A951] to-[#E2CF8A]',
    accent: '#C8A951',
    icon: 'DoorOpen',
    nehemias: 'Puerta del Pescado (Neh 3:3)',
    proposito: 'Integrar y afirmar a los nuevos creyentes en la iglesia.',
    proceso: [
      'Se realiza despues de la conversion mediante los libros MCD y NPT',
      'Se presenta la vision de la iglesia',
      'Se ministra el Espiritu Santo',
      'Se formaliza la membresia',
      'Inicia LBS en grupo pequeno (casa)',
      'Es bautizado',
      'Participa en un retiro espiritual',
      'Recibe discipulado de consolidacion (3 meses)',
    ],
    bienvenida: ['Transporte', 'Recepcion en la puerta con amor', 'Entrega de tarjeta de informacion', 'Conexion con el equipo de bienvenida', 'Entrega de obsequios (libros MCD y NPT)'],
    ministerios: ['Ujieres', 'Transporte', 'Mentores de MCD y NPT', 'Mentores de 3 meses', 'Ejecutiva de retiros LBS', 'Multimedia'],
  },
  {
    num: 3,
    nombre: 'Cuidado Pastoral Inmediato',
    resumen: 'Atencion, consejeria y acompanamiento',
    color: 'from-rose-500 to-pink-600',
    accent: '#e11d48',
    icon: 'Heart',
    nehemias: 'Puerta de las Ovejas (Neh 3:1-2)',
    proposito: 'Atender personas que necesitan apoyo espiritual urgente.',
    responsabilidades: ['Oracion personal', 'Consejeria basica', 'Canalizar a discipulado', 'Acompanamiento espiritual'],
    actividades: ['Reuniones de cuidado pastoral', 'Seguimiento espiritual', 'Oracion personalizada'],
    ministerios: ['Grupo pastoral', 'Ministerio de misiones'],
  },
  {
    num: 4,
    nombre: 'Retiros y Encuentros (LBS)',
    resumen: 'Liberacion, bendicion y sanidad',
    color: 'from-emerald-600 to-teal-700',
    accent: '#059669',
    icon: 'Mountain',
    nehemias: 'Puerta del Valle (Neh 3:13)',
    proposito: 'Facilitar encuentros profundos con Dios.',
    actividades: ['Retiros espirituales', 'Encuentros de restauracion', 'Jornadas de oracion', 'Talleres espirituales'],
    responsabilidades: ['Organizacion logistica', 'Preparacion espiritual', 'Seguimiento de participantes'],
    ministerios: ['Grupo pastoral', 'Ujieres', 'Maestros de ninos', 'Cocina', 'Multimedia'],
    tiempo: 'LBS: tratamiento de 3 semanas (21 dias) - liberacion, bendicion y sanidad.',
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
    responsabilidades: ['Discipulado uno a uno', 'Formacion biblica', 'Seguimiento espiritual'],
    actividades: ['Grupos de discipulado', 'Estudios biblicos'],
    ministerios: ['Mentores MCD y NPT', 'Mentores de 3 meses', 'Mentores LBS', 'Lideres de celulas', 'Maestros de ninos', 'Maestros de discipulado', 'Maestros de liderazgo'],
  },
  {
    num: 6,
    nombre: 'Visitacion Pastoral',
    resumen: 'Cuidado fuera del templo',
    color: 'from-orange-500 to-amber-600',
    accent: '#f97316',
    icon: 'HouseIcon',
    nehemias: 'Puerta del Muladar (Neh 3:14) - Limpieza y santidad',
    proposito: 'Extender el cuidado pastoral fuera del templo y conquistar territorios para Cristo.',
    responsabilidades: ['Visitar enfermos', 'Visitar ausentes', 'Visitar amigos de la iglesia', 'Orar en los hogares', 'Restaurar miembros alejados'],
    actividades: ['Visitas pastorales', 'Oracion en hogares', 'Acompanamiento familiar'],
    ministerios: ['Ministerio de bienvenida', 'Parejas mentoras', 'Ministerio pastoral'],
    operacion72: 'Llamadas, visitas a personas nuevas, enfermos, seguimiento a no comprometidos, restaurar ausentes, orar por familias.',
  },
  {
    num: 7,
    nombre: 'Multimedia y Comunicacion',
    resumen: 'Tecnologia, redes sociales, teatro',
    color: 'from-fuchsia-600 to-pink-700',
    accent: '#c026d3',
    icon: 'Megaphone',
    nehemias: 'Puerta de las Aguas (Neh 3:26) - La Palabra',
    proposito: 'Apoyar la comunicacion y ensenanza del ministerio.',
    responsabilidades: ['Transmision de cultos', 'Manejo de redes sociales', 'Produccion audiovisual', 'Apoyo a celulas digitales', 'Discipulado en linea (Zoom)'],
    actividades: ['Grabacion de ensenanzas', 'Publicacion de contenido', 'Comunicacion digital'],
    ministerios: ['Teatro', 'Fotografia y video'],
  },
  {
    num: 8,
    nombre: 'Administracion y Recursos',
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
    responsabilidades: ['Organizar congresos', 'Planificar conferencias', 'Coordinar eventos anuales', 'Capacitacion ministerial'],
    actividades: ['Congresos anuales', 'Seminarios de liderazgo', 'Eventos especiales', 'Retiros de lanzamiento', 'Mantenimiento', 'Pro-templo'],
    ministerios: ['Grupo pastoral', 'Multimedia', 'Mantenimiento', 'Secretarias', 'Finanzas', 'Mentores y maestros', 'Ujieres', 'Cocina'],
  },
];

export const LAS_7_SEMANAS = [
  { num: 1, titulo: 'Preparacion - Oracion Profetica', sub: 'Organizacion', color: 'from-green-500 to-emerald-600' },
  { num: 2, titulo: 'Invasion', sub: 'Contactados', color: 'from-teal-600 to-cyan-700' },
  { num: 3, titulo: 'MCD', sub: 'Mi Caracter Deseado · Asistencia', color: 'from-blue-500 to-indigo-600' },
  { num: 4, titulo: 'Naci Para Triunfar', sub: 'NPT', color: 'from-yellow-500 to-amber-600' },
  { num: 5, titulo: 'Liberacion', sub: 'LBS 1', color: 'from-orange-500 to-red-500' },
  { num: 6, titulo: 'Bendicion', sub: 'LBS 2', color: 'from-amber-700 to-orange-800' },
  { num: 7, titulo: 'Sanidad', sub: 'LBS 3', color: 'from-indigo-600 to-purple-700' },
];

// ============================================================================
// SLIDES - 28 slides alineados al manual impreso
// Notas pastorales CONCRETAS: nada queda a la imaginacion.
// ============================================================================

// Notas pastorales por puerta (slides 12-20)
const NOTAS_PUERTAS = {
  1: {
    abrir: 'Antes de hablar de estrategias, hablemos del altar. Ninguna de las nueve puertas que veremos hoy abre sin oracion. Ninguna.',
    decir: [
      'La Puerta 1 cubre espiritualmente al pastor, a los lideres, a los visitantes y a cada celula del sistema. Sin esa cobertura, lo demas se cae.',
      'Tres acciones diarias: orar por el pastor por nombre, orar por los visitantes del domingo anterior, y orar por cada celula con su lider.',
      'Cuando un equipo dedica 30 minutos diarios a interceder, en menos de tres meses la atmosfera de la iglesia cambia. Es ley espiritual.',
    ],
    ilustrar: 'Nehemias reconstruyo la Puerta de la Fuente antes que ninguna otra. Sabia que sin agua no hay ciudad. Hoy te digo: sin oracion no hay iglesia, solo edificio bonito con sillas vacias por dentro.',
    preguntar: 'Cuando fue la ultima vez que tu equipo de Puerta 1 se reunio a orar mas de 30 minutos seguidos, sin agenda, solo a buscar el rostro de Dios?',
    aplicar: 'Esta semana, agenda UN dia fijo (lunes o jueves) de 7 a 8 PM para vigilia de Puerta 1. Convoca minimo a 5 intercesores y reparte una lista escrita con: 1) nombre del pastor, 2) los 3 ultimos visitantes, 3) las celulas que estan en crisis.',
    transicion: 'Donde hay oracion, llegan personas nuevas. La primera puerta que tocan no es esta: es la Puerta 2.',
  },
  2: {
    abrir: 'Hay personas que llegaron buscando a Dios y se fueron sin que nadie las mirara a los ojos. Esa iglesia NO somos nosotros.',
    decir: [
      'La Bienvenida no es protocolo: es la primera version del rostro del Padre que esa persona va a ver.',
      'En el primer dia el visitante recibe: saludo en la puerta, tarjeta con sus datos, libro MCD, libro NPT y mentor asignado. No al mes. El mismo dia.',
      'Despues del primer dia viene el proceso completo: vision de la iglesia, ministracion del Espiritu Santo, membresia, LBS, bautismo, retiro y 3 meses de seguimiento. Saltarse uno corta el proceso.',
    ],
    ilustrar: 'El padre del hijo prodigo no le dijo "agenda una cita para el lunes". Corrio. Lo abrazo. Le puso anillo en el dedo y mato el becerro. Ese mismo dia. Asi de rapida y completa es la bienvenida del Reino.',
    preguntar: 'Si HOY entrara por esa puerta una persona quebrantada... saldria con un libro en la mano y un mentor en el celular, o solo con un "Dios te bendiga"?',
    aplicar: 'Antes del proximo culto, prepara 10 kits fisicos con: libro MCD + libro NPT + tarjeta de bienvenida + boligrafo. Asigna 2 ujieres entrenados para entregarlos. Cada visitante sale con kit en mano. Cero excepciones.',
    transicion: 'Pero algunas almas llegan con heridas que no esperan al lunes. Ahi entra la Puerta 3.',
  },
  3: {
    abrir: 'Hay un dolor que no avisa. Llega un martes a las 3 de la manana. Y la iglesia tiene que estar lista para responder esa misma noche.',
    decir: [
      'Cuidado Pastoral Inmediato es la primera linea de respuesta cuando alguien tiene una crisis: muerte, divorcio, adiccion, suicidio.',
      'Cuatro acciones concretas: oracion personal por telefono, consejeria basica de 30 minutos, canalizacion al discipulado y acompanamiento por 7 dias.',
      'Este equipo NO reemplaza al pastor. Sostiene al alma mientras llega el pastor, para que cuando el pastor llegue, encuentre vida y no funeral.',
    ],
    ilustrar: 'Las ovejas heridas no buscan un programa de los domingos. Buscan a alguien que se agache hasta el suelo donde estan tiradas, las cargue en hombros y las lleve al rebano. Eso es Puerta 3 con piel humana.',
    preguntar: 'Si esta noche un miembro tuyo intenta hacerse dano... su familia tiene un numero de telefono de Puerta 3 guardado, o van a llamar al 911 porque no saben a quien llamar primero?',
    aplicar: 'Esta semana arma una tarjeta de bolsillo con 3 telefonos de Puerta 3 (lider + 2 asistentes). Imprime 100 copias. Reparte una a cada lider, cada anciano y cada miembro fundador antes del proximo culto.',
    transicion: 'Cuando la herida es mas profunda, no basta una llamada. Hace falta apartarse 21 dias con Dios. Eso es Puerta 4.',
  },
  4: {
    abrir: 'Hay batallas espirituales que no se ganan en el culto del domingo. Se ganan en un retiro, lejos del telefono, frente a frente con Dios.',
    decir: [
      'LBS significa Liberacion, Bendicion y Sanidad. Son 21 dias divididos en 3 retiros de 7 dias cada uno.',
      'Liberacion rompe cadenas generacionales. Bendicion declara identidad y proposito. Sanidad cierra heridas del alma. Tres fases. Sin saltarse ninguna.',
      'Cada retiro debe terminar con testimonios escritos de cada participante: que perdono, que recibio, en que cambio. Sin testimonios escritos, no hay evidencia de fruto.',
    ],
    ilustrar: 'David escribio sus salmos mas profundos en el valle, no en el palacio. Jose se hizo gobernador en la carcel, no en la casa de Potifar. Jesus se preparo 40 dias en el desierto antes del ministerio. Sin valle, no hay altura. El retiro es el valle.',
    preguntar: 'Cuantas personas en tu congregacion estan cargando cadenas que solo se rompen en un retiro de 21 dias... y nadie las ha invitado todavia porque no hay fecha?',
    aplicar: 'Antes del proximo domingo, escribe en tu libreta los nombres de 5 personas que necesitan LBS. Llama a las 5 personalmente esta semana. Frase exacta: "Hay un retiro que cambia vidas y senti que tu nombre debia estar en la lista."',
    transicion: 'Cuando regresan transformadas, no podemos abandonarlas a su suerte. Hay que formarlas. Esa es la Puerta 5.',
  },
  5: {
    abrir: 'Un nuevo creyente sin mentor es como un bebe en la nieve. Puede sobrevivir solo... pero pocos lo logran. La estadistica del Reino es brutal en eso.',
    decir: [
      'Los primeros 3 meses despues de la conversion DECIDEN si esa persona se queda 30 anos o se va en 30 dias. No exagero.',
      'El mentor no es maestro de Biblia. Es puente humano entre el evangelio y la realidad: el matrimonio, el trabajo, el dinero, los hijos.',
      'Un mentor activo se reune semanalmente con su discipulo, le manda un mensaje cada lunes y ora por el cada noche por nombre. Sin esos tres habitos, no es mentor: es contacto.',
    ],
    ilustrar: 'Pablo le dijo a Timoteo: "Lo que has oido de mi, encarga a hombres fieles que sean idoneos para ensenar tambien a otros." En un solo versiculo Pablo planto cuatro generaciones: Pablo a Timoteo, Timoteo a hombres fieles, hombres fieles a otros, y otros a una cuarta generacion. Ese es el ADN del mentor.',
    preguntar: 'Si Dios te pidiera cuentas hoy mismo... a quien estas formando con tu vida y no solo con tu sermon? Si la respuesta es "a nadie", ahi esta tu primera asignacion de la semana.',
    aplicar: 'Esta semana escoge UNA persona que se convirtio en los ultimos 3 meses. Llamala manana. Frase exacta: "Quiero comprometerme contigo 8 semanas. Una hora a la semana, mismo dia, misma hora." Pon la primera reunion en el calendario antes de colgar.',
    transicion: 'Y a los que se ausentaron, tampoco los abandonamos. Vamos NOSOTROS a sus casas. Esa es la Puerta 6.',
  },
  6: {
    abrir: 'Si la iglesia solo cuida al que viene los domingos, va a perder al que dejo de venir el lunes. Y al que se alejo en silencio, alguien lo dejo ir sin pelear.',
    decir: [
      'Visitacion Pastoral es la iglesia ROMPIENDO sus paredes y entrando a los hogares de su gente.',
      'Cinco frentes obligatorios cada semana: visitar 1 enfermo, visitar 1 ausente del ultimo mes, visitar 1 amigo de la iglesia, orar en 1 hogar nuevo, restaurar a 1 miembro alejado.',
      'Cada visita lleva un mensaje claro: "Tu vida le importa a Dios y a esta iglesia, por eso hoy estoy en tu puerta."',
    ],
    ilustrar: 'Nehemias llamo a esta puerta del Muladar: el lugar donde se botaba la basura de Jerusalen. Y precisamente ahi reconstruyo. Donde habia desperdicio y olor, ahora hay limpieza y orden. Eso mismo llevamos a cada hogar quebrantado: limpieza espiritual.',
    preguntar: 'Cuantos miembros se han alejado en los ultimos 3 meses sin que nadie tome el telefono y diga: "Te extranamos, queremos pasar a verte el sabado"? Esos son los nombres que Dios te va a pedir cuentas.',
    aplicar: 'Antes del proximo culto, lista los 7 ausentes del ultimo mes. Asigna 1 lider a cada nombre. Cada lider hace 1 llamada de 5 minutos esta semana con esta frase: "Te extranamos, no llamo para juzgarte sino para preguntarte como estas."',
    transicion: 'Y el mensaje que nace en el altar tiene que llegar a cada pantalla del mundo. Esa es la Puerta 7.',
  },
  7: {
    abrir: 'Hoy una persona puede llorar sola a las 2 de la manana, abrir su telefono y buscar una palabra. Esa palabra debe ser la nuestra y debe estar publicada.',
    decir: [
      'Multimedia no es un lujo de iglesia moderna. Es el puente entre el mensaje del altar y la generacion que vive en la pantalla.',
      'La iglesia ya no cierra el domingo a las 12 del mediodia. Vive 24 horas al dia, 7 dias a la semana, en cada video, predica subida y testimonio publicado.',
      'Cada culto debe estar editado y publicado en menos de 48 horas. Cada predica debe tener miniatura, titulo y descripcion clara. Si no, se pierde el alcance.',
    ],
    ilustrar: 'Nehemias llamo a la suya Puerta de las Aguas, simbolo de la Palabra. Hoy las aguas corren por wifi. Si nuestra senal no esta ahi, otros estan ocupando ese pulpito digital y formando a nuestra gente con doctrina ajena.',
    preguntar: 'La predica del domingo pasado... cuantas personas pudo tocar el martes en la noche si hubiera estado publicada? Y cuantas no la veran nunca porque nadie la subio?',
    aplicar: 'Esta semana asigna por nombre UN responsable fijo de Multimedia. Su acuerdo escrito: cada culto editado y publicado en menos de 48 horas en YouTube + Instagram + Facebook. Sin excepciones. Sin atrasos.',
    transicion: 'Y nada de esto se sostiene sin recursos en mano. La Puerta 8 es la que provee esas herramientas.',
  },
  8: {
    abrir: 'La vision sin recursos termina en frustracion y queja. Por eso Dios siempre proveyo logistica antes de cada gran movimiento de su pueblo.',
    decir: [
      'Administracion y Recursos no es contar dinero en una oficina. Es abrir camino fisico para que cada alma encuentre Biblia, manual y herramienta cuando llega.',
      'Tres inventarios deben estar siempre completos: Biblias para nuevos creyentes, manuales de discipulado para mentores y materiales de las 9 puertas para lideres.',
      'Lo que se administra con orden alcanza al doble de personas. Lo que se administra sin orden se gasta sin fruto y nadie sabe en que.',
    ],
    ilustrar: 'Nehemias llamo a esta Puerta del Caballo. Los caballos son simbolo de guerra. Y ningun ejercito en la historia ha ganado una guerra sin logistica detras. Tampoco la iglesia gana guerra espiritual sin Biblias en mano.',
    preguntar: 'Si manana llegan 20 nuevos creyentes... hay 20 Biblias listas para entregar? hay 20 manuales? hay 20 boligrafos? O les vamos a decir "vuelvan la otra semana" y los perdemos en el camino?',
    aplicar: 'Esta semana, Puerta 8 hace inventario fisico: cuenta exactamente cuantas Biblias, cuantos manuales y cuantos boligrafos hay. Lo que falte para llegar a 30 unidades, se compra antes del proximo culto. Reporta el numero al pastor el sabado.',
    transicion: 'Y para encender corazones en masa, Dios siempre uso momentos clave. La Puerta 9 los planifica con disciplina.',
  },
  9: {
    abrir: 'Hay momentos que cambian a una iglesia para siempre: un congreso, un retiro de lanzamiento, una noche de gloria. Esos momentos no se improvisan tres semanas antes.',
    decir: [
      'Congresos y Eventos Especiales son los puntos de inflexion donde Dios acelera de un solo golpe lo que el sistema construye semana a semana.',
      'Cada evento debe tener cuatro datos por escrito antes de promocionarse: fecha, equipo responsable, presupuesto en numeros y meta de almas alcanzadas.',
      'En un evento se cruzan todas las puertas: Pastoral predica, Multimedia transmite, Finanzas administra, Cocina alimenta, Ujieres reciben. Es la sinfonia completa.',
    ],
    ilustrar: 'Nehemias llamo a la suya Puerta Oriental, por donde entra el Rey de gloria. Cada congreso tuyo debe abrir cielos sobre tu congregacion, no solo llenar bancas y vender camisetas. La diferencia se mide en testimonios escritos despues del evento.',
    preguntar: 'El proximo evento grande de tu iglesia... va a ser un mover de Dios documentado con testimonios, o un evento mas que la gente olvida en una semana porque no se ministro nada profundo?',
    aplicar: 'Esta semana, define en una hoja: 1) FECHA del proximo evento grande, 2) NOMBRE del coordinador, 3) PRESUPUESTO en dolares, 4) META de almas. Pega esa hoja en la oficina pastoral. Si no esta escrito, no existe.',
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
    description: 'Modelo integral de cuidado, consolidacion, discipulado y multiplicacion',
    notes: {
      abrir: 'Hay momentos en la vida de una iglesia que no se repiten dos veces. Este es uno de esos momentos. Lo que vamos a abrir hoy no es un manual mas: es una puerta espiritual.',
      decir: [
        'Dios no nos llamo a sobrevivir religiosamente cada domingo. Nos llamo a edificar generacionalmente con un modelo claro y replicable.',
        'Lo que tienes en tus manos es fruto de oracion, lagrimas y revelacion. No es teoria de seminario, es estrategia profetica probada.',
        'Vamos a recorrer juntos el QUE, el COMO y CUAL es tu rol especifico. Nadie sale de aqui sin saber su puerta.',
      ],
      ilustrar: 'Hay personas que toda su vida estuvieron cerca del fuego de Dios y nunca se calentaron. Estaban en el culto pero no en la presencia. Hoy te invito a acercarte tanto al fuego, que cuando salgas de este lugar, los que te conocen noten algo diferente en tu rostro.',
      preguntar: 'Vas a recibir esto como una capacitacion mas que se agrega a tu calendario... o como el momento que parte tu ano en dos y marca a la generacion que viene detras de ti?',
      aplicar: 'Ahora mismo, antes de seguir, escribe tu nombre completo en la primera pagina de este manual y la fecha de hoy. Esa firma no es tramite: es pacto entre tu y Dios. Quien firma, se compromete.',
      transicion: 'Antes de caminar por el sistema, revisemos el mapa completo. Porque todos los que llegan lejos, primero saben hacia donde van.',
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
      abrir: 'Antes de hablar de fruto, hablemos de raiz. Antes de la raiz, miremos el mapa. Y antes del mapa, despertemos el hambre de recorrerlo completo.',
      decir: [
        'Este indice no es decoracion. Es la ruta que Dios trazo paso a paso para esta iglesia y para tu vida en este ano.',
        'Son 29 paginas divididas en 4 partes: Fundamentos, las 9 Puertas, Liderazgo y Estrategia. Ninguna parte se salta. Ninguna sobra.',
        'Lo que hoy parece complicado, en 6 semanas sera tu lenguaje natural. Vas a hablar de Puerta 3 como hablas de tu casa.',
      ],
      ilustrar: 'Una iglesia sin indice escrito cae en activismo: muchas reuniones, mucho movimiento, mucho cansancio, poco fruto medible. Hoy rompemos ese ciclo escribiendo paso por paso adonde vamos.',
      preguntar: 'Cuantas veces empezaste algo importante en tu ministerio sin saber adonde ibas exactamente? Eso se acaba en esta pagina, hoy, en este momento.',
      aplicar: 'Pasa el dedo por las 4 secciones del indice. Marca con un asterisco la parte que mas curiosidad despierta en tu corazon. Esa es la parte por la que Dios te trajo hoy. La leeras esta misma semana.',
      transicion: 'Ahora levantamos la mirada del indice al llamado. Antes del sistema, esta la invitacion divina.',
    },
  },

  // ----- 3. UNA INVITACION -----
  {
    id: 'invitacion',
    type: 'invitacion',
    title: 'Una Invitacion',
    subtitle: 'Bienvenido a este Manual',
    notes: {
      abrir: 'Lo que tienes en las manos no nacio de una idea humana ni de una junta administrativa. Nacio en una madrugada de oracion, frente a Dios, con conviccion profetica clara.',
      decir: [
        'Hay vidas concretas esperando ser alcanzadas con tu llamada. Hay suenos esperando ser activados con tu mentoria. Hay puertas esperando ser abiertas con tu obediencia.',
        'Esto no es informacion para acumular en una libreta: es estrategia espiritual para ejecutar esta misma semana.',
        'Hacer cosas buenas sin orden cansa el alma y produce burnout. Hacer cosas buenas con orden multiplica vida y genera fruto que permanece.',
      ],
      ilustrar: 'La Biblia dice: "Donde no hay vision, el pueblo se desenfrena." Hoy no estas perdiendo el tiempo asistiendo a otra reunion. Estas recibiendo una vision por la que valdra la pena vivir los proximos 12 meses sin distraerte.',
      preguntar: 'Cuantas cosas buenas estas haciendo en tu ministerio que NO estan produciendo fruto medible? Y cuanto tiempo mas vas a esperar para corregir el rumbo?',
      aplicar: 'Saca un boligrafo ahora. Cada vez que una frase te impacte el corazon en este manual, subrayala. Al final del dia, repasa lo subrayado: ahi esta tu primer paso de obediencia para esta semana.',
      transicion: 'Ahora la pregunta no es solo QUE hace este manual. Es para QUIEN fue escrito. La respuesta te incluye a ti.',
    },
  },

  // ----- 4. PARA QUIEN + PROMESA -----
  {
    id: 'para-quien-promesa',
    type: 'para-quien-promesa',
    title: 'Para quien es este manual?',
    subtitle: 'Como leerlo · Nuestra Promesa',
    notes: {
      abrir: 'Si estas en este lugar hoy, este manual es para TI. No te lo regalaron por casualidad. Dios te lo entrego con un proposito que vamos a definir esta noche.',
      decir: [
        'Lo vas a leer con tres herramientas: lapiz en la mano, oracion en el corazon y tu equipo al lado. Esa combinacion es la que cambia ministerios.',
        'Tres acciones obligatorias mientras lees: subrayar lo que impacta, marcar con asterisco lo que vas a implementar y poner signo de pregunta a lo que te desafia.',
        'La promesa es directa: si aplicas con disciplina cada parte, en 90 dias veras fruto medible. No por el manual: porque Dios honra los principios que estan adentro.',
      ],
      ilustrar: 'El pastor lo lee como pastor y reorganiza su vision. El mentor lo lee como mentor y mejora su discipulado. El servidor lo lee como servidor y descubre cual es su puerta. El nuevo creyente lo lee y entiende su proceso completo. Cada quien encuentra su nombre en estas paginas.',
      preguntar: 'Vas a leerlo una sola vez como una novela en una tarde... o lo vas a usar como herramienta de trabajo todos los lunes durante todo el ano?',
      aplicar: 'Define HOY mismo, antes de salir de aqui, desde que rol vas a leer este manual. Escribelo en la primera pagina junto a tu nombre. Opciones: pastor, lider, mentor, servidor o nuevo creyente. Esa decision define todo.',
      transicion: 'Antes de los detalles, miremos la fotografia completa del sistema en una sola pagina.',
    },
  },

  // ----- 5. INTRO MANUAL -----
  {
    id: 'intro-manual',
    type: 'intro-manual',
    title: 'Introduccion del Manual',
    subtitle: 'Una Invitacion a ver la iglesia con nuevos ojos',
    notes: {
      abrir: 'Hay una forma vieja de ver la iglesia, basada en programas y eventos. Y hay una forma nueva, basada en procesos y personas. Esta pagina te invita a abrir los ojos del espiritu y ver con la nueva.',
      decir: [
        'Cinco pilares sostienen el sistema completo: el corazon (vision/mision/valores), la base biblica, el proceso claro, las herramientas practicas y la estrategia de ganar.',
        'No basta con tener corazon: hay que tener proceso. No basta con tener proceso: hay que tener herramientas. Y nada de eso vale sin estrategia que mida resultados.',
        'Cada pilar sostiene a los demas como las patas de una silla. Si quitas uno, el sistema entero se cae al suelo. Por eso Dios pidio los cinco, no algunos.',
      ],
      ilustrar: 'Hay vidas concretas esperando ser ALCANZADAS con un mensaje. Hay suenos esperando ser ACTIVADOS con una palabra de fe. Hay puertas espirituales esperando ser ABIERTAS con tu obediencia. La iglesia es la mano que Dios usa para abrir esas puertas a otros.',
      preguntar: 'Cual de los cinco pilares esta mas debil hoy en tu area? Si no puedes responder en 5 segundos, ahi esta tu primera tarea concreta de la semana.',
      aplicar: 'Esta semana, identifica el pilar mas debil de tu area por escrito. Antes del proximo viernes, da UN paso concreto para fortalecerlo y manda una foto de evidencia al lider de tu puerta.',
      transicion: 'Empezamos por el primer pilar: el corazon del sistema. Nuestra identidad como iglesia.',
    },
  },

  // ----- 6. NUESTRA IDENTIDAD -----
  {
    id: 'identidad',
    type: 'identidad',
    title: 'Nuestra Identidad',
    subtitle: 'Vision · Mision · Valores',
    notes: {
      abrir: 'Antes de leer la pantalla, contesta esta pregunta en silencio: quien soy yo cuando nadie de la iglesia me esta viendo? Esa respuesta es tu identidad real, no la del slide.',
      decir: [
        'No buscamos sumar mas asistentes a la lista del domingo. Buscamos formar mas LIDERES que multipliquen. La diferencia no es semantica: es generacional.',
        'Mision en orden estricto: evangelizar, consolidar, discipular y enviar. Saltarse cualquiera produce iglesias grandes pero debiles que crecen y luego se desploman.',
        'Los siete valores no son adornos colgados en la pared del lobby. Son el filtro con el que evaluamos cada decision en cada puerta.',
      ],
      ilustrar: 'Si la iglesia dice que valora el orden y nuestra area es un caos, los valores son solo papel pintado. Si decimos que amamos las almas y no llamamos a un ausente en 30 dias, el amor es solo discurso para los domingos.',
      preguntar: 'Tu area refleja amor activo por las almas? Refleja orden visible? Si la respuesta sincera es no, ahi esta el punto exacto donde Dios quiere comenzar a trabajar contigo.',
      aplicar: 'Esta semana, cada lider hace una hoja con los 7 valores en columna. Al lado de cada uno escribe SI o NO segun como esta su area. Donde haya 3 NO seguidos, ahi se enfoca el plan de los proximos 30 dias.',
      transicion: 'La razon profunda detras de todo este sistema no nacio en una junta. Esta escrita hace 2,500 anos en Nehemias capitulo 3.',
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
      abrir: 'Cosecha y Restitucion. No es un eslogan bonito para una camiseta. Es un mandato profetico. Y los mandatos no se decoran: se obedecen con fechas y resultados.',
      decir: [
        'Nehemias reconstruyo PRIMERO las puertas, antes que las casas y antes que el templo. Sin puertas no hay proteccion, ni orden, ni crecimiento sano.',
        'Asigno el trabajo POR ZONAS. Cada familia sabia exactamente que pedazo del muro reconstruia y a quien protegia. Eso es estructura celular antes del Nuevo Testamento.',
        'Dios prometio devolver lo perdido y multiplicar el fruto cuando hay puertas reconstruidas. Esa promesa es para tu iglesia este mismo ano.',
      ],
      ilustrar: 'En tiempos de Nehemias, los muros de Jerusalen estaban rotos por 70 anos. Hoy nuestras puertas rotas son los procesos sin terminar, las llamadas que se quedan sin hacer y los discipulados que se cortan en la semana 4. Hay que reconstruir cada brecha.',
      preguntar: 'Cuantas puertas espirituales en tu vida y en tu area estan rotas hoy? Y por cuanto tiempo mas vas a vivir con esas grietas abiertas dejando que el enemigo entre por ahi?',
      aplicar: 'Antes del proximo domingo, identifica UN area de tu ministerio que esta rota. Escribe un plan de 30 dias en una hoja con: meta, fecha de inicio, fecha de cierre y 3 acciones concretas. Pega esa hoja en tu agenda.',
      transicion: 'Ahora bajamos del lema profetico al sistema concreto que vamos a ejecutar: la Ley de las 7 Semanas.',
    },
  },

  // ----- 8. LEY DE LAS 7 SEMANAS -----
  {
    id: 'ley-7-semanas',
    type: 'ley-7-semanas',
    title: 'La Ley de las 7 Semanas',
    subtitle: 'Un proceso de crecimiento y formacion',
    notes: {
      abrir: 'Siete semanas. Un calendario sagrado. No siete deseos puestos en una lista, sino siete decisiones que, ejecutadas con disciplina, parten un ano ministerial en dos.',
      decir: [
        'Cada semana tiene UN objetivo concreto: Preparacion, Invasion, MCD, NPT, Liberacion, Bendicion, Sanidad. Saltarse una rompe el efecto domino del proceso.',
        'No es un ritmo religioso para cumplir. Es el ritmo del Reino. Dios siempre opera en tiempos definidos. Quien entiende los tiempos, recoge cosechas a tiempo.',
        'Trabajamos en equipo con UN objetivo unificado por 7 semanas seguidas. La unidad acelera lo que la division retrasa anos enteros.',
      ],
      ilustrar: 'Una semana sin proposito escrito equivale a un mes perdido en el calendario. Pero 7 semanas con objetivo claro y equipo activo producen lo que muchas iglesias no logran en 7 meses de actividad sin orden.',
      preguntar: 'En que semana del proceso suele caerse la gente de tu equipo (semana 3? semana 5?), y que vas a hacer DIFERENTE esta vez para que no vuelvan a caer en el mismo punto?',
      aplicar: 'Antes de salir hoy, define la fecha exacta de inicio de tu primer ciclo de 7 semanas. Marca en tu calendario los 7 lunes consecutivos. Ese sera tu mapa visible cada manana al despertar.',
      transicion: 'Y para conectar las 9 puertas con las 7 semanas, Dios nos dio un motor especifico: el Modelo CAP.',
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
      abrir: 'CAP no es una sigla mas para memorizar. Es la respuesta divina al problema de toda iglesia que crece rapido y se queda sin estructura para sostener ese crecimiento.',
      decir: [
        'CAP significa Consolidacion y Activacion por Puertas. El don que Dios te dio es la llave que abre tu puerta especifica en el Reino.',
        'La iglesia funciona como un cuerpo humano: no todos hacemos lo mismo, pero TODOS somos necesarios. Lo que tu haces nadie mas lo hace igual que tu.',
        'Tres niveles que se sostienen entre si: Formacion (ensenar), Seguimiento (acompanar), Crecimiento (multiplicar). Si quitas uno, los otros dos se derrumban en menos de 6 meses.',
      ],
      ilustrar: 'Sin CAP, la persona entra por la Puerta 2 (bienvenida) y se cae por la Puerta 5 (discipulado) porque nadie la asigno a nadie. Con CAP, cada persona entra con un proceso, un lider asignado por nombre y un destino ministerial claro.',
      preguntar: 'Cuantas personas estan entrando a tu iglesia HOY sin un sistema solido de integracion que las asigne a una puerta y a un mentor? Y a quien le rendiras cuentas el dia que se vayan?',
      aplicar: 'Esta semana, identifica UNA persona en tu lista que llego sin proceso definido. Asignale por escrito: 1) puerta especifica, 2) mentor con nombre y telefono, 3) semana en que comienza. Sin esos 3 datos no es discipulado: es deseo.',
      transicion: 'Y para activar todo este motor, Dios nos da un principio profetico que cambia el ritmo: el Tiempo 3, la Operacion 72.',
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
      abrir: 'Tiempo 3. Tres dias. No es casualidad biblica ni un numero al azar. Es el patron profetico que Dios uso en cada gran movimiento de su historia con su pueblo.',
      decir: [
        'Moises dijo: "en tres dias". Josue dijo: "en tres dias poseeremos la tierra". Jesus dijo: "en tres dias resucitare". Tres veces el mismo patron divino marcado.',
        'Aplicacion practica: en 3 DIAS atendemos al nuevo creyente. LBS dura 3 SEMANAS. Seguimiento intensivo de 3 MESES. Tres ritmos sincronizados.',
        'Mes 1: el llamado se confirma. Mes 2: el privilegio de servir se descubre. Mes 3: predestinado para ganar a otros se activa. Tres meses, tres niveles, una persona transformada.',
      ],
      ilustrar: 'Cuando esperamos 30 dias para llamar a un visitante nuevo, ya lo perdimos en el camino. La estadistica es brutal: en 72 horas se decide si esa persona regresa el siguiente domingo o no. Asi de serio es el principio.',
      preguntar: 'Que pasaria en tu iglesia si cada visitante recibiera una llamada de 5 minutos en menos de 72 horas? cuantos creyentes mas tendrias en 6 meses si solo cumplieran esa regla?',
      aplicar: 'Manana antes de las 12 del mediodia, cada lider revisa su lista de visitantes de los ultimos 7 dias. Llama a cada uno en menos de 72 horas. Frase exacta: "Soy del equipo de bienvenida, llamo solo para preguntarte como estas y orar por ti 3 minutos."',
      transicion: 'Ahora entramos a la columna vertebral del sistema: las 9 puertas que sostienen toda la casa.',
    },
  },

  // ----- 11. LAS 9 PUERTAS (intro) -----
  {
    id: 'las-9-puertas',
    type: 'las-9-puertas',
    title: 'Las 9 Puertas',
    subtitle: 'El sistema completo de activacion',
    notes: {
      abrir: 'Cada necesidad humana tiene una puerta asignada. Cada puerta tiene una respuesta concreta. Y Dios diseno exactamente NUEVE para que ninguna alma quede sin atender en tu iglesia.',
      decir: [
        'Si llega un enfermo se conecta con la Puerta 6. Si llega una crisis se canaliza a la Puerta 3. Si llega una peticion urgente se activa la Puerta 1. Si llega un nuevo creyente se asigna a la Puerta 5.',
        'Si llega un visitante se atiende en la Puerta 2. Para un evento se planifica desde la Puerta 9. Para difusion se llama a la Puerta 7. Para material se pide a la Puerta 8. Para encuentro profundo se invita a la Puerta 4.',
        'Cada una de las 9 puertas debe tener 4 elementos por escrito: UN lider por nombre, UN asistente por nombre, UN equipo de minimo 3 personas y MET-AS anuales medibles. Sin esos 4, no es puerta: es solo un letrero pintado.',
      ],
      ilustrar: 'Una iglesia sin puertas asignadas funciona como una ambulancia sin departamentos: todos atienden todo y al final nadie atiende a nadie con profundidad. El paciente termina mareado entre voluntarios bien intencionados pero descoordinados.',
      preguntar: 'Si entra un visitante nuevo el proximo domingo... alguien de tu equipo sabe en menos de 60 segundos a cual de las 9 puertas lo conecta? O lo van a dejar deambulando entre saludos vacios?',
      aplicar: 'Antes de la proxima reunion de lideres, memoriza las 9 puertas con su numero, su nombre y su color. En la reunion el equipo se las pregunta uno a uno sin trampa. Quien falle 2, asume el reto de estudiarlas en 7 dias.',
      transicion: 'Ahora vamos puerta por puerta. La Puerta 1 es la base de todo: la cobertura espiritual que sostiene la casa.',
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
      abrir: 'Sin estructura clara, todo trabajo se diluye y todo llamado se gasta. Esta pagina es la columna vertebral del ministerio. Sin esta columna, el cuerpo no se levanta.',
      decir: [
        'La cadena de mando es: Pastor manda al Coordinador. Coordinador supervisa a 9 lideres de puerta. Cada lider dirige su equipo. Cada equipo sirve a la iglesia.',
        'Las CELULAS detectan necesidades en la base. Las PUERTAS responden con equipo y proceso. Nunca al reves: la celula no responde, ella solo detecta y reporta.',
        'El flujo natural es: persona llega → Bienvenida la recibe → entra a una celula → toma discipulado → va a retiro → empieza a servir → se forma como lider → abre nueva celula. Asi se multiplica.',
      ],
      ilustrar: 'Una iglesia sin jerarquia clara es como un ejercito sin oficiales asignados: todos pelean al mismo tiempo, nadie protege la retaguardia y al final se cansan sin saber por que perdieron.',
      preguntar: 'Cada lider de tu iglesia sabe a quien reporta sus avances y quienes le reportan a el? Si la respuesta es "no estoy seguro", ahi hay una grieta y por las grietas se escapa el fruto.',
      aplicar: 'Esta semana, cada lider dibuja en una hoja su linea de mando: arriba, el nombre del coordinador. Al centro, su nombre. Abajo, los nombres de su equipo. Antes del viernes, comparte esa hoja con todo su equipo.',
      transicion: 'En el corazon de toda esta estructura hay una persona clave que decide si funciona o no: el lider de puerta.',
    },
  },

  // ----- 22. EL LIDER DE PUERTA -----
  {
    id: 'lider-puerta',
    type: 'lider',
    title: 'El Lider de Puerta',
    subtitle: 'Cuidar · Ubicar · Activar · Desarrollar',
    notes: {
      abrir: 'Un lider biblico NO es un jefe que da ordenes. Si tu equipo te tiene miedo de hablarte, no eres lider: eres tirano con titulo. Y eso aqui no funciona.',
      decir: [
        'CUIDAR significa conocer a tu gente: sabes quien esta bien, quien esta triste y quien esta escondiendo dolor detras de una sonrisa el domingo.',
        'UBICAR significa ayudar a cada miembro a encontrar su lugar segun su don, no usarlos para tus tareas. Hay diferencia entre asignar y explotar.',
        'ACTIVAR Y DESARROLLAR significa formar OTROS lideres que un dia te reemplacen. El exito ministerial se mide por los lideres que dejas formados, no por los aplausos que recibes en el escenario.',
      ],
      ilustrar: 'Lo dijo un lider biblico bien claro: el verdadero liderazgo no se mide por cuantos te siguen mientras estas en el cargo. Se mide por cuantos lideres dejas formados y operando cuando ya no estas para supervisarlos.',
      preguntar: 'Si revisamos los ultimos 12 meses de tu liderazgo... cuantos lideres NUEVOS se formaron bajo tu cobertura con nombre y apellido? La respuesta dolera, pero ilumina el camino.',
      aplicar: 'Antes del proximo domingo, identifica UNA persona en tu equipo con potencial real de lider futuro. Anota su nombre. Llamala manana. Frase exacta: "Quiero invertir 30 minutos por semana en formarte como lider, durante los proximos 3 meses. Me lo permites?"',
      transicion: 'Y para formar al nuevo creyente, hace falta otro actor clave que toca corazones uno a uno: el mentor.',
    },
  },

  // ----- 23. MENTOR -----
  {
    id: 'mentor',
    type: 'mentor',
    title: 'Proposito del Mentor',
    subtitle: '2 Timoteo 2:2',
    notes: {
      abrir: 'El mentor no es un maestro de teologia que da clases en el templo. Es un puente humano entre el evangelio y la vida real: el matrimonio, el trabajo, las cuentas, los hijos, las decisiones.',
      decir: [
        'El mentor existe para 4 razones concretas: afirmar la fe del nuevo creyente, ayudarlo a cambiar su estilo de vida, integrarlo a la iglesia y prepararlo para servir.',
        'Perfil obligatorio del mentor: vida de oracion diaria, amor visible por las almas, conocimiento biblico solido y testimonio limpio publico y privado.',
        'Tres habitos minimos del mentor activo cada semana: 1) un mensaje cada lunes, 2) una reunion presencial o por video de 1 hora, 3) oracion por nombre cada noche. Sin esos 3, no es mentor: es contacto.',
      ],
      ilustrar: 'Un nuevo creyente sin mentor asignado es un bebe sin madre que lo amamante. Puede sobrevivir comiendo lo que encuentre... pero su desarrollo siempre estara incompleto y vulnerable. La iglesia no puede permitirse hijos huerfanos.',
      preguntar: 'A cuantas personas estas formando como mentor en este momento de tu vida? Si la respuesta es CERO... que vas a hacer al respecto antes del proximo domingo a las 12 del mediodia?',
      aplicar: 'Antes de salir hoy, escribe el nombre de UN nuevo creyente en tu manual. Llamalo manana. Comprometete por 8 semanas exactas, una hora a la semana, mismo dia, misma hora. Pon las 8 reuniones en tu calendario antes de colgar el telefono.',
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
      abrir: 'Las primeras 8 semanas DECIDEN si el nuevo creyente echa raices que aguantan tormentas o se seca al primer viento fuerte. Aqui no hay plan B. Lo que sembremos aqui, eso vamos a recoger.',
      decir: [
        'Cada una de las 8 semanas tiene UN tema principal y UN texto biblico ancla. Nada al azar, nada improvisado: todo bajo orden divino y revisable.',
        'Semanas 1 a 4 trabajan las raices: salvacion, oracion diaria, lectura biblica, importancia de la iglesia local. Sin raices, la primera tormenta de la vida lo arranca de cuajo.',
        'Semanas 5 a 8 producen la cosecha: santidad practica, descubrir su proposito, identificar su don y formacion en liderazgo basico. Aqui formamos al proximo lider que un dia sera mentor de otro.',
      ],
      ilustrar: 'En 8 semanas exactas, una persona puede pasar de "acabo de aceptar a Cristo el domingo pasado" a "estoy formando a alguien mas en su primera semana de discipulado". Esa es la velocidad del Reino cuando hay mapa claro y mentor activo.',
      preguntar: 'Hay material fisico impreso de las 8 semanas LISTO HOY en una caja para entregar a un nuevo creyente que se convierta el proximo domingo? Si la respuesta es no, ya entiendes por que se nos van.',
      aplicar: 'Esta semana, Puerta 8 manda a imprimir 30 paquetes del Discipulado de 8 Semanas. Cada paquete con 8 hojas anilladas. Antes del proximo domingo, las 30 carpetas estan en una caja en la oficina pastoral lista para entregar.',
      transicion: 'Ahora la pregunta clave que muchas iglesias evitan: cuando decimos que una persona esta REALMENTE consolidada?',
    },
  },

  // ----- 25. CONSOLIDADO DE PUERTA -----
  {
    id: 'consolidado-puerta',
    type: 'consolidado',
    title: 'Consolidado de Puerta',
    subtitle: 'No por emocion · Por evidencia',
    notes: {
      abrir: 'Llego la hora de medir con honestidad brutal. No nos vamos a enganar mas con apariencias del domingo, ni a llamar consolidado a quien solo asiste y aplaude.',
      decir: [
        'Hay 4 indicadores tangibles para llamar a alguien CONSOLIDADO: Ubicacion, Activacion, Cobertura y Proceso. Si falta UNO solo de los 4, no esta consolidado: esta de paso por la iglesia.',
        'Ubicado quiere decir que tiene puerta asignada por escrito. Activo quiere decir que ya esta sirviendo en algo concreto. Cubierto quiere decir que un lider lo conoce por nombre y le marca cuenta. En proceso quiere decir que sigue formandose semana a semana.',
        'No queremos asistentes que decoran las bancas los domingos. Queremos consolidados que multiplican vida durante toda la semana. Esa es la diferencia entre congregacion y movimiento.',
      ],
      ilustrar: 'Cien asistentes que ocupan banca pero no sirven valen menos en el Reino que diez consolidados que multiplican fruto cada mes. Esa es la matematica de Dios, no la nuestra. Por eso Jesus escogio doce, no doscientos.',
      preguntar: 'De toda tu lista actual de personas... a cuantas concretamente puedes marcarles HOY los 4 checks completos? Sean honestos en el equipo. La verdad sana, la mentira mata el ministerio.',
      aplicar: 'Esta semana, cada lider hace una tabla en una hoja con los nombres de su equipo en filas y los 4 indicadores en columnas. Marca SI o NO en cada celda. Donde haya "NO", ahi tiene trabajo concreto para los proximos 30 dias.',
      transicion: 'Y para mantener todo este sistema en movimiento constante, hace falta UNA herramienta semanal que muchos subestiman.',
    },
  },

  // ----- 26. REUNION DE SUPERVISORES -----
  {
    id: 'reunion-supervisores',
    type: 'reunion',
    title: 'Reunion Mensual de Supervisores',
    subtitle: '30 minutos · Maximo enfoque',
    notes: {
      abrir: 'Esta reunion mensual de 30 minutos NO es para dar reportes bonitos ni para socializar. Es para asegurar que el sistema completo esta vivo y avanzando segun las metas escritas.',
      decir: [
        'Agenda fija de 30 minutos exactos: 5 minutos de inicio con oracion, 5 minutos de evaluacion por puerta, 10 minutos de bloqueos, 5 minutos de ajustes y 5 minutos de activacion final.',
        'Lo que NO se hace en esta reunion: alargarla, desviarse del tema, contar historias largas, quejarse sin solucion. Lo que SI se hace: ir al punto, escuchar al lider, decidir y ejecutar antes del lunes.',
        'Tu rol como coordinadora no es moderadora ni secretaria que toma notas. Eres la persona que ENFOCA al equipo, CORRIGE desviaciones y ACTIVA acciones concretas. Punto final.',
      ],
      ilustrar: 'Tres frases clave que tienes que repetir hasta que se vuelvan cultura del equipo: "Vamos al punto." "Cual es el siguiente paso concreto?" "Eso lo resolvemos antes del lunes." Repitelas en cada reunion sin pena.',
      preguntar: 'Cuantas reuniones del ultimo trimestre terminaron sin un siguiente paso CONCRETO escrito en el grupo de WhatsApp? Esas no son reuniones: son sesiones de desahogo disfrazadas de trabajo ministerial.',
      aplicar: 'En la proxima reunion mensual, ponle un cronometro visible al telefono en el centro de la mesa. Si pasa de los 30 minutos, identifiquen quien desvio el tema y por que. Sin pena, con amor, pero sin pena.',
      transicion: 'Y todo este sistema apunta a UNA sola meta medible al final del ano: ganar lideres servidores que multipliquen vida.',
    },
  },

  // ----- 27. ESTRATEGIA DE GANAR -----
  {
    id: 'estrategia-ganar',
    type: 'estrategia',
    title: 'Estrategia de Ganar',
    subtitle: '40 lideres · Plan anual',
    notes: {
      abrir: 'No estamos hablando de "mas asistencia los domingos" como meta vaga. Estamos hablando de 40 LIDERES servidores formados, activos y multiplicando antes del cierre del ano. Esa es la meta exacta.',
      decir: [
        'Cada 2 semanas debe haber personas concretas haciendo MCD, NPT, Bienvenida y Retiros LBS. Movimiento medible en una hoja, no esperanzas vagas.',
        'Tres discipulados clave en orden: primero "Mi llamado es sobrenatural", luego el segundo discipulado y al final el tercer discipulado. En ese orden estricto, sin saltos.',
        'Cada persona que se inscribe en consolidacion recibe reconocimiento PUBLICO desde el escenario el domingo siguiente. Lo que celebramos en publico, eso multiplicamos en privado.',
      ],
      ilustrar: 'El plan de visita pastoral son 4 pasos exactos: 1) Confirmar datos por telefono, 2) Entregar un regalo en la mano (libro o tarjeta), 3) Ofrecer MCD con fecha de inicio, 4) Conectar con mentor por nombre. Cuatro pasos sencillos que producen un lider en 90 dias.',
      preguntar: 'De los 40 lideres que queremos ganar este ano... cuantos estan ya identificados con NOMBRE Y APELLIDO en una lista escrita de oracion? Si no estan en lista, no estan en el plan.',
      aplicar: 'Antes de salir hoy, escribe en tu manual los primeros 5 nombres con apellido de tu lista personal hacia los 40. Por esos 5 vas a orar cada manana antes de las 8am. Por esos 5 vas a llorar. Por esos 5 vas a ayunar el primer viernes del mes.',
      transicion: 'Y ahora cerramos. Todo lo que hemos visto se reduce a UNA sola palabra que define a la iglesia que Dios suena: cultura.',
    },
  },

  // ----- 28. CULTURA Y LLAMADO FINAL -----
  {
    id: 'cultura-cierre',
    type: 'cierre',
    title: 'Cultura y Llamado Final',
    subtitle: 'Ano de Cosecha y Restitucion',
    notes: {
      abrir: 'Cinco palabras que ya no son adornos colgados en la pared del lobby. Son los pilares vivos que nos sostienen como casa de oracion: Amor, Orden, Oracion, Servicio y Unidad. Cinco. Ni mas, ni menos.',
      decir: [
        'Las CELULAS detectan la necesidad. Las PUERTAS responden con equipo y proceso. El LIDERAZGO supervisa los resultados. Y solo DIOS transforma. Esa es la cadena exacta del Reino, sin saltarse eslabones.',
        'Hay UNA puerta especifica para que sirvas con tu don. Hay UNA funcion para tu llamado. Hay UNA respuesta clara para cada necesidad de tu iglesia. Aqui nadie sobra. Nadie esta de relleno.',
        'Este es el ano de cosecha y restitucion. Lo que el enemigo robo en anos pasados, Dios lo devuelve este ano. Lo que parecia tarde, Dios lo acelera. Cree y avanza con disciplina.',
      ],
      ilustrar: 'Hay una frase que sera nuestra firma como iglesia y la diras en cada reunion: "Aqui cada miembro tiene un lugar, cada necesidad tiene una respuesta y cada vida tiene un proceso." Esa frase es nuestro pacto. Memorizala.',
      preguntar: 'Vas a salir de aqui como observador que aplaude la vision desde la silla... o como protagonista que la ejecuta de lunes a viernes? La cosecha se reparte solo entre los que trabajan en ella, no entre los que la celebran.',
      aplicar: 'Antes de levantarte de tu silla hoy, escribe en tu manual estas tres lineas exactas: 1) PUERTA donde voy a servir el proximo trimestre. 2) NOMBRE Y APELLIDO de la persona que voy a discipular 8 semanas. 3) FECHA exacta del lunes en que comienzo. Sin esas 3 lineas escritas, esto fue solo emocion pasajera.',
      transicion: 'Cerramos declarando juntos en voz alta: "Soy parte de la cosecha de este ano. Mi puerta esta abierta. Aqui estoy. Senor, enviame."',
      versiculoFinal: '"Porque de la manera que en un cuerpo tenemos muchos miembros, pero no todos los miembros tienen la misma funcion..." — Romanos 12:4',
    },
  },
];
