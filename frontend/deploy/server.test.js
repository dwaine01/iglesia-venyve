/* Pruebas del servidor del panel (node --test frontend/deploy): app, reenvío de /api,
 * subidas grandes, WebSocket, servidor caído y protección contra el reenvío a sí mismo. */
'use strict';

const assert = require('node:assert/strict');
const fs = require('fs');
const http = require('http');
const net = require('net');
const os = require('os');
const path = require('path');
const test = require('node:test');
const zlib = require('zlib');

const { createPanelServer } = require('./server');

const listen = (server) => new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server.address().port)));
const close = (server) => new Promise((resolve) => { server.close(() => resolve()); server.closeAllConnections(); });

function request(port, { method = 'GET', path: url = '/', headers = {}, body } = {}) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port, method, path: url, headers }, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks) }));
    });
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

let build;
let backend;
let backendPort;
let panel;
let panelPort;
const seen = [];

test.before(async () => {
  build = fs.mkdtempSync(path.join(os.tmpdir(), 'panel-build-'));
  fs.mkdirSync(path.join(build, 'static', 'js'), { recursive: true });
  fs.writeFileSync(path.join(build, 'index.html'), `<!doctype html><title>Panel</title>${'<!-- relleno -->'.repeat(200)}`);
  fs.writeFileSync(path.join(build, 'static', 'js', 'main.abc123.js'), `console.log("panel");${' '.repeat(4000)}`);
  fs.writeFileSync(path.join(build, 'manifest.json'), '{"name":"Panel"}');

  // Servidor falso que hace de backend: devuelve lo que recibió y acepta un WebSocket.
  backend = http.createServer((req, res) => {
    let size = 0;
    req.on('data', (chunk) => { size += chunk.length; });
    req.on('end', () => {
      seen.push({ method: req.method, url: req.url, headers: req.headers, size });
      res.writeHead(req.url.startsWith('/api/missing') ? 404 : 200, { 'content-type': 'application/json', 'x-backend': 'si', 'set-cookie': 'prueba=1; Path=/' });
      res.end(JSON.stringify({ url: req.url, size, host: req.headers.host }));
    });
  });
  backend.on('upgrade', (req, socket) => {
    seen.push({ upgrade: req.url, headers: req.headers });
    socket.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: prueba\r\n\r\n');
    socket.write('hola-desde-el-servidor');
    socket.on('data', (data) => socket.write(Buffer.concat([Buffer.from('eco:'), data])));
  });
  backendPort = await listen(backend);
  panel = createPanelServer({ buildDir: build, target: `http://127.0.0.1:${backendPort}`, log: { error() {} } });
  panelPort = await listen(panel);
});

test.after(async () => {
  await close(panel);
  await close(backend);
  fs.rmSync(build, { recursive: true, force: true });
  http.globalAgent.destroy();
});

test('la app: direcciones como /r/<código> devuelven index.html; los archivos de /static, con caché larga', async () => {
  const page = await request(panelPort, { path: '/r/8GS8CFVB' });
  assert.equal(page.status, 200);
  assert.match(page.headers['content-type'], /text\/html/);
  assert.equal(page.headers['cache-control'], 'no-cache');
  assert.match(page.body.toString(), /<title>Panel<\/title>/);

  const script = await request(panelPort, { path: '/static/js/main.abc123.js', headers: { 'accept-encoding': 'gzip' } });
  assert.equal(script.status, 200);
  assert.match(script.headers['content-type'], /javascript/);
  assert.match(script.headers['cache-control'], /immutable/);
  assert.equal(script.headers['content-encoding'], 'gzip');
  assert.match(zlib.gunzipSync(script.body).toString(), /console.log\("panel"\)/);

  assert.equal((await request(panelPort, { path: '/static/js/no-existe.js' })).status, 404);
  const again = await request(panelPort, { path: '/manifest.json', headers: { 'if-none-match': (await request(panelPort, { path: '/manifest.json' })).headers.etag } });
  assert.equal(again.status, 304);
});

test('nunca entrega archivos fuera de la carpeta de la app', async () => {
  for (const sneaky of ['/../../etc/passwd', '/%2e%2e/%2e%2e/etc/passwd', '/..%2f..%2fetc%2fpasswd', '/static/../../server.js']) {
    const answer = await request(panelPort, { path: sneaky });
    assert.ok(!answer.body.toString().includes('root:'), sneaky);
    assert.ok([200, 404].includes(answer.status), sneaky);
  }
});

test('/api se reenvía al servidor con su ruta, encabezados y respuesta', async () => {
  const answer = await request(panelPort, { path: '/api/kiosk/config?link=ABC&tablet=Tableta%201A2B', headers: { authorization: 'Bearer prueba', 'x-forwarded-for': '203.0.113.7', host: 'panel.iglesiavenyve.org' } });
  assert.equal(answer.status, 200);
  assert.equal(answer.headers['x-backend'], 'si');
  assert.deepEqual(answer.headers['set-cookie'], ['prueba=1; Path=/']);
  const got = seen.at(-1);
  assert.equal(got.url, '/api/kiosk/config?link=ABC&tablet=Tableta%201A2B');
  assert.equal(got.headers.host, `127.0.0.1:${backendPort}`);
  assert.equal(got.headers.authorization, 'Bearer prueba');
  assert.equal(got.headers['x-forwarded-for'].split(',')[0].trim(), '203.0.113.7');  // la conexión real queda primera
  assert.equal(got.headers['x-forwarded-host'], 'panel.iglesiavenyve.org');
  assert.equal((await request(panelPort, { path: '/api/missing' })).status, 404);
});

test('subida grande (25 MB) pasa completa y por partes', async () => {
  const body = Buffer.alloc(25 * 1024 * 1024, 7);
  const answer = await request(panelPort, { method: 'POST', path: '/api/subir', headers: { 'content-type': 'application/octet-stream', 'content-length': body.length }, body });
  assert.equal(answer.status, 200);
  assert.equal(JSON.parse(answer.body).size, body.length);
  // Texto (como envía la tableta): llega tal cual.
  const text = await request(panelPort, { method: 'POST', path: '/api/kiosk/registrations', headers: { 'content-type': 'text/plain;charset=UTF-8' }, body: '{"nombre":"Ana"}' });
  assert.equal(JSON.parse(text.body).size, 16);
  assert.equal(seen.at(-1).headers['content-type'], 'text/plain;charset=UTF-8');
});

test('WebSocket (radio): se abre por el panel y los datos van y vienen', async () => {
  const socket = net.connect(panelPort, '127.0.0.1');
  await new Promise((resolve) => socket.on('connect', resolve));
  socket.write('GET /api/radio/ws/campana?token=abc HTTP/1.1\r\nHost: panel.iglesiavenyve.org\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n');
  let received = '';
  socket.on('data', (data) => { received += data.toString(); });
  await new Promise((resolve) => { const check = setInterval(() => { if (received.includes('hola-desde-el-servidor')) { clearInterval(check); resolve(); } }, 20); });
  assert.match(received, /^HTTP\/1.1 101/);
  socket.write('audio');
  await new Promise((resolve) => { const check = setInterval(() => { if (received.includes('eco:audio')) { clearInterval(check); resolve(); } }, 20); });
  const got = seen.find((item) => item.upgrade);
  assert.equal(got.upgrade, '/api/radio/ws/campana?token=abc');
  assert.equal(got.headers.upgrade, 'websocket');
  socket.end();
  await new Promise((resolve) => { const check = setInterval(() => { panel.getConnections((error, count) => { if (!error && count === 0) { clearInterval(check); resolve(); } }); }, 20); });
});

test('si el servidor no responde: 502 con un mensaje claro', async () => {
  const dead = createPanelServer({ buildDir: build, target: 'http://127.0.0.1:1', log: { error() {} } });
  const port = await listen(dead);
  const answer = await request(port, { path: '/api/health' });
  assert.equal(answer.status, 502);
  assert.match(JSON.parse(answer.body).detail, /no pudo comunicarse/);
  assert.equal((await request(port, { path: '/' })).status, 200);  // la app sigue abriendo
  await close(dead);
});

test('no se reenvía a sí mismo si el destino es el mismo panel', async () => {
  const loop = createPanelServer({ buildDir: build, target: 'https://panel.iglesiavenyve.org', log: { error() {} } });
  const port = await listen(loop);
  const answer = await request(port, { path: '/api/health', headers: { host: 'panel.iglesiavenyve.org' } });
  assert.equal(answer.status, 508);
  await close(loop);
});
