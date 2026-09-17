import React, { useEffect, useRef, useState } from 'react';
import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';
import QRCode from 'qrcode';
import { Download } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { MembershipCardBack, MembershipCardFront, MembershipCertificateTemplate } from './MembershipDocumentTemplates';

const waitForImages = async (element) => {
  const images = [...element.querySelectorAll('img')];
  await Promise.all(images.map((image) => image.complete ? image.decode?.().catch(() => {}) : new Promise((resolve) => { image.onload = resolve; image.onerror = resolve; })));
};

const capture = async (element) => {
  await document.fonts?.ready;
  await waitForImages(element);
  return html2canvas(element, { scale: 2, useCORS: true, backgroundColor: '#ffffff', logging: false });
};

export const MembershipDocumentDialog = ({ open, onOpenChange, documentType, data, photoSrc, signatureSrc }) => {
  const [qrSrc, setQrSrc] = useState('');
  const [downloading, setDownloading] = useState(false);
  const certificateRef = useRef(null);
  const cardFrontRef = useRef(null);
  const cardBackRef = useRef(null);

  useEffect(() => {
    if (!data?.verification_path) return;
    QRCode.toDataURL(`${window.location.origin}${data.verification_path}`, { errorCorrectionLevel: 'H', margin: 1, width: 720, color: { dark: '#102A2D', light: '#FFFFFF' } }).then(setQrSrc).catch(() => toast.error('No se pudo generar el QR'));
  }, [data]);

  const download = async () => {
    setDownloading(true);
    try {
      const safeName = (data.person.full_name || 'miembro').replace(/[^A-Za-z0-9áéíóúñÁÉÍÓÚÑ]+/g, '-');
      if (documentType === 'certificate') {
        const canvas = await capture(certificateRef.current);
        const pdf = new jsPDF({ orientation: 'landscape', unit: 'in', format: 'letter', compress: true });
        pdf.addImage(canvas.toDataURL('image/jpeg', 0.96), 'JPEG', 0, 0, 11, 8.5, undefined, 'FAST');
        pdf.save(`certificado-miembro-${safeName}.pdf`);
      } else {
        const front = await capture(cardFrontRef.current);
        const back = await capture(cardBackRef.current);
        const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: [53.98, 85.6], compress: true });
        pdf.addImage(front.toDataURL('image/jpeg', 0.97), 'JPEG', 0, 0, 85.6, 53.98, undefined, 'FAST');
        pdf.addPage([53.98, 85.6], 'landscape');
        pdf.addImage(back.toDataURL('image/jpeg', 0.97), 'JPEG', 0, 0, 85.6, 53.98, undefined, 'FAST');
        pdf.save(`carnet-miembro-${safeName}.pdf`);
      }
      toast.success('PDF listo para imprimir');
    } catch (error) {
      toast.error('No se pudo generar el PDF');
    } finally {
      setDownloading(false);
    }
  };

  if (!data) return null;
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="max-h-[94vh] max-w-6xl overflow-y-auto bg-[#F4F7F6]" data-testid="membership-document-preview-dialog"><DialogHeader><DialogTitle>{documentType === 'certificate' ? 'Certificado oficial de miembro' : 'Carnet oficial de miembro'}</DialogTitle></DialogHeader>{documentType === 'certificate' ? <div className="membership-preview-frame"><MembershipCertificateTemplate data={data} signatureSrc={signatureSrc} /></div> : <Tabs defaultValue="front"><TabsList data-testid="membership-card-side-tabs"><TabsTrigger value="front" data-testid="membership-card-front-tab">Frente</TabsTrigger><TabsTrigger value="back" data-testid="membership-card-back-tab">Reverso</TabsTrigger></TabsList><TabsContent value="front"><div className="membership-card-preview"><MembershipCardFront data={data} photoSrc={photoSrc} /></div></TabsContent><TabsContent value="back"><div className="membership-card-preview"><MembershipCardBack data={data} qrSrc={qrSrc} /></div></TabsContent></Tabs>}<div className="flex justify-end border-t pt-4"><Button onClick={download} disabled={downloading || documentType === 'card' && !qrSrc} data-testid="download-membership-document-button"><Download className="h-4 w-4" />{downloading ? 'Generando…' : 'Descargar PDF imprimible'}</Button></div><div className="membership-export-stage" aria-hidden="true">{documentType === 'certificate' ? <div ref={certificateRef} className="membership-export-certificate"><MembershipCertificateTemplate data={data} signatureSrc={signatureSrc} exportMode /></div> : <><div ref={cardFrontRef} className="membership-export-card"><MembershipCardFront data={data} photoSrc={photoSrc} exportMode /></div><div ref={cardBackRef} className="membership-export-card"><MembershipCardBack data={data} qrSrc={qrSrc} exportMode /></div></>}</div></DialogContent></Dialog>;
};