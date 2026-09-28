import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Plus } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { LibraryBookFormDialog } from '../../components/library/LibraryBookFormDialog';

export default function LibraryCatalogPage() {
  const { API, getAuthHeaders } = useAuth();
  const [books, setBooks] = useState([]);
  const [search, setSearch] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const refresh = useCallback(async () => {
    const { data } = await axios.get(`${API}/api/library/books`, getAuthHeaders());
    setBooks(data.items || []);
  }, [API]);

  useEffect(() => { refresh(); }, [refresh]);

  const toggleActive = async (bookId) => {
    await axios.patch(`${API}/api/library/books/${bookId}/toggle-active`, {}, getAuthHeaders());
    await refresh();
  };

  const filtered = books.filter((b) => b.name.toLowerCase().includes(search.toLowerCase()) || (b.sku || '').toLowerCase().includes(search.toLowerCase()));

  return <main className="min-h-screen bg-[#F4F1EA] px-4 py-6 sm:px-8" data-testid="library-catalog-page">
    <div className="mx-auto max-w-6xl space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div><Link to="/libreria" className="text-sm text-[#0879BE]">← Librería 360</Link><h1 className="font-serif text-3xl text-[#132443]">Catálogo maestro</h1></div>
        <Button className="bg-[#132443]" onClick={() => { setEditing(null); setDialogOpen(true); }} data-testid="open-new-book-button"><Plus className="h-4 w-4" />Nuevo material</Button>
      </header>
      <Input placeholder="Buscar por nombre o SKU…" value={search} onChange={(e) => setSearch(e.target.value)} data-testid="library-catalog-search-input" className="max-w-sm" />
      <div className="rounded-2xl border border-slate-200 bg-white p-2">
        <Table><TableHeader><TableRow><TableHead>Material</TableHead><TableHead>SKU</TableHead><TableHead>Tipo</TableHead><TableHead>Proceso</TableHead><TableHead>Precio miembro</TableHead><TableHead>Costo</TableHead><TableHead>Estado</TableHead><TableHead /></TableRow></TableHeader>
          <TableBody>{filtered.map((book) => <TableRow key={book.book_id} data-testid={`library-catalog-row-${book.book_id}`}>
            <TableCell>{book.name}</TableCell><TableCell>{book.sku || '—'}</TableCell><TableCell>{book.item_type}</TableCell><TableCell>{book.process_key || '—'}</TableCell>
            <TableCell>{book.member_price_cents ? `$${(book.member_price_cents / 100).toFixed(2)}` : 'Gratis'}</TableCell>
            <TableCell>${(book.cost_price_cents / 100).toFixed(2)}</TableCell>
            <TableCell><Badge variant={book.is_active ? 'default' : 'outline'}>{book.is_active ? 'Activo' : 'Inactivo'}</Badge></TableCell>
            <TableCell className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => { setEditing(book); setDialogOpen(true); }} data-testid={`edit-book-${book.book_id}`}>Editar</Button>
              <Button size="sm" variant="ghost" onClick={() => toggleActive(book.book_id)} data-testid={`toggle-active-book-${book.book_id}`}>{book.is_active ? 'Desactivar' : 'Activar'}</Button>
            </TableCell>
          </TableRow>)}</TableBody>
        </Table>
      </div>
    </div>
    <LibraryBookFormDialog open={dialogOpen} onOpenChange={setDialogOpen} book={editing} onSaved={refresh} />
  </main>;
}
