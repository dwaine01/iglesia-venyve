import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { jsPDF } from 'jspdf';
import QRCode from 'qrcode';
import { Download, Tag } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Checkbox } from '../../components/ui/checkbox';
import { Input } from '../../components/ui/input';
import { BookThumbnail } from '../../components/library/BookThumbnail';

const COLS = 3, ROWS = 10, LABEL_W = 2.625, LABEL_H = 1, MARGIN_X = 0.1875, MARGIN_Y = 0.5, GAP_X = 0.125;

export default function LibraryLabelsPage() {
  const { API, getAuthHeaders } = useAuth();
  const [books, setBooks] = useState([]);
  const [selected, setSelected] = useState({});
  const [generating, setGenerating] = useState(false);

  useEffect(() => { axios.get(`${API}/api/library/books`, { ...getAuthHeaders(), params: { active: true } }).then((r) => setBooks(r.data.items || [])); }, [API]);

  const toggle = (bookId) => setSelected((prev) => { const next = { ...prev }; if (next[bookId] !== undefined) delete next[bookId]; else next[bookId] = 6; return next; });
  const setQty = (bookId, qty) => setSelected((prev) => ({ ...prev, [bookId]: Math.max(1, Number(qty) || 1) }));

  const selectedBooks = useMemo(() => books.filter((b) => selected[b.book_id] !== undefined), [books, selected]);
  const totalLabels = useMemo(() => Object.values(selected).reduce((sum, qty) => sum + qty, 0), [selected]);

  const generatePdf = async () => {
    if (selectedBooks.length === 0) return toast.error('Seleccione al menos un material');
    setGenerating(true);
    try {
      const doc = new jsPDF({ unit: 'in', format: 'letter' });
      let index = 0;
      const perPage = COLS * ROWS;
      for (const book of selectedBooks) {
        const qrDataUrl = await QRCode.toDataURL(`VYV-LIB-${book.book_id}`, { width: 160, margin: 0 });
        const qty = selected[book.book_id];
        for (let i = 0; i < qty; i += 1) {
          if (index > 0 && index % perPage === 0) doc.addPage();
          const posOnPage = index % perPage;
          const col = posOnPage % COLS, row = Math.floor(posOnPage / COLS);
          const x = MARGIN_X + col * (LABEL_W + GAP_X);
          const y = MARGIN_Y + row * LABEL_H;
          doc.setDrawColor(200); doc.rect(x, y, LABEL_W, LABEL_H);
          doc.addImage(qrDataUrl, 'PNG', x + 0.08, y + 0.1, 0.8, 0.8);
          doc.setFontSize(8); doc.setFont(undefined, 'bold');
          doc.text((book.name || '').slice(0, 26), x + 1.0, y + 0.25, { maxWidth: LABEL_W - 1.05 });
          doc.setFontSize(7); doc.setFont(undefined, 'normal');
          doc.text(`SKU: ${book.sku || '—'}`, x + 1.0, y + 0.48);
          if (book.process_key || book.level) doc.text(`${book.process_key || ''}${book.level ? ' · ' + book.level : ''}`.slice(0, 30), x + 1.0, y + 0.66, { maxWidth: LABEL_W - 1.05 });
          index += 1;
        }
      }
      doc.save('etiquetas-libreria.pdf');
      toast.success(`${index} etiquetas generadas`);
    } finally { setGenerating(false); }
  };

  return <main className="min-h-screen bg-[#F4F1EA] px-4 py-6 sm:px-8" data-testid="library-labels-page">
    <div className="mx-auto max-w-5xl space-y-5">
      <header><Link to="/libreria" className="text-sm text-[#0879BE]">← Librería 360</Link><h1 className="font-serif text-3xl text-[#132443]">Etiquetas imprimibles</h1><p className="text-sm text-slate-600">Genera hojas de etiquetas con QR interno (mismo código que usa el escáner), formato de 3 columnas por hoja Carta/A4.</p></header>

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="labels-book-list">
          <h2 className="mb-2 font-serif text-lg text-[#132443]">1. Seleccione materiales</h2>
          <ul className="divide-y">{books.map((b) => <li key={b.book_id} className="flex items-center gap-3 py-2" data-testid={`labels-book-row-${b.book_id}`}>
            <Checkbox checked={selected[b.book_id] !== undefined} onCheckedChange={() => toggle(b.book_id)} data-testid={`labels-select-${b.book_id}`} />
            <BookThumbnail fileId={b.cover_file_id} size={32} /><span className="flex-1">{b.name}</span>
            {selected[b.book_id] !== undefined && <Input type="number" min="1" className="w-20" value={selected[b.book_id]} onChange={(e) => setQty(b.book_id, e.target.value)} data-testid={`labels-qty-${b.book_id}`} />}
          </li>)}</ul>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="labels-summary">
            <p className="text-sm text-slate-600">Materiales seleccionados: <strong>{selectedBooks.length}</strong></p>
            <p className="text-sm text-slate-600">Total de etiquetas: <strong data-testid="labels-total-count">{totalLabels}</strong></p>
            <Button className="mt-3 w-full bg-[#132443]" onClick={generatePdf} disabled={generating} data-testid="generate-labels-pdf-button"><Download className="h-4 w-4" />Generar PDF</Button>
          </div>
          {selectedBooks.length > 0 && <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="labels-preview">
            <h3 className="mb-2 flex items-center gap-2 font-serif text-base text-[#132443]"><Tag className="h-4 w-4" />Vista previa</h3>
            {selectedBooks.slice(0, 1).map((b) => <div key={b.book_id} className="flex items-center gap-2 rounded border border-dashed border-slate-300 p-2 text-xs" data-testid={`labels-preview-card-${b.book_id}`}>
              <BookThumbnail fileId={b.cover_file_id} size={40} />
              <div><p className="font-semibold">{b.name}</p><p className="text-slate-500">SKU: {b.sku || '—'}</p>{(b.process_key || b.level) && <p className="text-slate-400">{b.process_key} {b.level}</p>}</div>
            </div>)}
          </div>}
        </div>
      </div>
    </div>
  </main>;
}
