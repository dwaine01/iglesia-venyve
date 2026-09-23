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

const CARD_CAPTURE = Object.freeze({ width: 2764, height: 1743 });
const CERTIFICATE_CAPTURE = Object.freeze({ width: 2112, height: 1632 });

const normalizeCanvas = (source, target) => {
  const canvas = document.createElement('canvas');
  canvas.width = target.width;
  canvas.height = target.height;
  const context = canvas.getContext('2d');
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = 'high';
  context.fillStyle = '#ffffff';
  context.fillRect(0, 0, target.width, target.height);
  context.drawImage(source, 0, 0, target.width, target.height);
  return canvas;
};

const prepareSvgLayers = async (element, target) => {
  const replacements = [];
  const documentBounds = element.getBoundingClientRect();
  const captureScale = target.width / documentBounds.width;
  for (const svg of element.querySelectorAll('svg[data-vv-art]')) {
    const svgBounds = svg.getBoundingClientRect();
    const vector = new Image();
    vector.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(new XMLSerializer().serializeToString(svg))}`;
    await vector.decode();
    const layer = document.createElement('canvas');
    layer.width = Math.max(1, Math.round(svgBounds.width * captureScale));
    layer.height = Math.max(1, Math.round(svgBounds.height * captureScale));
    layer.getContext('2d').drawImage(vector, 0, 0, layer.width, layer.height);
    const image = document.createElement('img');
    image.id = svg.id;
    image.alt = '';
    image.setAttribute('aria-hidden', 'true');
    image.setAttribute('data-vv-art', svg.getAttribute('data-vv-art'));
    image.src = layer.toDataURL('image/png');
    svg.replaceWith(image);
    await image.decode();
    replacements.push({ image, svg });
  }
  return () => replacements.forEach(({ image, svg }) => image.replaceWith(svg));
};

const capture = async (element, target) => {
  await document.fonts?.ready;
  await waitForImages(element);
  const restoreSvgLayers = await prepareSvgLayers(element, target);
  try {
    const bounds = element.getBoundingClientRect();
    const source = await html2canvas(element, {
      scale: target.width / bounds.width,
      useCORS: true,
      backgroundColor: '#ffffff',
      logging: false,
      width: bounds.width,
      height: bounds.height,
      windowWidth: Math.ceil(bounds.width),
      windowHeight: Math.ceil(bounds.height),
    });
    return normalizeCanvas(source, target);
  } finally {
    restoreSvgLayers();
  }
};

export const downloadMembershipPdf = async ({ documentType, data, certificate, cardFront, cardBack }) => {
  const safeName = (data.person.full_name || 'miembro').replace(/[^A-Za-z0-9áéíóúñÁÉÍÓÚÑ]+/g, '-');
  if (documentType === 'certificate') {
    const canvas = await capture(certificate, CERTIFICATE_CAPTURE);
    const pdf = new jsPDF({ orientation: 'landscape', unit: 'in', format: [11, 8.5], compress: true });
    pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 0, 0, 11, 8.5, undefined, 'FAST');
    pdf.save(`certificado-membresia-${safeName}.pdf`);
    return;
  }
  const front = await capture(cardFront, CARD_CAPTURE);
  const back = await capture(cardBack, CARD_CAPTURE);
  const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: [85.6, 53.98], compress: true });
  pdf.addImage(front.toDataURL('image/png'), 'PNG', 0, 0, 85.6, 53.98, undefined, 'FAST');
  pdf.addPage([85.6, 53.98], 'landscape');
  pdf.addImage(back.toDataURL('image/png'), 'PNG', 0, 0, 85.6, 53.98, undefined, 'FAST');
  pdf.save(`carnet-miembro-${safeName}.pdf`);
};