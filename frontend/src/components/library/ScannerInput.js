import React, { useEffect, useRef, useState } from 'react';
import { Html5Qrcode } from 'html5-qrcode';
import { Camera, Keyboard } from 'lucide-react';

import { Button } from '../ui/button';
import { Input } from '../ui/input';

let scannerIdCounter = 0;

/** Campo de escaneo reutilizable: cámara (QR/código de barras vía html5-qrcode),
 * o escáner USB/teclado + búsqueda manual (los escáneres USB escriben el código
 * y presionan Enter automáticamente, por eso basta un input enfocado). */
export const ScannerInput = ({ onDetected, placeholder = 'Escanee o escriba el código y presione Enter', testIdPrefix = 'scanner' }) => {
  const [mode, setMode] = useState('keyboard');
  const [manualValue, setManualValue] = useState('');
  const [elementId] = useState(() => `scanner-region-${++scannerIdCounter}`);
  const scannerRef = useRef(null);
  const inputRef = useRef(null);
  const firstKeyAtRef = useRef(null);

  useEffect(() => {
    if (mode !== 'camera') return;
    const scanner = new Html5Qrcode(elementId);
    scannerRef.current = scanner;
    let stopped = false;
    scanner.start({ facingMode: 'environment' }, { fps: 10, qrbox: 220 }, (decodedText, decodedResult) => {
      if (stopped) return;
      const format = decodedResult?.result?.format?.formatName || '';
      onDetected(decodedText, format.includes('QR') ? 'QR_SCAN' : 'BARCODE_SCAN');
    }, () => {}).catch(() => {});
    return () => { stopped = true; scanner.stop().then(() => scanner.clear()).catch(() => {}); };
  }, [mode, elementId, onDetected]);

  useEffect(() => { if (mode === 'keyboard') inputRef.current?.focus(); }, [mode]);

  const submitManual = (event) => {
    event.preventDefault();
    const value = manualValue.trim();
    if (!value) return;
    const elapsed = firstKeyAtRef.current ? Date.now() - firstKeyAtRef.current : 9999;
    onDetected(value, elapsed < 800 && value.length > 3 ? 'BARCODE_SCAN' : 'MANUAL');
    setManualValue(''); firstKeyAtRef.current = null;
  };

  return <div className="space-y-2" data-testid={`${testIdPrefix}`}>
    <div className="flex gap-2">
      <Button type="button" size="sm" variant={mode === 'keyboard' ? 'default' : 'outline'} onClick={() => setMode('keyboard')} data-testid={`${testIdPrefix}-mode-keyboard`}><Keyboard className="h-4 w-4" />Escáner USB / Manual</Button>
      <Button type="button" size="sm" variant={mode === 'camera' ? 'default' : 'outline'} onClick={() => setMode('camera')} data-testid={`${testIdPrefix}-mode-camera`}><Camera className="h-4 w-4" />Cámara</Button>
    </div>
    {mode === 'keyboard' ? (
      <form onSubmit={submitManual} className="flex gap-2">
        <Input ref={inputRef} value={manualValue} onChange={(e) => { if (!firstKeyAtRef.current) firstKeyAtRef.current = Date.now(); setManualValue(e.target.value); }} placeholder={placeholder} data-testid={`${testIdPrefix}-manual-input`} />
        <Button type="submit" data-testid={`${testIdPrefix}-manual-submit`}>Buscar</Button>
      </form>
    ) : <div id={elementId} className="mx-auto max-w-xs overflow-hidden rounded-lg border" data-testid={`${testIdPrefix}-camera-region`} />}
  </div>;
};
