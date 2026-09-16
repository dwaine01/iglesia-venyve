import React, { useRef, useState } from 'react';
import axios from 'axios';
import { Mic, Square } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '../ui/button';
import { useAuth } from '../../context/AuthContext';
import { translateTechnicalText } from '../../lib/displayLabels';

const supportedAudioType = () => {
  if (!window.MediaRecorder?.isTypeSupported) return '';
  return ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'].find((type) => window.MediaRecorder.isTypeSupported(type)) || '';
};

const microphoneError = (error) => {
  if (error?.name === 'NotAllowedError') return 'El navegador bloqueó el micrófono. Activa el permiso del micrófono y vuelve a intentarlo.';
  if (error?.name === 'NotFoundError') return 'No se encontró un micrófono disponible en este dispositivo.';
  if (error?.name === 'NotSupportedError') return 'Este navegador no admite grabación de audio. Usa Safari actualizado, Chrome o Edge.';
  if (error?.name === 'TimeoutError') return 'El micrófono no respondió. Revisa el permiso del navegador y vuelve a intentarlo.';
  return translateTechnicalText(error?.response?.data?.detail || error?.message || 'No se pudo iniciar la grabación');
};

export const BoardRecorder = ({ meetingId, enabled, onCompleted }) => {
  const { API, getAuthHeaders } = useAuth();
  const [recording, setRecording] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const startedAtRef = useRef(null);

  const start = async () => {
    setRequesting(true);
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new DOMException('Grabación no disponible', 'NotSupportedError');
      const stream = await Promise.race([
        navigator.mediaDevices.getUserMedia({ audio: true }),
        new Promise((_, reject) => window.setTimeout(() => reject(new DOMException('Permiso de micrófono pendiente', 'TimeoutError')), 15000)),
      ]);
      streamRef.current = stream;
      const mimeType = supportedAudioType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      const contentType = recorder.mimeType || mimeType || 'audio/webm';
      const initiated = await axios.post(`${API}/api/board/recordings/uploads`, { meeting_id: meetingId, content_type: contentType }, getAuthHeaders());
      chunksRef.current = [];
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onstop = async () => {
        setUploading(true);
        try {
          const blob = new Blob(chunksRef.current, { type: contentType });
          const chunkBytes = 1024 * 1024;
          let sequence = 0;
          for (let offset = 0; offset < blob.size; offset += chunkBytes) {
            const chunk = blob.slice(offset, Math.min(offset + chunkBytes, blob.size), contentType);
            await axios.put(`${API}/api/board/recordings/uploads/${initiated.data.upload_id}/chunks/${sequence}`, chunk, { headers: { ...getAuthHeaders().headers, 'Content-Type': contentType } });
            sequence += 1;
          }
          const durationSeconds = Math.max(0.1, (Date.now() - startedAtRef.current) / 1000);
          await axios.post(`${API}/api/board/recordings/uploads/${initiated.data.upload_id}/complete`, { duration_seconds: durationSeconds }, getAuthHeaders());
          toast.success('Grabación guardada de forma privada');
          await onCompleted?.();
        } catch (error) { toast.error(microphoneError(error)); }
        finally { setUploading(false); streamRef.current?.getTracks().forEach((track) => track.stop()); }
      };
      recorder.start(1000);
      recorderRef.current = recorder;
      startedAtRef.current = Date.now();
      setRecording(true);
      toast.success('Grabación iniciada');
    } catch (error) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      toast.error(microphoneError(error));
    } finally { setRequesting(false); }
  };

  const stop = () => { recorderRef.current?.stop(); setRecording(false); };

  return <div className="border bg-white p-4" data-testid="board-recorder"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-semibold">Grabación privada de la reunión</p><p className="text-xs text-slate-500">El audio se guarda dentro de la reunión y nunca se comparte públicamente.</p>{recording && <p className="mt-2 flex items-center gap-2 text-sm font-semibold text-red-700" data-testid="recording-live-status"><span className="h-2.5 w-2.5 animate-pulse rounded-full bg-red-600" />Grabando ahora</p>}</div>{recording ? <Button onClick={stop} variant="destructive" data-testid="stop-recording-button"><Square className="mr-2 h-4 w-4" />Detener y guardar</Button> : <Button onClick={start} disabled={!enabled || uploading || requesting} className="bg-red-700 hover:bg-red-800" data-testid="start-recording-button"><Mic className="mr-2 h-4 w-4" />{requesting ? 'Esperando micrófono…' : uploading ? 'Guardando audio…' : 'Iniciar grabación'}</Button>}</div>{!enabled && <p className="mt-3 border-l-2 border-amber-500 pl-3 text-xs text-amber-800" data-testid="recording-requires-open-meeting">Primero guarda la asistencia, confirma el aviso y abre la reunión.</p>}</div>;
};