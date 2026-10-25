/* Textos fijos de la tableta en español e inglés (sin dependencias: un diccionario).
 * Los textos editables (bienvenida, aviso de privacidad y confirmación) llegan del
 * servidor en ambos idiomas. Lo que se GUARDA (claves y valores) no cambia con el idioma. */

const es = {
  chooseTitle: 'Elige tu idioma',
  chooseSubtitle: 'Choose your language',
  begin: 'Iniciar registro',
  step: (current, total) => `Paso ${current} de ${total}`,
  cancel: 'Cancelar', back: 'Atrás', next: 'Siguiente', finish: 'Terminar registro', saving: 'Guardando…', done: 'Listo',
  stillThere: '¿Sigues ahí?', idleWarning: (seconds) => `Por tu privacidad, el registro se borrará en ${seconds} segundos.`, continue: 'Continuar',
  waiting: (count) => `${count} registro(s) esperando internet`,
  needLinkTitle: 'Esta tableta necesita el enlace nuevo', openLink: 'Abra el enlace de tabletas que aparece en Registro de visitantes › Enlaces.', linkGone: 'Este enlace ya no funciona.',
  preparing: 'Preparando el registro…', retryNow: 'Reintentar ahora', retrying: 'Reintentando…',
  serverError: (status) => `El servidor respondió con un error (${status}). Reintentando…`,
  slow: 'El servidor tardó demasiado en responder. Reintentando…', outdated: 'El servidor todavía no tiene la versión nueva. Reintentando…',
  blocked: 'El servidor responde, pero este navegador bloqueó el pedido. Reintentando…', serverUnreachable: 'La tableta tiene internet y abre el panel, pero no llega al servidor. Reintentando…', offlineServer: 'No hay conexión con el servidor. Revise el internet de la tableta. Reintentando…',
  thanks: (name) => `¡Gracias, ${name}!`, yourNumber: 'Tu número de registro',
  offlineSaved: 'Tu registro quedó guardado en esta tableta y se enviará apenas vuelva el internet. Un servidor te dará tu número.',
  checkData: 'Revisa los datos e intenta de nuevo.',
  services: { sunday: 'Servicio del domingo', wednesday: 'Servicio del miércoles' },
  // Paso 1
  nameTitle: '¿Cómo te llamas?', firstName: 'Nombre', lastName: 'Apellidos', preferred: '¿Cómo te gusta que te llamen?', preferredHint: 'Ej.: Toño',
  sex: 'Sexo', female: 'Femenino', male: 'Masculino', careNote: 'Cuidamos tus datos: solo los usamos para darte la bienvenida y servirte.',
  // Contacto
  contactTitle: '¿Cómo te contactamos?', phone: 'Teléfono', email: 'Correo electrónico', methodsLabel: '¿Cómo prefieres que te contactemos? Puedes elegir varias.',
  methods: { call: 'Llamada', text: 'Mensaje de texto', whatsapp: 'WhatsApp', email: 'Correo electrónico' },
  // Dónde vives
  homeTitle: '¿Dónde vives?', street: 'Calle y número', city: 'Ciudad', zip: 'Código postal', newInArea: '¿Eres nuevo en esta área?',
  birthTitle: 'Fecha de nacimiento', birthHint: 'Para tenerte presente el día de tu cumpleaños', day: 'Día', month: 'Mes', year: 'Año',
  months: ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'],
  yes: 'Sí', no: 'No',
  // Visita
  visitTitle: 'Tu visita', firstVisit: '¿Es tu primera vez con nosotros?', firstTime: 'Primera vez', beenBefore: 'Ya los había visitado',
  invitedBy: '¿Quién te invitó?', invitedHint: 'Nombre de quien te invitó', heard: '¿Cómo te enteraste de nosotros?',
  heardOptions: { 'Invitación de alguien': 'Invitación de alguien', 'Redes sociales': 'Redes sociales', Internet: 'Internet', 'Pasé por la iglesia': 'Pasé por la iglesia', 'Evento o campaña Ven y Come': 'Evento o campaña Ven y Come', Otro: 'Otro' },
  // Fe
  faithTitle: 'Tu fe', christian: '¿Eres cristiano o cristiana?', christianOptions: { yes: 'Sí', on_way: 'Estoy en camino', not_yet: 'No todavía' },
  accept: 'Quiero aceptar a Jesús como mi Salvador', acceptOptions: { today: 'Hoy', another_day: 'Otro día' },
  reconcile: 'Deseo reconciliarme con Dios', faithInfo: 'Quiero informarme de cómo ser cristiano', otherChurch: '¿Asistes a otra iglesia?', churchName: 'Nombre de la iglesia', pastorName: 'Nombre del pastor',
  // Familia
  familyTitle: 'Tu familia', marital: 'Estado civil', maritalOptions: { single: 'Soltero o soltera', married: 'Casado o casada', other: 'Otro' }, spouse: 'Nombre de tu esposo o esposa',
  hasChildren: '¿Tienes hijos?', companions: '¿Quién te acompaña hoy?', companionsHint: 'Ej.: mi esposa y mis dos hijos', childName: (index) => `Nombre del hijo o hija ${index}`, age: 'Edad',
  childAge: (index) => `Edad del hijo o hija ${index}`, removeChild: (index) => `Quitar al hijo o hija ${index}`, remove: 'Quitar', addChild: 'Agregar otro hijo', kids: 'Deseo que mis hijos participen en el ministerio de niños',
  // Servir
  serveTitle: '¿Cómo podemos servirte?', serveHint: 'Puedes elegir varias.',
  serveGroups: { prayer: 'Oración', visit: 'Visita e información', counseling: 'Consejería y familia', serve: 'Participar y servir' },
  requests: {
    prayer_me: 'Quiero oración por mí', prayer_family: 'Quiero oración por mi familia', call_prayer: 'Llámenme para orar', visit: 'Me gustaría que me visiten', info: 'Quiero saber más de esta iglesia',
    counseling_personal: 'Consejería personal', counseling_marriage: 'Consejería matrimonial', counseling_family: 'Consejería familiar', support_child: 'Apoyo para un hijo o familiar', other_help: 'Otra ayuda',
    membership: 'Me gustaría pertenecer a la iglesia', serve: 'Quiero servir en la iglesia', home_service: 'Me gustaría un culto en mi casa', no_followup: 'Prefiero no recibir seguimiento por ahora',
  },
  // Notas
  notesTitle: 'Cuéntanos un poco más', notesHint: 'Es confidencial.', prayerWhy: '¿Por qué quieres que oremos?', prayerOnly: 'Solo lo verá el equipo de oración.',
  counselingTell: 'Cuéntanos brevemente', counselingOnly: 'Solo lo verá el equipo pastoral.', needsWhat: '¿Qué otra ayuda necesitas?', confidential: 'Confidencial.',
  // Apoyo y cierre
  givingTitle: 'Apoyo', giving: 'Quiero información para ofrendar o donar mensualmente', givingNote: 'No pedimos datos de pago. La encargada de finanzas te dará la información.',
  closeTitle: '¿Podemos comunicarnos contigo para darte seguimiento?', needContact: 'Para darte seguimiento necesitamos tu teléfono o tu correo.', addContact: 'Escribir mi teléfono o correo',
};

const en = {
  chooseTitle: 'Choose your language',
  chooseSubtitle: 'Elige tu idioma',
  begin: 'Start registration',
  step: (current, total) => `Step ${current} of ${total}`,
  cancel: 'Cancel', back: 'Back', next: 'Next', finish: 'Finish registration', saving: 'Saving…', done: 'Done',
  stillThere: 'Are you still there?', idleWarning: (seconds) => `For your privacy, this registration will be cleared in ${seconds} seconds.`, continue: 'Continue',
  waiting: (count) => `${count} registration(s) waiting for internet`,
  needLinkTitle: 'This tablet needs the new link', openLink: 'Open the tablet link shown in Visitor registration › Links.', linkGone: 'This link no longer works.',
  preparing: 'Preparing the registration…', retryNow: 'Try again now', retrying: 'Trying again…',
  serverError: (status) => `The server answered with an error (${status}). Trying again…`,
  slow: 'The server took too long to answer. Trying again…', outdated: 'The server does not have the new version yet. Trying again…',
  blocked: 'The server answers, but this browser blocked the request. Trying again…', serverUnreachable: 'The tablet has internet and opens the panel, but cannot reach the server. Trying again…', offlineServer: 'There is no connection to the server. Check the tablet internet. Trying again…',
  thanks: (name) => `Thank you, ${name}!`, yourNumber: 'Your registration number',
  offlineSaved: 'Your registration was saved on this tablet and will be sent as soon as the internet is back. A volunteer will give you your number.',
  checkData: 'Please check your information and try again.',
  services: { sunday: 'Sunday service', wednesday: 'Wednesday service' },
  nameTitle: 'What is your name?', firstName: 'First name', lastName: 'Last name', preferred: 'What do you like to be called?', preferredHint: 'Example: Tony',
  sex: 'Sex', female: 'Female', male: 'Male', careNote: 'We take care of your information: we only use it to welcome you and serve you.',
  contactTitle: 'How can we contact you?', phone: 'Phone', email: 'Email', methodsLabel: 'How do you prefer us to contact you? You can choose more than one.',
  methods: { call: 'Phone call', text: 'Text message', whatsapp: 'WhatsApp', email: 'Email' },
  homeTitle: 'Where do you live?', street: 'Street and number', city: 'City', zip: 'ZIP code', newInArea: 'Are you new to this area?',
  birthTitle: 'Date of birth', birthHint: 'So we can remember you on your birthday', day: 'Day', month: 'Month', year: 'Year',
  months: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  yes: 'Yes', no: 'No',
  visitTitle: 'Your visit', firstVisit: 'Is this your first time with us?', firstTime: 'First time', beenBefore: 'I have visited before',
  invitedBy: 'Who invited you?', invitedHint: 'Name of the person who invited you', heard: 'How did you hear about us?',
  heardOptions: { 'Invitación de alguien': 'Someone invited me', 'Redes sociales': 'Social media', Internet: 'Internet', 'Pasé por la iglesia': 'I passed by the church', 'Evento o campaña Ven y Come': 'Ven y Come event or campaign', Otro: 'Other' },
  faithTitle: 'Your faith', christian: 'Are you a Christian?', christianOptions: { yes: 'Yes', on_way: 'I am on my way', not_yet: 'Not yet' },
  accept: 'I want to accept Jesus as my Savior', acceptOptions: { today: 'Today', another_day: 'Another day' },
  reconcile: 'I want to reconcile with God', faithInfo: 'I want to learn how to become a Christian', otherChurch: 'Do you attend another church?', churchName: 'Name of the church', pastorName: 'Name of the pastor',
  familyTitle: 'Your family', marital: 'Marital status', maritalOptions: { single: 'Single', married: 'Married', other: 'Other' }, spouse: 'Name of your husband or wife',
  hasChildren: 'Do you have children?', companions: 'Who came with you today?', companionsHint: 'Example: my wife and my two children', childName: (index) => `Name of child ${index}`, age: 'Age',
  childAge: (index) => `Age of child ${index}`, removeChild: (index) => `Remove child ${index}`, remove: 'Remove', addChild: 'Add another child', kids: 'I would like my children to take part in the children’s ministry',
  serveTitle: 'How can we serve you?', serveHint: 'You can choose more than one.',
  serveGroups: { prayer: 'Prayer', visit: 'Visit and information', counseling: 'Counseling and family', serve: 'Belong and serve' },
  requests: {
    prayer_me: 'I would like prayer for me', prayer_family: 'I would like prayer for my family', call_prayer: 'Call me to pray', visit: 'I would like a visit', info: 'I want to know more about this church',
    counseling_personal: 'Personal counseling', counseling_marriage: 'Marriage counseling', counseling_family: 'Family counseling', support_child: 'Support for a child or relative', other_help: 'Other help',
    membership: 'I would like to belong to the church', serve: 'I want to serve in the church', home_service: 'I would like a service in my home', no_followup: 'I prefer not to receive follow-up for now',
  },
  notesTitle: 'Tell us a little more', notesHint: 'It is confidential.', prayerWhy: 'What would you like us to pray for?', prayerOnly: 'Only the prayer team will see it.',
  counselingTell: 'Tell us briefly', counselingOnly: 'Only the pastoral team will see it.', needsWhat: 'What other help do you need?', confidential: 'Confidential.',
  givingTitle: 'Giving', giving: 'I would like information to give or donate monthly', givingNote: 'We do not ask for payment information. The finance coordinator will give you the information.',
  closeTitle: 'May we contact you to follow up?', needContact: 'To follow up with you we need your phone or your email.', addContact: 'Write my phone or email',
};

export const KIOSK_TEXT = { es, en };
export const LANGUAGES = [['es', 'Español'], ['en', 'English']];
