// Audio del Radio: captura del micrófono → PCM 16 kHz mono 16 bits en
// fragmentos de 40 ms, y reproducción en orden con un colchón adaptable.
// Sin librerías: Web Audio (AudioWorklet con respaldo ScriptProcessor).
// Se reproduce al ritmo del AudioContext (48/44,1 kHz) para que funcione igual
// en iPhone (Safari no acepta búferes de 16 kHz en todas las versiones).
export const RADIO_RATE = 16000;
const CHUNK = 640; // 40 ms a 16 kHz

const WORKLET = `class Tap extends AudioWorkletProcessor { process(inputs) { const ch = inputs[0] && inputs[0][0]; if (ch) this.port.postMessage(ch.slice(0)); return true; } }
registerProcessor('radio-tap', Tap);`;

/** Registro de diagnóstico con código (se ve en la consola del navegador). */
export function radioLog(code, detail) {
  try { console.warn(`[radio] ${code}`, detail ?? ''); } catch (error) { /* sin consola */ }
}

function resample(input, fromRate, toRate) {
  if (fromRate === toRate) return input;
  const ratio = fromRate / toRate;
  const length = Math.floor(input.length / ratio);
  const output = new Float32Array(length);
  for (let index = 0; index < length; index += 1) {
    const position = index * ratio;
    const left = Math.floor(position);
    const right = Math.min(left + 1, input.length - 1);
    output[index] = input[left] + (input[right] - input[left]) * (position - left);
  }
  return output;
}

const toInt16 = (floats) => {
  const out = new Int16Array(floats.length);
  for (let index = 0; index < floats.length; index += 1) {
    const value = Math.max(-1, Math.min(1, floats[index]));
    out[index] = value < 0 ? value * 0x8000 : value * 0x7fff;
  }
  return out;
};

const rms = (frame) => {
  let sum = 0;
  for (let index = 0; index < frame.length; index += 1) sum += frame[index] * frame[index];
  return Math.sqrt(sum / (frame.length || 1));
};

export function createAudioContext() {
  const Context = window.AudioContext || window.webkitAudioContext;
  return new Context({ latencyHint: 'interactive' });
}

export const isIOS = () => /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

/** Navegadores dentro de otras apps (WhatsApp, Facebook, Instagram…): suelen no dar micrófono. */
export function inAppBrowser() {
  const ua = navigator.userAgent || '';
  if (/FBAN|FBAV|FB_IAB|FBIOS/i.test(ua)) return 'Facebook';
  if (/Instagram/i.test(ua)) return 'Instagram';
  if (/WhatsApp/i.test(ua)) return 'WhatsApp';
  if (/Line\//i.test(ua)) return 'LINE';
  if (/TikTok|musical_ly|Bytedance/i.test(ua)) return 'TikTok';
  if (/Snapchat/i.test(ua)) return 'Snapchat';
  return null;
}

/** 'granted' | 'denied' | 'prompt' | null (si el navegador no lo informa). */
export async function micPermission() {
  try {
    const status = await navigator.permissions?.query({ name: 'microphone' });
    return status?.state || null;
  } catch (error) { return null; }
}

/** Código claro por tipo de error de getUserMedia. */
export function micErrorCode(error) {
  const name = error?.name || '';
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') return 'denied';
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError' || name === 'OverconstrainedError') return 'notfound';
  if (name === 'NotReadableError' || name === 'TrackStartError' || name === 'AbortError') return 'busy';
  if (name === 'SecurityError') return 'insecure';
  if (name === 'NoFrames') return 'noframes';
  return 'unsupported';
}

// El módulo del worklet se carga UNA vez por contexto (registrar dos veces el mismo nombre falla).
function tapModule(context) {
  if (!context.audioWorklet) return Promise.reject(new Error('Sin AudioWorklet'));
  if (!context.__radioTap) {
    const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }));
    context.__radioTap = context.audioWorklet.addModule(url).finally(() => URL.revokeObjectURL(url));
  }
  return context.__radioTap;
}

/** Micrófono abierto y SIEMPRE capturando (no se apaga la pista: en iPhone
 * apagarla puede romper la captura); solo se ENVÍA mientras `setSending(true)`.
 * Verifica que lleguen datos: si el worklet no entrega nada en 800 ms usa el
 * respaldo ScriptProcessor. Lanza un error con `name` si no se puede. */
export async function openMicrophone(context, onChunk) {
  if (!navigator.mediaDevices?.getUserMedia) {
    const error = new Error(window.isSecureContext === false ? 'Se necesita https' : 'Sin micrófono en este navegador');
    error.name = window.isSecureContext === false ? 'SecurityError' : 'NotSupportedError';
    throw error;
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
  // En iPhone, abrir el micrófono puede suspender/interrumpir el contexto: se reanuda.
  try { await context.resume(); } catch (error) { radioLog('CTX_RESUME_FAIL', error?.message); }
  const source = context.createMediaStreamSource(stream);
  const mute = context.createGain(); mute.gain.value = 0; // el nodo debe llegar al destino para procesar, sin oírse
  mute.connect(context.destination);
  let sending = false;
  let pending = new Float32Array(0);
  let level = 0;
  let frames = 0;
  const push = (frame) => {
    frames += 1;
    level = Math.max(rms(frame), level * 0.85);
    if (!sending) return;
    const resampled = resample(frame, context.sampleRate, RADIO_RATE);
    const merged = new Float32Array(pending.length + resampled.length);
    merged.set(pending); merged.set(resampled, pending.length);
    let offset = 0;
    while (merged.length - offset >= CHUNK) {
      onChunk(toInt16(merged.subarray(offset, offset + CHUNK)).buffer);
      offset += CHUNK;
    }
    pending = merged.slice(offset);
  };
  const scriptNode = () => {
    const node = context.createScriptProcessor(2048, 1, 1);
    node.onaudioprocess = (event) => push(event.inputBuffer.getChannelData(0));
    return node;
  };
  let node;
  let kind = 'worklet';
  try {
    await tapModule(context);
    node = new AudioWorkletNode(context, 'radio-tap');
    node.port.onmessage = (event) => push(event.data);
  } catch (error) {
    radioLog('MIC_WORKLET_FAIL', error?.message);
    node = scriptNode(); kind = 'script';
  }
  source.connect(node); node.connect(mute);
  await new Promise((resolve) => setTimeout(resolve, 800));
  if (!frames && kind === 'worklet') {
    radioLog('MIC_WORKLET_NO_FRAMES', context.state);
    try { source.disconnect(node); node.disconnect(); } catch (error) { /* nada */ }
    node = scriptNode(); kind = 'script';
    source.connect(node); node.connect(mute);
    await new Promise((resolve) => setTimeout(resolve, 800));
  }
  if (!frames) {
    stream.getTracks().forEach((track) => track.stop());
    radioLog('MIC_NO_FRAMES', { state: context.state, kind });
    const error = new Error('El micrófono no entrega sonido'); error.name = 'NoFrames';
    throw error;
  }
  const track = stream.getAudioTracks()[0];
  return {
    kind,
    track,
    setSending(value) { sending = value; pending = new Float32Array(0); },
    level() { return level; },
    frames() { return frames; },
    close() { sending = false; try { source.disconnect(); node.disconnect(); mute.disconnect(); } catch (error) { /* ya desconectado */ } stream.getTracks().forEach((item) => item.stop()); },
  };
}

/** Reproduce fragmentos PCM16 16 kHz EN ORDEN con colchón adaptable: empieza
 * en 120 ms y, si la red se atrasa (corte), sube hasta 400 ms para no saltar. */
export function createPlayer(context, output = context.destination) {
  let playhead = 0;
  let target = 0.12;
  let underruns = 0;
  return {
    play(arrayBuffer) {
      const ints = new Int16Array(arrayBuffer);
      const floats = new Float32Array(ints.length);
      for (let index = 0; index < ints.length; index += 1) floats[index] = ints[index] / 0x8000;
      const samples = resample(floats, RADIO_RATE, context.sampleRate);
      const buffer = context.createBuffer(1, samples.length, context.sampleRate);
      buffer.copyToChannel ? buffer.copyToChannel(samples, 0) : buffer.getChannelData(0).set(samples);
      const node = context.createBufferSource();
      node.buffer = buffer; node.connect(output);
      const now = context.currentTime;
      if (playhead < now + 0.02) {
        if (playhead) { underruns += 1; target = Math.min(0.4, target + 0.06); }
        playhead = now + target; // colchón al empezar o tras un corte
      } else if (playhead > now + 1.2) {
        playhead = now + target; // se acumuló demasiado retraso: se recorta
      }
      node.start(playhead);
      playhead += buffer.duration;
    },
    reset() { playhead = 0; },
    stats() { return { target, underruns }; },
  };
}

/** Sonido corto de aviso (alguien empezó a hablar / te dieron el turno). */
export function beep(context, frequency = 880, duration = 0.12, output = context.destination) {
  try {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(0.0001, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.25, context.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + duration);
    oscillator.connect(gain); gain.connect(output);
    oscillator.start(); oscillator.stop(context.currentTime + duration + 0.02);
  } catch (error) { /* sin audio disponible */ }
}

/** Salida del radio: volumen (hasta 200 %, con compresor para no distorsionar),
 * medidor de nivel y un <audio> real como salida. El <audio> (medio) suena con
 * el volumen de medios por la bocina y no lo silencia el interruptor de
 * silencio del iPhone (Web Audio directo sí); en Android sigue sonando en
 * segundo plano mientras el sistema lo permita. */
export function createOutput(context) {
  const gain = context.createGain();
  const compressor = context.createDynamicsCompressor();
  compressor.threshold.value = -12; compressor.knee.value = 6; compressor.ratio.value = 6; compressor.attack.value = 0.003; compressor.release.value = 0.15;
  const analyser = context.createAnalyser();
  analyser.fftSize = 512;
  gain.connect(compressor); compressor.connect(analyser);
  const samples = new Float32Array(analyser.fftSize);
  let element = null;
  const direct = () => { try { analyser.disconnect(); } catch (error) { /* nada */ } analyser.connect(context.destination); element = null; };
  try {
    if (!context.createMediaStreamDestination) throw new Error('sin MediaStreamDestination');
    const destination = context.createMediaStreamDestination();
    analyser.connect(destination);
    element = new Audio();
    element.setAttribute('playsinline', ''); element.autoplay = true;
    element.srcObject = destination.stream;
  } catch (error) { radioLog('OUT_NO_STREAM_DEST', error?.message); direct(); }
  return {
    node: gain,
    get mode() { return element ? 'media' : 'webaudio'; },
    // Debe llamarse dentro de un toque del usuario la primera vez.
    async start() {
      if (!element) return true;
      try { await element.play(); return true; } catch (error) {
        radioLog('OUT_MEDIA_PLAY_FAIL', error?.name);
        direct(); return false; // Sin <audio> (bloqueado): directo a los parlantes.
      }
    },
    resume() { if (element && element.paused) element.play().catch((error) => radioLog('OUT_MEDIA_RESUME_FAIL', error?.name)); },
    setVolume(value) { gain.gain.setTargetAtTime(Math.max(0, Math.min(2, value)), context.currentTime, 0.02); },
    level() { analyser.getFloatTimeDomainData(samples); return rms(samples); },
    close() { try { element?.pause(); if (element) element.srcObject = null; } catch (error) { /* nada */ } },
  };
}

/** «Probar bocina»: tres tonos por la misma salida del radio. */
export function speakerTest(context, output) {
  [440, 554, 659].forEach((frequency, index) => {
    const at = context.currentTime + index * 0.28;
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = 'triangle'; oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(0.5, at + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.25);
    oscillator.connect(gain); gain.connect(output);
    oscillator.start(at); oscillator.stop(at + 0.27);
  });
}

/** Mensaje de voz: WAV PCM16 16 kHz (se reproduce igual en iPhone y Android). */
export function encodeWav(chunks) {
  const total = chunks.reduce((sum, chunk) => sum + chunk.byteLength, 0);
  const buffer = new ArrayBuffer(44 + total);
  const view = new DataView(buffer);
  const write = (offset, text) => { for (let index = 0; index < text.length; index += 1) view.setUint8(offset + index, text.charCodeAt(index)); };
  write(0, 'RIFF'); view.setUint32(4, 36 + total, true); write(8, 'WAVE'); write(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, RADIO_RATE, true); view.setUint32(28, RADIO_RATE * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  write(36, 'data'); view.setUint32(40, total, true);
  let offset = 44;
  chunks.forEach((chunk) => { new Uint8Array(buffer, offset, chunk.byteLength).set(new Uint8Array(chunk)); offset += chunk.byteLength; });
  return new Blob([buffer], { type: 'audio/wav' });
}
