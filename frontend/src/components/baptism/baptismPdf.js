import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

const CERTIFICATE_CAPTURE = Object.freeze({ width: 2112, height: 1632 });
const SVG_COLOR_TOKENS = ['--vv-navy', '--vv-blue', '--vv-green', '--vv-white', '--vv-off-white', '--vv-charcoal'];

const waitForImages = async (element) => {
  const images = [...element.querySelectorAll('img')];
  await Promise.all(images.map((image) => (
    image.complete
      ? image.decode?.().catch(() => {})
      : new Promise((resolve) => { image.onload = resolve; image.onerror = resolve; })
  )));
};

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
  const documentElement = element.matches?.('[data-vv-document]') ? element : element.querySelector('[data-vv-document]');
  const documentStyles = getComputedStyle(documentElement || element);
  for (const svg of element.querySelectorAll('svg[data-vv-art]')) {
    const svgBounds = svg.getBoundingClientRect();
    const clone = svg.cloneNode(true);
    SVG_COLOR_TOKENS.forEach((token) => clone.style.setProperty(token, documentStyles.getPropertyValue(token)));
    const vector = new Image();
    vector.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(new XMLSerializer().serializeToString(clone))}`;
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

const printFrame = async ({ elements }) => {
  const frame = document.createElement('iframe');
  frame.title = 'Documento listo para imprimir';
  frame.style.cssText = 'position:fixed;right:0;bottom:0;width:1px;height:1px;border:0;opacity:0;pointer-events:none;';
  document.body.appendChild(frame);
  const styles = [...document.querySelectorAll('link[rel="stylesheet"], style')].map((node) => node.outerHTML).join('');
  const pages = elements.map((element) => `<div class="vv-print-page">${element.outerHTML}</div>`).join('');
  const printDocument = frame.contentDocument;
  printDocument.open();
  printDocument.write(`<!doctype html><html><head><meta charset="utf-8"><base href="${document.baseURI}">${styles}<style>@page{size:11in 8.5in;margin:0}html,body{margin:0!important;padding:0!important;background:#fff!important}.vv-print-page{width:11in;height:8.5in;margin:0;overflow:hidden;break-after:page;page-break-after:always}.vv-print-page:last-child{break-after:auto;page-break-after:auto}.vv-print-page>[data-vv-document]{margin:0!important;box-shadow:none!important}</style></head><body>${pages}</body></html>`);
  printDocument.close();
  await printDocument.fonts?.ready;
  await waitForImages(printDocument.body);
  const cleanup = () => { if (frame.isConnected) frame.remove(); };
  frame.contentWindow.addEventListener('afterprint', cleanup, { once: true });
  frame.contentWindow.focus();
  frame.contentWindow.print();
  window.setTimeout(cleanup, 60000);
};

export const printBaptismDocument = async ({ certificate }) => {
  if (!certificate) throw new Error('Documento no disponible para impresión');
  await printFrame({ elements: [certificate] });
};

export const downloadBaptismPdf = async ({ data, certificate }) => {
  const safeName = (data.person.full_name || 'bautismo').replace(/[^A-Za-z0-9áéíóúñÁÉÍÓÚÑ]+/g, '-');
  const canvas = await capture(certificate, CERTIFICATE_CAPTURE);
  const pdf = new jsPDF({ orientation: 'landscape', unit: 'in', format: [11, 8.5], compress: true });
  pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 0, 0, 11, 8.5, undefined, 'FAST');
  pdf.save(`certificado-bautismo-${safeName}.pdf`);
};
