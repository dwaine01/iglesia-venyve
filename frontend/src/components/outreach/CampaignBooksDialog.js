import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Loader2, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { errorDetailText } from '../../lib/errorText';

export const CampaignBooksDialog = ({ open, onOpenChange, campaign, mentorOptions }) => {
  const { API, getAuthHeaders } = useAuth();
  const [books, setBooks] = useState([]);
  const [rows, setRows] = useState([]);
  const [queue, setQueue] = useState([{ mentor_person_id: '', book_id: '', quantity: 10 }]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const roster = mentorOptions.filter((mentor) => (campaign?.assigned_mentor_ids || []).includes(mentor.person_id));

  const load = async () => {
    if (!campaign) return;
    setLoading(true);
    try {
      const [booksRes, rowsRes] = await Promise.all([
        axios.get(`${API}/api/library/books?active=true`, getAuthHeaders()),
        axios.get(`${API}/api/mentorship/outreach/campaigns/${campaign.campaign_id}/books`, getAuthHeaders()),
      ]);
      setBooks(booksRes.data.items || []);
      setRows(rowsRes.data.items || []);
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudieron cargar los libros de la invasión'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (open) load(); }, [open, campaign]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateQueueRow = (index, field, value) => {
    setQueue((prev) => prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  };

  const addQueueRow = () => setQueue((prev) => [...prev, { mentor_person_id: '', book_id: '', quantity: 10 }]);
  const removeQueueRow = (index) => setQueue((prev) => prev.filter((_, i) => i !== index));

  const submit = async () => {
    const assignments = queue.filter((row) => row.mentor_person_id && row.book_id && row.quantity > 0)
      .map((row) => ({ mentor_person_id: row.mentor_person_id, book_id: row.book_id, quantity: Number(row.quantity) }));
    if (assignments.length === 0) {
      toast.error('Seleccione al menos un mentor, libro y cantidad');
      return;
    }
    setSaving(true);
    try {
      await axios.post(`${API}/api/mentorship/outreach/campaigns/${campaign.campaign_id}/books`, { assignments }, getAuthHeaders());
      toast.success('Libros asignados');
      setQueue([{ mentor_person_id: '', book_id: '', quantity: 10 }]);
      load();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudieron asignar los libros'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto bg-white" data-testid="campaign-books-dialog">
        <DialogHeader><DialogTitle>Libros de {campaign?.name}</DialogTitle></DialogHeader>
        {loading ? (
          <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
        ) : (
          <div className="space-y-4">
            <div data-testid="campaign-books-current-list">
              <h4 className="mb-2 text-sm font-semibold text-[#101D36]">Ya asignado</h4>
              {rows.length === 0 ? (
                <p className="text-xs text-slate-400">Todavía no se han asignado libros a esta invasión.</p>
              ) : (
                <div className="space-y-1">
                  {rows.map((row) => (
                    <div key={`${row.mentor_person_id}-${row.book_id}`} className="flex items-center justify-between rounded-md border border-[#E8E5DE] px-3 py-1.5 text-xs" data-testid={`campaign-books-row-${row.mentor_person_id}-${row.book_id}`}>
                      <span>{row.mentor_name} · {row.book_name}</span>
                      <span className="text-slate-500">Asignados: {row.assigned} · Entregados: {row.delivered} · Restan: {row.remaining}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div>
              <h4 className="mb-2 text-sm font-semibold text-[#101D36]">Asignar más</h4>
              <div className="space-y-2">
                {queue.map((row, index) => (
                  <div key={index} className="grid grid-cols-[1fr_1fr_90px_32px] items-center gap-2" data-testid={`campaign-books-queue-row-${index}`}>
                    <Select value={row.mentor_person_id} onValueChange={(value) => updateQueueRow(index, 'mentor_person_id', value)}>
                      <SelectTrigger data-testid={`campaign-books-mentor-select-${index}`}><SelectValue placeholder="Mentor" /></SelectTrigger>
                      <SelectContent className="bg-white">
                        {roster.map((mentor) => <SelectItem key={mentor.person_id} value={mentor.person_id}>{mentor.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Select value={row.book_id} onValueChange={(value) => updateQueueRow(index, 'book_id', value)}>
                      <SelectTrigger data-testid={`campaign-books-book-select-${index}`}><SelectValue placeholder="Libro" /></SelectTrigger>
                      <SelectContent className="bg-white">
                        {books.map((book) => <SelectItem key={book.book_id} value={book.book_id}>{book.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <Input type="number" min={1} value={row.quantity} onChange={(event) => updateQueueRow(index, 'quantity', event.target.value)} data-testid={`campaign-books-quantity-input-${index}`} />
                    <Button type="button" size="icon" variant="ghost" onClick={() => removeQueueRow(index)} data-testid={`campaign-books-remove-row-${index}`}><Trash2 className="h-4 w-4 text-slate-400" /></Button>
                  </div>
                ))}
              </div>
              <Button type="button" size="sm" variant="outline" className="mt-2" onClick={addQueueRow} data-testid="campaign-books-add-row-button"><Plus className="h-4 w-4" /> Agregar fila</Button>
            </div>

            <Button disabled={saving} onClick={submit} className="w-full bg-[#132443]" data-testid="campaign-books-submit-button">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Guardar asignaciones'}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
