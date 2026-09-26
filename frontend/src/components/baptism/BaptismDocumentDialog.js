import React, { useEffect, useRef, useState } from 'react';
import QRCode from 'qrcode';
import { Download, Minus, Plus, Printer } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { BaptismCertificateTemplate } from './BaptismCertificateTemplate';
import { downloadBaptismPdf, printBaptismDocument } from './baptismPdf';

export const BaptismDocumentDialog = ({ open, onOpenChange, data, signatureSrc }) => {
  const [qrSrc, setQrSrc] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [printing, setPrinting] = useState(false);
  const [zoom, setZoom] = useState(1);
  const certificateRef = useRef(null);

  useEffect(() => {
    if (!data?.verification_path) return;
    QRCode.toDataURL(`${window.location.origin}${data.verification_path}`, {
      errorCorrectionLevel: 'Q', margin: 4, width: 900,
      color: { dark: '#07111F', light: '#FFFFFF' },
    }).then(setQrSrc).catch(() => toast.error('No se pudo generar el QR'));
  }, [data]);
  useEffect(() => { if (open) setZoom(1); }, [open]);

  const download = async () => {
    setDownloading(true);
    try {
      await downloadBaptismPdf({ data, certificate: certificateRef.current });
      toast.success('PDF listo para impresión profesional');
    } catch { toast.error('No se pudo generar el PDF'); }
    finally { setDownloading(false); }
  };

  const print = async () => {
    setPrinting(true);
    try {
      await printBaptismDocument({ certificate: certificateRef.current });
      toast.success('Documento preparado para impresión');
    } catch { toast.error('No se pudo preparar la impresión'); }
    finally { setPrinting(false); }
  };

  if (!data) return null;
  const shellStyle = { zoom };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[94vh] max-w-6xl overflow-y-auto bg-[#F4F6F7]" data-testid="baptism-document-preview-dialog">
        <DialogHeader>
          <DialogTitle>Certificado oficial de bautismo</DialogTitle>
          <DialogDescription data-testid="baptism-document-preview-description">Vista fiel del documento imprimible con medidas físicas oficiales.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-center justify-between gap-3 border-y border-slate-200 py-2">
          <span className="text-xs font-semibold uppercase text-slate-500" data-testid="baptism-document-format-label">Letter horizontal · 11 × 8.5 pulgadas</span>
          <div className="flex items-center gap-1" aria-label="Zoom del documento">
            <Button type="button" variant="outline" size="icon" title="Reducir zoom" onClick={() => setZoom((value) => Math.max(.75, value - .25))} disabled={zoom <= .75} data-testid="baptism-preview-zoom-out"><Minus className="h-4 w-4" /></Button>
            <span className="w-14 text-center text-sm font-semibold" data-testid="baptism-preview-zoom-value">{Math.round(zoom * 100)}%</span>
            <Button type="button" variant="outline" size="icon" title="Aumentar zoom" onClick={() => setZoom((value) => Math.min(1.5, value + .25))} disabled={zoom >= 1.5} data-testid="baptism-preview-zoom-in"><Plus className="h-4 w-4" /></Button>
          </div>
        </div>
        <div className="max-w-full overflow-auto p-2">
          <div style={{ ...shellStyle, width: 'max-content', margin: '0 auto' }}><BaptismCertificateTemplate data={data} signatureSrc={signatureSrc} qrSrc={qrSrc} /></div>
        </div>
        <div className="flex flex-wrap justify-end gap-2 border-t pt-4">
          <Button variant="outline" onClick={print} disabled={printing || downloading || !qrSrc} data-testid="print-baptism-document-button"><Printer className="h-4 w-4" />{printing ? 'Preparando impresión…' : 'Imprimir directamente'}</Button>
          <Button onClick={download} disabled={downloading || printing || !qrSrc} data-testid="download-baptism-document-button"><Download className="h-4 w-4" />{downloading ? 'Generando PDF…' : 'Descargar PDF imprimible'}</Button>
        </div>
        <div aria-hidden="true" style={{ position: 'fixed', left: '-20000px', top: 0, zIndex: -1 }}>
          <div ref={certificateRef} style={{ width: '11in', height: '8.5in' }}><BaptismCertificateTemplate data={data} signatureSrc={signatureSrc} qrSrc={qrSrc} exportMode /></div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
