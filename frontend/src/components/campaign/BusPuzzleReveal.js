import React, { useEffect, useMemo, useRef, useState } from 'react';
import { buildJigsawPieces, gridFor, seededShuffle, JIGSAW_CELL } from '../../lib/jigsawPieces';
import { formatUsdCents, normalizeSearchText } from '../../lib/campaignFormat';

const IMAGE_ASPECT = 2164 / 688;
const PIECE_VALUE_CENTS = 10000;
// Silueta real del autobús (mismo alfa que las imágenes de color) usada para saber qué
// celdas de la cuadrícula caen realmente dentro del vehículo y cuáles quedan en zonas
// muertas (cielo, piso, huecos entre ruedas) donde nunca debe asignarse una donación.
const SILHOUETTE_SRC = '/campaign/bus_silhouette.png';
const VALID_OPACITY_THRESHOLD = 0.55;

function sampleCellOpacity(alpha, imgW, imgH, cols, rows, r, c) {
  const cellW = imgW / cols;
  const cellH = imgH / rows;
  const samples = 5;
  let opaque = 0;
  for (let sy = 0; sy < samples; sy++) {
    for (let sx = 0; sx < samples; sx++) {
      const px = Math.min(imgW - 1, Math.floor(c * cellW + ((sx + 0.5) / samples) * cellW));
      const py = Math.min(imgH - 1, Math.floor(r * cellH + ((sy + 0.5) / samples) * cellH));
      if (alpha[py * imgW + px] > 128) opaque += 1;
    }
  }
  return opaque / (samples * samples);
}

// Busca una resolución de cuadrícula con suficientes celdas "válidas" (dentro de la
// silueta) para que cada donación (totalPieces) caiga siempre en una celda visible.
function computeValidGrid(totalPieces, aspect, alpha, imgW, imgH) {
  let factor = 1.25;
  let last = null;
  for (let attempt = 0; attempt < 6; attempt++) {
    const target = Math.ceil(totalPieces * factor);
    const { cols, rows } = gridFor(target, aspect);
    const validIds = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (sampleCellOpacity(alpha, imgW, imgH, cols, rows, r, c) >= VALID_OPACITY_THRESHOLD) {
          validIds.push(r * cols + c);
        }
      }
    }
    last = { cols, rows, validIds };
    if (validIds.length >= totalPieces) return last;
    factor += 0.25;
  }
  return last;
}

function useValidGrid(totalPieces) {
  const [gridInfo, setGridInfo] = useState(null);
  const alphaCacheRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      if (!alphaCacheRef.current) {
        const img = new window.Image();
        img.src = SILHOUETTE_SRC;
        await new Promise((resolve, reject) => { img.onload = resolve; img.onerror = reject; });
        const canvas = document.createElement('canvas');
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);
        const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const alpha = new Uint8ClampedArray(canvas.width * canvas.height);
        for (let i = 0; i < alpha.length; i++) alpha[i] = data[i * 4 + 3];
        alphaCacheRef.current = { alpha, w: canvas.width, h: canvas.height };
      }
      if (cancelled) return;
      const { alpha, w, h } = alphaCacheRef.current;
      setGridInfo(computeValidGrid(totalPieces, IMAGE_ASPECT, alpha, w, h));
    };
    load().catch(() => {});
    return () => { cancelled = true; };
  }, [totalPieces]);

  return gridInfo;
}

// Rompecabezas REAL (piezas con pestañas que encajan) sobre el autobús: cada pieza
// completada (umbral de $100) muestra el color real + el nombre del donante que la
// completó; las piezas parciales se van aclarando proporcionalmente. Todo el mosaico
// se recorta con la silueta real del autobús (máscara SVG) para que las piezas del
// borde sigan el contorno del vehículo en vez de un rectángulo. Las donaciones solo se
// asignan a celdas dentro de la silueta real (ver computeValidGrid) para que ningún
// nombre de donante quede "flotando" fuera del autobús.
export const BusPuzzleReveal = ({ pieces = [], totalPieces = 120, donorTotals = {}, searchQuery = '' }) => {
  const gridInfo = useValidGrid(totalPieces);
  const fallback = useMemo(() => gridFor(totalPieces, IMAGE_ASPECT), [totalPieces]);
  const cols = gridInfo?.cols || fallback.cols;
  const rows = gridInfo?.rows || fallback.rows;
  const jigsaw = useMemo(() => buildJigsawPieces(cols, rows, 7), [cols, rows]);
  const viewW = cols * JIGSAW_CELL;
  const viewH = rows * JIGSAW_CELL;

  // Orden de revelado disperso (no lineal): la donación #k se asigna a una celda
  // aleatoria (pero fija/determinística) de entre las celdas VÁLIDAS (dentro de la
  // silueta), para que las donaciones aparezcan repartidas por el techo, el centro,
  // el frente, etc., sin nunca caer en una zona muerta fuera del autobús.
  const destinations = useMemo(() => {
    if (!gridInfo || gridInfo.validIds.length === 0) return [];
    const order = seededShuffle(gridInfo.validIds.length, 2026);
    const shuffledValid = order.map((i) => gridInfo.validIds[i]);
    return Array.from({ length: totalPieces }, (_, k) => shuffledValid[k % shuffledValid.length]);
  }, [gridInfo, totalPieces]);

  const gridState = useMemo(() => {
    const arr = new Array(cols * rows).fill(null);
    destinations.forEach((gridId, k) => { arr[gridId] = pieces[k] || null; });
    return arr;
  }, [destinations, pieces, cols, rows]);

  const prevFullRef = useRef(new Set());
  const [popping, setPopping] = useState(new Set());

  useEffect(() => {
    const newlyFull = new Set();
    gridState.forEach((p, gridId) => {
      if (p?.status === 'full' && !prevFullRef.current.has(gridId)) newlyFull.add(gridId);
    });
    if (newlyFull.size > 0) {
      setPopping(newlyFull);
      const timer = setTimeout(() => setPopping(new Set()), 1400);
      prevFullRef.current = new Set(gridState.map((p, gridId) => (p?.status === 'full' ? gridId : null)).filter((v) => v !== null));
      return () => clearTimeout(timer);
    }
    prevFullRef.current = new Set(gridState.map((p, gridId) => (p?.status === 'full' ? gridId : null)).filter((v) => v !== null));
  }, [gridState]);

  const firstName = (label) => (label && label !== 'Donante anónimo' ? label.trim().split(/\s+/)[0] : null);
  const searchNorm = normalizeSearchText(searchQuery);
  const [hover, setHover] = useState(null);

  const showTooltip = (e, label, name) => {
    setHover({ x: e.clientX, y: e.clientY, name, label, totalCents: donorTotals[label] || 0 });
  };
  const moveTooltip = (e) => {
    setHover((prev) => (prev ? { ...prev, x: e.clientX, y: e.clientY } : prev));
  };
  const hideTooltip = () => setHover(null);

  return (
    <div className="relative h-full w-full" data-testid="bus-puzzle-reveal">
      <svg viewBox={`0 0 ${viewW} ${viewH}`} className="h-full w-full" preserveAspectRatio="xMidYMid meet">
        <defs>
          {jigsaw.map((piece) => (
            <clipPath id={`vyc-piece-${piece.id}`} key={piece.id}><path d={piece.d} /></clipPath>
          ))}
          <mask id="vyc-bus-silhouette-mask">
            <image href="/campaign/bus_mask_white.png" width={viewW} height={viewH} preserveAspectRatio="none" />
          </mask>
        </defs>

        <g mask="url(#vyc-bus-silhouette-mask)">
          <image href="/campaign/bus_color_transparent.png" width={viewW} height={viewH} preserveAspectRatio="none" />

          {jigsaw.map((piece) => {
            const state = gridState[piece.id] || { status: 'empty', fill_ratio: 0, donor_label: null };
            const opacity = state.status === 'full' ? 0 : state.status === 'partial' ? Math.max(0, 1 - state.fill_ratio) : 1;
            return (
              <g
                key={piece.id}
                clipPath={`url(#vyc-piece-${piece.id})`}
                data-testid={`jigsaw-piece-${piece.id}`}
                className={popping.has(piece.id) ? 'campaign-piece-pop' : ''}
                style={{ opacity, transition: 'opacity 1.1s ease' }}
              >
                <image href="/campaign/bus_color_dim.png" width={viewW} height={viewH} preserveAspectRatio="none" />
              </g>
            );
          })}

          {jigsaw.map((piece) => (
            <path key={`outline-${piece.id}`} d={piece.d} fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="1.3" />
          ))}

          {jigsaw.map((piece) => {
            const state = gridState[piece.id];
            const name = state?.status === 'full' ? firstName(state.donor_label) : null;
            if (!name) return null;
            const isMatch = Boolean(searchNorm) && normalizeSearchText(name).includes(searchNorm);
            return (
              <g key={`label-group-${piece.id}`}>
                {isMatch && (
                  <path
                    d={piece.d}
                    fill="rgba(244,196,48,0.25)"
                    stroke="#F4C430"
                    strokeWidth="3"
                    className="campaign-piece-search-highlight"
                    data-testid={`jigsaw-piece-highlight-${piece.id}`}
                  />
                )}
                <text
                  x={piece.cx}
                  y={piece.cy}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize="11"
                  fontWeight="700"
                  fill="#ffffff"
                  stroke="#07080c"
                  strokeWidth="2"
                  paintOrder="stroke"
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={(e) => showTooltip(e, state.donor_label, name)}
                  onMouseMove={moveTooltip}
                  onMouseLeave={hideTooltip}
                  data-testid={`jigsaw-piece-label-${piece.id}`}
                >
                  {name}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      {hover && (
        <div
          className="pointer-events-none fixed z-50 rounded-lg border border-[#F4C430]/50 bg-black/90 px-3 py-2 text-xs text-white shadow-xl"
          style={{ left: hover.x + 16, top: hover.y + 16 }}
          data-testid="bus-puzzle-tooltip"
        >
          <p className="font-bold text-[#F4C430]">{hover.label}</p>
          <p>Esta pieza: {formatUsdCents(PIECE_VALUE_CENTS)}</p>
          <p>Total donado: {formatUsdCents(hover.totalCents)}</p>
        </div>
      )}
    </div>
  );
};
