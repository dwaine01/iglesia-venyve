import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Bot, FileCheck2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { DoorEmpty, DoorError, DoorLoading, DoorShell } from '../../components/doors/DoorShell';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { displayLabel, minuteTypeLabel, translateTechnicalText } from '../../lib/displayLabels';

const renderHumanizedContent = (value, path = 'content') => {
  if (value === null || value === undefined || value === '') return <span>Sin contenido</span>;
  if (Array.isArray(value)) {
    return (
      <ul className="list-disc space-y-1 pl-5">
        {value.map((item, index) => <li key={`${path}-${index}`}>{renderHumanizedContent(item, `${path}-${index}`)}</li>)}
      </ul>
    );
  }
  if (typeof value === 'object') {
    return (
      <div className="space-y-3">
        {Object.entries(value).map(([key, item]) => (
          <section key={`${path}-${key}`}>
            <p className="text-xs font-semibold uppercase text-[#8A6818]">{displayLabel(key)}</p>
            <div className="mt-1">{renderHumanizedContent(item, `${path}-${key}`)}</div>
          </section>
        ))}
      </div>
    );
  }
  return <span className="whitespace-pre-wrap">{translateTechnicalText(String(value))}</span>;
};

const MinuteCard = ({ item, onStatusChange }) => (
  <article className="border bg-white p-5" data-testid={`minutes-book-${item.minute_id}`}>
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <p className="flex items-center gap-2 font-semibold">
          {item.minute_type === 'ai_draft'
            ? <Bot className="h-4 w-4 shrink-0 text-[#9E8232]" />
            : <FileCheck2 className="h-4 w-4 shrink-0" />}
          <span>{item.meeting?.title || 'Reunión'}</span>
        </p>
        <p className="text-xs text-slate-500" data-testid={`minute-summary-${item.minute_id}`}>
          {item.meeting?.scheduled_at ? new Date(item.meeting.scheduled_at).toLocaleString('es') : 'Fecha por confirmar'}
          {' · '}versión {item.version}{' · '}{minuteTypeLabel(item.minute_type)}
        </p>
        <div className="mt-3 max-h-48 overflow-y-auto border-l-2 border-slate-200 pl-3 text-sm text-slate-600" data-testid={`minute-content-${item.minute_id}`}>
          {renderHumanizedContent(item.content)}
        </div>
      </div>
      <Select value={item.status} onValueChange={(value) => onStatusChange(item, value)}>
        <SelectTrigger className="w-full sm:w-40" data-testid={`minute-status-${item.minute_id}`}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="bg-white">
          <SelectItem value="draft">Borrador</SelectItem>
          <SelectItem value="review">En revisión</SelectItem>
          <SelectItem value="official">Oficial</SelectItem>
          <SelectItem value="rejected">Rechazada</SelectItem>
          <SelectItem value="ai_draft">Borrador asistido</SelectItem>
        </SelectContent>
      </Select>
    </div>
  </article>
);

export default function BoardMinutesPage() {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/api/board/minutes`, getAuthHeaders());
      setItems(response.data.items || []);
    } catch (requestError) {
      setError(translateTechnicalText(requestError?.response?.data?.detail || 'No se pudo cargar el libro.'));
    } finally {
      setLoading(false);
    }
  }, [API, getAuthHeaders]);

  useEffect(() => { load(); }, [load]);

  const update = async (item, status) => {
    try {
      await axios.put(`${API}/api/board/minutes/${item.minute_id}/status`, { status }, getAuthHeaders());
      toast.success(status === 'official' ? 'Minuta marcada oficial por revisión humana' : 'Estado actualizado');
      await load();
    } catch (requestError) {
      toast.error(translateTechnicalText(requestError?.response?.data?.detail || 'No se pudo revisar'));
    }
  };

  if (loading) {
    return <DoorShell eyebrow="Junta Directiva" title="Libro de minutas" description="Cargando versiones..." guideKey="board_meeting"><DoorLoading /></DoorShell>;
  }

  return (
    <DoorShell eyebrow="Junta Directiva" title="Libro de minutas" description="Versiones humanas y asistidas; ninguna minuta se vuelve oficial sin revisión." guideKey="board_meeting">
      {error ? <DoorError message={error} /> : (
        <section className="space-y-3" data-testid="minutes-book-list">
          {items.length
            ? items.map((item) => <MinuteCard key={item.minute_id} item={item} onStatusChange={update} />)
            : <DoorEmpty testId="minutes-book-empty">No hay minutas todavía.</DoorEmpty>}
        </section>
      )}
    </DoorShell>
  );
}