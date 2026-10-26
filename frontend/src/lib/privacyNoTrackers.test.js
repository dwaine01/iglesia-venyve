/* Privacidad: el panel muestra nombres, teléfonos y peticiones de oración. Ninguna analítica ni
 * grabación de sesión de terceros puede cargarse en la página (PostHog venía de la plantilla). */
const fs = require('fs');
const path = require('path');

test('la página no carga analítica ni grabación de sesión de terceros', () => {
  const html = fs.readFileSync(path.join(__dirname, '../../public/index.html'), 'utf8').toLowerCase();
  ['posthog', 'session_recording', 'googletagmanager', 'google-analytics', 'hotjar', 'clarity.ms', 'segment.com'].forEach((tracker) => {
    expect(html).not.toContain(tracker);
  });
});
