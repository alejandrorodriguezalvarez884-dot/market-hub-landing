// The score of the progress cut, synthesised: nothing in it is a recording. It is low, slow and
// wide, and it never stops moving forward: low strings bow a steady pulse, the bass climbs a step
// with every change of chord (progress.js), a great drum marks the bars, and the orchestra grows
// part by part until the horns take a tune and bring it home on the logo. The picture's own notes
// (EVENTS) are low too: a plucked string where the first score had a bell.

import { BAR, BARS, BEAT, DURATION, EVENTS, HARMONY, HITS, PARTS, at, drive, drum } from "./progress.js";

export const RATE = 48000;

const hz = (midi) => 440 * 2 ** ((midi - 69) / 12);
// F major pentatonic, two octaves under the first score's: from F2. It sits well over every chord.
const STEPS = [41, 43, 45, 48, 50, 53, 55, 57, 60, 62];
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

// The tune: [bar, beat, note, length in beats, level]. The cellos first, under the news; then the
// horns, from My Hub to the end, each phrase a little higher than the last.
const TUNE = [
  [12, 1, 57, 4, 0.6], [13, 1, 53, 2, 0.6], [13, 3, 57, 2, 0.6], [14, 1, 60, 4, 0.6], [15, 1, 57, 2, 0.6], [15, 3, 60, 2, 0.6],
  [16, 1, 62, 4, 1], [17, 1, 65, 2, 1], [17, 3, 62, 2, 1], [18, 1, 64, 4, 1], [19, 1, 67, 2, 1], [19, 3, 64, 2, 1],
  [20, 1, 65, 3, 1], [20, 4, 69, 1, 1], [21, 1, 67, 4, 1],
  [22, 1, 69, 4, 1], [23, 1, 65, 2, 1], [23, 3, 62, 2, 1], [24, 1, 69, 2, 1], [24, 3, 72, 2, 1], [25, 1, 69, 4, 1],
  [26, 1, 70, 2, 1.05], [26, 3, 74, 2, 1.05], [27, 1, 72, 2, 1.1], [27, 3, 76, 2, 1.1], [28, 1, 67, 2, 1], [28, 3, 72, 2, 1.1],
];

// `parts` leaves the orchestra or the picture's notes out, to weigh one against the other.
export async function score(parts = { pad: true, played: true }) {
  const ac = new OfflineAudioContext(2, RATE * DURATION, RATE);

  // Everything meets here: a gentle compressor, then the fades at both ends.
  const out = ac.createGain();
  out.gain.setValueAtTime(0, 0);
  out.gain.linearRampToValueAtTime(1, 0.4);
  out.gain.setValueAtTime(1, DURATION - 1.8);
  out.gain.linearRampToValueAtTime(0, DURATION - 0.05);
  const squeeze = ac.createDynamicsCompressor();
  squeeze.threshold.value = -16;
  squeeze.knee.value = 10;
  squeeze.ratio.value = 2.5;
  squeeze.attack.value = 0.02;
  squeeze.release.value = 0.4;
  const mix = ac.createGain();
  mix.connect(squeeze).connect(out).connect(ac.destination);

  // A hall (a made-up impulse: hiss that dies away slowly): this music wants a large room.
  const hall = ac.createConvolver();
  const impulse = ac.createBuffer(2, RATE * 3.6, RATE);
  for (let ch = 0; ch < 2; ch++) {
    const hiss = noise(11 + ch, 3.6), data = impulse.getChannelData(ch);
    for (let i = 0; i < data.length; i++) data[i] = hiss[i] * (1 - i / data.length) ** 2.8;
  }
  hall.buffer = impulse;
  const hallTone = ac.createBiquadFilter();  // a dark room: the hiss of the top is taken off
  hallTone.type = "lowpass";
  hallTone.frequency.value = 3200;
  const hallOut = ac.createGain();
  hallOut.gain.value = 0.3;
  hall.connect(hallTone).connect(hallOut).connect(mix);

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
  // A gain that jumps to `level` at `t` and dies away over `length`.
  const struck = (t, level, length, attack = 0.003) => {
    const g = ac.createGain();
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(level, t + attack);
    g.gain.exponentialRampToValueAtTime(0.0004, t + length);
    return g;
  };
  // A gain that rises to `level`, holds it and lets go: a held note.
  const held = (t, level, length, attack, release) => {
    const g = ac.createGain();
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(level, t + attack);
    g.gain.setValueAtTime(level, t + Math.max(attack, length));
    g.gain.linearRampToValueAtTime(0, t + Math.max(attack, length) + release);
    return g;
  };
  const filter = (type, frequency, q = 0.7) => {
    const f = ac.createBiquadFilter();
    f.type = type;
    f.frequency.value = frequency;
    f.Q.value = q;
    return f;
  };
  const tone = (type, frequency, t, length, detune = 0) => {
    const osc = ac.createOscillator();
    osc.type = type;
    osc.frequency.value = frequency;
    osc.detune.value = detune;
    osc.start(t);
    osc.stop(t + length);
    return osc;
  };
  const both = (node, send = 1) => {
    node.connect(mix);
    const g = ac.createGain();
    g.gain.value = send;
    node.connect(g).connect(hall);
  };

  // --- The orchestra -------------------------------------------------------------------------------
  const play = {
    // The pulse: a short stroke of the bow on a low string.
    bow(t, midi, gain = 1, bright = 0.5, pan = 0) {
      const cut = filter("lowpass", 450 + 1500 * bright, 0.8);
      const g = ac.createGain();
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.16 * gain, t + 0.03);
      g.gain.exponentialRampToValueAtTime(0.045 * gain, t + 0.26);
      g.gain.linearRampToValueAtTime(0, t + 0.42);
      for (const detune of [-8, 0, 8]) tone("sawtooth", hz(midi), t, 0.45, detune).connect(cut);
      const p = placed(pan);
      cut.connect(g).connect(p);
      both(p, 0.8);
    },
    // Held strings: many detuned saws behind a filter that opens as the film grows.
    strings(t, notes, length, level = 1, bright = 0.5, attack = 0.5) {
      const cut = filter("lowpass", 380 + 2000 * bright ** 1.5, 0.5);
      const g = held(t, level, length, attack, 0.7);
      notes.forEach((midi, n) => {
        for (const detune of [-9 - n, 9 + n]) {
          const each = ac.createGain();
          each.gain.value = 0.042;
          tone("sawtooth", hz(midi), t, length + attack + 0.8, detune).connect(each).connect(cut);
        }
      });
      cut.connect(g);
      both(g, 1);
    },
    // The bass under everything: round, and held for as long as the chord is.
    bass(t, midi, length, level = 1) {
      const g = held(t, 0.13 * level, length, 0.08, 0.45);
      tone("sine", hz(midi), t, length + 0.6).connect(g);
      const edge = ac.createGain();
      edge.gain.value = 0.7;
      tone("sawtooth", hz(midi), t, length + 0.6).connect(filter("lowpass", 520, 0.7)).connect(edge).connect(g);
      g.connect(mix);
    },
    // A low note of the piano where the chord changes, left to ring.
    piano(t, midi, gain = 1) {
      const cut = filter("lowpass", 2200, 0.5);
      cut.frequency.setValueAtTime(2200, t);
      cut.frequency.exponentialRampToValueAtTime(500, t + 1.4);
      for (const note of [midi - 12, midi]) {
        [[1, 1, 3.2], [2.003, 0.5, 2.4], [3.01, 0.28, 1.7], [4.02, 0.14, 1.2], [5.04, 0.07, 0.8]].forEach(([mult, level, length]) =>
          tone("sine", hz(note) * mult, t, length + 0.1).connect(struck(t, 0.21 * gain * level, length, 0.004)).connect(cut));
      }
      both(cut, 0.9);
    },
    // The tune: a horn, or a section of cellos when it is low. Round, with a slow attack.
    horn(t, midi, length, gain = 1) {
      const cut = filter("lowpass", 600, 0.7);
      cut.frequency.setValueAtTime(600, t);
      cut.frequency.linearRampToValueAtTime(1700, t + 0.14);
      cut.frequency.linearRampToValueAtTime(1150, t + 0.5);
      const g = held(t, 0.38 * gain, length - 0.1, 0.09, 0.3);
      const wobble = tone("sine", 5, t, length + 0.5);
      const depth = ac.createGain();
      depth.gain.value = 0;
      depth.gain.setValueAtTime(0, t + 0.3);
      depth.gain.linearRampToValueAtTime(5, t + 0.7);
      wobble.connect(depth);
      for (const [type, mult, level, detune] of [["sawtooth", 1, 0.6, -5], ["sawtooth", 1, 0.6, 5], ["sine", 0.5, 0.45, 0]]) {
        const osc = tone(type, hz(midi) * mult, t, length + 0.5, detune);
        depth.connect(osc.detune);
        const each = ac.createGain();
        each.gain.value = level;
        osc.connect(each).connect(cut);
      }
      cut.connect(g);
      both(g, 1.1);
    },
    // The brass, all together, where a part lands: it swells and falls away.
    brass(t, notes, weight = 1) {
      const cut = filter("lowpass", 700, 0.6);
      cut.frequency.setValueAtTime(700, t);
      cut.frequency.linearRampToValueAtTime(2400, t + 0.12);
      cut.frequency.exponentialRampToValueAtTime(800, t + 1.8);
      const g = ac.createGain();
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.2 * weight, t + 0.07);
      g.gain.exponentialRampToValueAtTime(0.0004, t + 2.4);
      for (const midi of notes) for (const detune of [-6, 6]) tone("sawtooth", hz(midi), t, 2.5, detune).connect(cut);
      cut.connect(g);
      both(g, 1);
    },
    // The great drum: deep, with the skin heard for a moment.
    drum(t, gain = 1) {
      const deep = tone("sine", 82, t, 0.9);
      deep.frequency.setValueAtTime(82, t);
      deep.frequency.exponentialRampToValueAtTime(44, t + 0.18);
      const skin = tone("triangle", 165, t, 0.3);
      skin.frequency.exponentialRampToValueAtTime(90, t + 0.12);
      const g = ac.createGain();
      g.gain.value = 1;
      deep.connect(struck(t, 0.5 * gain, 0.6, 0.004)).connect(g);
      skin.connect(struck(t, 0.3 * gain, 0.18, 0.003)).connect(g);
      hissAt(t, 0.1).connect(filter("lowpass", 320)).connect(struck(t, 0.4 * gain, 0.09, 0.002)).connect(g);
      both(g, 0.5);
    },
    // A roll on the kettledrum, growing into a landing.
    roll(from, to, weight = 1) {
      const strokes = Math.round((to - from) / (BEAT / 4));
      for (let i = 0; i < strokes; i++) {
        const t = from + (i * (to - from)) / strokes;
        const k = (i + 1) / strokes;
        const osc = tone("sine", 87, t, 0.4);
        osc.frequency.exponentialRampToValueAtTime(80, t + 0.2);
        const g = struck(t, weight * (0.06 + 0.4 * k * k), 0.3, 0.006);
        osc.connect(g);
        both(g, 0.7);
      }
    },
    // A cymbal: rising into a landing, and washing away after it.
    cymbal(from, to, weight = 1) {
      const g = ac.createGain();
      g.gain.setValueAtTime(0.0004, from);
      g.gain.exponentialRampToValueAtTime(0.09 * weight, to);
      g.gain.exponentialRampToValueAtTime(0.0004, to + 2.6);
      hissAt(from, to - from + 2.7).connect(filter("highpass", 2600, 0.5)).connect(filter("lowpass", 9000, 0.5)).connect(g);
      both(g, 0.8);
    },
    // A part landing: the drum, a boom under it, the piano's lowest note and the brass.
    land(t, notes, bass, weight = 1) {
      play.drum(t, 1.15 * weight);
      const boom = tone("sine", 58, t, 1.8);
      boom.frequency.exponentialRampToValueAtTime(31, t + 1);
      boom.connect(struck(t, 0.22 * weight, 1.3, 0.006)).connect(mix);
      play.piano(t, bass, 1.1 * weight);
      play.brass(t, notes, weight);
    },
  };

  if (parts.pad) {
    // One low note under the mark, from the first second.
    play.bass(0.3, 38, at(4) - 0.6, 0.55);
    play.strings(0.6, [50, 57], at(4) - 1.2, 0.5, 0.15, 3);

    for (let bar = 0; bar < BARS; bar++) {
      const chord = HARMONY[bar];
      const { bass, notes } = chord;
      const d = drive(bar);
      const on = (beat) => at(bar, beat);
      const changed = bar >= 4 && chord !== HARMONY[bar - 1];
      let bars = 1;  // how long this chord lasts
      while (bar + bars < BARS && HARMONY[bar + bars] === chord) bars++;

      if (bar === 4 || changed) {
        const length = bars * BAR - 0.15;
        if (bar < 29) {
          play.strings(on(1), notes, length, 0.45 + d * 0.55, d * 0.85, bar === 4 ? 0.8 : 0.35);
          play.bass(on(1), bass, length, 0.6 + d * 0.4);
          if (bass >= 41) play.bass(on(1), bass - 12, length, 0.5 + d * 0.3);
        }
        if (bar >= 6 && bar < 28 && !HITS.some(([b]) => b === bar)) play.piano(on(1), bass, 0.55 + d * 0.4);
      }

      // The pulse: the low strings bow every beat; later an octave under, then between the beats too.
      if (bar >= 1 && bar < 28) {
        const level = 0.3 + 0.7 * d;
        [0, 0, 7, 0].forEach((up, i) => play.bow(on(1 + i), bass + 12 + up, level * [1, 0.6, 0.8, 0.6][i], 0.15 + d * 0.6, i % 2 ? 0.3 : -0.3));
        if (bar >= 8) for (const beat of [1, 3]) play.bow(on(beat), bass, level * 0.8, 0.1 + d * 0.4, 0);
        if (bar >= 16) [7, 12, 7, 12].forEach((up, i) => play.bow(on(1.5 + i), bass + 12 + up, level * (bar >= 22 ? 0.6 : 0.42), 0.2 + d * 0.6, i % 2 ? -0.45 : 0.45));
        if (bar >= 22) for (const beat of [1, 2, 3, 4]) play.bow(on(beat), bass + 24, level * 0.45, 0.4 + d * 0.5, 0.15);
      }

      // The great drum.
      for (const beat of drum(bar)) if (!(beat === 1 && HITS.some(([b]) => b === bar))) play.drum(on(beat), (beat === 1 ? 1 : 0.6) * (0.45 + 0.55 * d));
    }

    for (const [bar, weight] of HITS) {
      const { bass, notes } = HARMONY[bar];
      play.land(at(bar), bar === 29 ? [53, 57, 60, 65, 69] : notes.map((n) => n + (bar >= 16 ? 12 : 0)), bass, weight);
    }
    // Into each landing: the cymbal rises, and from the middle of the film the kettledrum rolls.
    play.cymbal(at(3), at(4), 0.6);
    play.cymbal(at(7, 3), at(8), 0.8);
    play.cymbal(at(11, 3), at(12), 0.6);
    play.cymbal(at(15), at(16), 1);
    play.roll(at(15), at(16), 0.8);
    play.cymbal(at(21), at(22), 0.9);
    play.roll(at(21), at(22), 0.8);
    play.cymbal(at(26), at(28), 1.1);
    play.roll(at(26), at(28), 1);
    play.cymbal(at(28, 2), at(29), 1.2);
    play.roll(at(28), at(29), 1.15);

    for (const [bar, beat, midi, length, level] of TUNE) play.horn(at(bar, beat), midi, length * BEAT, level * (bar < 16 ? 1 : 0.5 + 0.5 * drive(bar)));

    // Home: the whole orchestra on F, held to the end, and two last strokes of the drum under the words.
    const home = at(PARTS.name);
    play.strings(home, [41, 48, 53, 57, 60, 65, 69, 72], DURATION - home - 1.2, 1.15, 0.85, 0.05);
    play.bass(home, 29, DURATION - home - 1, 1);
    play.bass(home, 41, DURATION - home - 1, 0.8);
    [65, 69, 72, 77].forEach((midi, i) => play.horn(home, midi, 4.6 * BEAT, 0.75 - i * 0.08));
    play.drum(at(30), 0.55);
    play.drum(at(30, 3), 0.4);
  }

  // --- What the picture plays ----------------------------------------------------------------------
  const voices = {
    // A low string, plucked: the sound of a mark landing.
    pluck({ t, step, gain = 1, pan = 0 }) {
      const f = stepHz(step);
      const env = struck(t, 0.42 * gain, 1.2, 0.006);
      const cut = filter("lowpass", 1500);
      cut.frequency.setValueAtTime(1500, t);
      cut.frequency.exponentialRampToValueAtTime(420, t + 0.7);
      for (const [mult, level, type] of [[1, 1, "triangle"], [2, 0.4, "sine"], [3, 0.14, "sine"]]) {
        const g = ac.createGain();
        g.gain.value = level;
        tone(type, f * mult, t, 1.3).connect(g).connect(env);
      }
      const p = placed(pan * 0.6);
      env.connect(cut).connect(p);
      both(p, 0.9);
    },
    // A word, a key, a line of text: a soft knock on wood.
    tick({ t, gain = 1, pan = 0 }) {
      const p = placed(pan * 0.6);
      hissAt(t, 0.08).connect(filter("bandpass", 650, 2.2)).connect(struck(t, 0.3 * gain, 0.07, 0.003)).connect(p);
      both(p, 0.6);
    },
    // The dot travelling: air, rising and falling, low.
    whoosh({ t, length = 0.9 }) {
      const sweep = filter("bandpass", 160, 0.9);
      sweep.frequency.setValueAtTime(160, t);
      sweep.frequency.exponentialRampToValueAtTime(1300, t + length * 0.55);
      sweep.frequency.exponentialRampToValueAtTime(300, t + length);
      const env = ac.createGain();
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(0.2, t + length * 0.5);
      env.gain.linearRampToValueAtTime(0, t + length);
      hissAt(t, length).connect(sweep).connect(env);
      both(env, 0.8);
    },
    // The dot sliding along its line: one low note bent from where it was to where it lands.
    glide({ t, from, to, length = 0.8 }) {
      const env = ac.createGain();
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(0.1, t + 0.08);
      env.gain.setValueAtTime(0.1, t + Math.max(0.09, length - 0.1));
      env.gain.linearRampToValueAtTime(0, t + length + 0.25);
      for (const [mult, level, type] of [[1, 1, "sine"], [2, 0.3, "triangle"]]) {
        const osc = tone(type, stepHz(from) * mult, t, length + 0.3);
        osc.frequency.setValueAtTime(stepHz(from) * mult, t);
        osc.frequency.exponentialRampToValueAtTime(stepHz(to) * mult, t + length);
        const g = ac.createGain();
        g.gain.value = level;
        osc.connect(g).connect(env);
      }
      both(env, 0.8);
    },
    // A line being drawn: a low note rising under it.
    swell({ t, length = 1.2 }) {
      const env = ac.createGain();
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(0.22, t + length * 0.7);
      env.gain.linearRampToValueAtTime(0, t + length + 0.5);
      for (const [f0, f1, level, type] of [[58, 87.3, 1, "sine"], [116, 174.6, 0.25, "triangle"]]) {
        const osc = tone(type, f0, t, length + 0.6);
        osc.frequency.setValueAtTime(f0, t);
        osc.frequency.exponentialRampToValueAtTime(f1, t + length);
        const g = ac.createGain();
        g.gain.value = level;
        osc.connect(g).connect(env);
      }
      env.connect(mix);
    },
    // Reading, counting: a breath of air, barely there.
    shimmer({ t, length }) {
      const env = ac.createGain();
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(0.012, t + 0.5);
      env.gain.setValueAtTime(0.012, t + Math.max(0.6, length - 0.5));
      env.gain.linearRampToValueAtTime(0, t + Math.max(0.7, length));
      hissAt(t, length).connect(filter("bandpass", 3000, 0.6)).connect(env);
      both(env, 1);
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

// Where the sound sits, to check a render without ears: the loudness of the whole, of its low end
// (the drum and the bass) and of its top (the cymbal, the air), bar by bar, in dB.
export function balance(buffer) {
  const [left, right] = [buffer.getChannelData(0), buffer.getChannelData(1)];
  const pole = (frequency) => 1 - Math.exp((-2 * Math.PI * frequency) / RATE);
  const [slow, fast] = [pole(150), pole(4000)];
  const sums = Array.from({ length: BARS }, () => [0, 0, 0, 0]);
  let l1 = 0, l2 = 0, h1 = 0, h2 = 0;
  for (let i = 0; i < left.length; i++) {
    const x = (left[i] + right[i]) / 2;
    l1 += slow * (x - l1);
    l2 += slow * (l1 - l2);  // twice over: a steeper slope
    h1 += fast * (x - h1);
    h2 += fast * (h1 - h2);
    const bar = Math.min(BARS - 1, Math.floor(i / RATE / BAR));
    sums[bar][0] += x * x;
    sums[bar][1] += l2 * l2;
    sums[bar][2] += (x - h2) * (x - h2);
    sums[bar][3]++;
  }
  const db = (k) => sums.map((s) => Math.round(10 * Math.log10(s[k] / s[3] + 1e-12) * 10) / 10);
  return { all: db(0), low: db(1), high: db(2) };
}
