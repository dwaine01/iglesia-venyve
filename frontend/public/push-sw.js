/* Service worker SOLO para notificaciones push (Fase 6B). Se registra únicamente
   cuando el servidor tiene el push activado y la persona lo permite. */
self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (error) { data = { title: 'Ven y Ve 360', body: event.data && event.data.text() }; }
  event.waitUntil(self.registration.showNotification(data.title || 'Ven y Ve 360', { body: data.body || '', data: { url: data.url || '/' } }));
});
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
    const existing = clients.find((client) => 'focus' in client);
    if (existing) { existing.navigate(url); return existing.focus(); }
    return self.clients.openWindow(url);
  }));
});
