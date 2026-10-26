/* Cada ícono del menú lateral debe estar importado: un ícono sin importar rompe el menú entero
   en tiempo de ejecución (pasó con «Datos de prueba»). Revisión estática del archivo. */
const fs = require('fs');
const path = require('path');

test('todos los íconos del menú están importados de lucide-react', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'components', 'AppLayout.js'), 'utf8');
  const importBlock = source.match(/import\s*{([^}]*)}\s*from\s*'lucide-react'/);
  expect(importBlock).not.toBeNull();
  const imported = new Set(importBlock[1].split(',').map((name) => name.trim()).filter(Boolean));
  const used = [...source.matchAll(/icon:\s*([A-Z][A-Za-z0-9]*)/g)].map((match) => match[1]);
  const missing = [...new Set(used)].filter((name) => !imported.has(name));
  expect(missing).toEqual([]);
});
