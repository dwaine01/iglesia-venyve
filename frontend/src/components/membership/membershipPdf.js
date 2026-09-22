import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

const waitForImages = async (element) => {
  const images = [...element.querySelectorAll('img')];
  await Promise.all(images.map((image) => (
    image.complete
      ? image.decode?.().catch(() => {})
      : new Promise((resolve) => { image.onload = resolve; image.onerror = resolve; })
  )));
};

const capture = async (element) => {
  await document.fonts?.ready;
  await waitForImages(element);
  return html2canvas(element, {
    scale: 2,
    useCORS: true,
    backgroundColor: '#ffffff',
    logging: false,
    width: element.offsetWidth,
    height: element.offsetHeight,
  });
};

export const downloadMembershipPdf = async ({ documentType, data, certificate, cardFront, cardBack }) => {
  const safeName = (data.person.full_name || 'miembro').replace(/[^A-Za-z0-9áéíóúñÁÉÍÓÚÑ]+/g, '-');
  if (documentType === 'certificate') {
    const canvas = await capture(certificate);
    const pdf = new jsPDF({ orientation: 'landscape', unit: 'in', format: [11, 8.5], compress: true });
    pdf.addImage(canvas.toDataURL('image/jpeg', 0.98), 'JPEG', 0, 0, 11, 8.5, undefined, 'FAST');
    pdf.save(`certificado-membresia-${safeName}.pdf`);
    return;
  }
  const front = await capture(cardFront);
  const back = await capture(cardBack);
  const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: [85.6, 53.98], compress: true });
  pdf.addImage(front.toDataURL('image/jpeg', 0.98), 'JPEG', 0, 0, 85.6, 53.98, undefined, 'FAST');
  pdf.addPage([85.6, 53.98], 'landscape');
  pdf.addImage(back.toDataURL('image/jpeg', 0.98), 'JPEG', 0, 0, 85.6, 53.98, undefined, 'FAST');
  pdf.save(`carnet-miembro-${safeName}.pdf`);
};