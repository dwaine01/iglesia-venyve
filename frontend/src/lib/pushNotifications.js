// Notificaciones push en este dispositivo (Fase 6B). Solo se ofrece cuando el
// servidor responde enabled=true (el dueño lo activa con variables de entorno).
const toKey = (base64) => {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const raw = window.atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from([...raw].map((char) => char.charCodeAt(0)));
};

export const pushSupported = () => typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;

export async function enablePush(publicKey, save) {
  if (!pushSupported()) throw new Error('Este navegador no permite avisos push');
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('No diste permiso para recibir avisos en este dispositivo');
  const registration = await navigator.serviceWorker.register(`${process.env.PUBLIC_URL || ''}/push-sw.js`);
  const subscription = (await registration.pushManager.getSubscription()) || await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: toKey(publicKey) });
  await save(subscription.toJSON());
}
