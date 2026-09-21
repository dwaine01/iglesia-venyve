import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { CheckCircle2, Loader2, Mic, Square } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { translateTechnicalText } from '../../lib/displayLabels';
import { Button } from '../ui/button';

const supportedAudioType = () => {
  if (!window.MediaRecorder?.isTypeSupported) return '';
  return ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'].find((type) => window.MediaRecorder.isTypeSupported(type)) || '';
};

const recorderError = (error) => {
  if (error?.name === 'NotAllowedError') return 'Chrome bloqueó el micrófono. Autorice el micrófono para este sitio y pulse “Iniciar grabación” nuevamente.';
  if (error?.name === 'NotFoundError') return 'Chrome no encontró un micrófono disponible.';
  if (error?.name === 'NotReadableError') return 'Otro programa está usando el micrófono. Cierre ese programa y vuelva a intentarlo.';
  if (error?.name === 'NotSupportedError') return 'Este navegador no admite la grabación requerida.';
  return translateTechnicalText(error?.response?.data?.detail || error?.message || 'No se pudo grabar el audio');
};

const formatDuration = (seconds) => `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;

export const BoardRecorder = ({ meetingId, enabled, onCompleted, onChunkUploaded }) => {
  const { API, getAuthHeaders } = useAuth();
  const [recording, setRecording] = useState(false); const [uploading, setUploading] = useState(false); const [requesting, setRequesting] = useState(false);
  const [elapsed, setElapsed] = useState(0); const [uploadedBytes, setUploadedBytes] = useState(0); const [errorMessage, setErrorMessage] = useState(''); const [saved, setSaved] = useState(false);
  const recorderRef = useRef(null); const streamRef = useRef(null); const startedAtRef = useRef(null); const uploadIdRef = useRef(null); const sequenceRef = useRef(0); const uploadChainRef = useRef(Promise.resolve()); const uploadErrorRef = useRef(null);

  useEffect(() => {
    if (!recording) return undefined;
    const tick = () => setElapsed(Math.max(0, Math.floor((Date.now() - startedAtRef.current) / 1000)));
    tick(); const timer = window.setInterval(tick, 1000); return () => window.clearInterval(timer);
  }, [recording]);

  useEffect(() => {
    const warn = (event) => { if (recorderRef.current?.state === 'recording') { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', warn);
    return () => { window.removeEventListener('beforeunload', warn); if (recorderRef.current?.state === 'recording') recorderRef.current.stop(); };
  }, []);

  const enqueueChunk = (blob, contentType) => {
    if (!blob?.size || !uploadIdRef.current || uploadErrorRef.current) return;
    const sequence = sequenceRef.current; sequenceRef.current += 1;
    uploadChainRef.current = uploadChainRef.current.then(async () => {
      if (uploadErrorRef.current) return;
      try {
        const chunkElapsed = Math.max(0, (Date.now() - startedAtRef.current) / 1000);
        const response = await axios.put(`${API}/api/board/recordings/uploads/${uploadIdRef.current}/chunks/${sequence}`, blob, { headers: { ...getAuthHeaders().headers, 'Content-Type': contentType, 'X-Recording-Elapsed-Seconds': String(chunkElapsed) } });
        setUploadedBytes(response.data.total_bytes || 0);
        onChunkUploaded?.();
      } catch (error) {
        uploadErrorRef.current = error; setErrorMessage(recorderError(error));
        if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
      }
    });
  };

  const finalize = async () => {
    setRecording(false); setUploading(true);
    try {
      await uploadChainRef.current;
      if (uploadErrorRef.current) throw uploadErrorRef.current;
      if (sequenceRef.current === 0) throw new Error('El micrófono no produjo audio. Verifique el dispositivo e inténtelo nuevamente.');
      const durationSeconds = Math.max(0.1, (Date.now() - startedAtRef.current) / 1000);
      await axios.post(`${API}/api/board/recordings/uploads/${uploadIdRef.current}/complete`, { duration_seconds: durationSeconds }, getAuthHeaders());
      setSaved(true); toast.success('Grabación guardada de forma privada'); await onCompleted?.();
    } catch (error) {
      if (uploadIdRef.current && (uploadErrorRef.current || sequenceRef.current === 0)) axios.delete(`${API}/api/board/recordings/uploads/${uploadIdRef.current}`, getAuthHeaders()).catch(() => {});
      const message = recorderError(error); setErrorMessage(message); toast.error(message);
    } finally {
      setUploading(false); streamRef.current?.getTracks().forEach((track) => track.stop()); streamRef.current = null; recorderRef.current = null; uploadIdRef.current = null;
    }
  };

  const start = async () => {
    setRequesting(true); setErrorMessage(''); setSaved(false); setElapsed(0); setUploadedBytes(0); uploadIdRef.current = null; sequenceRef.current = 0; uploadErrorRef.current = null; uploadChainRef.current = Promise.resolve();
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new DOMException('Grabación no disponible', 'NotSupportedError');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      streamRef.current = stream; const mimeType = supportedAudioType(); const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream); const contentType = recorder.mimeType || mimeType || 'audio/webm';
      const initiated = await axios.post(`${API}/api/board/recordings/uploads`, { meeting_id: meetingId, content_type: contentType }, getAuthHeaders());
      uploadIdRef.current = initiated.data.upload_id; recorderRef.current = recorder;
      recorder.ondataavailable = (event) => enqueueChunk(event.data, contentType);
      recorder.onerror = (event) => { uploadErrorRef.current = event.error || new Error('MediaRecorderError'); setErrorMessage(recorderError(uploadErrorRef.current)); };
      recorder.onstop = finalize; startedAtRef.current = Date.now(); recorder.start(5000); setRecording(true); toast.success('Grabación iniciada');
    } catch (error) {
      if (uploadIdRef.current) axios.delete(`${API}/api/board/recordings/uploads/${uploadIdRef.current}`, getAuthHeaders()).catch(() => {});
      streamRef.current?.getTracks().forEach((track) => track.stop()); streamRef.current = null; const message = recorderError(error); setErrorMessage(message); toast.error(message);
    } finally { setRequesting(false); }
  };

  const stop = () => { if (recorderRef.current?.state === 'recording') recorderRef.current.stop(); };

  return <section className="border bg-white p-4" data-testid="board-recorder"><div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-semibold">Grabación privada de la reunión</p><p className="text-xs text-slate-500">El audio se guarda por bloques mientras la reunión continúa.</p>{recording && <div className="mt-3 flex flex-wrap items-center gap-3 text-sm font-semibold text-red-700" data-testid="recording-live-status"><span className="h-2.5 w-2.5 animate-pulse rounded-full bg-red-600" />Grabando <b className="font-mono text-lg" data-testid="recording-elapsed-timer">{formatDuration(elapsed)}</b><span className="text-xs font-normal text-slate-500" data-testid="recording-uploaded-bytes">{Math.round(uploadedBytes / 1024)} KB protegidos</span></div>}{uploading && <p className="mt-3 flex items-center gap-2 text-sm text-amber-800" data-testid="recording-finalizing-status"><Loader2 className="h-4 w-4 animate-spin" />Finalizando y verificando audio…</p>}{saved && !recording && !uploading && <p className="mt-3 flex items-center gap-2 text-sm text-emerald-700" data-testid="recording-saved-status"><CheckCircle2 className="h-4 w-4" />Audio guardado y disponible abajo.</p>}</div>{recording ? <Button onClick={stop} variant="destructive" data-testid="stop-recording-button"><Square className="mr-2 h-4 w-4" />Detener y guardar</Button> : <Button onClick={start} disabled={!enabled || uploading || requesting} className="bg-red-700 hover:bg-red-800" data-testid="start-recording-button"><Mic className="mr-2 h-4 w-4" />{requesting ? 'Esperando permiso de Chrome…' : uploading ? 'Guardando audio…' : 'Iniciar grabación'}</Button>}</div>{errorMessage && <div className="mt-4 border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert" data-testid="recording-error-alert">{errorMessage}</div>}{!enabled && <p className="mt-3 border-l-2 border-amber-500 pl-3 text-xs text-amber-800" data-testid="recording-requires-open-meeting">Primero guarda la asistencia, confirma el aviso y abre la reunión.</p>}</section>;
};