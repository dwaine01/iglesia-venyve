// Ubicación actual del celular para ubicar una casa. Pide permiso al
// navegador y explica claramente si se niega o si la precisión es mala.
export const LOW_ACCURACY_M = 100;

const MESSAGES = {
  1: 'No diste permiso de ubicación. Actívalo para este sitio en los ajustes del navegador, o escribe la dirección.',
  2: 'El celular no pudo obtener la ubicación. Sal a un lugar abierto o escribe la dirección.',
  3: 'La ubicación tardó demasiado. Intenta de nuevo o escribe la dirección.',
};

export function getCurrentLocation() {
  return new Promise((resolve, reject) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      reject(new Error('Este navegador no permite obtener la ubicación. Escribe la dirección.'));
      return;
    }
    if (typeof window !== 'undefined' && window.isSecureContext === false) {
      reject(new Error('La ubicación solo funciona en una conexión segura (https).'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy_m: Math.round(position.coords.accuracy || 0),
      }),
      (error) => reject(new Error(MESSAGES[error.code] || 'No se pudo obtener la ubicación.')),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 },
    );
  });
}

export const accuracyLabel = (meters) => (meters == null ? '' : meters <= 20 ? `precisión buena (±${meters} m)` : meters <= LOW_ACCURACY_M ? `precisión aceptable (±${meters} m)` : `precisión baja (±${meters} m)`);

// Enlaces de navegación: Apple Maps en iPhone/iPad, Google Maps en lo demás.
export function directionsUrl(latitude, longitude, address) {
  const isApple = typeof navigator !== 'undefined' && /iPhone|iPad|iPod|Macintosh/.test(navigator.userAgent) && 'ontouchend' in document;
  if (latitude != null && longitude != null) {
    return isApple ? `https://maps.apple.com/?daddr=${latitude},${longitude}&dirflg=w` : `https://www.google.com/maps/dir/?api=1&destination=${latitude},${longitude}&travelmode=walking`;
  }
  const query = encodeURIComponent(address || '');
  return isApple ? `https://maps.apple.com/?daddr=${query}` : `https://www.google.com/maps/dir/?api=1&destination=${query}`;
}
