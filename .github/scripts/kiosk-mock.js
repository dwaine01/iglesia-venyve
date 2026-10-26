// Página local de PRUEBA para las capturas del registro: sirve el panel compilado y simula /api/kiosk
// con datos de prueba (nada se guarda ni se envía). Uso: node kiosk-mock.js <carpeta build> [puerto]
const http = require('http'); const fs = require('fs'); const path = require('path');
const BUILD = process.argv[2]; const PORT = Number(process.argv[3] || 4310);
const texts = { welcome: "¡Bienvenido a Casa de Oración!\n¡Nos alegra que estés aquí!\nEsperamos que hagas de esta iglesia tu casa y de esta familia tu familia.\nQueremos conocerte y saber cómo podemos servirte.",
  privacy: "Usamos tus datos solo para darte la bienvenida y servirte mejor.\nNo los compartimos con nadie fuera de la iglesia.\nPuedes pedir que los corrijamos o borremos cuando quieras.",
  confirmation: "¡Gracias por registrarte!\nYa eres parte de esta familia.\nSi necesitas algo, muestra este número a cualquier servidor de la iglesia.", privacy_version: 'v1' };
const config = { device_name: 'Tableta PRUEBA', service: { kind: 'sunday', label: 'Culto dominical' }, texts, texts_en: { ...texts, welcome: 'Welcome to Casa de Oración!\nWe are glad you are here!\nWe hope you make this church your home.\nWe want to get to know you.' },
  timeouts: { form_warn_seconds: 240, form_reset_seconds: 300, start_reset_seconds: 600, confirm_reset_seconds: 60 }, ask_birth_year: false, short_path: '/r/PRUEBA' };
const types = { '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.json': 'application/json', '.svg': 'image/svg+xml', '.html': 'text/html', '.woff2': 'font/woff2', '.ico': 'image/x-icon' };
http.createServer((req, res) => {
  const url = req.url.split('?')[0];
  if (url.startsWith('/api/')) {
    res.setHeader('Content-Type', 'application/json');
    if (url === '/api/kiosk/config') return res.end(JSON.stringify(config));
    if (url === '/api/kiosk/ping') return res.end(JSON.stringify({ ok: true, kiosk_api: 5 }));
    if (url === '/api/kiosk/registrations/draft') return res.end('{"ok":true}');
    if (url === '/api/kiosk/registrations') return res.end(JSON.stringify({ visitor_number: 'V-0427', greeting_name: 'María', confirmation: texts.confirmation }));
    res.statusCode = 404; return res.end('{}');
  }
  let file = path.join(BUILD, url);
  if (!file.startsWith(BUILD) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) file = path.join(BUILD, 'index.html');
  res.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
}).listen(PORT, () => console.log('mock on', PORT));
