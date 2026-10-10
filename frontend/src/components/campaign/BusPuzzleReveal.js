import React, { useEffect, useMemo, useRef, useState } from 'react';
import { buildJigsawPieces, gridFor, JIGSAW_CELL } from '../../lib/jigsawPieces';

const IMAGE_ASPECT = 2164 / 688;

// Rompecabezas REAL (piezas con pestañas que encajan) sobre el autobús: cada pieza
// completada (umbral de $100) muestra el color real + el nombre del donante que la
// completó; las piezas parciales se van aclarando proporcionalmente. Todo el mosaico
// se recorta con la silueta real del autobús (máscara SVG) para que las piezas del
// borde sigan el contorno del vehículo en vez de un rectángulo.
export const BusPuzzleReveal = ({ pieces = [], totalPieces = 120 }) => {
  const { cols, rows } = useMemo(() => gridFor(totalPieces, IMAGE_ASPECT), [totalPieces]);
  const jigsaw = useMemo(() => buildJigsawPieces(cols, rows, 7), [cols, rows]);
  const viewW = cols * JIGSAW_CELL;
  const viewH = rows * JIGSAW_CELL;

  const prevFullRef = useRef(new Set());
  const [popping, setPopping] = useState(new Set());

  useEffect(() => {
    const newlyFull = new Set();
    pieces.forEach((p, idx) => {
      if (p?.status === 'full' && !prevFullRef.current.has(idx)) newlyFull.add(idx);
    });
    if (newlyFull.size > 0) {
      setPopping(newlyFull);
      const timer = setTimeout(() => setPopping(new Set()), 1400);
      prevFullRef.current = new Set(pieces.map((p, idx) => (p?.status === 'full' ? idx : null)).filter((v) => v !== null));
      return () => clearTimeout(timer);
    }
    prevFullRef.current = new Set(pieces.map((p, idx) => (p?.status === 'full' ? idx : null)).filter((v) => v !== null));
  }, [pieces]);

  const firstName = (label) => (label && label !== 'Donante anónimo' ? label.trim().split(/\s+/)[0] : null);

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
            const state = pieces[piece.id] || { status: 'empty', fill_ratio: 0, donor_label: null };
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
            const state = pieces[piece.id];
            const name = state?.status === 'full' ? firstName(state.donor_label) : null;
            if (!name) return null;
            return (
              <text
                key={`label-${piece.id}`}
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
                data-testid={`jigsaw-piece-label-${piece.id}`}
              >
                {name}
              </text>
            );
          })}
        </g>
      </svg>
    </div>
  );
};
