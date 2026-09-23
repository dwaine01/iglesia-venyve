import React, { useEffect, useRef, useState } from 'react';
import QRCode from 'qrcode';
import { Download, Minus, Plus } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { MembershipCardBack, MembershipCardFront, MembershipCertificateTemplate } from './MembershipDocumentTemplates';
import { downloadMembershipPdf } from './membershipPdf';

export const MembershipDocumentDialog = ({ open, onOpenChange, documentType, data, photoSrc, signatureSrc }) => {
  const [qrSrc, setQrSrc] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [zoom, setZoom] = useState(1);
  const certificateRef = useRef(null);
  const cardFrontRef = useRef(null);
  const cardBackRef = useRef(null);

  useEffect(() => {
    if (!data?.verification_path) return;
    QRCode.toDataURL(`${window.location.origin}${data.verification_path}`, {
      errorCorrectionLevel: 'Q', margin: 4, width: 900,
      color: { dark: '#07111F', light: '#FFFFFF' },
    }).then(setQrSrc).catch(() => toast.error('No se pudo generar el QR'));
  }, [data]);
  useEffect(() => { if (open) setZoom(1); }, [open, documentType]);

  const download = async () => {
    setDownloading(true);
    try {
      await downloadMembershipPdf({
        documentType, data, certificate: certificateRef.current,
        cardFront: cardFrontRef.current, cardBack: cardBackRef.current,
      });
      toast.success('PDF listo para impresión profesional');
    } catch { toast.error('No se pudo generar el PDF'); }
    finally { setDownloading(false); }
  };

  if (!data) return null;
  const shellStyle = { zoom };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[94vh] max-w-6xl overflow-y-auto bg-[#F4F6F7]" data-testid="membership-document-preview-dialog">
        <DialogHeader>
          <DialogTitle>{documentType === 'certificate' ? 'Certificado oficial de membresía' : 'Carnet oficial de miembro'}</DialogTitle>
          <DialogDescription data-testid="membership-document-preview-description">Vista fiel del documento imprimible con medidas físicas oficiales.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-center justify-between gap-3 border-y border-slate-200 py-2">
          <span className="text-xs font-semibold uppercase text-slate-500" data-testid="membership-document-format-label">{documentType === 'certificate' ? 'Letter horizontal · 11 × 8.5 pulgadas' : 'CR80 / ID-1 · 85.60 × 53.98 mm'}</span>
          <div className="flex items-center gap-1" aria-label="Zoom del documento">
            <Button type="button" variant="outline" size="icon" title="Reducir zoom" onClick={() => setZoom((value) => Math.max(.75, value - .25))} disabled={zoom <= .75} data-testid="membership-preview-zoom-out"><Minus className="h-4 w-4" /></Button>
            <span className="w-14 text-center text-sm font-semibold" data-testid="membership-preview-zoom-value">{Math.round(zoom * 100)}%</span>
            <Button type="button" variant="outline" size="icon" title="Aumentar zoom" onClick={() => setZoom((value) => Math.min(1.5, value + .25))} disabled={zoom >= 1.5} data-testid="membership-preview-zoom-in"><Plus className="h-4 w-4" /></Button>
          </div>
        </div>
        <div className="membership-document-scroll">
          {documentType === 'certificate' ? (
            <div className="membership-preview-zoom-shell certificate" style={shellStyle}><MembershipCertificateTemplate data={data} signatureSrc={signatureSrc} qrSrc={qrSrc} /></div>
          ) : (
            <Tabs defaultValue="front">
              <TabsList data-testid="membership-card-side-tabs"><TabsTrigger value="front" data-testid="membership-card-front-tab">Frente</TabsTrigger><TabsTrigger value="back" data-testid="membership-card-back-tab">Reverso</TabsTrigger></TabsList>
              <TabsContent value="front"><div className="membership-preview-zoom-shell card" style={shellStyle}><MembershipCardFront data={data} photoSrc={photoSrc} qrSrc={qrSrc} /></div></TabsContent>
              <TabsContent value="back"><div className="membership-preview-zoom-shell card" style={shellStyle}><MembershipCardBack data={data} signatureSrc={signatureSrc} /></div></TabsContent>
            </Tabs>
          )}
        </div>
        <div className="flex justify-end border-t pt-4"><Button onClick={download} disabled={downloading || !qrSrc} data-testid="download-membership-document-button"><Download className="h-4 w-4" />{downloading ? 'Generando PDF…' : 'Descargar PDF imprimible'}</Button></div>
        <div className="membership-export-stage" aria-hidden="true">
          {documentType === 'certificate' ? <div ref={certificateRef} className="membership-export-certificate"><MembershipCertificateTemplate data={data} signatureSrc={signatureSrc} qrSrc={qrSrc} exportMode /></div> : <><div ref={cardFrontRef} className="membership-export-card"><MembershipCardFront data={data} photoSrc={photoSrc} qrSrc={qrSrc} exportMode /></div><div ref={cardBackRef} className="membership-export-card"><MembershipCardBack data={data} signatureSrc={signatureSrc} exportMode /></div></>}
        </div>
      </DialogContent>
    </Dialog>
  );
};