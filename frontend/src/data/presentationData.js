/**
 * Contenido completo de la presentacion extraido de 13 documentos.
 *
 * IMPORTANTE - Logica de las notas (revisada 2026-04-26):
 *  - Lo que ve la AUDIENCIA en pantalla = visual limpio, palabras clave.
 *  - Las NOTAS del pastor / Notas TV = guion para PREDICAR con CORAZON.
 *    Cada nota busca CONECTAR, REFLEXIONAR, IMPACTAR y MOVER al lector
 *    a abrir el manual y vivir la vision.
 *
 *  Estructura de cada nota (6 secciones):
 *      abrir       -> apertura PASTORAL que toca el corazon (no informa)
 *      decir       -> 3-4 verdades dichas con conviccion y ternura
 *      ilustrar    -> imagen / parabola / dato que pinta el alma
 *      preguntar   -> 1 pregunta que atraviesa, no que interroga
 *      aplicar     -> invitacion concreta (no tarea fria)
 *      transicion  -> mano extendida hacia el siguiente slide
 *
 *  REGLA CRITICA - notas UNIVERSALES:
 *      - NO usar fechas (enero, este ano, hace 6 meses, etc.)
 *      - NO asumir historias propias (cuando llegamos, antes eramos)
 *      - NO mencionar nombres especificos
 *      - SI usar principios biblicos, lenguaje pastoral, aplicaciones
 *        concretas pero genericas. La pastora aterriza el ejemplo.
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
// Notas pastorales: para CONECTAR, REFLEXIONAR, IMPACTAR.
// ============================================================================

// Notas pastorales por puerta (slides 12-20)
const NOTAS_PUERTAS = {
  1: {
    abrir: 'Antes de hablar de estrategias, hablemos del altar. Ninguna puerta abre sin oracion. Ninguna.',
    decir: [
      'La intercesion no es UN ministerio mas. Es el AIRE que respira todo el sistema.',
      'Cuando un pueblo ora, el cielo se inclina. Cuando un equipo ora, la tierra cede.',
      'Sin oracion, lo demas se vuelve actividad religiosa: ruido sin presencia.',
    ],
    ilustrar: 'Nehemias reconstruyo la Puerta de la Fuente. Sin agua, no hay vida. Sin oracion, no hay iglesia — solo edificio.',
    preguntar: 'Cuando fue la ultima vez que ORAMOS por nuestra iglesia mas tiempo del que la criticamos?',
    aplicar: 'Comprometete con UN tiempo fijo de oracion esta semana. No general — ESPECIFICO. Por nombres, por puertas, por almas.',
    transicion: 'Y donde hay oracion, hay frutos que llegan. Esos frutos primero tocan la Puerta 2: la Bienvenida.',
  },
  2: {
    abrir: 'Hay personas que llegaron buscando a Dios y se fueron sin que nadie las mirara a los ojos. No queremos ser esa iglesia.',
    decir: [
      'La bienvenida no es un protocolo. Es la PRIMERA forma en que esa persona ve el rostro del Padre.',
      'Una sonrisa puede salvar un alma del rechazo. Un saludo frio puede confirmar el rechazo que ya traia.',
      'Aqui no se entrega un libro: se entrega un PROCESO. MCD, NPT, vision, retiro, mentor, celula, bautismo. Camino completo.',
    ],
    ilustrar: 'El Padre del hijo prodigo no le dio una cita para el lunes. CORRIO. Lo abrazo. Le puso anillo. Asi se recibe a un alma.',
    preguntar: 'Si una persona quebrantada visita HOY tu iglesia... saldra sintiendo que la abrazaron, o que la observaron?',
    aplicar: 'Mira al primer rostro nuevo este domingo. Acercate. Pregunta su nombre. Recordalo. Eso ya cambio una vida.',
    transicion: 'Pero a veces el alma que llega trae heridas que no esperan al lunes. Ahi entra la Puerta 3.',
  },
  3: {
    abrir: 'Hay un dolor que no avisa. Llega un martes, a las 3 de la manana. Y la iglesia tiene que estar lista para responder.',
    decir: [
      'Cuidado Pastoral Inmediato no es un favor: es una urgencia del Reino.',
      'Cuatro brazos: oracion personal, consejeria basica, canalizacion a discipulado, acompanamiento.',
      'No reemplazamos al pastor. Somos las MANOS que sostienen al alma mientras llega el pastor.',
    ],
    ilustrar: 'Las ovejas heridas no buscan un programa: buscan un pastor que se agache hasta su nivel y las cargue. Eso es Puerta 3.',
    preguntar: 'Si alguien de tu iglesia tuviera una crisis esta noche... sabria a quien llamar antes que al psicologo?',
    aplicar: 'Que cada lider tenga DOS numeros de Puerta 3 guardados en su telefono. Hoy. No manana.',
    transicion: 'Cuando la herida es profunda, hace falta mas que una llamada. Hace falta apartarse con Dios. Eso es Puerta 4.',
  },
  4: {
    abrir: 'Hay batallas que no se ganan en el culto del domingo. Se ganan en un retiro, lejos del ruido, frente a frente con Dios.',
    decir: [
      'LBS: Liberacion, Bendicion, Sanidad. 21 dias donde Dios desnuda el alma y la viste de nuevo.',
      'No es un evento emocional. Es un PROCESO ESPIRITUAL con tres fases que Dios usa para sanar generaciones.',
      'Cada retiro debe producir testimonios concretos: cadenas rotas, perdones dados, propositos descubiertos.',
    ],
    ilustrar: 'La Puerta del Valle. En el valle es donde David escribio salmos, Jose se hizo fuerte y Jesus se preparo. Sin valle, no hay altura.',
    preguntar: 'Cuantas personas estan llevando cadenas que solo se rompen en un retiro... y nadie las ha invitado todavia?',
    aplicar: 'Esta semana, escribe TRES nombres de personas que necesitan un retiro. Llamalas tu mismo. Una por una.',
    transicion: 'Y cuando regresan transformadas, no podemos abandonarlas. Hay que formarlas. Eso es Puerta 5.',
  },
  5: {
    abrir: 'Un nuevo creyente sin mentor es como un bebe en la nieve. Puede sobrevivir... pero pocos lo hacen.',
    decir: [
      'Los primeros 3 meses DECIDEN si esa persona se queda o se pierde.',
      'Mentor no es maestro: es PUENTE entre el evangelio y la vida real.',
      'Sin mentor, el discipulo es huerfano. Con mentor, en 90 dias forma a otro. Esa es la matematica del Reino.',
    ],
    ilustrar: 'Pablo a Timoteo: "Lo que has oido de mi, esto encarga a hombres fieles que sean idoneos para ensenar tambien a otros." Cuatro generaciones en un versiculo.',
    preguntar: 'Si Dios te pidiera cuentas hoy... a quien estas formando con tu vida, no solo con tu boca?',
    aplicar: 'Identifica UNA persona nueva. Ofrecele 8 semanas de tu tiempo. No mas. Pero las 8 completas.',
    transicion: 'Y a los que se ausentaron, no los abandonamos. Vamos NOSOTROS por ellos. Eso es Puerta 6.',
  },
  6: {
    abrir: 'Si solo cuidamos al que viene, vamos a perder al que se aleja. Y al que se alejo, alguien lo dejo ir sin pelear.',
    decir: [
      'Visitacion Pastoral es la iglesia ROMPIENDO sus paredes para llegar a los hogares.',
      'Cinco frentes: enfermos, ausentes, amigos de la iglesia, hogares enteros, alejados que necesitan restauracion.',
      'Cada visita es una declaracion: "Tu vida le importa al Padre. Por eso hoy estoy en tu puerta."',
    ],
    ilustrar: 'Puerta del Muladar: donde habia basura, ahora hay limpieza. Eso es lo que llevamos a cada hogar quebrantado.',
    preguntar: 'Cuantos miembros se han alejado en silencio... porque nadie tomo el telefono y dijo: "Te extranamos"?',
    aplicar: 'Llama a UNA persona ausente esta semana. No para regañarla. Para amarla. "Solo queria saber como estabas."',
    transicion: 'Y el mensaje que nace en el altar tiene que llegar a cada pantalla. Eso es Puerta 7.',
  },
  7: {
    abrir: 'Hoy una persona puede llorar a las 2 de la manana y abrir su telefono buscando una palabra. Esa palabra debe ser nuestra.',
    decir: [
      'Multimedia no es lujo: es el puente entre el mensaje y la generacion que vive en pantalla.',
      'La iglesia no cierra el domingo a las 12. Vive 24/7 en cada video, cada predica, cada testimonio publicado.',
      'Donde haya senal de internet, debe haber senal del Espiritu. Esa es la mision.',
    ],
    ilustrar: 'Puerta de las Aguas: la Palabra. Hoy las aguas corren por wifi. Si no estamos ahi, otros estan ocupando ese pulpito.',
    preguntar: 'La predica del domingo... cuantos corazones podria tocar el martes si estuviera publicada? Cuantos no la veran porque no la subimos?',
    aplicar: 'Asigna UN responsable concreto. Cada culto, editado y publicado en menos de 48 horas. Punto.',
    transicion: 'Y nada de esto se sostiene sin recursos. La Puerta 8 es la que provee.',
  },
  8: {
    abrir: 'La vision sin recursos se vuelve frustracion. Por eso Dios siempre proveyo logistica antes de cada gran movimiento.',
    decir: [
      'Administracion y Recursos no es contar dinero: es ABRIR camino para que las almas se discipulen.',
      'Biblias listas. Manuales en mano. Materiales disponibles. Cuando un alma llega, debe encontrar herramienta — no excusa.',
      'Lo que se administra con orden, alcanza el doble. Lo que se administra con caos, se gasta sin fruto.',
    ],
    ilustrar: 'Puerta del Caballo: ningun ejercito gana una guerra sin logistica. Y nosotros estamos en guerra espiritual.',
    preguntar: 'Si HOY entran 20 nuevos creyentes... hay 20 Biblias listas? hay 20 manuales? O les vamos a decir "vuelvan la otra semana"?',
    aplicar: 'Inventario esta semana. Cuenta lo que hay. Lista lo que falta. Lo que falta se compra antes del proximo culto.',
    transicion: 'Y para encender corazones, Dios siempre uso momentos. La Puerta 9 los planifica.',
  },
  9: {
    abrir: 'Hay momentos que cambian a una iglesia para siempre: un congreso, un retiro de lanzamiento, una noche de gloria. Estos no se improvisan.',
    decir: [
      'Congresos y Eventos no son entretenimiento: son PUNTOS DE INFLEXION que Dios usa para acelerar todo el sistema.',
      'Cada evento debe tener fecha, equipo, presupuesto y meta de almas. Si falta uno, falta todo.',
      'Aqui se cruzan todas las puertas: pastoral, multimedia, finanzas, cocina, ujieres. Es la sinfonia del Reino.',
    ],
    ilustrar: 'Puerta Oriental: por ahi entra el Rey de gloria. Cada congreso debe abrir cielos, no solo llenar agenda.',
    preguntar: 'El proximo evento grande... va a ser un mover de Dios o un evento mas que la gente olvida en una semana?',
    aplicar: 'Define el proximo evento grande. Fecha. Equipo. Meta. Si lo escribes, ya empezo a existir.',
    transicion: 'Cerramos las nueve puertas. Ahora alzamos la mirada para ver el sistema completo.',
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
      abrir: 'Hay momentos en la vida de una iglesia que no se repiten. Este es uno. Lo que vamos a abrir hoy no es un manual: es una PUERTA.',
      decir: [
        'Dios no nos llamo para sobrevivir religiosamente. Nos llamo a EDIFICAR generacionalmente.',
        'Lo que tienes en tus manos es fruto de oracion, lagrimas y revelacion. No es teoria — es estrategia profetica.',
        'Cuando salgas de aqui, no quiero que seas la misma persona. Y creo que tu tampoco quieres serlo.',
      ],
      ilustrar: 'Hay personas que toda su vida estuvieron CERCA del fuego de Dios y nunca se calentaron. Hoy te invito a acercarte tanto, que no puedas salir igual.',
      preguntar: 'Vas a recibir esto como una capacitacion mas... o como un MOMENTO que marca tu vida y la de tu generacion?',
      aplicar: 'Escribe tu nombre en la primera pagina de este manual. No es un tramite — es un PACTO entre tu y Dios.',
      transicion: 'Antes de caminar, miremos el mapa. Porque todos los que llegan lejos, primero saben a donde van.',
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
      abrir: 'Antes de hablar de fruto, hablemos de raiz. Antes del fruto, viene el mapa. Y antes del mapa, viene la sed por encontrarlo.',
      decir: [
        'Este indice no es decoracion. Es la ruta que Dios trazo para esta iglesia y para tu vida.',
        'Cuatro partes. Ninguna se salta. Ninguna sobra. Cada una sostiene a la siguiente.',
        'Lo que hoy parece complicado, en pocas semanas sera tu lenguaje natural. Confia en el proceso.',
      ],
      ilustrar: 'Una iglesia sin mapa cae en activismo: mucha actividad, poco fruto, mucho cansancio, poco gozo. Hoy rompemos ese ciclo.',
      preguntar: 'Cuantas veces empezaste algo importante sin saber a donde ibas? Eso se acaba aqui, en esta pagina.',
      aplicar: 'Pasa el dedo por el indice. Marca la parte que mas curiosidad despierta en tu corazon. Esa parte te esta llamando.',
      transicion: 'Ahora levantamos la mirada. Antes del sistema, esta el LLAMADO.',
    },
  },

  // ----- 3. UNA INVITACION -----
  {
    id: 'invitacion',
    type: 'invitacion',
    title: 'Una Invitacion',
    subtitle: 'Bienvenido a este Manual',
    notes: {
      abrir: 'Lo que tienes en las manos NO nacio de una idea humana. Nacio en una madrugada de oracion, frente a Dios, con conviccion profetica.',
      decir: [
        'Hay vidas esperando ser alcanzadas. Suenos esperando ser activados. Puertas esperando ser abiertas. Y muchas de esas puertas dependen de TI.',
        'Esto no es informacion para acumular: es una estrategia espiritual para EJECUTAR.',
        'Hacer cosas buenas sin orden cansa el alma. Hacer cosas buenas con orden multiplica la vida.',
      ],
      ilustrar: '"Donde no hay vision, el pueblo perece." Hoy no estas perdiendo el tiempo: estas recibiendo una vision por la que valdra la pena vivir.',
      preguntar: 'Cuantas cosas buenas estas haciendo que NO estan produciendo fruto medible? Y cuanto mas vas a esperar para corregirlo?',
      aplicar: 'Subraya en este manual aquello que toca tu corazon. Eso que subraye Dios — no tu cabeza — sera tu primer paso.',
      transicion: 'Ahora la pregunta no es solo QUE hace este manual. Es para QUIEN fue escrito. Y la respuesta te va a sorprender.',
    },
  },

  // ----- 4. PARA QUIEN + PROMESA -----
  {
    id: 'para-quien-promesa',
    type: 'para-quien-promesa',
    title: 'Para quien es este manual?',
    subtitle: 'Como leerlo · Nuestra Promesa',
    notes: {
      abrir: 'Si estas aqui, este manual es para TI. No te lo regalaron por casualidad — Dios te lo entrego con proposito.',
      decir: [
        'Lealo con LAPIZ EN MANO, con ORACION en el corazon y con tu equipo al lado. Asi se lee un manual que cambia vidas.',
        'Subrayen lo que impacta. Marquen lo que van a implementar. Regresen a lo que les desafia.',
        'La promesa: si lo aplican con disciplina, VEN FRUTO. No por el manual — sino porque Dios honra los principios que estan aqui.',
      ],
      ilustrar: 'El pastor lee como pastor. El mentor lee como mentor. El servidor descubre su puerta. El nuevo creyente entiende su proceso. Cada quien encuentra su lugar en estas paginas.',
      preguntar: 'Vas a leerlo una sola vez como una novela... o lo vas a usar como herramienta de trabajo todo el ano?',
      aplicar: 'Define HOY desde que lugar lo vas a leer: pastor, lider, mentor, servidor o nuevo creyente. Esa decision cambia todo.',
      transicion: 'Antes de entrar en los detalles, mira la fotografia completa del sistema. Una sola pagina lo dice todo.',
    },
  },

  // ----- 5. INTRO MANUAL -----
  {
    id: 'intro-manual',
    type: 'intro-manual',
    title: 'Introduccion del Manual',
    subtitle: 'Una Invitacion a ver la iglesia con nuevos ojos',
    notes: {
      abrir: 'Hay una forma vieja de ver la iglesia. Y hay una forma NUEVA. Esta pagina te invita a abrir los ojos del espiritu.',
      decir: [
        'Cinco pilares sostienen el sistema: el corazon (vision/mision/valores), la base biblica, el proceso claro, las herramientas practicas, y la estrategia de ganar.',
        'No basta con tener corazon: hay que tener proceso. No basta con tener proceso: hay que tener herramientas. Y nada de eso vale sin estrategia.',
        'Cada pilar sostiene a los demas. Si quitas uno, el sistema entero se cae. Por eso Dios pidio TODOS — no algunos.',
      ],
      ilustrar: 'Hay vidas esperando ser ALCANZADAS, suenos esperando ser ACTIVADOS, puertas esperando ser ABIERTAS. La iglesia es la mano que Dios usa para abrir esas puertas.',
      preguntar: 'Cual de los cinco pilares esta mas debil hoy en tu area? Si no puedes responder, ahi tienes tu primera tarea.',
      aplicar: 'Identifica el pilar mas debil. Esta semana das UN paso concreto para fortalecerlo. No esperes mas.',
      transicion: 'Y empezamos por el primer pilar: el corazon del sistema. Nuestra IDENTIDAD.',
    },
  },

  // ----- 6. NUESTRA IDENTIDAD -----
  {
    id: 'identidad',
    type: 'identidad',
    title: 'Nuestra Identidad',
    subtitle: 'Vision · Mision · Valores',
    notes: {
      abrir: 'Antes de leer la pantalla, hazte esta pregunta: quien soy yo cuando NADIE me esta viendo? Esa respuesta es tu identidad real.',
      decir: [
        'No buscamos mas asistentes. Buscamos mas LIDERES. La diferencia no es semantica — es generacional.',
        'Mision: evangelizar, consolidar, discipular y enviar. En ese orden. Saltarse pasos produce iglesias grandes pero debiles.',
        'Los valores no son adornos para colgar en la pared. Son el filtro que evalua CADA decision en cada puerta.',
      ],
      ilustrar: 'Si decimos que valoramos el orden y nuestra area es un caos, los valores son solo papel. Si decimos que amamos las almas y no llamamos al ausente, el amor es solo discurso.',
      preguntar: 'Tu area refleja AMOR por las almas? Refleja ORDEN? Si no, ahi tienes el punto exacto donde Dios quiere comenzar.',
      aplicar: 'Cada lider evalua su area frente a los 7 valores. Escribe UNO que necesita mejorar. Y empieza esta semana.',
      transicion: 'La razon profunda detras de todo esto no nacio aqui. Esta escrita hace siglos en Nehemias 3.',
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
      abrir: 'Cosecha y Restitucion. No es un eslogan bonito: es un MANDATO PROFETICO. Y los mandatos no se decoran — se obedecen.',
      decir: [
        'Nehemias reconstruyo PRIMERO las puertas. Sin puertas no hay proteccion, ni orden, ni crecimiento sano.',
        'Asigno el trabajo POR ZONAS. Eso es consolidacion. Cada quien sabia donde construir y a quien proteger.',
        'Dios prometio devolver lo perdido y multiplicar el fruto cuando hay puertas reconstruidas. Esa promesa es para TI hoy.',
      ],
      ilustrar: 'En tiempos de Nehemias el muro estaba roto. Hoy las puertas rotas son los procesos sin terminar, las llamadas sin hacer, los discipulados sin seguimiento. Hay que reconstruir.',
      preguntar: 'Cuantas "puertas" en tu vida y en tu area estan sin reconstruir? Y por cuanto tiempo mas vas a vivir con esas grietas abiertas?',
      aplicar: 'Identifica UN area de tu ministerio que esta rota. Traza un plan de 30 dias para repararla. Comienza manana.',
      transicion: 'Ahora bajamos del lema al sistema concreto. Te presento la LEY DE LAS 7 SEMANAS.',
    },
  },

  // ----- 8. LEY DE LAS 7 SEMANAS -----
  {
    id: 'ley-7-semanas',
    type: 'ley-7-semanas',
    title: 'La Ley de las 7 Semanas',
    subtitle: 'Un proceso de crecimiento y formacion',
    notes: {
      abrir: 'Siete semanas. Un calendario sagrado. No siete deseos — siete decisiones que, si se ejecutan con disciplina, parten un ano en dos.',
      decir: [
        'Cada semana tiene un OBJETIVO concreto. Si saltas una, comprometes el resto. La disciplina aqui es innegociable.',
        'No es ritmo religioso: es ritmo del REINO. Dios opera en tiempos. Quien entiende los tiempos, recoge cosechas.',
        'Trabajamos en equipo, con un mismo objetivo. La unidad acelera lo que la division retrasa anos.',
      ],
      ilustrar: 'Una semana sin proposito = un mes perdido. Pero 7 semanas con proposito producen lo que muchos no logran en 7 meses.',
      preguntar: 'En que semana del proceso suele caerse la gente... y que vas a hacer DIFERENTE esta vez para que no se caiga?',
      aplicar: 'Define HOY la semana en que vas a iniciar tu primer ciclo completo. Calendario en mano. Fecha en negro y blanco.',
      transicion: 'Y para conectar las puertas con el proceso, Dios nos dio un motor especifico: el MODELO CAP.',
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
      abrir: 'CAP no es una sigla mas. Es la respuesta de Dios al problema de toda iglesia que crece y se queda sin estructura para sostener ese crecimiento.',
      decir: [
        'EL DON ES LA LLAVE. Tu don es lo que abre tu puerta en el Reino. Sin don activado, hay servicio... pero no hay propósito.',
        'La iglesia es un cuerpo. No todos hacemos lo mismo. Pero todos somos NECESARIOS. Lo que tu haces, nadie mas lo hace igual.',
        'Tres niveles que se sostienen: Formacion, Seguimiento, Crecimiento. Si quitas uno, los otros dos se derrumban.',
      ],
      ilustrar: 'Sin CAP, la gente entra por una puerta y se cae por otra. Con CAP, cada persona tiene proceso, tiene lider y tiene destino.',
      preguntar: 'Cuantas personas estan entrando a tu iglesia HOY sin un sistema solido que los integre? Y a quien le rendiras cuentas si se pierden?',
      aplicar: 'Identifica una persona que llego SIN proceso. Asignale puerta, mentor y semana. No la dejes a la deriva.',
      transicion: 'Y para activar todo esto, Dios nos da un principio profetico que cambia el ritmo: el TIEMPO 3 — la Operacion 72.',
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
      abrir: 'Tiempo 3. Tres dias. No es casualidad biblica. Es el patron profetico que Dios ha usado en CADA gran movimiento de su historia.',
      decir: [
        'Moises: "en tres dias". Josue: "en tres dias poseeremos la tierra". Jesus: "en tres dias resucitare". Tres veces Dios marco el patron.',
        'Aplicacion practica: en 3 DIAS atendemos al nuevo creyente. LBS en 3 SEMANAS. Seguimiento de 3 MESES.',
        'Mes 1: el llamado. Mes 2: el privilegio de servir. Mes 3: predestinado para ganar. Tres meses, tres niveles.',
      ],
      ilustrar: 'Cuando esperamos 30 dias para llamar a un visitante, ya lo perdimos. En 72 horas se DECIDE su destino espiritual. Asi de serio.',
      preguntar: 'Que pasaria en tu iglesia si TODO visitante recibiera contacto en menos de 72 horas, sin excepciones, sin excusas?',
      aplicar: 'Cada lider revisa HOY su lista de visitantes recientes. Los contacta en las proximas 72 horas. No manana — hoy.',
      transicion: 'Y ahora entramos a la columna vertebral del sistema: las NUEVE PUERTAS que sostienen todo.',
    },
  },

  // ----- 11. LAS 9 PUERTAS (intro) -----
  {
    id: 'las-9-puertas',
    type: 'las-9-puertas',
    title: 'Las 9 Puertas',
    subtitle: 'El sistema completo de activacion',
    notes: {
      abrir: 'Cada necesidad humana tiene una puerta. Cada puerta tiene una respuesta. Y Dios diseno NUEVE para que ningun alma quede sin atender.',
      decir: [
        'Enfermo necesita Puerta 6. Crisis necesita Puerta 3. Peticion urgente necesita Puerta 1. Nuevo creyente necesita Puerta 5.',
        'Visitante necesita Puerta 2. Evento necesita Puerta 9. Difusion necesita Puerta 7. Material necesita Puerta 8. Encuentro profundo necesita Puerta 4.',
        'Cada puerta debe tener LIDER, ASISTENTE, EQUIPO y METAS ANUALES. Sin esos cuatro, no es puerta — es un letrero.',
      ],
      ilustrar: 'Una iglesia sin puertas es como una ambulancia sin departamentos: todos atienden a todos, y al final nadie atiende a nadie. Caos disfrazado de servicio.',
      preguntar: 'Si llega un visitante nuevo HOY a tu iglesia... alguien sabe exactamente a que puerta lo conecta? O lo van a dejar deambulando entre saludos?',
      aplicar: 'Memoriza las 9 puertas con sus colores. En la proxima reunion, el equipo se las pregunta unos a otros. Sin trampa.',
      transicion: 'Ahora entramos puerta por puerta. La Puerta 1 es la base de todo: la cobertura espiritual que sostiene la casa.',
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
      abrir: 'Sin estructura, el trabajo se diluye y el llamado se gasta. Esta pagina es la columna vertebral del ministerio.',
      decir: [
        'Pastor → Coordinador → 9 Lideres de Puerta → Equipos → Iglesia. Cada nivel con autoridad clara y rendicion de cuentas concreta.',
        'Las CELULAS detectan necesidades. Las PUERTAS responden con equipo y proceso. Nunca al reves.',
        'Flujo natural: persona llega → bienvenida → celula → discipulado y retiro → empieza a servir → se forma → abre celula. Multiplicacion organica.',
      ],
      ilustrar: 'Una iglesia sin jerarquia clara es un ejercito sin oficiales: todos pelean, nadie gana, y al final se cansan sin saber por que.',
      preguntar: 'Cada quien sabe a quien reporta y quienes le reportan? Si no, ahi hay una grieta — y por las grietas se escapa el fruto.',
      aplicar: 'Dibuja TU linea de mando. Arriba, quien. Abajo, quienes. Compartelo con tu equipo esta semana.',
      transicion: 'En el corazon de toda esta estructura esta una persona clave: el LIDER de Puerta.',
    },
  },

  // ----- 22. EL LIDER DE PUERTA -----
  {
    id: 'lider-puerta',
    type: 'lider',
    title: 'El Lider de Puerta',
    subtitle: 'Cuidar · Ubicar · Activar · Desarrollar',
    notes: {
      abrir: 'Un lider NO es un jefe. Si tu equipo te tiene miedo, no eres lider — eres tirano con titulo. Eso aqui no funciona.',
      decir: [
        'CUIDAR: conoce a tu gente. Sabe quien esta bien, quien esta triste, quien esta escondido detras de una sonrisa.',
        'UBICAR: ayuda a cada uno a encontrar SU lugar. No los uses para tus tareas — UBICALOS en su don.',
        'ACTIVAR Y DESARROLLAR: forma OTROS lideres. El exito ministerial se mide por los lideres que dejas atras, no por los aplausos que recibes.',
      ],
      ilustrar: 'El verdadero liderazgo no se mide por cuantos te siguen. Se mide por cuantos LIDERES dejas formados cuando ya no estes.',
      preguntar: 'Si revisamos los ultimos meses... cuantos lideres NUEVOS se han formado de verdad bajo tu liderazgo? La respuesta dolera, pero ilumina.',
      aplicar: 'Identifica UNA persona en tu equipo con potencial real de lider. Empieza a formarla esta semana. Inviertele tiempo personal.',
      transicion: 'Y para formar al nuevo creyente, hace falta otro actor clave que toca corazones uno a uno: el MENTOR.',
    },
  },

  // ----- 23. MENTOR -----
  {
    id: 'mentor',
    type: 'mentor',
    title: 'Proposito del Mentor',
    subtitle: '2 Timoteo 2:2',
    notes: {
      abrir: 'El mentor no es un maestro de teologia. Es un PUENTE entre el evangelio y la vida real. Donde el sermon termina, el mentor comienza.',
      decir: [
        'Cuatro razones de existir: afirmar la fe, cambiar el estilo de vida, integrar a la iglesia, preparar para servir.',
        'Perfil: vida de oracion + amor profundo por las almas + conocimiento biblico solido + buen testimonio publico y privado.',
        'Responsabilidades minimas: contacto SEMANAL, reunion semanal, oracion diaria por su discipulo, llevarlo a celula y a puerta.',
      ],
      ilustrar: 'Un nuevo creyente sin mentor es un bebe sin madre. Puede sobrevivir... pero su desarrollo siempre estara incompleto. La iglesia no puede permitirse hijos huerfanos.',
      preguntar: 'A cuantas personas estas formando como mentor en este momento? Y si la respuesta es CERO... que vas a hacer al respecto antes del proximo domingo?',
      aplicar: 'Ofrecete a ser mentor de UN nuevo creyente. Comprometete por 8 semanas completas. Solo eso. Pero las 8 enteras.',
      transicion: 'Y cada mentor necesita un mapa para no improvisar. Ese mapa se llama DISCIPULADO en 8 SEMANAS.',
    },
  },

  // ----- 24. DISCIPULADO 8 SEMANAS -----
  {
    id: 'discipulado-8-semanas',
    type: 'discipulado-8',
    title: 'Discipulado en 8 Semanas',
    subtitle: 'El mapa del nuevo creyente',
    notes: {
      abrir: 'Las primeras 8 semanas DECIDEN si el nuevo creyente echa raices o se seca. No hay plan B. Lo que sembremos aqui, eso reciviremos despues.',
      decir: [
        'Cada semana tiene un tema y un texto biblico ancla. Nada al azar — todo bajo orden divino.',
        'S1-S4: salvacion, oracion, Biblia, iglesia. Las RAICES. Sin raices, la primera tormenta lo arranca.',
        'S5-S8: santidad, proposito, don y liderazgo. La COSECHA. Aqui formamos al proximo lider que un dia sera mentor de otro.',
      ],
      ilustrar: 'En 8 semanas, una persona puede pasar de "acabo de aceptar a Cristo" a "estoy formando a alguien mas". Esa es la velocidad del Reino cuando hay orden.',
      preguntar: 'Hay material fisico de las 8 semanas LISTO HOY para entregar a un nuevo creyente? Si no, ya entiendes por que se nos van.',
      aplicar: 'Imprime y arma carpetas con el plan de 8 semanas. Antes del proximo culto. Listas para entregar en mano.',
      transicion: 'Ahora la pregunta clave que muchos evitan: cuando decimos que una persona esta REALMENTE consolidada?',
    },
  },

  // ----- 25. CONSOLIDADO DE PUERTA -----
  {
    id: 'consolidado-puerta',
    type: 'consolidado',
    title: 'Consolidado de Puerta',
    subtitle: 'No por emocion · Por evidencia',
    notes: {
      abrir: 'Llego la hora de medir con honestidad. No nos vamos a enganar mas con apariencias, ni a llamar consolidado a quien solo asiste.',
      decir: [
        'Cuatro indicadores tangibles: UBICACION, ACTIVACION, COBERTURA, PROCESO. Si falta UNO, no esta consolidado — esta de paso.',
        'Ubicado = tiene puerta. Activo = ya sirve. Cubierto = un lider lo conoce por nombre. En proceso = sigue formandose semana a semana.',
        'No queremos asistentes que decoran bancas. Queremos consolidados que multiplican vida. Esa es la diferencia.',
      ],
      ilustrar: '100 asistentes que no sirven valen menos en el Reino que 10 consolidados que multiplican. Esa es la matematica de Dios — no la nuestra.',
      preguntar: 'De toda tu lista actual... a cuantas personas puedes marcarles HOY los 4 checks? Sean honestos. La verdad sana, la mentira mata.',
      aplicar: 'Hagan una tabla del equipo con los 4 indicadores. SI o NO en cada uno. Donde haya "NO", ahi hay trabajo pendiente.',
      transicion: 'Y para mantener todo este sistema en movimiento, hace falta UNA herramienta semanal que muchos subestiman.',
    },
  },

  // ----- 26. REUNION DE SUPERVISORES -----
  {
    id: 'reunion-supervisores',
    type: 'reunion',
    title: 'Reunion Mensual de Supervisores',
    subtitle: '30 minutos · Maximo enfoque',
    notes: {
      abrir: 'Esta reunion no es para dar reportes bonitos. Es para asegurar que el SISTEMA esta vivo y avanzando. Cada minuto cuenta.',
      decir: [
        'Agenda fija de 30 minutos: Inicio 5 · Evaluacion 5 c/u · Bloqueos 10 · Ajustes 5 · Activacion 5. Cronometrada.',
        'Lo que NO se hace: alargar, desviarse, contar historias largas, quejarse sin solucion. Lo que SI se hace: ir al punto, escuchar, decidir, ejecutar.',
        'Tu rol no es moderadora ni secretaria — es la persona que ENFOCA, CORRIGE y ACTIVA al equipo. Punto final.',
      ],
      ilustrar: 'Tres frases clave: "Vamos al punto." "Cual es el siguiente paso?" "Eso lo resolvemos esta semana." Repitelas hasta que se vuelvan cultura.',
      preguntar: 'Cuantas reuniones terminan sin un siguiente paso CONCRETO? Esas no son reuniones — son sesiones de desahogo disfrazadas de trabajo.',
      aplicar: 'En la proxima reunion cronometrenla. Si pasa de 30 minutos, identifiquen QUIEN desvio y por que. Sin pena, con amor — pero sin pena.',
      transicion: 'Y todo este sistema apunta a UNA sola cosa medible al final del ano: ganar lideres servidores que multipliquen.',
    },
  },

  // ----- 27. ESTRATEGIA DE GANAR -----
  {
    id: 'estrategia-ganar',
    type: 'estrategia',
    title: 'Estrategia de Ganar',
    subtitle: '40 lideres · Plan anual',
    notes: {
      abrir: 'No estamos hablando de "mas asistencia los domingos". Estamos hablando de 40 LIDERES SERVIDORES formados, activos, multiplicando. Esa es la meta.',
      decir: [
        'Cada 2 semanas: personas haciendo MCD, NPT, Bienvenida, Retiros LBS. Movimiento medible, no esperanzas vagas.',
        'Discipulados clave: "Mi llamado es sobrenatural" + el segundo y el tercer discipulado. En orden, sin saltos.',
        'Quien se inscribe en consolidacion debe recibir un reconocimiento PUBLICO claro. Lo que celebramos, eso multiplicamos.',
      ],
      ilustrar: 'Plan de visita: confirma datos, entrega un regalo, ofrece MCD, conecta con mentor. Cuatro pasos sencillos que producen un lider en pocos meses.',
      preguntar: 'De los 40 lideres que queremos ganar este ano... cuantos ya estan identificados con NOMBRE Y APELLIDO en tu lista de oracion?',
      aplicar: 'Escribe los primeros 5 nombres de tu lista personal. Por ellos vas a orar, por ellos vas a llorar, por ellos vas a ayunar.',
      transicion: 'Y ahora cerramos. Todo lo que hemos visto se reduce a una sola palabra que define a la iglesia que Dios suena: CULTURA.',
    },
  },

  // ----- 28. CULTURA Y LLAMADO FINAL -----
  {
    id: 'cultura-cierre',
    type: 'cierre',
    title: 'Cultura y Llamado Final',
    subtitle: 'Ano de Cosecha y Restitucion',
    notes: {
      abrir: 'Cinco palabras que ya no son adornos en la pared. Son los pilares que nos sostienen: AMOR · ORDEN · ORACION · SERVICIO · UNIDAD.',
      decir: [
        'Las CELULAS detectan. Las PUERTAS responden. El LIDERAZGO supervisa. Y DIOS — solo Dios — transforma. Esa es la cadena del Reino.',
        'Hay una puerta para que sirvas. Una funcion para tu don. Una respuesta para cada necesidad. Nadie sobra. Nadie esta de relleno.',
        'Este es el ano de cosecha. Lo que parecia perdido, Dios lo restituye. Lo que parecia tarde, Dios lo acelera. Cree y avanza.',
      ],
      ilustrar: '"Aqui cada miembro tiene un lugar, cada necesidad tiene una respuesta, y cada vida tiene un proceso." Esa frase es nuestra firma. Nuestro pacto. Nuestro estilo de iglesia.',
      preguntar: 'Vas a salir de aqui como observador que aplaude... o como protagonista que ejecuta? La cosecha se reparte solo entre quienes trabajan en ella.',
      aplicar: 'Antes de irte, escribe en tu manual estas tres cosas: la PUERTA donde vas a servir, la PERSONA a quien vas a discipular, la SEMANA en que comienzas.',
      transicion: 'Cerramos declarando juntos: "Soy parte de la cosecha. Mi puerta esta abierta. Aqui estoy. Envia me."',
      versiculoFinal: '"Porque de la manera que en un cuerpo tenemos muchos miembros, pero no todos los miembros tienen la misma funcion..." — Romanos 12:4',
    },
  },
];
