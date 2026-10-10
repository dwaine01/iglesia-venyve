const CELL = 100;
const BUMP = 15;
const ZONE = 34;
const S = (CELL - ZONE) / 2;
const E = S + ZONE;

function mulberry32(seed) {
  let a = seed;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hEdgeForward(x0, y, sign) {
  const sweep = sign > 0 ? 1 : 0;
  return `L ${x0 + S} ${y} A ${ZONE / 2} ${BUMP} 0 0 ${sweep} ${x0 + E} ${y} L ${x0 + CELL} ${y}`;
}
function hEdgeBackward(x0, y, sign) {
  const sweep = sign > 0 ? 0 : 1;
  return `L ${x0 + E} ${y} A ${ZONE / 2} ${BUMP} 0 0 ${sweep} ${x0 + S} ${y} L ${x0} ${y}`;
}
function vEdgeForward(x, y0, sign) {
  const sweep = sign > 0 ? 1 : 0;
  return `L ${x} ${y0 + S} A ${BUMP} ${ZONE / 2} 0 0 ${sweep} ${x} ${y0 + E} L ${x} ${y0 + CELL}`;
}
function vEdgeBackward(x, y0, sign) {
  const sweep = sign > 0 ? 0 : 1;
  return `L ${x} ${y0 + E} A ${BUMP} ${ZONE / 2} 0 0 ${sweep} ${x} ${y0 + S} L ${x} ${y0}`;
}

// Genera 120 piezas de rompecabezas real (bordes con pestañas que encajan entre
// piezas vecinas) para superponer sobre la imagen del autobús. Determinístico (seed fija)
// para que el mosaico sea siempre el mismo en cada carga de pantalla.
export function buildJigsawPieces(cols, rows, seed = 7) {
  const rand = mulberry32(seed);
  const hSign = Array.from({ length: rows + 1 }, () => Array.from({ length: cols }, () => (rand() < 0.5 ? -1 : 1)));
  const vSign = Array.from({ length: rows }, () => Array.from({ length: cols + 1 }, () => (rand() < 0.5 ? -1 : 1)));

  const pieces = [];
  let id = 0;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const x0 = c * CELL;
      const y0 = r * CELL;
      let d = `M ${x0} ${y0}`;
      d += r === 0 ? ` L ${x0 + CELL} ${y0}` : ' ' + hEdgeForward(x0, y0, hSign[r][c]);
      d += c === cols - 1 ? ` L ${x0 + CELL} ${y0 + CELL}` : ' ' + vEdgeForward(x0 + CELL, y0, vSign[r][c + 1]);
      d += r === rows - 1 ? ` L ${x0} ${y0 + CELL}` : ' ' + hEdgeBackward(x0, y0 + CELL, hSign[r + 1][c]);
      d += c === 0 ? ` L ${x0} ${y0}` : ' ' + vEdgeBackward(x0, y0, vSign[r][c]);
      d += ' Z';
      pieces.push({ id: id++, r, c, d, cx: x0 + CELL / 2, cy: y0 + CELL / 2 });
    }
  }
  return pieces;
}

export function gridFor(total, aspect) {
  let best = { cols: total, rows: 1, score: Infinity };
  for (let rows = 1; rows <= total; rows++) {
    if (total % rows !== 0) continue;
    const cols = total / rows;
    const score = Math.abs(cols / rows - aspect);
    if (score < best.score) best = { cols, rows, score };
  }
  return best;
}

export function seededShuffle(n, seed) {
  const rand = mulberry32(seed);
  const arr = Array.from({ length: n }, (_, i) => i);
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

export const JIGSAW_CELL = CELL;
