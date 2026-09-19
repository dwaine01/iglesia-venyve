import React, { useEffect, useRef, useState } from 'react';
import { Camera, CameraOff, Loader2 } from 'lucide-react';
import { Button } from '../ui/button';

export const QrScanner = ({ onScan }) => {
  const videoRef = useRef(null); const streamRef = useRef(null); const frameRef = useRef(null);
  const [active, setActive] = useState(false); const [starting, setStarting] = useState(false); const [error, setError] = useState('');
  const stop = () => { if (frameRef.current) cancelAnimationFrame(frameRef.current); streamRef.current?.getTracks().forEach((track) => track.stop()); streamRef.current = null; setActive(false); };
  useEffect(() => stop, []);
  const start = async () => {
    setError('');
    if (!('BarcodeDetector' in window) || !navigator.mediaDevices?.getUserMedia) { setError('Escáner no disponible en este navegador. Use el campo de código.'); return; }
    setStarting(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false }); streamRef.current = stream; videoRef.current.srcObject = stream; await videoRef.current.play(); setActive(true);
      const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
      const scan = async () => { if (!streamRef.current) return; try { const codes = await detector.detect(videoRef.current); if (codes[0]?.rawValue) { const value = codes[0].rawValue; stop(); onScan(value); return; } } catch (scanError) { setError('No se pudo leer la cámara. Use el campo de código.'); stop(); return; } frameRef.current = requestAnimationFrame(scan); };
      frameRef.current = requestAnimationFrame(scan);
    } catch (cameraError) { setError('No se pudo abrir la cámara. Use el campo de código.'); stop(); }
    finally { setStarting(false); }
  };
  return <section className="border bg-slate-950 p-3 text-white" data-testid="qr-scanner"><div className="aspect-video overflow-hidden bg-black"><video ref={videoRef} muted playsInline className={`h-full w-full object-cover ${active ? 'block' : 'hidden'}`} data-testid="qr-scanner-video" />{!active && <div className="flex h-full items-center justify-center text-slate-400"><Camera className="h-12 w-12" /></div>}</div>{error && <p className="mt-2 text-xs text-amber-300" data-testid="qr-scanner-error">{error}</p>}<Button type="button" onClick={active ? stop : start} disabled={starting} className="mt-3 w-full bg-white text-slate-950 hover:bg-slate-100" data-testid="qr-scanner-toggle-button">{starting ? <Loader2 className="h-4 w-4 animate-spin" /> : active ? <CameraOff className="h-4 w-4" /> : <Camera className="h-4 w-4" />}{active ? 'Detener cámara' : 'Escanear QR'}</Button></section>;
};