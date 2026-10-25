// Audio del Radio (R1): captura del micrófono → PCM 16 kHz mono 16 bits en
// fragmentos de 40 ms, y reproducción en orden con un pequeño colchón.
// Sin librerías: Web Audio (AudioWorklet con respaldo ScriptProcessor).
// Se reproduce al ritmo del AudioContext (48/44,1 kHz) para que funcione igual
// en iPhone (Safari no acepta búferes de 16 kHz en todas las versiones).
export const RADIO_RATE = 16000;
const CHUNK = 640; // 40 ms a 16 kHz

const WORKLET = `class Tap extends AudioWorkletProcessor { process(inputs) { const ch = inputs[0] && inputs[0][0]; if (ch) this.port.postMessage(ch.slice(0)); return true; } }
registerProcessor('radio-tap', Tap);`;

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

export function createAudioContext() {
  const Context = window.AudioContext || window.webkitAudioContext;
  return new Context({ latencyHint: 'interactive' });
}

/** Micrófono abierto pero sin enviar hasta `setSending(true)` (mantener para hablar). */
export async function openMicrophone(context, onChunk) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
  const source = context.createMediaStreamSource(stream);
  let sending = false;
  let pending = new Float32Array(0);
  const push = (frame) => {
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
  let node;
  try {
    const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }));
    await context.audioWorklet.addModule(url);
    URL.revokeObjectURL(url);
    node = new AudioWorkletNode(context, 'radio-tap');
    node.port.onmessage = (event) => push(event.data);
  } catch (error) {
    node = context.createScriptProcessor(2048, 1, 1);
    node.onaudioprocess = (event) => push(event.inputBuffer.getChannelData(0));
  }
  const mute = context.createGain(); mute.gain.value = 0; // el nodo debe llegar al destino para procesar, sin oírse
  source.connect(node); node.connect(mute); mute.connect(context.destination);
  stream.getAudioTracks().forEach((track) => { track.enabled = false; });
  return {
    setSending(value) {
      sending = value; pending = new Float32Array(0);
      stream.getAudioTracks().forEach((track) => { track.enabled = value; });
    },
    close() { sending = false; try { source.disconnect(); node.disconnect(); } catch (error) { /* ya desconectado */ } stream.getTracks().forEach((track) => track.stop()); },
  };
}

/** Reproduce fragmentos PCM16 16 kHz en orden, con ~150 ms de colchón.
 * `output` = nodo de salida (volumen/silencio → <audio> real); por omisión, los parlantes. */
export function createPlayer(context, output = context.destination) {
  let playhead = 0;
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
      if (playhead < now + 0.03) playhead = now + 0.15; // colchón al empezar o tras un corte
      node.start(playhead);
      playhead += buffer.duration;
    },
    reset() { playhead = 0; },
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

/** Salida de audio para el radio global: volumen/silencio y, si se puede, un
 * <audio> real (Android Chrome sigue sonando con la app en segundo plano o la
 * pantalla apagada mientras haya un medio reproduciéndose). */
export function createOutput(context) {
  const gain = context.createGain();
  let element = null;
  try {
    if (!context.createMediaStreamDestination) throw new Error('sin MediaStreamDestination');
    const destination = context.createMediaStreamDestination();
    gain.connect(destination);
    element = new Audio();
    element.setAttribute('playsinline', ''); element.autoplay = true;
    element.srcObject = destination.stream;
  } catch (error) {
    gain.connect(context.destination);
    element = null;
  }
  return {
    node: gain,
    element,
    // Debe llamarse dentro de un toque del usuario la primera vez.
    async start() {
      if (!element) return true;
      try { await element.play(); return true; } catch (error) {
        // Sin <audio> (bloqueado): directo a los parlantes.
        try { gain.disconnect(); } catch (disconnectError) { /* nada */ }
        gain.connect(context.destination); element = null; return false;
      }
    },
    setVolume(value) { gain.gain.setTargetAtTime(Math.max(0, Math.min(1, value)), context.currentTime, 0.02); },
    close() { try { element?.pause(); if (element) element.srcObject = null; } catch (error) { /* nada */ } },
  };
}

export const isIOS = () => /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

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
