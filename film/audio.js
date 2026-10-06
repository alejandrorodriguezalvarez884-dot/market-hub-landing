// The soundtrack, synthesised: nothing in it is a recording. A slow pad carries the harmony
// (CHORDS in film.js) and everything else is played by the picture (EVENTS): a note when a row of
// the ruler lands, a glide when the dot slides, air when the dot travels between parts.

import { CHORDS, DURATION, EVENTS } from "./film.js";

export const RATE = 48000;

const hz = (midi) => 440 * 2 ** ((midi - 69) / 12);
// F major pentatonic from F4: any two of its notes sound well together, over every chord used.
const STEPS = [65, 67, 69, 72, 74, 77, 79, 81, 84, 86];
const stepHz = (step) => hz(STEPS[Math.min(STEPS.length - 1, Math.max(0, Math.round(step)))]);

function noise(seed, seconds) {
  let s = seed >>> 0;
  const data = new Float32Array(Math.floor(RATE * seconds));
  for (let i = 0; i < data.length; i++) {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;  // the same hiss in every render
    data[i] = s / 2147483648 - 1;
  }
  return data;
}

// `parts` leaves the pad or the played notes out, to weigh one against the other.
export async function score(parts = { pad: true, played: true }) {
  const ac = new OfflineAudioContext(2, RATE * DURATION, RATE);

  // Everything meets here: a gentle compressor, then the fades at both ends.
  const out = ac.createGain();
  out.gain.setValueAtTime(0, 0);
  out.gain.linearRampToValueAtTime(1, 0.4);
  out.gain.setValueAtTime(1, DURATION - 1.4);
  out.gain.linearRampToValueAtTime(0, DURATION - 0.05);
  const squeeze = ac.createDynamicsCompressor();
  squeeze.threshold.value = -16;
  squeeze.ratio.value = 3;
  squeeze.attack.value = 0.012;
  squeeze.release.value = 0.3;
  const mix = ac.createGain();
  mix.connect(squeeze).connect(out).connect(ac.destination);

  // A room (a made-up impulse: hiss that dies away) and an echo, for the notes to ring in.
  const room = ac.createConvolver();
  const impulse = ac.createBuffer(2, RATE * 2.8, RATE);
  for (let ch = 0; ch < 2; ch++) {
    const hiss = noise(11 + ch, 2.8), data = impulse.getChannelData(ch);
    for (let i = 0; i < data.length; i++) data[i] = hiss[i] * (1 - i / data.length) ** 3.2;
  }
  room.buffer = impulse;
  const roomOut = ac.createGain();
  roomOut.gain.value = 0.3;
  room.connect(roomOut).connect(mix);
  const echo = ac.createDelay(1);
  echo.delayTime.value = 0.36;
  const echoTone = ac.createBiquadFilter();
  echoTone.type = "lowpass";
  echoTone.frequency.value = 2200;
  const again = ac.createGain();
  again.gain.value = 0.3;
  const echoOut = ac.createGain();
  echoOut.gain.value = 0.26;
  echo.connect(echoTone).connect(again).connect(echo);
  echoTone.connect(echoOut).connect(mix);
  echoOut.connect(room);

  const hissBuffer = ac.createBuffer(1, RATE * 2, RATE);
  hissBuffer.copyToChannel(noise(5, 2), 0);
  const hissAt = (t, length) => {
    const src = ac.createBufferSource();
    src.buffer = hissBuffer;
    src.loop = true;
    src.start(t, (t * 0.37) % 1.5);
    src.stop(t + length + 0.1);
    return src;
  };
  const placed = (pan = 0) => {
    const p = ac.createStereoPanner();
    p.pan.value = Math.max(-1, Math.min(1, pan));
    return p;
  };

  // --- The pad ---------------------------------------------------------------------------------
  const warm = ac.createBiquadFilter();
  warm.type = "lowpass";
  warm.frequency.value = 760;
  warm.Q.value = 0.4;
  const drift = ac.createOscillator();  // the filter opens and closes, very slowly
  drift.frequency.value = 0.06;
  const depth = ac.createGain();
  depth.gain.value = 260;
  drift.connect(depth).connect(warm.frequency);
  drift.start(0);
  const padOut = ac.createGain();
  padOut.gain.value = 1;
  warm.connect(padOut).connect(mix);
  padOut.connect(room);
  (parts.pad ? CHORDS : []).forEach(([at, bass, notes], i) => {
    const until = i + 1 < CHORDS.length ? CHORDS[i + 1][0] : DURATION;
    const voice = (freq, type, level, detune, attack, to) => {
      const osc = ac.createOscillator();
      osc.type = type;
      osc.frequency.value = freq;
      osc.detune.value = detune;
      const g = ac.createGain();
      const start = Math.max(0, at - 0.4);
      g.gain.setValueAtTime(0, start);
      g.gain.linearRampToValueAtTime(level, start + attack);
      g.gain.setValueAtTime(level, until - 0.2);
      g.gain.linearRampToValueAtTime(0, until + 2.2);
      osc.connect(g).connect(to);
      osc.start(start);
      osc.stop(Math.min(DURATION, until + 2.3));
    };
    notes.forEach((midi, n) => {
      voice(hz(midi), "sawtooth", 0.011, -7 - n, 1.8, warm);
      voice(hz(midi), "sawtooth", 0.011, 8 + n, 1.8, warm);
    });
    voice(hz(bass), "sine", 0.06, 0, 0.6, mix);
    voice(hz(bass + 12), "triangle", 0.03, 0, 0.6, warm);
  });

  // --- What the picture plays ------------------------------------------------------------------
  const voices = {
    // A plucked note: the sound of a mark landing.
    pluck({ t, step, gain = 1, pan = 0 }) {
      const f = stepHz(step);
      const env = ac.createGain();
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(0.22 * gain, t + 0.005);
      env.gain.exponentialRampToValueAtTime(0.0004, t + 1.1);
      const tone = ac.createBiquadFilter();
      tone.type = "lowpass";
      tone.frequency.setValueAtTime(5200, t);
      tone.frequency.exponentialRampToValueAtTime(1200, t + 0.5);
      for (const [mult, level, type] of [[1, 1, "triangle"], [2, 0.22, "sine"], [3, 0.06, "sine"]]) {
        const osc = ac.createOscillator();
        osc.type = type;
        osc.frequency.value = f * mult;
        const g = ac.createGain();
        g.gain.value = level;
        osc.connect(g).connect(env);
        osc.start(t);
        osc.stop(t + 1.2);
      }
      const p = placed(pan);
      env.connect(tone).connect(p);
      p.connect(mix);
      p.connect(echo);
      p.connect(room);
    },
    // A word, a key, a line of text: a short dry tap.
    tick({ t, gain = 1, pan = 0 }) {
      const src = hissAt(t, 0.06);
      const band = ac.createBiquadFilter();
      band.type = "bandpass";
      band.frequency.value = 2400;
      band.Q.value = 1.4;
      const env = ac.createGain();
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(0.11 * gain, t + 0.002);
      env.gain.exponentialRampToValueAtTime(0.0004, t + 0.05);
      const p = placed(pan);
      src.connect(band).connect(env).connect(p);
      p.connect(mix);
      p.connect(room);
    },
    // The dot travelling: air, rising and falling.
    whoosh({ t, length = 0.9 }) {
      const src = hissAt(t, length);
      const band = ac.createBiquadFilter();
      band.type = "bandpass";
      band.Q.value = 0.9;
      band.frequency.setValueAtTime(260, t);
      band.frequency.exponentialRampToValueAtTime(2600, t + length * 0.55);
      band.frequency.exponentialRampToValueAtTime(500, t + length);
      const env = ac.createGain();
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(0.07, t + length * 0.5);
      env.gain.linearRampToValueAtTime(0, t + length);
      src.connect(band).connect(env);
      env.connect(mix);
      env.connect(room);
    },
    // The dot sliding along its line: one note bent from where it was to where it lands.
    glide({ t, from, to, length = 0.8 }) {
      const env = ac.createGain();
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(0.06, t + 0.08);
      env.gain.setValueAtTime(0.06, t + length - 0.1);
      env.gain.linearRampToValueAtTime(0, t + length + 0.25);
      for (const [mult, level, type] of [[0.5, 1, "sine"], [1, 0.3, "triangle"]]) {
        const osc = ac.createOscillator();
        osc.type = type;
        osc.frequency.setValueAtTime(stepHz(from) * mult, t);
        osc.frequency.exponentialRampToValueAtTime(stepHz(to) * mult, t + length);
        const g = ac.createGain();
        g.gain.value = level;
        osc.connect(g).connect(env);
        osc.start(t);
        osc.stop(t + length + 0.3);
      }
      env.connect(mix);
      env.connect(room);
    },
    // A line being drawn: a low note rising under it.
    swell({ t, length = 1.2 }) {
      const env = ac.createGain();
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(0.22, t + length * 0.7);
      env.gain.linearRampToValueAtTime(0, t + length + 0.5);
      for (const [f0, f1, level, type] of [[58, 87.3, 1, "sine"], [116, 174.6, 0.25, "triangle"]]) {
        const osc = ac.createOscillator();
        osc.type = type;
        osc.frequency.setValueAtTime(f0, t);
        osc.frequency.exponentialRampToValueAtTime(f1, t + length);
        const g = ac.createGain();
        g.gain.value = level;
        osc.connect(g).connect(env);
        osc.start(t);
        osc.stop(t + length + 0.6);
      }
      env.connect(mix);
    },
    // Reading, counting: a thin bright air that comes and goes.
    shimmer({ t, length }) {
      const src = hissAt(t, length);
      const high = ac.createBiquadFilter();
      high.type = "highpass";
      high.frequency.value = 6500;
      const env = ac.createGain();
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(0.03, t + 0.5);
      env.gain.setValueAtTime(0.03, t + length - 0.5);
      env.gain.linearRampToValueAtTime(0, t + length);
      src.connect(high).connect(env);
      env.connect(mix);
      env.connect(room);
    },
  };
  for (const event of parts.played ? EVENTS : []) voices[event.kind](event);

  const rendered = await ac.startRendering();
  // Bring the loudest sample to just under full scale.
  const channels = [rendered.getChannelData(0), rendered.getChannelData(1)];
  let peak = 0;
  for (const data of channels) for (let i = 0; i < data.length; i++) peak = Math.max(peak, Math.abs(data[i]));
  const k = parts.pad && parts.played && peak > 0 ? 0.89 / peak : 1;
  for (const data of channels) for (let i = 0; i < data.length; i++) data[i] *= k;
  return rendered;
}

// Loudness over time, to check a render without ears: RMS per second, in dB.
export function levels(buffer) {
  const [left, right] = [buffer.getChannelData(0), buffer.getChannelData(1)];
  const out = [];
  for (let s = 0; s < Math.floor(buffer.duration); s++) {
    let sum = 0;
    for (let i = s * RATE; i < (s + 1) * RATE; i++) sum += left[i] * left[i] + right[i] * right[i];
    out.push(Math.round(10 * Math.log10(sum / (2 * RATE) + 1e-12) * 10) / 10);
  }
  return out;
}
