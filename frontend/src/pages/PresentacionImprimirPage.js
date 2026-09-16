import React, { useEffect, useRef, useState } from 'react';
import { Printer, Home, Download, Loader2, FileDown, Info, CheckCircle2, X as XIcon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  LAS_9_PUERTAS,
  LAS_7_SEMANAS,
  SLIDES,
  IMAGEN_INTRODUCCION,
  IMAGEN_LEY_7_SEMANAS,
  LOGO_IGLESIA,
} from '../data/presentationData';

/**
 * Manual imprimible en formato A4.
 * - Texto claro, amplio espaciado, gráficos simples
 * - Optimizado para impresión (print styles)
 * - Exportación nativa a PDF (recomendado): motor del navegador — fidelidad 100%
 * - Descarga alternativa (html2canvas + jsPDF): para casos offline o sin diálogo
 */
export default function PresentacionImprimirPage() {
  const navigate = useNavigate();
  const manualRef = useRef(null);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
  const [showPrintHelp, setShowPrintHelp] = useState(false);

  useEffect(() => {
    document.title = 'Manual - La Ley de las 7 Semanas';
  }, []);

  // Detecta si la página está siendo renderizada para generar el PDF
  // (el backend Playwright agrega ?pdf=1 al cargar la URL).
  const isPdfMode = typeof window !== 'undefined' &&
    new URLSearchParams(window.location.search).get('pdf') === '1';

  // NUEVO MÉTODO PRINCIPAL: PDF generado server-side con Playwright (Chromium).
  // Fidelidad 100% — texto vectorial seleccionable, drop caps perfectos,
  // sin distorsión ni aplastamiento. El backend hace todo el trabajo.
  const [isDownloadingServer, setIsDownloadingServer] = useState(false);
  const handleDownloadServerPdf = async () => {
    if (isDownloadingServer) return;
    setIsDownloadingServer(true);
    const API = process.env.REACT_APP_BACKEND_URL;
    const token = localStorage.getItem('token');
    const loadingToast = toast.loading('Generando PDF del manual...', {
      description: 'El servidor está renderizando cada página. Esto tarda unos 10-20 segundos.',
    });
    try {
      const resp = await fetch(`${API}/api/manual/pdf`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) {
        const txt = await resp.text().catch(() => '');
        throw new Error(`HTTP ${resp.status} ${txt.slice(0, 120)}`);
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Manual-La-Ley-de-las-7-Semanas.pdf';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.dismiss(loadingToast);
      toast.success('¡PDF descargado!', {
        description: `Manual-La-Ley-de-las-7-Semanas.pdf (${(blob.size / 1024 / 1024).toFixed(1)} MB)`,
      });
    } catch (err) {
      console.error('Error generando PDF server-side:', err);
      toast.dismiss(loadingToast);
      toast.error('No se pudo generar el PDF', {
        description: 'Intenta la opción alternativa "Descarga rápida" o "Imprimir desde navegador".',
      });
    } finally {
      setIsDownloadingServer(false);
    }
  };

  // Alternativa: impresión nativa del navegador (abre diálogo del sistema).
  const handlePrintNative = () => {
    setShowPrintHelp(false);
    setTimeout(() => window.print(), 150);
  };
  const openPrintHelp = () => setShowPrintHelp(true);

  const handleDownloadPdf = async () => {
    if (!manualRef.current || isGeneratingPdf) return;
    setIsGeneratingPdf(true);
    // Marcador de versión visible en la consola del navegador.
    // Si al dar click NO ves este mensaje, tu navegador está usando JS cacheado:
    // haz Ctrl+Shift+R (o Cmd+Shift+R en Mac) para forzar recarga.
    console.log('[PDF Manual] Generator v2 — slicing en múltiples páginas A4 (27 págs esperadas)');
    const loadingToast = toast.loading('Generando PDF del manual (v2)...', {
      description: 'Renderizando cada página, por favor espera unos segundos.',
    });

    // Helper: convierte una imagen externa a data URL usando el proxy del backend
    // para evitar errores CORS durante la captura con html2canvas.
    const API = process.env.REACT_APP_BACKEND_URL;
    const toDataUrl = async (url) => {
      try {
        if (!url || url.startsWith('data:') || url.startsWith('blob:')) return url;
        const proxied = `${API}/api/proxy/image?url=${encodeURIComponent(url)}`;
        const resp = await fetch(proxied, { cache: 'force-cache' });
        if (!resp.ok) throw new Error(`proxy ${resp.status}`);
        const blob = await resp.blob();
        return await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => resolve(reader.result);
          reader.onerror = reject;
          reader.readAsDataURL(blob);
        });
      } catch (err) {
        console.warn('toDataUrl falló para', url, err);
        return url;
      }
    };

    // Pre-cargar imágenes como data URLs
    const imgs = Array.from(manualRef.current.querySelectorAll('img'));
    const originals = imgs.map((img) => img.getAttribute('src'));
    const dataUrls = await Promise.all(originals.map(toDataUrl));
    imgs.forEach((img, i) => {
      if (dataUrls[i] && dataUrls[i] !== originals[i]) {
        img.setAttribute('src', dataUrls[i]);
      }
    });
    // Tick para aplicar los nuevos src y re-layout
    await new Promise((r) => setTimeout(r, 200));

    try {
      // Render por-página: evita el límite de tamaño de canvas del navegador
      // (~16384px) que causaba que un manual largo quedara en blanco.
      const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
        import('html2canvas'),
        import('jspdf'),
      ]);

      const pages = Array.from(manualRef.current.querySelectorAll('.manual-page'));
      if (pages.length === 0) throw new Error('No se encontraron páginas para renderizar');

      const A4_W_MM = 210;
      const A4_H_MM = 297;
      const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4', compress: true });
      let isFirstPdfPage = true;

      // Helper: agrega una imagen (o su recorte) al PDF preservando aspect-ratio.
      // Si el contenido es más alto que A4, lo divide en múltiples páginas
      // (sin distorsionar el ancho ni aplastar la altura) para mantener
      // la integridad visual del diseño original.
      const addCanvasToPdf = (canvas) => {
        const mmPerPx = A4_W_MM / canvas.width;
        const canvasHeightMm = canvas.height * mmPerPx;

        // Caso 1: cabe en una sola página A4.
        if (canvasHeightMm <= A4_H_MM + 0.5) {
          if (!isFirstPdfPage) pdf.addPage();
          isFirstPdfPage = false;
          const imgData = canvas.toDataURL('image/jpeg', 0.92);
          pdf.addImage(imgData, 'JPEG', 0, 0, A4_W_MM, canvasHeightMm, undefined, 'FAST');
          return;
        }

        // Caso 2: contenido más alto que A4 → dividir en múltiples páginas.
        const sliceHeightPx = Math.floor(A4_H_MM / mmPerPx); // altura de slice en px
        let yOffset = 0;
        while (yOffset < canvas.height) {
          const remaining = canvas.height - yOffset;
          const currentSliceHeight = Math.min(sliceHeightPx, remaining);

          // Crear canvas temporal para este slice
          const sliceCanvas = document.createElement('canvas');
          sliceCanvas.width = canvas.width;
          sliceCanvas.height = currentSliceHeight;
          const ctx = sliceCanvas.getContext('2d');
          // Fondo blanco para slices que no llenan completamente
          ctx.fillStyle = '#ffffff';
          ctx.fillRect(0, 0, sliceCanvas.width, sliceCanvas.height);
          // Dibujar porción correspondiente del canvas original
          ctx.drawImage(
            canvas,
            0, yOffset, canvas.width, currentSliceHeight, // source rect
            0, 0, canvas.width, currentSliceHeight        // dest rect
          );

          const sliceData = sliceCanvas.toDataURL('image/jpeg', 0.92);
          const sliceHeightMm = currentSliceHeight * mmPerPx;

          if (!isFirstPdfPage) pdf.addPage();
          isFirstPdfPage = false;
          pdf.addImage(sliceData, 'JPEG', 0, 0, A4_W_MM, sliceHeightMm, undefined, 'FAST');

          yOffset += currentSliceHeight;
        }
      };

      for (let i = 0; i < pages.length; i++) {
        const pageEl = pages[i];
        // Capturar cada .manual-page como canvas individual
        const canvas = await html2canvas(pageEl, {
          scale: 2,
          useCORS: true,
          allowTaint: true,
          backgroundColor: '#ffffff',
          logging: false,
          letterRendering: true,
          imageTimeout: 15000,
          windowWidth: pageEl.scrollWidth || 794,
          windowHeight: pageEl.scrollHeight || 1123,
        });

        addCanvasToPdf(canvas);

        // Actualizar progreso cada 3 páginas
        if ((i + 1) % 3 === 0 || i === pages.length - 1) {
          toast.loading(`Renderizando página ${i + 1} de ${pages.length}...`, { id: loadingToast });
        }
      }

      pdf.save('Manual-La-Ley-de-las-7-Semanas.pdf');

      const totalPdfPages = pdf.getNumberOfPages();
      toast.dismiss(loadingToast);
      toast.success('¡PDF descargado!', {
        description: `Manual-La-Ley-de-las-7-Semanas.pdf (${totalPdfPages} páginas)`,
      });
    } catch (err) {
      console.error('Error generando PDF:', err);
      toast.dismiss(loadingToast);
      toast.error('No se pudo generar el PDF', {
        description: 'Intenta usar la opción "Imprimir" y guardar como PDF desde el navegador.',
      });
    } finally {
      // Restaurar src originales
      imgs.forEach((img, i) => {
        if (originals[i]) img.setAttribute('src', originals[i]);
      });
      setIsGeneratingPdf(false);
    }
  };

  return (
    <div className={`min-h-screen bg-gray-200 print:bg-white ${isPdfMode ? 'pdf-mode' : ''}`}>
      {/* Barra superior (oculta al imprimir) */}
      <div className="sticky top-0 z-50 bg-[#1B2A4A] text-white px-4 py-3 flex items-center justify-between gap-2 shadow-lg print:hidden" data-testid="manual-toolbar">
        <button
          onClick={() => navigate('/presentacion')}
          className="flex items-center gap-2 text-sm hover:text-[#C8A951] transition-colors"
          data-testid="btn-volver-manual"
        >
          <Home className="w-4 h-4" /> <span className="hidden sm:inline">Volver</span>
        </button>
        <p className="text-sm font-medium hidden md:block truncate">Manual Carta (8.5×11) · La Ley de las 7 Semanas</p>
        <div className="flex items-center gap-2">
          {/* Botón PRIMARIO: PDF server-side (Playwright) — fidelidad 100% */}
          <button
            onClick={handleDownloadServerPdf}
            disabled={isDownloadingServer || isGeneratingPdf}
            className="flex items-center gap-2 bg-gradient-to-br from-[#C8A951] to-[#E2CF8A] text-[#1B2A4A] px-3 sm:px-4 py-1.5 rounded-lg font-bold shadow-md hover:shadow-lg hover:-translate-y-0.5 active:translate-y-0 transition-[transform,box-shadow] duration-150 disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:translate-y-0"
            data-testid="btn-descargar-pdf-server"
            aria-label="Descargar manual en PDF (alta fidelidad)"
          >
            {isDownloadingServer ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-xs sm:text-sm">Generando PDF…</span>
              </>
            ) : (
              <>
                <FileDown className="w-4 h-4" />
                <span className="text-xs sm:text-sm">Descargar PDF</span>
              </>
            )}
          </button>

          {/* Botón SECUNDARIO: imprimir desde navegador (diálogo nativo) */}
          <button
            onClick={openPrintHelp}
            disabled={isDownloadingServer || isGeneratingPdf}
            className="flex items-center gap-2 border border-[#C8A951]/60 text-[#C8A951] px-3 sm:px-4 py-1.5 rounded-lg font-medium hover:bg-[#C8A951]/10 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            data-testid="btn-imprimir-navegador"
            aria-label="Imprimir o guardar como PDF desde el navegador"
            title="Alternativa: imprime desde tu navegador"
          >
            <Printer className="w-4 h-4" />
            <span className="text-xs hidden sm:inline">Imprimir</span>
          </button>
        </div>
      </div>

      {/* Modal de ayuda previo a imprimir — guía al usuario para obtener PDF limpio */}
      {showPrintHelp && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 print:hidden"
          onClick={() => setShowPrintHelp(false)}
          data-testid="print-help-modal"
        >
          <div
            className="relative max-w-lg w-full bg-white rounded-2xl shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="bg-gradient-to-br from-[#0F1A33] via-[#1B2A4A] to-[#2A3D63] text-white p-5 relative overflow-hidden">
              <div className="absolute -top-10 -right-10 w-40 h-40 bg-[#C8A951]/15 rounded-full blur-3xl pointer-events-none" />
              <button
                onClick={() => setShowPrintHelp(false)}
                className="absolute top-3 right-3 p-1.5 rounded-lg hover:bg-white/10 transition-colors"
                aria-label="Cerrar"
              >
                <XIcon className="w-4 h-4" />
              </button>
              <div className="relative z-10 flex items-start gap-3">
                <div className="p-2 rounded-xl bg-[#C8A951]/20 border border-[#C8A951]/40 shrink-0">
                  <FileDown className="w-5 h-5 text-[#C8A951]" />
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-[0.25em] text-[#C8A951] font-bold">Guardar como PDF</p>
                  <h3 className="text-xl font-bold mt-0.5" style={{ fontFamily: 'Spectral, serif' }}>
                    Calidad máxima, salida limpia
                  </h3>
                  <p className="text-xs text-white/70 mt-1 leading-relaxed">
                    Usaremos el motor de impresión de tu navegador para obtener un PDF con fidelidad 100% — drop caps, gradientes y tipografías perfectas.
                  </p>
                </div>
              </div>
            </div>

            {/* Instrucciones */}
            <div className="p-5 space-y-4">
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-full bg-[#C8A951] text-[#0F1A33] flex items-center justify-center text-xs font-bold shrink-0">1</div>
                <div className="text-sm text-[#1B2A4A] leading-relaxed">
                  En <strong>Destino</strong>, selecciona <span className="font-mono bg-[#F5F0E8] px-1.5 py-0.5 rounded text-[#1B2A4A] text-xs">Guardar como PDF</span>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-full bg-[#C8A951] text-[#0F1A33] flex items-center justify-center text-xs font-bold shrink-0">2</div>
                <div className="text-sm text-[#1B2A4A] leading-relaxed">
                  Despliega <strong>Más ajustes</strong> (o <em>Más opciones</em>) y <strong>desmarca</strong>:
                  <ul className="mt-1 ml-1 space-y-0.5 text-xs text-[#1B2A4A]/80 list-disc list-inside">
                    <li>“Encabezados y pies de página”</li>
                    <li>“Gráficos de fondo” → <span className="text-[#C8A951] font-bold">marca esta</span> para conservar colores</li>
                  </ul>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="w-7 h-7 rounded-full bg-[#C8A951] text-[#0F1A33] flex items-center justify-center text-xs font-bold shrink-0">3</div>
                <div className="text-sm text-[#1B2A4A] leading-relaxed">
                  Click en <strong>Guardar</strong> y elige dónde guardar el archivo.
                </div>
              </div>

              <div className="bg-[#F5F0E8] border border-[#C8A951]/30 rounded-lg p-3 flex items-start gap-2">
                <Info className="w-4 h-4 text-[#C8A951] shrink-0 mt-0.5" />
                <p className="text-xs text-[#1B2A4A]/80 leading-relaxed">
                  <strong>Este método es el recomendado.</strong> Si prefieres descarga directa sin diálogo (menor fidelidad tipográfica),
                  usa el botón <em>“Descarga rápida”</em> que ves al lado.
                </p>
              </div>
            </div>

            {/* Footer */}
            <div className="px-5 pb-5 flex items-center gap-2 justify-end">
              <button
                onClick={() => setShowPrintHelp(false)}
                className="text-sm px-4 py-2 text-[#1B2A4A]/70 hover:text-[#1B2A4A] transition-colors"
                data-testid="btn-cancelar-print-help"
              >
                Cancelar
              </button>
              <button
                onClick={handlePrintNative}
                className="inline-flex items-center gap-2 text-sm bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] text-white font-bold px-5 py-2.5 rounded-lg shadow-md hover:shadow-lg hover:-translate-y-0.5 transition-[transform,box-shadow] duration-150"
                data-testid="btn-abrir-dialogo-impresion"
              >
                <CheckCircle2 className="w-4 h-4" />
                Abrir diálogo de impresión
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        /* ========== IMPRESIÓN NATIVA — FIDELIDAD 100% ========== */
        @media print {
          /* Márgenes cero en la hoja para que cada .manual-page (ya diseñada
             con sus márgenes internos) ocupe exactamente US Letter (8.5x11 in). */
          @page { size: Letter; margin: 0; }

          html, body {
            background: white !important;
            margin: 0 !important;
            padding: 0 !important;
          }

          /* Preservar colores de fondo y tipografías exactamente como se ven */
          * {
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
            color-adjust: exact !important;
          }

          .page-break { page-break-before: always; }
          .no-print, .print\\:hidden { display: none !important; }

          /* Ocultar el badge de Emergent al imprimir */
          #emergent-badge, [id="emergent-badge"], a[href*="emergent.sh"] {
            display: none !important;
          }

          /* El contenedor del manual no debe forzar ancho de pantalla */
          .manual-content-root { padding: 0 !important; margin: 0 !important; }

          /* Reset de box-shadow y márgenes entre páginas al imprimir */
          .manual-page {
            box-shadow: none !important;
            margin: 0 !important;
            width: auto !important;
            min-height: auto !important;
            padding: 16mm 16mm 25mm 16mm !important;
            page-break-after: always;
            break-after: page;
          }
          .manual-page:last-child {
            page-break-after: auto;
            break-after: auto;
          }
          /* Evitar que títulos queden huérfanos al final de una página impresa */
          .manual-page h1, .manual-page h2, .manual-page h3 {
            page-break-after: avoid;
            break-after: avoid-page;
          }
          .manual-page::after { bottom: 6mm !important; }
        }

        /* ========== MODO PDF (server-side, Playwright) — BLOQUEADO ==========
           Estrategia: CADA .manual-page es una hoja US Letter RIGIDA de 8.5x11
           pulgadas (215.9 x 279.4 mm) con overflow:hidden y page-break-
           before/after:always. Chromium NO puede re-fluir, re-ajustar, partir
           ni fusionar contenido. Se preserva EXACTAMENTE la misma paginacion
           que se ve en pantalla. */
        .pdf-mode {
          background: white !important;
        }
        .pdf-mode #emergent-badge,
        .pdf-mode [id="emergent-badge"],
        .pdf-mode a[href*="emergent.sh"] {
          display: none !important;
        }
        .pdf-mode .manual-content-root {
          padding: 0 !important;
          margin: 0 !important;
          counter-reset: manualpage;
        }

        /* LA REGLA CLAVE: cada .manual-page se bloquea como hoja US Letter */
        .pdf-mode .manual-page {
          width: 8.5in !important;
          height: 11in !important;        /* FIJA (no min-height) → sin expansión */
          max-height: 11in !important;
          overflow: hidden !important;    /* si algo excede, se recorta visualmente */
          margin: 0 !important;
          padding: 16mm 16mm 25mm 16mm !important;
          box-shadow: none !important;
          position: relative !important;
          background: white !important;
          box-sizing: border-box !important;
          display: flex !important;
          flex-direction: column !important;

          /* Forzar saltos de página RÍGIDOS */
          page-break-before: always !important;
          break-before: page !important;
          page-break-after: always !important;
          break-after: page !important;
          page-break-inside: avoid !important;
          break-inside: avoid !important;

          counter-increment: manualpage !important;
        }
        /* La primera página NO necesita break-before */
        .pdf-mode .manual-page:first-child {
          page-break-before: auto !important;
          break-before: auto !important;
        }
        /* La última NO necesita break-after */
        .pdf-mode .manual-page:last-child {
          page-break-after: auto !important;
          break-after: auto !important;
        }

        /* Restaurar el pie de página con número dentro de cada hoja fija */
        .pdf-mode .manual-page::after {
          content: "— " counter(manualpage, decimal-leading-zero) " —" !important;
          position: absolute !important;
          bottom: 8mm !important;
          left: 0 !important;
          right: 0 !important;
          text-align: center !important;
          font-size: 9.5px !important;
          letter-spacing: 0.35em !important;
          color: rgba(27, 42, 74, 0.45) !important;
          font-family: 'Figtree', -apple-system, sans-serif !important;
          font-weight: 600 !important;
        }
        .pdf-mode .manual-page.cover-page::after {
          content: none !important;
        }

        /* Toolbar/modal nunca deben aparecer en el PDF */
        .pdf-mode [data-testid="manual-toolbar"],
        .pdf-mode [data-testid="print-help-modal"] {
          display: none !important;
        }

        /* Desactivar @page counter (usamos el ::after per-page) */
        .pdf-mode img {
          max-width: 100%;
        }

        /* Numeración nativa de Chromium via @page — se mantiene pero la
           regla de .pdf-mode .manual-page::after sobrescribe con mayor
           especificidad, mostrando SOLO los números del manual rígido. */
        @page {
          size: Letter;
          margin: 0;
        }

        /* ========== VISTA EN PANTALLA (no pdf-mode) ========== */
        .manual-content-root { counter-reset: manualpage; }
        .manual-page {
          position: relative;
          width: 8.5in;
          height: 11in;                 /* tamaño FIJO en pantalla (igual al PDF) */
          min-height: 11in;
          max-height: 11in;
          overflow: hidden;             /* preview idéntico al PDF: nada se desborda */
          margin: 0 auto 10mm auto;
          padding: 16mm 16mm 25mm 16mm; /* padding-bottom 25mm: zona segura GRANDE */
          background: white;
          box-shadow: 0 4px 20px rgba(0,0,0,0.1);
          font-family: 'Figtree', -apple-system, sans-serif;
          color: #1B2A4A;
          font-size: 11pt;              /* base tipográfica tipo libro */
          line-height: 1.6;             /* aireado pero no disperso */
          counter-increment: manualpage;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;       /* permite usar flex-grow para distribuir */
        }
        /* Barrera de seguridad: la cinta blanca del folio tapa cualquier
           desborde accidental, protegiendo al número de página de ser cubierto. */
        .manual-page::before {
          content: "";
          position: absolute;
          left: 0;
          right: 0;
          bottom: 0;
          height: 18mm;                  /* cinta inferior protectora */
          background: white;
          z-index: 5;                    /* por debajo del folio (10) */
          pointer-events: none;
        }
        /* La portada NO lleva cinta blanca — su layout es único */
        .manual-page.cover-page::before { display: none; }

        /* ====== SISTEMA TIPOGRÁFICO PROPORCIONADO PARA 8.5×11in ======
           Tamaños calibrados para llenar la página de forma estética sin
           desbordarse. Más aireado que un manual técnico, más denso que un
           libro ilustrado. */
        .manual-page h1 { font-family: 'Spectral', Georgia, serif; font-size: 34pt; line-height: 1.1; }
        .manual-page h2 { font-family: 'Spectral', Georgia, serif; font-size: 24pt; line-height: 1.15; }
        .manual-page h3 { font-family: 'Spectral', Georgia, serif; font-size: 17pt; line-height: 1.25; }
        .manual-page h4 { font-size: 11pt; line-height: 1.3; }
        .manual-page p  { font-size: 11pt; line-height: 1.6; }
        .manual-page li { font-size: 10.5pt; line-height: 1.55; }

        /* Tailwind overrides específicos para el manual:
           valores pensados para ocupar la página de forma equilibrada. */
        .manual-page .text-xs   { font-size: 9pt; }
        .manual-page .text-sm   { font-size: 10.5pt; line-height: 1.55; }
        .manual-page .text-base { font-size: 11.5pt; line-height: 1.6; }
        .manual-page .text-lg   { font-size: 13.5pt; line-height: 1.5; }
        .manual-page .text-xl   { font-size: 16pt; line-height: 1.4; }
        .manual-page .text-2xl  { font-size: 20pt; line-height: 1.25; }
        .manual-page .text-3xl  { font-size: 24pt; line-height: 1.2; }
        .manual-page .text-4xl  { font-size: 30pt; line-height: 1.15; }
        .manual-page .text-5xl  { font-size: 38pt; line-height: 1.1; }
        .manual-page .text-6xl  { font-size: 48pt; line-height: 1.05; }

        /* Pie de página con número — centrado sobre cinta blanca protectora.
           La combinación ::before (cinta blanca z:5) + ::after (folio z:10)
           garantiza que NINGÚN contenido accidental pueda tapar el folio. */
        .manual-page::after {
          content: "— " counter(manualpage, decimal-leading-zero) " —";
          position: absolute;
          bottom: 10mm;
          left: 0;
          right: 0;
          text-align: center;
          font-size: 9pt;
          letter-spacing: 0.35em;
          color: rgba(27, 42, 74, 0.65);
          font-family: 'Figtree', -apple-system, sans-serif;
          font-weight: 600;
          z-index: 10;
          pointer-events: none;
        }
        /* La portada NO lleva número pero sí incrementa (así página 2 = "02") */
        .manual-page.cover-page::after { content: none; }
      `}</style>

      <div ref={manualRef} className="py-6 print:py-0 manual-content-root" data-testid="manual-content">
        {/* PÁGINA 1: Portada — distribución vertical equilibrada con flex */}
        <div className="manual-page cover-page">
          <div className="flex flex-col items-center text-center h-full w-full">
            {/* Bloque superior: sello institucional */}
            <div className="pt-6 pb-2">
              <p className="text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold">Primera Iglesia del Nazareno</p>
              <p className="text-[10pt] uppercase tracking-[0.3em] text-[#1B2A4A]/55 italic mt-1">Casa de Oración Ven y Ve</p>
            </div>

            {/* Logo centrado con protagonismo */}
            <div className="mt-6 w-52 h-52 bg-[#0F1A33] rounded-full flex items-center justify-center shadow-2xl p-5">
              <img
                src={LOGO_IGLESIA}
                alt="Casa de Oración Ven y Ve"
                className="w-full h-full object-contain logo-transparent"
              />
            </div>

            {/* Bloque central: título principal */}
            <div className="mt-auto mb-auto pt-10 flex flex-col items-center">
              <p className="text-sm uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-4">Manual Oficial</p>
              <h1 className="text-6xl font-bold text-[#1B2A4A] leading-[1.05]" style={{ fontFamily: 'Spectral, serif' }}>
                La Ley de las<br /><span className="italic text-[#C8A951]">7 Semanas</span>
              </h1>
              <div className="w-28 h-1 bg-[#C8A951] my-6" />
              <p className="text-2xl italic text-[#1B2A4A]/75" style={{ fontFamily: 'Spectral, serif' }}>
                Sistema Celular y las 9 Puertas
              </p>
              <p className="text-base text-[#1B2A4A]/60 mt-4 max-w-md leading-relaxed">
                Modelo integral de cuidado, consolidación,<br />discipulado y multiplicación.
              </p>
            </div>

            {/* Bloque inferior: año de cosecha */}
            <div className="pb-4 pt-4 w-full">
              <div className="flex items-center justify-center gap-3">
                <div className="w-12 h-px bg-[#C8A951]/50" />
                <p className="text-base font-bold text-[#C8A951] uppercase tracking-[0.3em]">
                  Año de Cosecha y Restitución
                </p>
                <div className="w-12 h-px bg-[#C8A951]/50" />
              </div>
              <p className="text-[9pt] uppercase tracking-widest text-[#1B2A4A]/40 mt-3">
                Edición Oficial
              </p>
            </div>
          </div>
        </div>

        {/* PÁGINA 2: Introducción - Parte 1 (Invitación + ¿Qué encontrarás?) */}
        <div className="manual-page page-break">
          <div className="text-center mb-6">
            <p className="text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-2">Bienvenido a este Manual</p>
            <h1 className="text-4xl font-bold text-[#1B2A4A] leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
              Una <span className="italic text-[#C8A951]">Invitación</span>
            </h1>
            <div className="w-16 h-0.5 bg-[#C8A951] mx-auto my-4" />
          </div>

          <p className="text-base leading-relaxed text-[#1B2A4A] mb-4 first-letter:text-5xl first-letter:font-bold first-letter:text-[#C8A951] first-letter:float-left first-letter:mr-2 first-letter:leading-none first-letter:mt-1" style={{ fontFamily: 'Spectral, serif' }}>
            Hay vidas esperando ser alcanzadas, sueños esperando ser activados, y puertas
            esperando ser abiertas. Este manual no nació de una idea humana; nació de una
            <strong> convicción profética</strong>: que Dios quiere hacer algo nuevo, y lo hará
            a través de personas ordinarias dispuestas a servir con excelencia.
          </p>

          <p className="text-sm leading-relaxed mb-4">
            Lo que tienes en tus manos <strong>no es solo información</strong>. Es un mapa. Es una
            estrategia espiritual diseñada para transformar tu manera de ver la iglesia, el
            ministerio y tu propio llamado. Durante demasiado tiempo hemos hecho cosas buenas sin
            orden. Hoy es diferente. Hoy tenemos un <em>sistema</em>, una <em>ruta</em>, y un
            <em> propósito</em> que se puede medir.
          </p>

          <div className="my-5 p-4 bg-gradient-to-r from-[#C8A951]/10 to-[#E2CF8A]/5 border-l-4 border-[#C8A951] rounded-r">
            <p className="text-base italic text-[#1B2A4A] leading-relaxed" style={{ fontFamily: 'Spectral, serif' }}>
              "Donde no hay visión, el pueblo perece. Pero donde hay visión clara, hay dirección;
              donde hay orden, hay crecimiento; y donde hay propósito, hay multiplicación."
            </p>
          </div>

          <h3 className="text-xl font-bold text-[#1B2A4A] mt-5 mb-3">¿Qué encontrarás aquí?</h3>

          <div className="space-y-2">
            {[
              ['El corazón del sistema', 'La visión, misión y valores que sostienen todo lo que hacemos.'],
              ['Una base bíblica sólida', 'Las 9 Puertas en Nehemías 3 y el principio del Tiempo 3.'],
              ['Un proceso claro de transformación', 'De persona a discípulo, de discípulo a líder, en 7 semanas.'],
              ['Herramientas prácticas', 'Para mentores, líderes de puerta, supervisores y coordinadores.'],
              ['Una estrategia de ganar', 'Metas concretas, indicadores medibles y un plan de acción.'],
            ].map(([t, d], i) => (
              <div key={i} className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-[#1B2A4A] text-[#C8A951] font-bold flex items-center justify-center shrink-0 text-sm mt-0.5">
                  {String(i + 1).padStart(2, '0')}
                </div>
                <div>
                  <p className="font-bold text-base text-[#1B2A4A] leading-tight">{t}</p>
                  <p className="text-sm text-[#1B2A4A]/75 leading-snug">{d}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* PÁGINA 3: Introducción - Parte 2 (¿Para quién? + Cómo leerlo + Promesa) */}
        <div className="manual-page page-break">
          <div className="text-center mb-6">
            <p className="text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-2">Continuación</p>
            <h1 className="text-3xl font-bold text-[#1B2A4A] leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
              ¿Para quién es <span className="italic text-[#C8A951]">este manual?</span>
            </h1>
            <div className="w-16 h-0.5 bg-[#C8A951] mx-auto my-3" />
          </div>

          <p className="text-base leading-relaxed mb-4">
            Para el <strong>pastor</strong> que quiere levantar un equipo fuerte. Para el
            <strong> líder</strong> que sueña con ver a su gente crecer. Para el <strong>mentor
            </strong> que desea formar vidas con propósito. Para el <strong>servidor</strong> que
            aún no sabe cuál es su puerta, y quiere descubrirla. Y para el <strong>nuevo creyente
            </strong> que está dando sus primeros pasos y merece un proceso serio, ordenado y
            lleno de amor.
          </p>

          <div className="grid grid-cols-2 gap-3 my-5">
            {[
              ['👨‍💼', 'Pastor', 'Para levantar equipo fuerte'],
              ['🎯', 'Líder', 'Para ver crecer a su gente'],
              ['🌱', 'Mentor', 'Para formar vidas con propósito'],
              ['💪', 'Servidor', 'Para descubrir su puerta'],
              ['✨', 'Nuevo creyente', 'Para un proceso serio y ordenado'],
              ['👥', 'Supervisor', 'Para coordinar el movimiento'],
            ].map(([icon, t, d], i) => (
              <div key={i} className="flex items-center gap-2.5 p-3 bg-[#F5F0E8] rounded-lg border-l-4 border-[#C8A951]">
                <span className="text-2xl shrink-0">{icon}</span>
                <div>
                  <p className="font-bold text-sm text-[#1B2A4A] leading-tight">{t}</p>
                  <p className="text-xs text-[#1B2A4A]/70 leading-snug">{d}</p>
                </div>
              </div>
            ))}
          </div>

          <h3 className="text-xl font-bold text-[#1B2A4A] mt-5 mb-3">Cómo leerlo</h3>
          <p className="text-base leading-relaxed mb-5">
            No lo leas como un libro más. Léelo <strong>con lápiz en mano</strong>, con oración,
            con tu equipo al lado. Subraya lo que impacta tu corazón. Marca lo que quieres
            implementar. Regresa a las secciones que te desafían. Este manual está diseñado para
            ser usado, no solo guardado.
          </p>

          <div className="mt-5 p-5 bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] text-white rounded-lg text-center relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-[#C8A951]/10 rounded-full -mr-16 -mt-16" />
            <p className="text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-3 relative">Nuestra Promesa</p>
            <p className="text-base italic leading-relaxed relative" style={{ fontFamily: 'Spectral, serif' }}>
              Si aplicas con disciplina lo que aquí está escrito,
              <strong className="text-[#C8A951] not-italic"> verás fruto</strong>. No porque este manual
              sea mágico, sino porque está alineado con los principios que Dios mismo estableció
              para edificar Su casa.
            </p>
            <div className="w-12 h-0.5 bg-[#C8A951] mx-auto my-3 relative" />
            <p className="text-sm text-white/80 relative">Hoy comienza algo nuevo. Gira la página.</p>
          </div>
        </div>

        {/* PÁGINA 3: Infografía oficial de Introducción */}
        <div className="manual-page page-break">
          <div className="text-center mb-3">
            <p className="text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-1">Panorama Oficial</p>
            <h2 className="text-2xl font-bold text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>
              Introducción del Manual — <span className="italic text-[#C8A951]">Vista General</span>
            </h2>
            <div className="w-16 h-0.5 bg-[#C8A951] mx-auto mt-2" />
          </div>
          <div className="flex justify-center items-start">
            <img
              src={IMAGEN_INTRODUCCION}
              alt="Introducción del Manual - La Ley de las 7 Semanas"
              className="max-w-full h-auto rounded-lg shadow-xl border border-[#E7E2D6]"
              style={{ maxHeight: '215mm' }}
            />
          </div>
          <p className="text-center text-xs text-[#1B2A4A]/50 italic mt-2">
            Infografía oficial · La Ley de las 7 Semanas
          </p>
        </div>

        {/* PÁGINA 5: Índice — layout en 2 columnas con distribución equilibrada */}
        <div className="manual-page page-break">
          {/* Encabezado grande y elegante */}
          <div className="mb-7">
            <p className="text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-2">Contenido del Manual</p>
            <h1 className="text-5xl font-bold text-[#1B2A4A] leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
              Índice
            </h1>
            <div className="flex items-center gap-3 mt-4">
              <div className="w-20 h-1 bg-[#C8A951]" />
              <p className="text-xs italic text-[#1B2A4A]/60">28 páginas · 9 puertas · 7 semanas</p>
            </div>
          </div>

          {/* 2 columnas: Parte I (izq) + Parte II (der) */}
          <div className="grid grid-cols-2 gap-x-7 gap-y-3 flex-1">
            <div>
              <div className="mb-5">
                <div className="flex items-baseline gap-2 mb-3 pb-2 border-b-2 border-[#C8A951]/40">
                  <span className="text-2xl font-bold text-[#C8A951]" style={{ fontFamily: 'Spectral, serif' }}>I</span>
                  <p className="text-xs uppercase tracking-widest text-[#C8A951] font-bold">
                    Fundamentos
                  </p>
                </div>
                <div className="space-y-0.5">
                  {[
                    ['', 'Introducción · Una Invitación', '2'],
                    ['', '¿Para quién? · Promesa', '3'],
                    ['', 'Panorama · Infografía', '4'],
                    ['01', 'Nuestra Identidad', '6'],
                    ['02', '9 Puertas en Nehemías 3', '7'],
                    ['03', 'La Ley de las 7 Semanas', '8'],
                    ['', 'Recorrido Completo · Infografía', '9'],
                    ['04', 'Modelo CAP', '10'],
                    ['05', 'Operación 72 · Tiempo 3', '11'],
                    ['06', 'Las 9 Puertas · Introducción', '12'],
                  ].map(([num, titulo, pag], i) => (
                    <IndiceItem key={i} num={num} titulo={titulo} pag={pag} />
                  ))}
                </div>
              </div>

              <div>
                <div className="flex items-baseline gap-2 mb-3 pb-2 border-b-2 border-[#C8A951]/40">
                  <span className="text-2xl font-bold text-[#C8A951]" style={{ fontFamily: 'Spectral, serif' }}>III</span>
                  <p className="text-xs uppercase tracking-widest text-[#C8A951] font-bold">
                    Liderazgo y Formación
                  </p>
                </div>
                <div className="space-y-0.5">
                  <IndiceItem num="16" titulo="Estructura General del Sistema" sub="Jerarquía · Células · Cultura" pag="22" />
                  <IndiceItem num="17" titulo="El Líder de Puerta" sub="Cuidar · Ubicar · Activar" pag="23" />
                  <IndiceItem num="18" titulo="Propósito del Mentor" sub="Perfil y Responsabilidades" pag="24" />
                  <IndiceItem num="" titulo="Discipulado en 8 Semanas" sub="El mapa del nuevo creyente" pag="25" />
                </div>
              </div>
            </div>

            <div>
              <div className="mb-5">
                <div className="flex items-baseline gap-2 mb-3 pb-2 border-b-2 border-[#C8A951]/40">
                  <span className="text-2xl font-bold text-[#C8A951]" style={{ fontFamily: 'Spectral, serif' }}>II</span>
                  <p className="text-xs uppercase tracking-widest text-[#C8A951] font-bold">
                    Las 9 Puertas del Sistema
                  </p>
                </div>
                <div className="space-y-0.5">
                  {LAS_9_PUERTAS.map((p, i) => (
                    <IndiceItem
                      key={p.num}
                      num={`P${p.num}`}
                      titulo={p.nombre}
                      pag={String(i + 13)}
                    />
                  ))}
                </div>
              </div>

              <div>
                <div className="flex items-baseline gap-2 mb-3 pb-2 border-b-2 border-[#C8A951]/40">
                  <span className="text-2xl font-bold text-[#C8A951]" style={{ fontFamily: 'Spectral, serif' }}>IV</span>
                  <p className="text-xs uppercase tracking-widest text-[#C8A951] font-bold">
                    Estrategia y Ejecución
                  </p>
                </div>
                <div className="space-y-0.5">
                  <IndiceItem num="19" titulo="Consolidado de Puerta" sub="Los 4 indicadores tangibles" pag="26" />
                  <IndiceItem num="20" titulo="Reunión de Supervisores" sub="30 minutos con enfoque" pag="27" />
                  <IndiceItem num="21" titulo="Estrategia de Ganar" sub="40 líderes · Plan anual" pag="28" />
                  <IndiceItem num="" titulo="Llamado Final" sub="Año de Cosecha y Restitución" pag="29" />
                </div>
              </div>
            </div>
          </div>

          {/* Caja final expresiva, ocupa ancho completo */}
          <div className="mt-6 p-5 bg-gradient-to-r from-[#1B2A4A] to-[#0F1A33] text-white rounded-lg relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-[#C8A951]/10 rounded-full -mr-16 -mt-16" />
            <p className="text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-2 relative">Filosofía del Sistema</p>
            <p className="text-base italic leading-relaxed relative" style={{ fontFamily: 'Spectral, serif' }}>
              Un sistema sin orden se vuelve caos.<br/>
              <strong className="text-[#C8A951] not-italic">Un orden sin corazón se vuelve religión.</strong><br/>
              Este manual busca ambos: <span className="text-[#C8A951]">orden con corazón</span>.
            </p>
          </div>
        </div>

        {/* PÁGINA 5: Identidad */}
        <div className="manual-page page-break">
          <SectionHeader num="01" titulo="Nuestra Identidad" />

          <div className="grid grid-cols-2 gap-4 mb-5">
            <div className="p-5 bg-white border-2 border-[#E7E2D6] rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">👁</span>
                <h3 className="text-lg font-bold text-[#1B2A4A]">Visión</h3>
              </div>
              <p className="text-sm leading-relaxed text-[#1B2A4A]/85">
                Levantar discípulos que se conviertan en líderes, a través de un sistema intencional
                que transforma vidas y se multiplica.
              </p>
            </div>
            <div className="p-5 bg-white border-2 border-[#E7E2D6] rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">🎯</span>
                <h3 className="text-lg font-bold text-[#1B2A4A]">Misión</h3>
              </div>
              <p className="text-sm leading-relaxed text-[#1B2A4A]/85">
                Evangelizar, consolidar, discipular y enviar personas, mediante puertas
                ministeriales que garantizan crecimiento y multiplicación.
              </p>
            </div>
          </div>

          <div className="p-6 bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] text-white rounded-lg text-center relative overflow-hidden mb-6">
            <div className="absolute top-0 right-0 w-40 h-40 bg-[#C8A951]/10 rounded-full -mr-20 -mt-20" />
            <div className="absolute bottom-0 left-0 w-28 h-28 bg-[#C8A951]/5 rounded-full -ml-14 -mb-14" />
            <p className="text-xs uppercase tracking-widest text-[#C8A951] mb-3 font-bold relative">Declaración Central</p>
            <p className="text-2xl italic leading-snug relative" style={{ fontFamily: 'Spectral, serif' }}>
              Formamos discípulos,<br />
              levantamos líderes,<br />
              <span className="text-[#C8A951]">multiplicamos el Reino.</span>
            </p>
          </div>

          <h3 className="text-xl font-bold text-[#1B2A4A] mb-3">Nuestros Valores</h3>
          <div className="grid grid-cols-2 gap-2.5 mb-5">
            {[
              ['Presencia de Dios', 'Buscar Su rostro antes que Su mano'],
              ['Amor por las almas', 'Cada persona es valiosa y prioritaria'],
              ['Relaciones intencionales', 'No casualidad, sino propósito'],
              ['Formación continua', 'Aprender y crecer toda la vida'],
              ['Multiplicación', 'No sumar, sino multiplicar'],
              ['Orden', 'Estructura que sostiene el crecimiento'],
              ['Excelencia', 'Dar siempre lo mejor al Señor'],
            ].map(([v, d]) => (
              <div key={v} className="flex items-start gap-2.5 p-3 bg-[#F5F0E8] rounded-lg border-l-4 border-[#C8A951]">
                <span className="w-2.5 h-2.5 rounded-full bg-[#C8A951] shrink-0 mt-1.5" />
                <div>
                  <p className="font-bold text-sm text-[#1B2A4A] leading-tight">{v}</p>
                  <p className="text-xs text-[#1B2A4A]/65 italic leading-snug">{d}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 bg-[#F5F0E8]/70 border border-[#C8A951]/30 rounded-lg text-center">
            <p className="text-sm italic text-[#1B2A4A] leading-relaxed" style={{ fontFamily: 'Spectral, serif' }}>
              "Nuestra identidad no se negocia: <strong className="not-italic text-[#C8A951]">cuidar, formar y multiplicar</strong> es nuestro ADN."
            </p>
          </div>
        </div>

        {/* PÁGINA 6: Nehemías 3 */}
        <div className="manual-page page-break">
          <SectionHeader num="02" titulo="Las 9 Puertas en Nehemías 3" />
          <p className="mb-5 text-base leading-relaxed">
            Nehemías asignó el trabajo por zonas: eso es consolidación. No es solo construcción,
            es <strong>estrategia organizacional</strong>. Cada puerta representa un área ministerial
            concreta del sistema celular.
          </p>

          <div className="space-y-2 mb-5">
            {[
              ['Puerta de las Ovejas', 'Evangelismo', ''],
              ['Puerta del Pescado', 'Alcance', 'Neh 3:3'],
              ['Puerta Vieja', 'Fundamento · Sana doctrina', 'Neh 3:6'],
              ['Puerta del Valle', 'Sanidad (LBS)', 'Neh 3:13'],
              ['Puerta del Muladar', 'Limpieza · Santidad · Disciplina', 'Neh 3:14'],
              ['Puerta de la Fuente', 'Espíritu Santo · Ayuno · Oración', 'Neh 3:15'],
              ['Puerta de las Aguas', 'La Palabra', 'Neh 3:26'],
              ['Puerta del Caballo', 'Guerra espiritual', 'Neh 3:28'],
              ['Puerta Oriental', 'Expectativa del mover de Dios', 'Neh 3:29'],
            ].map(([n, d, r], i) => (
              <div key={i} className="flex items-center gap-3 p-2.5 bg-[#F5F0E8]/60 rounded border-l-4 border-[#C8A951]">
                <div className="w-9 h-9 rounded-full bg-[#C8A951] text-[#1B2A4A] font-bold flex items-center justify-center shrink-0 text-base">{i + 1}</div>
                <div className="flex-1">
                  <p className="font-bold text-base leading-tight">{n}</p>
                  <p className="text-sm text-[#1B2A4A]/70 leading-tight">{d}</p>
                </div>
                {r && <span className="text-xs text-[#C8A951] font-mono font-semibold">{r}</span>}
              </div>
            ))}
          </div>

          <div className="bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] text-white p-5 rounded-lg">
            <p className="text-xs uppercase tracking-widest text-[#C8A951] mb-2 font-bold">Principios</p>
            <p className="text-sm leading-relaxed">
              Nehemías reconstruyó primero las puertas porque: (1) sin puertas no hay protección,
              (2) sin puertas no hay orden, (3) sin puertas no hay crecimiento seguro,
              (4) sin puertas no hay una ciudad estable.
            </p>
          </div>
        </div>

        {/* PÁGINA 7: Las 7 Semanas */}
        <div className="manual-page page-break">
          <SectionHeader num="03" titulo="La Ley de las 7 Semanas" />
          <p className="mb-5 text-base leading-relaxed">
            Un proceso <strong>estructurado, intencional y continuo</strong>, enfocado en producir
            resultados reales y medibles. La visión no es abstracta, es concreta; y lo concreto
            produce resultados.
          </p>

          <h3 className="text-xl font-bold mb-3">Principios Clave</h3>
          <ul className="space-y-2 mb-6 list-none pl-0">
            {['La importancia de los procesos continuos', 'La necesidad de eliminar vacíos espirituales', 'El enfoque en la acción, no solo en la teoría', 'La disciplina en la ejecución', 'El trabajo en equipo con un mismo objetivo'].map((p, i) => (
              <li key={i} className="flex items-start gap-3 text-base">
                <span className="w-7 h-7 rounded-full bg-[#C8A951] text-[#1B2A4A] text-sm font-bold flex items-center justify-center shrink-0 mt-0.5">{i + 1}</span>
                <span>{p}</span>
              </li>
            ))}
          </ul>

          <h3 className="text-xl font-bold mb-3">Las 7 Semanas</h3>
          <div className="grid grid-cols-2 gap-2.5 mb-4">
            {LAS_7_SEMANAS.map(s => (
              <div key={s.num} className="p-3 border-2 border-[#E7E2D6] rounded-lg">
                <p className="text-[10pt] text-[#C8A951] font-bold uppercase tracking-wider">Semana {s.num}</p>
                <p className="font-bold text-base mt-0.5 leading-tight">{s.titulo}</p>
                <p className="text-xs text-[#1B2A4A]/60 mt-0.5 leading-snug">{s.sub}</p>
              </div>
            ))}
          </div>

          <div className="p-3 bg-gradient-to-r from-[#C8A951]/15 to-[#E2CF8A]/10 border-2 border-[#C8A951]/40 rounded-lg mb-5">
            <p className="text-center font-bold text-base">Retiro + Cierre</p>
            <p className="text-sm text-center text-[#1B2A4A]/70 mt-0.5">Culminación del proceso</p>
          </div>

          <h3 className="text-xl font-bold mb-3">Transformación Progresiva</h3>
          <div className="flex items-center justify-around text-center py-4 bg-[#F5F0E8]/70 rounded-lg border border-[#C8A951]/20">
            <div className="font-bold text-base">Persona</div>
            <div className="text-[#C8A951] font-bold text-lg">→</div>
            <div className="font-bold text-base">Discípulo</div>
            <div className="text-[#C8A951] font-bold text-lg">→</div>
            <div className="font-bold text-base">Obrero</div>
            <div className="text-[#C8A951] font-bold text-lg">→</div>
            <div className="font-bold text-base">Líder</div>
          </div>
        </div>

        {/* PÁGINA 8: Infografía oficial de "El Recorrido Completo" */}
        <div className="manual-page page-break">
          <div className="text-center mb-4">
            <p className="text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-2">El Recorrido Completo</p>
            <h2 className="text-2xl font-bold text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>
              Las 7 Semanas — <span className="italic text-[#C8A951]">Flujo Oficial</span>
            </h2>
            <div className="w-16 h-0.5 bg-[#C8A951] mx-auto mt-2" />
          </div>
          <div className="flex justify-center items-start">
            <img
              src={IMAGEN_LEY_7_SEMANAS}
              alt="La Ley de las 7 Semanas - Recorrido completo hasta Retiro + Cierre"
              className="max-w-full h-auto mx-auto rounded-lg border border-[#E7E2D6]"
              style={{ maxHeight: '200mm' }}
            />
          </div>
          <p className="text-center text-xs text-[#1B2A4A]/60 italic mt-3 max-w-lg mx-auto leading-snug">
            El proceso no se detiene: cada persona avanza por las 7 semanas hasta el Retiro
            y Cierre, y luego se convierte en discipuladora del siguiente ciclo. Es un círculo
            que nunca se rompe.
          </p>
        </div>

        {/* PÁGINA 9: Modelo CAP */}
        <div className="manual-page page-break">
          <SectionHeader num="04" titulo="Modelo CAP" subtitulo="Consolidación y Activación por Puertas" />
          <div className="p-3 bg-[#F5F0E8] border-l-4 border-[#C8A951] rounded mb-5">
            <p className="italic text-[#1B2A4A] text-base leading-relaxed" style={{ fontFamily: 'Spectral, serif' }}>
              "Escribe la visión y declárala en tablas, para que corra el que leyere en ella."
              <span className="block text-right text-sm mt-1 not-italic font-bold text-[#C8A951]">— Habacuc 2:2</span>
            </p>
          </div>

          <Card icon="🔑" titulo="El Don = La Llave">
            Tu don es la llave que abre tu puerta en el Reino. Cuando conectamos a una persona
            correctamente, algo se abre.
          </Card>

          <Card icon="🤝" titulo="El Cuerpo">
            La iglesia funciona como un cuerpo: no todos hacen lo mismo, pero todos son necesarios.
            Cada miembro tiene una función específica.
          </Card>

          <Card icon="📈" titulo="Tres Niveles de Crecimiento">
            Formación · Seguimiento · Crecimiento — un proceso gradual que lleva a cada persona
            de ser espectadora a protagonista activa del Reino.
          </Card>

          <h3 className="text-xl font-bold mt-6 mb-3">Flujo del Sistema</h3>
          <div className="grid grid-cols-2 gap-2.5">
            {['Llega una persona', 'Se recibe', 'Se conecta (atención / consolidación)', 'Se identifica su don', 'Se asigna a una puerta', 'Se activa', 'Se discipula', 'Sirve y crece'].map((paso, i) => (
              <div key={i} className="flex items-center gap-2.5 p-2.5 bg-[#F5F0E8]/70 rounded border-l-4 border-[#C8A951]">
                <div className="w-7 h-7 rounded-full bg-[#1B2A4A] text-white text-sm font-bold flex items-center justify-center shrink-0">{i + 1}</div>
                <span className="text-sm leading-tight font-medium">{paso}</span>
              </div>
            ))}
          </div>
        </div>

        {/* PÁGINA 11: Operación 72 — Tiempo 3, base profética */}
        <div className="manual-page page-break">
          <SectionHeader num="05" titulo="Operación 72" subtitulo="Equipo por Puertas · Isaías 61:1-5" />

          <div className="p-4 bg-[#F5F0E8] border-l-4 border-[#C8A951] rounded mb-4">
            <p className="text-[10pt] uppercase tracking-widest text-[#C8A951] font-bold mb-1.5">Base Profética</p>
            <p className="text-sm leading-relaxed italic" style={{ fontFamily: 'Spectral, serif' }}>
              "El propósito por el cual el Padre envía al Hijo al mundo: predicar las buenas
              noticias, ministrar sanidad al corazón herido, proclamar libertad a cautivos,
              el año de la buena voluntad de Jehová."
            </p>
          </div>

          <h3 className="text-lg font-bold mb-2">Nuevos Tiempos</h3>
          <div className="grid grid-cols-3 gap-2 mb-4">
            {[
              ['⏳', 'Consolidación', 'Completa'],
              ['💊', 'Sanidad', 'Integral'],
              ['💰', 'Prosperidad', 'Integral'],
            ].map(([icon, t, d], i) => (
              <div key={i} className="p-3 bg-white border-2 border-[#E7E2D6] rounded-lg text-center">
                <div className="text-2xl">{icon}</div>
                <p className="font-bold text-sm mt-1" style={{ fontFamily: 'Spectral, serif' }}>{t}</p>
                <p className="text-xs text-[#1B2A4A]/70">{d}</p>
              </div>
            ))}
          </div>

          <h3 className="text-lg font-bold mb-2">El Principio del Tiempo 3</h3>
          <p className="text-sm leading-relaxed mb-3">
            Moisés <em>"en tres días"</em>; Josué <em>"en tres días poseeremos"</em>; Jesús
            <em> "en tres días resucitaré"</em>. El tiempo 3 marca el principio operativo:
          </p>
          <ListBlock titulo="Aplicación práctica" items={[
            'En 3 días atenderemos con firmeza a los nuevos creyentes',
            'LBS: tratamiento de 3 semanas (21 días) — liberación, bendición y sanidad',
            'Operación 72 se desarrolla en 3 días intensivos',
            'Luego, 3 meses de seguimiento continuo con cada nuevo creyente',
          ]} />

          <div className="mt-4 p-4 bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] text-white rounded-lg">
            <p className="text-[10pt] uppercase tracking-widest text-[#C8A951] font-bold mb-1.5">Proceso de Formación (3 meses)</p>
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div><strong className="text-[#C8A951]">Mes 1:</strong> Profundizar en el llamado</div>
              <div><strong className="text-[#C8A951]">Mes 2:</strong> Privilegio de servir</div>
              <div><strong className="text-[#C8A951]">Mes 3:</strong> "Predestinado para ganar"</div>
            </div>
          </div>
        </div>

        {/* PÁGINA 12: Las 9 Puertas · Introducción con ejemplos prácticos */}
        <div className="manual-page page-break">
          <SectionHeader num="06" titulo="Las 9 Puertas" subtitulo="El sistema completo de activación" />

          <p className="text-base leading-relaxed mb-5">
            El sistema de puertas <strong>organiza el ministerio</strong> para que cada persona
            pueda ser recibida, cuidada, discipulada, servir, y finalmente convertirse en líder.
            Cada puerta tiene un <em>líder responsable</em>, un <em>asistente</em>, un
            <em> equipo de apoyo</em>, y <em>metas anuales</em>.
          </p>

          <h3 className="text-lg font-bold mb-3">Ejemplos Prácticos de Conexión</h3>
          <div className="space-y-2 mb-5">
            {[
              ['🤒', 'Enfermo', 'Puerta 6 · Visitación Pastoral'],
              ['✨', 'Nuevo creyente', 'Puerta 5 · Mentores de Discipulado'],
              ['🙏', 'Petición urgente', 'Puerta 1 · Intercesión Profética'],
              ['💔', 'Crisis personal', 'Puerta 3 · Cuidado Pastoral Inmediato'],
              ['🎉', 'Evento o congreso', 'Puerta 9 · Congresos y Eventos'],
              ['🙌', 'Visitante primera vez', 'Puerta 2 · Bienvenida'],
              ['📱', 'Difusión digital', 'Puerta 7 · Multimedia'],
              ['📚', 'Material didáctico', 'Puerta 8 · Administración'],
              ['⛰', 'Encuentro profundo', 'Puerta 4 · Retiros (LBS)'],
            ].map(([icon, necesidad, puerta], i) => (
              <div key={i} className="flex items-center gap-3 p-2.5 bg-[#F5F0E8]/70 rounded-lg border-l-4 border-[#C8A951]">
                <span className="text-xl shrink-0">{icon}</span>
                <div className="flex-1 flex items-center justify-between gap-2">
                  <p className="font-bold text-sm text-[#1B2A4A]">{necesidad}</p>
                  <span className="text-[#C8A951] font-bold">→</span>
                  <p className="text-sm text-[#1B2A4A]/80 italic text-right">{puerta}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="pt-3 p-4 bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] text-white rounded-lg text-center">
            <p className="text-sm italic leading-relaxed" style={{ fontFamily: 'Spectral, serif' }}>
              "Aquí cada miembro tiene un lugar, <strong className="text-[#C8A951] not-italic">cada necesidad
              tiene una respuesta</strong>, y cada vida tiene un proceso."
            </p>
          </div>
        </div>



        {/* PÁGINAS 13-21: Cada una de las 9 puertas */}
        {LAS_9_PUERTAS.map((p, idx) => (
          <div key={p.num} className="manual-page page-break">
            <SectionHeader num={String(idx + 7).padStart(2, '0')} titulo={`Puerta ${p.num}: ${p.nombre}`} subtitulo={p.resumen} />

            {p.nehemias && (
              <p className="text-sm italic text-[#C8A951] mb-4 font-semibold">📖 {p.nehemias}</p>
            )}

            <div className="p-4 bg-gradient-to-r from-[#F5F0E8] to-[#F5F0E8]/50 border-l-4 border-[#C8A951] rounded mb-4">
              <p className="text-[10pt] uppercase tracking-widest text-[#C8A951] font-bold mb-1.5">Propósito</p>
              <p className="text-base leading-relaxed">{p.proposito}</p>
            </div>

            {p.funciones && <ListBlock titulo="Funciones" items={p.funciones} />}
            {p.responsabilidades && <ListBlock titulo="Responsabilidades" items={p.responsabilidades} />}
            {p.actividades && <ListBlock titulo="Actividades" items={p.actividades} />}
            {p.proceso && <ListBlock titulo="Proceso" items={p.proceso} />}
            {p.bienvenida && <ListBlock titulo="Proceso de Bienvenida" items={p.bienvenida} />}
            {p.ministerios && (
              <div className="mt-4">
                <h4 className="text-[10pt] uppercase tracking-widest text-[#C8A951] font-bold mb-2">Ministerios de Apoyo</h4>
                <div className="flex flex-wrap gap-2">
                  {p.ministerios.map(m => (
                    <span key={m} className="px-3 py-1 bg-[#1B2A4A] text-white text-xs rounded-full font-medium">{m}</span>
                  ))}
                </div>
              </div>
            )}
            {p.estructura && <ListBlock titulo="Estructura" items={p.estructura} />}
            {p.indicadores && <ListBlock titulo="Indicadores de Éxito" items={p.indicadores} />}
            {p.tiempo && (
              <div className="mt-4 p-3 bg-[#C8A951]/15 border border-[#C8A951]/40 rounded-lg text-sm italic font-medium">
                ⏱ {p.tiempo}
              </div>
            )}
            {p.operacion72 && (
              <div className="mt-3 p-3 bg-purple-50 border border-purple-200 rounded-lg text-sm">
                <strong>Operación 72: </strong>{p.operacion72}
              </div>
            )}

            {/* Bloque final decorativo — SIN mt-auto para no invadir la zona del folio.
                Fluye naturalmente después del contenido, dejando siempre libre
                el margen inferior donde se ubica el número de página. */}
            <div className="pt-5">
              {/* Separador decorativo */}
              <div className="flex items-center gap-3 mb-3">
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-[#C8A951]/40 to-transparent" />
                <span className="text-[#C8A951] text-lg">✦</span>
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-[#C8A951]/40 to-transparent" />
              </div>

              <div className="p-3 bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] text-white rounded-lg text-center relative overflow-hidden">
                <div className="absolute top-0 right-0 w-20 h-20 bg-[#C8A951]/10 rounded-full -mr-10 -mt-10" />
                <p className="text-[10pt] uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-1 relative">Compromiso · Puerta {p.num}</p>
                <p className="text-xs italic leading-snug relative" style={{ fontFamily: 'Spectral, serif' }}>
                  "Cada puerta tiene su tiempo; cada tiempo tiene su puerta.
                  <span className="text-[#C8A951] font-bold not-italic"> Servir aquí es edificar el Reino.</span>"
                </p>
              </div>
            </div>
          </div>
        ))}

        {/* PÁGINA 22: Estructura General del Sistema */}
        <div className="manual-page page-break">
          <SectionHeader num="16" titulo="Estructura General del Sistema" subtitulo="Jerarquía · Células · Cultura" />

          <h3 className="text-lg font-bold mb-3">Jerarquía Ministerial</h3>
          <div className="space-y-1.5 mb-5">
            {[
              ['01', 'Pastor Principal', 'Visión y dirección del ministerio'],
              ['02', 'Coordinador General del Ministerio Celular', 'Supervisa la operación del sistema'],
              ['03', 'Junta Directiva + Líderes de Puerta', '9 líderes responsables, uno por puerta'],
              ['04', 'Equipos de servidores por puerta', 'Asistentes y voluntarios activos'],
              ['05', 'Iglesia · Miembros · Células', 'El cuerpo que se cuida y multiplica'],
            ].map(([n, t, d], i) => (
              <div key={i} className="flex items-center gap-3 p-2.5 bg-[#F5F0E8]/60 rounded border-l-4 border-[#C8A951]">
                <div className="w-9 h-9 rounded-full bg-[#1B2A4A] text-[#C8A951] font-bold flex items-center justify-center shrink-0 text-sm">{n}</div>
                <div className="flex-1">
                  <p className="font-bold text-sm text-[#1B2A4A] leading-tight">{t}</p>
                  <p className="text-xs text-[#1B2A4A]/70 leading-snug">{d}</p>
                </div>
              </div>
            ))}
          </div>

          <h3 className="text-lg font-bold mb-2">Células y Puertas · Sinergia</h3>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div className="p-3 bg-white border-2 border-[#E7E2D6] rounded-lg">
              <p className="text-[10pt] uppercase tracking-widest text-[#C8A951] font-bold mb-1">Las Células</p>
              <p className="text-sm leading-snug"><strong>DETECTAN</strong> necesidades en la gente: quién está ausente, quién necesita oración, quién está listo para crecer.</p>
            </div>
            <div className="p-3 bg-white border-2 border-[#E7E2D6] rounded-lg">
              <p className="text-[10pt] uppercase tracking-widest text-[#C8A951] font-bold mb-1">Las Puertas</p>
              <p className="text-sm leading-snug"><strong>RESPONDEN</strong> a esas necesidades con un equipo preparado, un proceso claro, y recursos específicos.</p>
            </div>
          </div>

          <div className="p-4 bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] text-white rounded-lg text-center">
            <p className="text-[10pt] uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-2">Cultura del Sistema</p>
            <p className="text-sm italic leading-relaxed" style={{ fontFamily: 'Spectral, serif' }}>
              No somos una iglesia que solo hace reuniones.<br/>
              <strong className="text-[#C8A951] not-italic">Somos una iglesia que se organiza para cuidar vidas.</strong><br/>
              Aquí cada miembro tiene un lugar, cada necesidad tiene una respuesta, y cada vida tiene un proceso.
            </p>
          </div>
        </div>



        {/* PÁGINA 19: El Líder */}
        <div className="manual-page page-break">
          <SectionHeader num="17" titulo="El Líder de Puerta" />
          <p className="mb-5 text-base leading-relaxed">
            Un líder <strong>NO es un jefe</strong>. Un líder es un <em>formador</em>,
            un <em>cuidador</em> y un <em>activador</em>. Su tarea es multiplicar — no acumular —
            poder: formar personas que a su vez formen a otras.
          </p>

          <div className="grid grid-cols-2 gap-3 mb-4">
            {[
              ['💚', 'Cuidar', 'Conocer a su gente, estar presente emocional y espiritualmente. Disponible y cercano.'],
              ['🧭', 'Ubicar', 'Ayudar a cada persona a encontrar su lugar. Identificar dones y conectar con oportunidades.'],
              ['🚀', 'Activar', 'Dar oportunidades de servir. Impulsar el siguiente paso. Generar compromiso real.'],
              ['👑', 'Desarrollar', 'Formar nuevos líderes. Acompañar procesos. Multiplicar el liderazgo.'],
            ].map(([icon, titulo, desc], i) => (
              <div key={i} className="p-4 bg-white border-2 border-[#E7E2D6] rounded-lg">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-xl">{icon}</span>
                  <h3 className="text-base font-bold text-[#1B2A4A]">{titulo}</h3>
                </div>
                <p className="text-xs leading-snug text-[#1B2A4A]/80">{desc}</p>
              </div>
            ))}
          </div>

          {/* Ley del Liderazgo: sin mt-auto para no invadir la zona del folio */}
          <div className="mt-5 p-4 bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] text-white rounded-lg text-center relative overflow-hidden">
            <div className="absolute top-0 right-0 w-20 h-20 bg-[#C8A951]/10 rounded-full -mr-10 -mt-10" />
            <p className="text-[10pt] uppercase tracking-widest text-[#C8A951] font-bold mb-1 relative">Ley del Liderazgo</p>
            <p className="text-sm italic leading-snug relative" style={{ fontFamily: 'Spectral, serif' }}>
              "El verdadero liderazgo no se mide por cuántos te siguen,
              sino por <span className="text-[#C8A951] font-bold not-italic">cuántos líderes levantas</span>."
            </p>
          </div>
        </div>

        {/* PÁGINA: Mentor - Parte 1 (propósito, perfil, responsabilidades) */}
        <div className="manual-page page-break">
          <SectionHeader num="18" titulo="Propósito del Mentor" subtitulo="2 Timoteo 2:2" />

          <p className="text-base leading-relaxed mb-5">
            El mentor es el <strong>puente</strong> entre el evangelio y la vida cotidiana. Su rol
            no es enseñar teología, sino acompañar una transformación concreta: ayudar al nuevo
            creyente a asentar su fe, a ordenar su vida y a integrarse activamente al Cuerpo.
          </p>

          <ListBlock titulo="El mentor existe para" items={[
            'Afirmar la fe del nuevo creyente',
            'Ayudarlo a cambiar su estilo de vida',
            'Integrarlo a la iglesia',
            'Prepararlo para servir',
          ]} />

          <h3 className="text-xl font-bold mt-6 mb-3">Perfil del Mentor</h3>
          <div className="grid grid-cols-2 gap-3 mb-5">
            <div className="p-4 bg-[#F5F0E8] rounded-lg border-l-4 border-[#C8A951]">
              <p className="font-bold text-base mb-2" style={{ fontFamily: 'Spectral, serif' }}>Espiritualmente</p>
              <ul className="text-sm space-y-1 list-disc pl-4 leading-snug">
                <li>Vida de oración constante</li>
                <li>Amor genuino por las personas</li>
                <li>Conocimiento bíblico básico</li>
                <li>Llenura del Espíritu</li>
              </ul>
            </div>
            <div className="p-4 bg-[#F5F0E8] rounded-lg border-l-4 border-[#C8A951]">
              <p className="font-bold text-base mb-2" style={{ fontFamily: 'Spectral, serif' }}>Carácter</p>
              <ul className="text-sm space-y-1 list-disc pl-4 leading-snug">
                <li>Paciencia con el proceso</li>
                <li>Responsabilidad y puntualidad</li>
                <li>Buen testimonio público</li>
                <li>Humildad y servicio</li>
              </ul>
            </div>
          </div>

          <h3 className="text-xl font-bold mt-5 mb-3">Responsabilidades</h3>
          <div className="space-y-2">
            {[
              ['📞', 'Contacto semanal', 'Llamada o mensaje personal — que sepa que alguien ora por él.'],
              ['📖', 'Reunión de discipulado', 'Una vez por semana, cara a cara, con material claro.'],
              ['🙏', 'Cuidado espiritual', 'Orar por su proceso, escuchar sin juzgar, aconsejar con la Palabra.'],
              ['🔗', 'Integración', 'Acompañar a la célula y a su puerta ministerial hasta que esté firme.'],
            ].map(([icon, t, d], i) => (
              <div key={i} className="flex items-center gap-3 p-3 bg-white border border-[#E7E2D6] rounded-lg">
                <span className="text-2xl shrink-0">{icon}</span>
                <div>
                  <p className="font-bold text-sm text-[#1B2A4A] leading-tight">{t}</p>
                  <p className="text-xs text-[#1B2A4A]/75 leading-snug">{d}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* PÁGINA: Mentor - Parte 2 (Discipulado en 8 semanas detallado) */}
        <div className="manual-page page-break">
          <SectionHeader num="18" titulo="Discipulado en 8 Semanas" subtitulo="El mapa del nuevo creyente" />

          <p className="text-base leading-relaxed mb-5">
            Las primeras 8 semanas son <strong>decisivas</strong>. Determinan si el nuevo creyente
            se queda o se pierde. Este plan semanal te da estructura clara — ningún tema al azar,
            ninguna semana sin propósito.
          </p>

          <div className="space-y-2.5">
            {[
              ['S1', 'Salvación y seguridad en Cristo', '2 Corintios 5:17 · Ser nueva criatura'],
              ['S2', 'Oración y relación con Dios', 'Jeremías 33:3 · Aprender a hablar con Él'],
              ['S3', 'La Biblia y crecimiento espiritual', 'El alimento diario del alma'],
              ['S4', 'La iglesia y congregarse', 'No somos piedras sueltas, somos familia'],
              ['S5', 'Cambio de vida y santidad', 'El evangelio transforma lo práctico'],
              ['S6', 'Visión y propósito', 'Descubrir para qué fuimos creados'],
              ['S7', 'Descubrir el don · servir en una puerta', 'Activar lo que Dios puso dentro'],
              ['S8', 'Preparación para el liderazgo', 'De discípulo a formador de otros'],
            ].map(([s, t, d]) => (
              <div key={s} className="flex items-center gap-3 p-3 border-2 border-[#E7E2D6] rounded-lg bg-white">
                <div className="w-12 h-12 rounded-lg bg-[#C8A951] text-[#1B2A4A] font-bold text-lg flex items-center justify-center shrink-0" style={{ fontFamily: 'Spectral, serif' }}>{s}</div>
                <div className="flex-1">
                  <p className="font-bold text-base text-[#1B2A4A] leading-tight" style={{ fontFamily: 'Spectral, serif' }}>{t}</p>
                  <p className="text-xs text-[#1B2A4A]/65 italic leading-snug mt-0.5">{d}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* PÁGINA: Consolidado de Puerta (dedicada) */}
        <div className="manual-page page-break">
          <SectionHeader num="19" titulo="Consolidado de Puerta" subtitulo="No por emoción. Por EVIDENCIA." />

          <p className="text-base leading-relaxed mb-5">
            Un consolidado <strong>no se mide por la intensidad de una experiencia</strong>, sino
            por cuatro indicadores tangibles que demuestran que la persona está arraigada. Estos
            cuatro puntos son el estándar: si no los cumple, no hay consolidación real, por más
            emotiva que haya sido su entrega.
          </p>

          <div className="grid grid-cols-2 gap-4 mb-5">
            {[
              ['📍', 'Ubicación', 'Tiene una puerta definida donde sirve', '#C8A951'],
              ['⚡', 'Activación', 'Ya está sirviendo, no solo observando', '#1B2A4A'],
              ['🛡', 'Cobertura', 'Tiene un líder que lo conoce por nombre', '#C8A951'],
              ['🔄', 'Proceso', 'Está en formación continua, no estancado', '#1B2A4A'],
            ].map(([icon, t, d, color], i) => (
              <div key={i} className="p-4 border-2 border-[#C8A951] rounded-lg text-center bg-white">
                <div className="text-3xl mb-2">{icon}</div>
                <p className="text-[10pt] text-[#C8A951] font-bold uppercase tracking-widest">Indicador {i + 1}</p>
                <p className="text-xl font-bold mt-1" style={{ fontFamily: 'Spectral, serif' }}>{t}</p>
                <p className="text-sm text-[#1B2A4A]/70 mt-1.5 leading-snug">{d}</p>
              </div>
            ))}
          </div>

          <div className="mt-5 p-5 bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] text-white rounded-lg text-center relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-[#C8A951]/10 rounded-full -mr-16 -mt-16" />
            <p className="italic text-lg leading-relaxed relative" style={{ fontFamily: 'Spectral, serif' }}>
              "No queremos solo personas presentes,
              <span className="text-[#C8A951] font-bold not-italic"> queremos personas firmes.</span>"
            </p>
            <div className="w-12 h-0.5 bg-[#C8A951]/60 mx-auto my-3 relative" />
            <p className="text-sm text-white/80 relative">Un cuerpo fuerte se mide por la firmeza de cada miembro.</p>
          </div>
        </div>

        {/* PÁGINA: Reunión Mensual de Supervisores (dedicada) */}
        <div className="manual-page page-break">
          <SectionHeader num="20" titulo="Reunión Mensual de Supervisores" subtitulo="30 minutos · Máximo enfoque" />

          <p className="text-base leading-relaxed mb-5">
            Una reunión <strong>breve, concreta y estratégica</strong>. No es para socializar;
            es para detectar, ajustar y activar. Cada minuto tiene un propósito. Cada agenda
            produce decisiones. Si sales sin un cambio claro, la reunión fracasó.
          </p>

          <div className="space-y-3">
            {[
              ['5 min', 'Inicio', 'Oración · Ministración · Bienvenida', 'Alinear corazones antes que mentes.'],
              ['5 min c/u', 'Evaluación por supervisor', '¿Cuántos líderes? ¿Quién avanza? ¿Quién necesita ayuda?', 'Nombre por nombre. Sin generalidades.'],
              ['10 min', 'Detección de bloqueos', '¿Dónde se detiene la gente? ¿Qué puerta falla?', 'El diagnóstico precede al tratamiento.'],
              ['5 min', 'Ajustes', '¿Qué corregir? ¿Qué puerta reforzar?', 'Decisiones concretas, con responsable.'],
              ['5 min', 'Activación', 'Orar · Declarar claridad, multiplicación, movimiento', 'Salir con fe renovada y pasos claros.'],
            ].map(([t, b, d, sub], i) => (
              <div key={i} className="flex gap-3 p-3 bg-[#F5F0E8]/70 rounded-lg border-l-4 border-[#C8A951]">
                <div className="w-20 font-mono font-bold text-sm shrink-0 text-[#C8A951] flex items-start pt-0.5">{t}</div>
                <div className="flex-1">
                  <p className="font-bold text-base leading-tight text-[#1B2A4A]">{b}</p>
                  <p className="text-sm text-[#1B2A4A]/75 leading-snug mt-0.5">{d}</p>
                  <p className="text-xs text-[#C8A951] italic mt-1">{sub}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-5 pt-4 p-3 bg-[#C8A951]/15 border border-[#C8A951]/40 rounded-lg text-center">
            <p className="text-sm italic text-[#1B2A4A] leading-relaxed" style={{ fontFamily: 'Spectral, serif' }}>
              <strong className="not-italic text-[#C8A951]">30 minutos bien invertidos</strong> valen
              más que 3 horas sin propósito.
            </p>
          </div>
        </div>


        {/* PÁGINA 28: Estrategia de Ganar */}
        <div className="manual-page page-break">
          <SectionHeader num="21" titulo="Estrategia de Ganar" subtitulo="Visión concreta · Meta medible" />

          <p className="text-base leading-relaxed mb-5">
            No hay fe sin acción, ni visión sin meta. La iglesia que quiere crecer debe
            <strong> escribir sus objetivos</strong>, definir sus tiempos y alinear su equipo
            detrás de un blanco común.
          </p>

          <div className="p-5 bg-gradient-to-br from-[#C8A951]/20 to-[#E2CF8A]/10 border-2 border-[#C8A951] rounded-lg text-center mb-5">
            <p className="text-[10pt] uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-2">Meta del Año</p>
            <p className="text-5xl font-bold text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>40 líderes</p>
            <p className="text-base text-[#1B2A4A]/80 mt-2">formados y activos, distribuidos en las 9 puertas</p>
          </div>

          <h3 className="text-lg font-bold mb-3">Plan Operativo</h3>
          <div className="space-y-2 mb-4">
            {[
              ['📅', 'Abril', 'Lanzamiento del sistema · Formación de líderes base'],
              ['🌱', 'Mayo — Junio', 'Primer ciclo de 7 semanas · Mentoría intensiva'],
              ['⚡', 'Julio', 'Operación 72 · Activación de servidores'],
              ['📈', 'Agosto — Octubre', 'Segundo y tercer ciclo · Multiplicación'],
              ['🎯', 'Noviembre — Diciembre', 'Retiro de cierre · Evaluación · Celebración'],
            ].map(([icon, tiempo, desc], i) => (
              <div key={i} className="flex items-center gap-3 p-3 bg-[#F5F0E8]/70 rounded-lg border-l-4 border-[#C8A951]">
                <span className="text-xl shrink-0">{icon}</span>
                <div className="w-40 font-bold text-sm shrink-0 text-[#1B2A4A]" style={{ fontFamily: 'Spectral, serif' }}>{tiempo}</div>
                <p className="text-sm text-[#1B2A4A]/85 leading-snug">{desc}</p>
              </div>
            ))}
          </div>

          <h3 className="text-lg font-bold mb-2">Invasiones Estratégicas</h3>
          <div className="grid grid-cols-3 gap-2 mb-4">
            {[
              ['🏠', 'Invasión a Hogares', 'Visitas puerta a puerta'],
              ['⛪', 'Invasión a Células', 'Multiplicación territorial'],
              ['🌆', 'Invasión a la Ciudad', 'Evangelismo masivo'],
            ].map(([icon, t, d], i) => (
              <div key={i} className="p-3 border-2 border-[#E7E2D6] rounded-lg text-center bg-white">
                <div className="text-2xl mb-1">{icon}</div>
                <p className="font-bold text-sm" style={{ fontFamily: 'Spectral, serif' }}>{t}</p>
                <p className="text-xs text-[#1B2A4A]/70">{d}</p>
              </div>
            ))}
          </div>

          <div className="p-4 bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] text-white rounded-lg text-center">
            <p className="text-sm italic leading-relaxed" style={{ fontFamily: 'Spectral, serif' }}>
              "La visión sin plan es sueño. El plan sin acción es desperdicio.
              <strong className="text-[#C8A951] not-italic"> La acción con fe es cosecha.</strong>"
            </p>
          </div>
        </div>


        {/* PÁGINA 22 FINAL: Llamado — distribuido con flex para llenar la página */}
        <div className="manual-page page-break">
          {/* Encabezado */}
          <div className="text-center mb-6">
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-[#C8A951] to-[#E2CF8A] flex items-center justify-center mb-5 shadow-xl mx-auto">
              <span className="text-4xl">🔥</span>
            </div>
            <p className="text-sm uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-3">Llamado a Servir</p>
            <h1 className="text-5xl font-bold text-[#1B2A4A] leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
              Año de <span className="italic text-[#C8A951]">Cosecha</span><br /> y <span className="italic text-[#C8A951]">Restitución</span>
            </h1>
            <div className="w-20 h-1 bg-[#C8A951] my-5 mx-auto" />
            <p className="text-base italic text-[#1B2A4A]/75 max-w-md mx-auto leading-relaxed" style={{ fontFamily: 'Spectral, serif' }}>
              Todo lo que has leído cobra sentido en una sola palabra: <strong className="not-italic text-[#C8A951]">servir</strong>.
            </p>
          </div>

          {/* 4 promesas con íconos */}
          <div className="grid grid-cols-1 gap-3 mb-6">
            {[
              ['🚪', 'Hay una puerta para servir', 'Cada creyente tiene un lugar preparado por Dios'],
              ['🎁', 'Hay una función para cada don', 'Tus talentos fueron diseñados con propósito'],
              ['🌱', 'Hay una necesidad en cada área', 'Donde miras carencia, Dios ve oportunidad'],
              ['👶', 'Hay una generación que cuidar', 'Lo que recibes, está llamado a pasar'],
            ].map(([icon, t, d], i) => (
              <div key={i} className="flex items-center gap-3 p-3 bg-[#F5F0E8] rounded-lg border-l-4 border-[#C8A951]">
                <span className="text-2xl shrink-0">{icon}</span>
                <div className="w-8 h-8 rounded-full bg-[#C8A951] text-[#1B2A4A] font-bold flex items-center justify-center text-sm shrink-0">{i + 1}</div>
                <div className="flex-1">
                  <p className="font-bold text-base leading-tight text-[#1B2A4A]">{t}</p>
                  <p className="text-xs text-[#1B2A4A]/65 italic leading-snug">{d}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Cita bíblica destacada */}
          <blockquote className="p-5 bg-gradient-to-br from-[#1B2A4A] to-[#0F1A33] text-white rounded-lg relative overflow-hidden mb-4">
            <div className="absolute top-0 right-0 w-32 h-32 bg-[#C8A951]/10 rounded-full -mr-16 -mt-16" />
            <p className="text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-2 relative">Palabra de Vida</p>
            <p className="text-base italic leading-relaxed relative" style={{ fontFamily: 'Spectral, serif' }}>
              "Porque de la manera que en un cuerpo tenemos muchos miembros,
              pero no todos los miembros tienen la misma función,
              así nosotros, siendo muchos, <strong className="text-[#C8A951] not-italic">somos un cuerpo en Cristo</strong>."
            </p>
            <p className="text-right mt-2 text-sm font-bold text-[#C8A951] relative">— Romanos 12:4-5</p>
          </blockquote>

          {/* Pie: cierre ceremonial */}
          <div className="text-center mt-5 pt-3 border-t-2 border-[#C8A951]/30">
            <p className="text-sm uppercase tracking-[0.3em] text-[#C8A951] font-bold mb-1">Tu turno comienza hoy</p>
            <p className="text-xs text-[#1B2A4A]/50 uppercase tracking-widest mt-2">
              © Manual Oficial · La Ley de las 7 Semanas
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ num, titulo, subtitulo }) {
  return (
    <div className="mb-6 pb-3 border-b-4 border-[#C8A951]">
      <p className="text-xs uppercase tracking-[0.3em] text-[#C8A951] font-bold">Sección {num}</p>
      <h2 className="text-4xl font-bold text-[#1B2A4A] mt-1 leading-tight">{titulo}</h2>
      {subtitulo && <p className="text-base text-[#1B2A4A]/70 italic mt-1">{subtitulo}</p>}
    </div>
  );
}

function Card({ icon, titulo, children }) {
  return (
    <div className="mb-4 p-5 bg-white border-2 border-[#E7E2D6] rounded-lg">
      <div className="flex items-center gap-2.5 mb-2">
        <span className="text-2xl">{icon}</span>
        <h3 className="text-lg font-bold text-[#1B2A4A]">{titulo}</h3>
      </div>
      <p className="text-base leading-relaxed text-[#1B2A4A]/85">{children}</p>
    </div>
  );
}

function ListBlock({ titulo, items }) {
  return (
    <div className="mt-4">
      <h4 className="text-[10pt] uppercase tracking-widest text-[#C8A951] font-bold mb-2">{titulo}</h4>
      <ul className="space-y-1.5 list-none pl-0">
        {items.map((it, i) => (
          <li key={i} className="flex items-start gap-2.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#C8A951] shrink-0 mt-2.5" />
            <span className="text-sm leading-relaxed">{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function IndiceItem({ num, titulo, sub, pag }) {
  return (
    <div className="flex items-baseline gap-2 py-1.5 border-b border-dotted border-[#1B2A4A]/20">
      {num && (
        <span className="font-mono text-[10pt] font-bold text-[#C8A951] w-8 shrink-0">{num}</span>
      )}
      {!num && <span className="w-8 shrink-0" />}
      <div className="flex-1 min-w-0">
        <p className="text-[11pt] font-semibold text-[#1B2A4A] leading-tight">{titulo}</p>
        {sub && <p className="text-[9.5pt] text-[#1B2A4A]/60 italic mt-0.5 leading-snug">{sub}</p>}
      </div>
      <span className="font-mono text-[10pt] font-bold text-[#1B2A4A]/80 shrink-0">{pag}</span>
    </div>
  );
}
