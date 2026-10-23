import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Badge } from '../ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { errorDetailText } from '../../lib/errorText';

const BookDeliveries = ({ campaignId, bookId }) => {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API}/api/mentorship/outreach/campaigns/${campaignId}/books/${bookId}/deliveries`, getAuthHeaders())
      .then((response) => setItems(response.data.items || []))
      .finally(() => setLoading(false));
  }, [API, getAuthHeaders, campaignId, bookId]);

  if (loading) return <Loader2 className="h-4 w-4 animate-spin text-slate-400" />;
  if (!items || items.length === 0) return <p className="text-xs text-slate-400">Sin entregas registradas todavía.</p>;
  return (
    <ul className="space-y-1 text-xs text-slate-600" data-testid={`campaign-report-deliveries-${bookId}`}>
      {items.map((item) => <li key={item.movement_id}>{item.person_name} · {new Date(item.occurred_at).toLocaleDateString('es-DO')}</li>)}
    </ul>
  );
};

export const CampaignReportDialog = ({ open, onOpenChange, campaign }) => {
  const { API, getAuthHeaders } = useAuth();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [openBook, setOpenBook] = useState(null);

  useEffect(() => {
    if (!open || !campaign) return;
    setLoading(true);
    axios.get(`${API}/api/mentorship/outreach/campaigns/${campaign.campaign_id}/report`, getAuthHeaders())
      .then((response) => setReport(response.data))
      .catch((error) => toast.error(errorDetailText(error, 'No se pudo cargar el informe de la invasión')))
      .finally(() => setLoading(false));
  }, [open, campaign, API, getAuthHeaders]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto bg-white" data-testid="campaign-report-dialog">
        <DialogHeader><DialogTitle>Informe de {campaign?.name}</DialogTitle></DialogHeader>
        {loading ? (
          <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
        ) : (
          <div className="space-y-3">
            {(report?.mentors || []).map((mentor) => (
              <div key={mentor.mentor_person_id} className="rounded-lg border border-[#E8E5DE] p-3" data-testid={`campaign-report-mentor-${mentor.mentor_person_id}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium text-[#101D36]">{mentor.mentor_name}</p>
                  {mentor.has_activity ? (
                    <Badge className="bg-emerald-100 text-emerald-800">{mentor.contacts_total} contactos · {mentor.accepted} aceptaron</Badge>
                  ) : (
                    <Badge className="bg-slate-100 text-slate-500" data-testid={`campaign-report-no-activity-${mentor.mentor_person_id}`}>Sin actividad</Badge>
                  )}
                </div>
                {mentor.books.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {mentor.books.map((book) => (
                      <div key={book.book_id}>
                        <button
                          type="button"
                          className="flex w-full items-center justify-between rounded px-1 py-1 text-left text-xs text-slate-600 hover:bg-[#F6F4EF]"
                          onClick={() => setOpenBook(openBook === `${mentor.mentor_person_id}-${book.book_id}` ? null : `${mentor.mentor_person_id}-${book.book_id}`)}
                          data-testid={`campaign-report-book-toggle-${mentor.mentor_person_id}-${book.book_id}`}
                        >
                          <span>{book.book_name} · asignados {book.assigned} · entregados {book.delivered}</span>
                          {openBook === `${mentor.mentor_person_id}-${book.book_id}` ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                        </button>
                        {openBook === `${mentor.mentor_person_id}-${book.book_id}` && (
                          <div className="ml-2 border-l border-slate-200 pl-2">
                            <BookDeliveries campaignId={campaign.campaign_id} bookId={book.book_id} />
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {(report?.mentors || []).length === 0 && <p className="text-sm text-slate-400">Esta invasión todavía no tiene mentores asignados.</p>}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
