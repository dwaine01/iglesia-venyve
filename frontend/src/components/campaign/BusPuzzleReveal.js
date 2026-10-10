import React, { useEffect, useMemo, useRef, useState } from 'react';

const COLS = 20;
const ROWS = 6;
const TOTAL = COLS * ROWS; // 120 piezas de $100 equivalentes

function mulberry32(seed) {
  let a = seed;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function seededShuffle(n, seed) {
  const arr = Array.from({ length: n }, (_, i) => i);
  const rand = mulberry32(seed);
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

// Revela progresivamente el autobús a color debajo de una silueta oscura,
// en 120 piezas equivalentes de $100, con soporte de montos fraccionarios.
export const BusPuzzleReveal = ({ percent = 0 }) => {
  const order = useMemo(() => seededShuffle(TOTAL, 2026), []);
  const rankByIndex = useMemo(() => {
    const map = new Array(TOTAL);
    order.forEach((idx, rank) => { map[idx] = rank; });
    return map;
  }, [order]);

  const piecesFloat = Math.max(0, Math.min(TOTAL, (percent || 0) * TOTAL));
  const fullCount = Math.floor(piecesFloat);
  const partial = piecesFloat - fullCount;

  const prevCountRef = useRef(0);
  const [popping, setPopping] = useState(new Set());

  useEffect(() => {
    const prev = prevCountRef.current;
    if (fullCount > prev) {
      const newly = order.slice(prev, fullCount);
      setPopping(new Set(newly));
      const timer = setTimeout(() => setPopping(new Set()), 1400);
      prevCountRef.current = fullCount;
      return () => clearTimeout(timer);
    }
    prevCountRef.current = fullCount;
  }, [fullCount, order]);

  return (
    <div className="relative w-full" style={{ aspectRatio: '2164 / 688' }} data-testid="bus-puzzle-reveal">
      <img
        src="/campaign/bus_color_transparent.png"
        alt="Autobús Ven y Come"
        className="absolute inset-0 h-full w-full object-contain"
        draggable={false}
      />
      <div
        className="absolute inset-0 grid"
        style={{ gridTemplateColumns: `repeat(${COLS}, 1fr)`, gridTemplateRows: `repeat(${ROWS}, 1fr)` }}
        data-testid="bus-puzzle-grid"
      >
        {Array.from({ length: TOTAL }, (_, idx) => {
          const rank = rankByIndex[idx];
          let opacity = 1;
          if (rank < fullCount) opacity = 0;
          else if (rank === fullCount) opacity = 1 - partial;
          const row = Math.floor(idx / COLS);
          const col = idx % COLS;
          return (
            <div
              key={idx}
              data-testid={`puzzle-piece-${idx}`}
              className={popping.has(idx) ? 'campaign-piece-pop' : ''}
              style={{
                backgroundImage: 'url(/campaign/bus_silhouette.png)',
                backgroundSize: `${COLS * 100}% ${ROWS * 100}%`,
                backgroundPosition: `${(col / (COLS - 1)) * 100}% ${(row / (ROWS - 1)) * 100}%`,
                opacity,
                transition: 'opacity 1.3s ease',
              }}
            />
          );
        })}
      </div>
    </div>
  );
};
