/* Servidor del panel (panel.iglesiavenyve.org) en Railway. Solo usa Node, sin paquetes.
 *
 * 1. Sirve la app de React (carpeta build). Las direcciones de la app, como /r/<código>,
 *    devuelven index.html.
 * 2. Reenvía /api/* al servidor de la iglesia (backend), WebSocket incluido (radio y
 *    pantalla de campaña). Así el navegador habla con UN SOLO dominio: el del panel.
 *    Las tabletas Amazon Fire (Silk) abrían el panel pero no lograban llegar a
 *    *.up.railway.app.
 *
 * Variables: PORT y API_PROXY_TARGET. Si falta API_PROXY_TARGET, se usa
 * REACT_APP_BACKEND_URL, la misma dirección del backend que ya tiene el servicio.
 * Puede ser la dirección privada de Railway, por ejemplo http://<servicio>.railway.internal:<puerto>. */
'use strict';

const fs = require('fs');
const http = require('http');
const https = require('https');
const path = require('path');
const zlib = require('zlib');
const crypto = require('crypto');

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8', '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.map': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json; charset=utf-8', '.txt': 'text/plain; charset=utf-8', '.xml': 'application/xml; charset=utf-8',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp',
  '.ico': 'image/x-icon', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.otf': 'font/otf',
  '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.mp4': 'video/mp4', '.webm': 'video/webm', '.pdf': 'application/pdf',
};
const COMPRESSIBLE = /^(text\/|application\/(javascript|json|manifest\+json|xml)|image\/svg)/;
// Encabezados de un solo tramo: no se reenvían (cada conexión tiene los suyos).
const HOP = new Set(['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'proxy-connection', 'te', 'trailer', 'transfer-encoding', 'upgrade']);

const isApi = (url) => url === '/api' || url.startsWith('/api/') || url.startsWith('/api?');

function forwardHeaders(req, target, upgrade) {
  const headers = {};
  for (const [name, value] of Object.entries(req.headers)) {
    if (!HOP.has(name) && name !== 'host') headers[name] = value;
  }
  headers.host = target.host;
  // Quién pidió de verdad (el límite de intentos del registro de visitantes lo usa).
  const client = req.socket.remoteAddress || '';
  headers['x-forwarded-for'] = req.headers['x-forwarded-for'] ? `${req.headers['x-forwarded-for']}, ${client}` : client;
  headers['x-forwarded-host'] = req.headers.host || '';
  headers['x-forwarded-proto'] = req.headers['x-forwarded-proto'] || 'https';
  if (upgrade) {
    headers.connection = 'Upgrade';
    headers.upgrade = req.headers.upgrade;
  }
  return headers;
}

function responseHeaders(raw) {
  const headers = {};
  for (const [name, value] of Object.entries(raw)) if (!HOP.has(name)) headers[name] = value;
  return headers;
}

function createPanelServer({ buildDir, target, log = console }) {
  const root = path.resolve(buildDir);
  const api = target ? new URL(target) : null;
  const client = api && api.protocol === 'http:' ? http : https;
  const agent = api ? new client.Agent({ keepAlive: true, maxSockets: 128 }) : null;
  const apiBase = api ? api.pathname.replace(/\/$/, '') : '';
  const cache = new Map();

  function proxy(req, res) {
    if (api && (req.headers['x-forwarded-host'] || req.headers.host) === api.host) {
      // El destino es el mismo panel: se reenviaría a sí mismo sin fin.
      res.writeHead(508, { 'content-type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ detail: 'API_PROXY_TARGET apunta al mismo panel. Debe ser la dirección del servidor (backend).' }));
      return;
    }
    if (!api) {
      res.writeHead(502, { 'content-type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ detail: 'El panel no tiene configurada la dirección del servidor (API_PROXY_TARGET).' }));
      return;
    }
    const upstream = client.request({ protocol: api.protocol, hostname: api.hostname, port: api.port || undefined, method: req.method, path: apiBase + req.url,
      headers: forwardHeaders(req, api, false), agent });
    upstream.on('response', (answer) => {
      res.writeHead(answer.statusCode, answer.statusMessage, responseHeaders(answer.headers));
      answer.pipe(res);
      answer.on('error', () => res.destroy());
    });
    upstream.on('error', (error) => {
      log.error(`[api] ${req.method} ${req.url.split('?')[0]}: ${error.code || error.message}`);
      if (!res.headersSent) {
        res.writeHead(502, { 'content-type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ detail: 'El panel no pudo comunicarse con el servidor. Intente de nuevo en unos segundos.' }));
      } else {
        res.destroy();
      }
    });
    req.on('aborted', () => upstream.destroy());
    req.pipe(upstream);  // los archivos que se suben pasan por partes, sin guardarse en memoria
  }

  function upgrade(req, socket, head) {
    if (!api || !isApi(req.url)) { socket.destroy(); return; }
    socket.on('error', () => socket.destroy());
    const upstream = client.request({ protocol: api.protocol, hostname: api.hostname, port: api.port || undefined, method: req.method, path: apiBase + req.url,
      headers: forwardHeaders(req, api, true), agent: false });
    upstream.on('upgrade', (answer, upstreamSocket, upstreamHead) => {
      const lines = [`HTTP/1.1 ${answer.statusCode} ${answer.statusMessage || 'Switching Protocols'}`];
      for (let index = 0; index < answer.rawHeaders.length; index += 2) lines.push(`${answer.rawHeaders[index]}: ${answer.rawHeaders[index + 1]}`);
      socket.write(`${lines.join('\r\n')}\r\n\r\n`);
      if (upstreamHead && upstreamHead.length) socket.write(upstreamHead);
      if (head && head.length) upstreamSocket.write(head);
      upstreamSocket.on('error', () => socket.destroy());
      socket.on('error', () => upstreamSocket.destroy());
      socket.on('close', () => upstreamSocket.destroy());
      upstreamSocket.on('close', () => socket.destroy());
      // Si una punta termina, se cierran las dos (si no, la conexión queda medio abierta para siempre).
      socket.on('end', () => { upstreamSocket.end(); socket.destroy(); });
      upstreamSocket.on('end', () => { socket.end(); upstreamSocket.destroy(); });
      socket.setNoDelay(true);
      upstreamSocket.setNoDelay(true);
      upstreamSocket.pipe(socket);
      socket.pipe(upstreamSocket);
    });
    upstream.on('response', (answer) => {  // el servidor no aceptó el WebSocket: se le dice al navegador tal cual
      const lines = [`HTTP/1.1 ${answer.statusCode} ${answer.statusMessage}`];
      for (let index = 0; index < answer.rawHeaders.length; index += 2) lines.push(`${answer.rawHeaders[index]}: ${answer.rawHeaders[index + 1]}`);
      socket.write(`${lines.join('\r\n')}\r\n\r\n`);
      answer.pipe(socket);
    });
    upstream.on('error', (error) => { log.error(`[ws] ${req.url.split('?')[0]}: ${error.code || error.message}`); socket.destroy(); });
    upstream.end();
  }

  function load(file) {
    if (cache.has(file)) return cache.get(file);
    const body = fs.readFileSync(file);
    const type = TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream';
    const entry = { body, type, etag: `"${crypto.createHash('sha1').update(body).digest('base64').slice(0, 27)}"`,
      gzip: COMPRESSIBLE.test(type) && body.length > 1024 ? zlib.gzipSync(body, { level: 9 }) : null };
    cache.set(file, entry);
    return entry;
  }

  function resolve(urlPath) {
    let decoded;
    try { decoded = decodeURIComponent(urlPath); } catch { return null; }
    const file = path.resolve(root, `.${path.posix.normalize(`/${decoded}`)}`);
    if (file !== root && !file.startsWith(root + path.sep)) return null;  // nunca fuera de la carpeta
    try { return fs.statSync(file).isFile() ? file : null; } catch { return null; }
  }

  function serveStatic(req, res) {
    if (req.method !== 'GET' && req.method !== 'HEAD') { res.writeHead(405, { allow: 'GET, HEAD' }); res.end(); return; }
    const urlPath = (req.url || '/').split('?')[0];
    let file = resolve(urlPath);
    if (!file) {
      // Un archivo de la compilación que no existe es 404; cualquier otra dirección es la app (index.html).
      if (urlPath.startsWith('/static/')) { res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' }); res.end('No encontrado'); return; }
      file = path.join(root, 'index.html');
    }
    const entry = load(file);
    const immutable = urlPath.startsWith('/static/');
    const headers = { 'content-type': entry.type, etag: entry.etag, vary: 'Accept-Encoding', 'x-content-type-options': 'nosniff',
      'cache-control': immutable ? 'public, max-age=31536000, immutable' : 'no-cache' };
    if (req.headers['if-none-match'] === entry.etag) { res.writeHead(304, headers); res.end(); return; }
    const gzip = entry.gzip && /\bgzip\b/.test(req.headers['accept-encoding'] || '');
    const body = gzip ? entry.gzip : entry.body;
    if (gzip) headers['content-encoding'] = 'gzip';
    headers['content-length'] = body.length;
    res.writeHead(200, headers);
    res.end(req.method === 'HEAD' ? undefined : body);
  }

  const server = http.createServer((req, res) => {
    if (isApi(req.url || '')) proxy(req, res);
    else serveStatic(req, res);
  });
  server.on('upgrade', upgrade);
  server.on('close', () => { if (agent) agent.destroy(); });
  server.on('clientError', (error, socket) => socket.destroy());
  // Subidas y reportes largos: sin límite corto de tiempo por pedido.
  server.requestTimeout = 10 * 60 * 1000;
  server.headersTimeout = 65 * 1000;
  server.keepAliveTimeout = 65 * 1000;
  return server;
}

module.exports = { createPanelServer, isApi };

if (require.main === module) {
  const target = (process.env.API_PROXY_TARGET || process.env.REACT_APP_BACKEND_URL || '').trim();
  const port = Number(process.env.PORT || 8080);
  const server = createPanelServer({ buildDir: process.env.BUILD_DIR || path.join(__dirname, 'build'), target });
  server.listen(port, '0.0.0.0', () => {
    console.log(`Panel en el puerto ${port}; /api → ${target ? new URL(target).origin : '(sin configurar)'}`);
  });
  const stop = () => server.close(() => process.exit(0));
  process.on('SIGTERM', stop);
  process.on('SIGINT', stop);
}
