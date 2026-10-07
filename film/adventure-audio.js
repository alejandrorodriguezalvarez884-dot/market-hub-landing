// The score of the adventure cut, synthesised: nothing in it is a recording. A band plays to the
// plan in adventure.js (128 beats a minute, a chord a bar): drums, a bass, a fast figure of short
// notes, held chords and, from My Hub on, a tune. It grows part by part, climbs before the end and
// lands on the logo. Over it the picture still plays its own notes (EVENTS), now on the beat.

import { BAR, BARS, BEAT, DURATION, EVENTS, HARMONY, HITS, PARTS, at, drive, kick } from "./adventure.js";

export const RATE = 48000;

const hz = (midi) => 440 * 2 ** ((midi - 69) / 12);
// F major pentatonic from F4, as in the first score: the picture's notes sit well over every chord.
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

// The tune: [bar, beat, note, length in beats]. It enters with My Hub and climbs through the tools.
const TUNE = [
  [16, 1, 72, 1.5], [16, 2.5, 77, 0.5], [16, 3, 81, 2],
  [17, 1, 79, 1.5], [17, 2.5, 76, 0.5], [17, 3, 72, 2],
  [18, 1, 74, 1.5], [18, 2.5, 77, 0.5], [18, 3, 81, 1], [18, 4, 79, 1],
  [19, 1, 77, 2], [19, 3, 74, 1], [19, 4, 70, 1],
  [20, 1, 72, 1.5], [20, 2.5, 77, 0.5], [20, 3, 81, 1], [20, 4, 84, 1],
  [21, 1, 79, 2], [21, 3, 76, 1], [21, 4, 79, 1],
  [22, 1, 81, 1.5], [22, 2.5, 77, 0.5], [22, 3, 74, 2],
  [23, 1, 82, 1.5], [23, 2.5, 77, 0.5], [23, 3, 74, 2],
  [24, 1, 81, 1.5], [24, 2.5, 84, 0.5], [24, 3, 77, 1], [24, 4, 81, 1],
  [25, 1, 79, 2], [25, 3, 76, 1], [25, 4, 72, 1],
  [26, 1, 74, 1], [26, 2, 77, 1], [26, 3, 82, 1], [26, 4, 86, 1],
  [27, 1, 76, 1], [27, 2, 79, 1], [27, 3, 84, 1], [27, 4, 88, 1],
];

// `parts` leaves the band or the picture's notes out, to weigh one against the other.
export async function score(parts = { pad: true, played: true }) {
  const ac = new OfflineAudioContext(2, RATE * DURATION, RATE);

  // Everything meets here: a compressor, then the fades at both ends.
  const out = ac.createGain();
  out.gain.setValueAtTime(0, 0);
  out.gain.linearRampToValueAtTime(1, 0.3);
  out.gain.setValueAtTime(1, DURATION - 1.6);
  out.gain.linearRampToValueAtTime(0, DURATION - 0.05);
  const squeeze = ac.createDynamicsCompressor();
  squeeze.threshold.value = -13;
  squeeze.knee.value = 8;
  squeeze.ratio.value = 4;
  squeeze.attack.value = 0.004;
  squeeze.release.value = 0.18;
  const mix = ac.createGain();
  mix.connect(squeeze).connect(out).connect(ac.destination);

  // A room (a made-up impulse: hiss that dies away) and an echo in time with the beat.
  const room = ac.createConvolver();
  const impulse = ac.createBuffer(2, RATE * 2.2, RATE);
  for (let ch = 0; ch < 2; ch++) {
    const hiss = noise(11 + ch, 2.2), data = impulse.getChannelData(ch);
    for (let i = 0; i < data.length; i++) data[i] = hiss[i] * (1 - i / data.length) ** 3.4;
  }
  room.buffer = impulse;
  const roomOut = ac.createGain();
  roomOut.gain.value = 0.2;
  room.connect(roomOut).connect(mix);
  const echo = ac.createDelay(1);
  echo.delayTime.value = BEAT * 0.75;
  const echoTone = ac.createBiquadFilter();
  echoTone.type = "lowpass";
  echoTone.frequency.value = 2600;
  const again = ac.createGain();
  again.gain.value = 0.3;
  const echoOut = ac.createGain();
  echoOut.gain.value = 0.24;
  echo.connect(echoTone).connect(again).connect(echo);
  echoTone.connect(echoOut).connect(mix);

  // The band's notes go through one fader, which dips on every kick and comes back: the pumping
  // that makes a beat push forward. The drums and the picture's notes do not dip.
  const band = ac.createGain();
  band.gain.setValueAtTime(1, 0);
  band.connect(mix);
  const kit = ac.createGain();
  kit.connect(mix);

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

  // --- The drums ---------------------------------------------------------------------------------
  const drums = {
    kick(t, gain = 1) {
      const osc = tone("sine", 165, t, 0.4);
      osc.frequency.setValueAtTime(165, t);
      osc.frequency.exponentialRampToValueAtTime(48, t + 0.11);
      osc.connect(struck(t, 0.6 * gain, 0.3)).connect(kit);
      hissAt(t, 0.03).connect(filter("highpass", 2500)).connect(struck(t, 0.22 * gain, 0.02, 0.001)).connect(kit);
      band.gain.setValueAtTime(1 - 0.5 * gain, t);
      band.gain.linearRampToValueAtTime(1, t + 0.22);
    },
    snare(t, gain = 1) {
      const body = tone("triangle", 210, t, 0.15);
      body.frequency.exponentialRampToValueAtTime(150, t + 0.09);
      body.connect(struck(t, 0.26 * gain, 0.11)).connect(kit);
      const crack = struck(t, 0.75 * gain, 0.19, 0.002);
      hissAt(t, 0.25).connect(filter("bandpass", 2400, 0.5)).connect(crack);
      crack.connect(kit);
      crack.connect(room);
    },
    hat(t, gain = 1, open = false) {
      const p = placed(0.25);
      hissAt(t, open ? 0.3 : 0.08).connect(filter("highpass", 7000)).connect(struck(t, 0.42 * gain, open ? 0.24 : 0.05, 0.001)).connect(p);
      p.connect(kit);
    },
    tom(t, frequency, gain = 1, pan = 0) {
      const osc = tone("sine", frequency, t, 0.5);
      osc.frequency.exponentialRampToValueAtTime(frequency * 0.6, t + 0.24);
      const p = placed(pan);
      osc.connect(struck(t, 0.5 * gain, 0.4)).connect(p);
      hissAt(t, 0.06).connect(filter("lowpass", 500)).connect(struck(t, 0.3 * gain, 0.05, 0.001)).connect(p);
      p.connect(kit);
      p.connect(room);
    },
    // A part landing: a low boom and a long crash.
    land(t, weight = 1) {
      const boom = tone("sine", 70, t, 1.8);
      boom.frequency.exponentialRampToValueAtTime(32, t + 0.9);
      boom.connect(struck(t, 0.42 * weight, 1.3, 0.004)).connect(kit);
      const crash = struck(t, 0.5 * weight, 2.2, 0.002);
      hissAt(t, 2.4).connect(filter("highpass", 3500)).connect(crash);
      crash.connect(kit);
      crash.connect(room);
    },
    // Air rising into a landing.
    rise(from, to, weight = 1) {
      const sweep = filter("bandpass", 300, 1.2);
      sweep.frequency.setValueAtTime(300, from);
      sweep.frequency.exponentialRampToValueAtTime(9000, to);
      const g = ac.createGain();
      g.gain.setValueAtTime(0, from);
      g.gain.linearRampToValueAtTime(0.3 * weight, to - 0.02);
      g.gain.linearRampToValueAtTime(0, to + 0.02);
      hissAt(from, to - from + 0.1).connect(sweep).connect(g);
      g.connect(kit);
      g.connect(room);
    },
  };

  // --- The band ------------------------------------------------------------------------------------
  const players = {
    // The bass: a short note, low and round.
    bass(t, midi, length, gain = 1) {
      const cut = filter("lowpass", 1500, 2);
      cut.frequency.setValueAtTime(1500, t);
      cut.frequency.exponentialRampToValueAtTime(220, t + Math.min(length, 0.3));
      const g = ac.createGain();
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.17 * gain, t + 0.006);
      g.gain.setValueAtTime(0.17 * gain, t + length * 0.7);
      g.gain.linearRampToValueAtTime(0, t + length);
      tone("sawtooth", hz(midi), t, length + 0.05).connect(cut).connect(g);
      const under = ac.createGain();
      under.gain.value = 0.8;
      tone("sine", hz(midi), t, length + 0.05).connect(under).connect(g);
      g.connect(band);
    },
    // The running figure: a short bowed note, as a string section plays them in a chase.
    run(t, midi, gain = 1, bright = 0.5, pan = 0) {
      const cut = filter("lowpass", 1800 + 4200 * bright, 0.8);
      const g = struck(t, 0.2 * gain, 0.2, 0.006);
      for (const detune of [-7, 7]) tone("sawtooth", hz(midi), t, 0.24, detune).connect(cut);
      const p = placed(pan);
      cut.connect(g).connect(p);
      p.connect(band);
      p.connect(room);
    },
    // A held chord: many detuned saws behind a filter that opens as the film grows.
    hold(t, notes, length, level = 1, bright = 0.5, attack = 0.1) {
      const cut = filter("lowpass", 700 + 4200 * bright ** 1.5, 0.5);
      const g = ac.createGain();
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(level, t + attack);
      g.gain.setValueAtTime(level, t + Math.max(attack, length - 0.06));
      g.gain.linearRampToValueAtTime(0, t + length + 0.25);
      notes.forEach((midi, n) => {
        for (const detune of [-9 - n, 9 + n]) {
          const each = ac.createGain();
          each.gain.value = 0.034;
          tone("sawtooth", hz(midi), t, length + 0.3, detune).connect(each).connect(cut);
        }
      });
      cut.connect(g);
      g.connect(band);
      g.connect(room);
    },
    // The chord struck hard where a part lands, like brass.
    blast(t, notes, weight = 1) {
      const cut = filter("lowpass", 5200, 0.6);
      cut.frequency.setValueAtTime(5200, t);
      cut.frequency.exponentialRampToValueAtTime(1100, t + 1.1);
      const g = struck(t, 0.3 * weight, 1.5, 0.012);
      for (const midi of [...notes, notes[0] + 12]) for (const detune of [-6, 6]) tone("sawtooth", hz(midi), t, 1.6, detune).connect(cut);
      cut.connect(g);
      g.connect(band);
      g.connect(room);
    },
    // The tune: one clear voice, with a little vibrato once a note is held.
    sing(t, midi, length, gain = 1) {
      const cut = filter("lowpass", 5200, 0.6);
      const g = ac.createGain();
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(0.36 * gain, t + 0.02);
      g.gain.setValueAtTime(0.31 * gain, t + Math.max(0.03, length - 0.08));
      g.gain.linearRampToValueAtTime(0, t + length + 0.06);
      const wobble = tone("sine", 5.5, t, length + 0.1);
      const depth = ac.createGain();
      depth.gain.setValueAtTime(0, t);
      depth.gain.linearRampToValueAtTime(0, t + 0.18);
      depth.gain.linearRampToValueAtTime(7, t + 0.4);
      wobble.connect(depth);
      for (const [type, level] of [["sawtooth", 0.55], ["triangle", 0.6]]) {
        const osc = tone(type, hz(midi), t, length + 0.1);
        depth.connect(osc.detune);
        const each = ac.createGain();
        each.gain.value = level;
        osc.connect(each).connect(cut);
      }
      const p = placed(0.1);
      cut.connect(g).connect(p);
      p.connect(band);
      p.connect(echo);
      p.connect(room);
    },
  };

  if (parts.pad) {
    for (let bar = 0; bar < BARS; bar++) {
      const { bass, notes } = HARMONY[bar];
      const [low, mid, high] = notes;
      const d = drive(bar);
      const on = (beat) => at(bar, beat);

      // Drums.
      for (const beat of kick(bar)) drums.kick(on(beat), bar < 4 ? 0.55 : bar >= 28 ? 0.8 : 1);
      if (bar >= 4 && bar < 8) drums.snare(on(3), 0.9);
      if (bar >= 8 && bar < 27) for (const beat of [2, 4]) drums.snare(on(beat), bar === 26 ? 0.7 : 1);
      if (bar === 26) for (let i = 0; i < 4; i++) drums.snare(on(1.5 + i), 0.3 + i * 0.08);  // the climb begins between the beats
      if (bar === 27) {  // the roll: sixteenths growing, then twice as fast into the landing
        for (let i = 0; i < 12; i++) drums.snare(on(1 + i / 4), 0.3 + i * 0.035);
        for (let i = 0; i < 8; i++) drums.snare(on(4 + i / 8), 0.72 + i * 0.03);
      }
      if (bar >= 2 && bar < 4) for (let i = 0; i < 8; i++) drums.hat(on(1 + i / 2), 0.25 + (bar - 2) * 0.2 + i * 0.02);
      if (bar >= 4 && bar < 22) for (let i = 0; i < 8; i++) drums.hat(on(1 + i / 2), i % 2 ? 1 : 0.55, bar >= 8 && bar % 2 === 1 && i === 7);
      if (bar >= 22 && bar < 27) for (let i = 0; i < 16; i++) drums.hat(on(1 + i / 4), [0.6, 0.35, 1, 0.35][i % 4]);
      if (bar === 15) [[3, 150], [3.5, 150], [4, 120], [4.25, 120], [4.5, 95], [4.75, 95]].forEach(([beat, f], i) => drums.tom(on(beat), f, 0.8 + i * 0.04, -0.4 + i * 0.16));
      if (bar === 21) [[4, 150], [4.25, 130], [4.5, 110], [4.75, 95]].forEach(([beat, f], i) => drums.tom(on(beat), f, 0.85 + i * 0.05, -0.3 + i * 0.2));
      if (bar === 28) [[2, 95], [3, 95], [4, 110], [4.5, 130]].forEach(([beat, f], i) => drums.tom(on(beat), f, 0.8 + i * 0.07, 0));

      // Bass: one long note while the pulse gathers, then eighths.
      if (bar >= 2 && bar < 4) players.bass(on(1), bass, BAR, 0.6);
      if (bar >= 4 && bar < 28) for (let i = 0; i < 8; i++) players.bass(on(1 + i / 2), bass + (bar === 27 && i >= 4 ? 12 : 0), BEAT / 2 - 0.02, (i % 2 ? 1 : 0.8) * (bar < 8 ? 0.85 : 1));
      if (bar === 28) players.bass(on(1), 34, 2 * BEAT, 0.9), players.bass(on(3), 36, 2 * BEAT, 0.9);
      if (bar === 29) players.bass(on(1), 29, 2.6 * BAR, 0.9), players.bass(on(1), 41, 2.6 * BAR, 0.6);

      // The running figure: quarters, then eighths, then sixteenths, brighter as the film grows.
      const top = low + 12;
      if (bar === 1) [low, high, top, high].forEach((midi, i) => players.run(on(1 + i), midi, 0.7, 0.1, -0.3));
      if (bar >= 2 && bar < 8) [low, high, top, high, mid + 12, high, top, high].forEach((midi, i) => players.run(on(1 + i / 2), midi, bar < 4 ? 0.8 : 1, 0.15 + d * 0.4, i % 2 ? 0.35 : -0.35));
      if (bar >= 8 && bar < 28) {
        const up = bar >= 16 ? 12 : 0;
        [low, top, high, top, mid, top, high, top, low, top, high, top, mid + 12, top, high, top].forEach((midi, i) =>
          players.run(on(1 + i / 4), midi + (up && i % 4 === 0 ? up : 0), (i % 4 === 0 ? 1 : 0.7) * (bar >= 26 ? 1.15 : 1), 0.3 + d * 0.5 + (bar === 27 ? i / 40 : 0), i % 2 ? 0.4 : -0.4));
      }

      // Held chords under it all, and the chord struck where a part lands.
      if (bar === 28) players.hold(on(1), [58, 62, 65, 70], 2 * BEAT, 0.9, 0.6), players.hold(on(3), [60, 64, 67, 72], 2 * BEAT, 1, 0.75);
      else if (bar === 29) players.hold(on(1), [53, 60, 65, 69, 72, 79], DURATION - on(1) - 0.5, 1.1, 0.8, 0.02);
      else if (bar < 28) players.hold(on(1), [...notes, bar >= 16 ? top : mid], BAR, 0.5 + d * 0.5, d * 0.7, bar < 4 ? 0.7 : 0.08);
    }
    for (const [bar, weight] of HITS) {
      drums.land(at(bar), weight);
      players.blast(at(bar), bar === 29 ? [65, 69, 72] : HARMONY[bar].notes, weight);
    }
    // The air rises into each landing: longest into the last.
    drums.rise(at(3), at(4), 0.8);
    drums.rise(at(7, 3), at(8), 0.9);
    drums.rise(at(11, 3), at(12), 0.6);
    drums.rise(at(15), at(16), 1);
    drums.rise(at(21), at(22), 0.9);
    drums.rise(at(26), at(28), 1.2);
    drums.rise(at(28, 2), at(29), 1.1);
    for (const [bar, beat, midi, length] of TUNE) players.sing(at(bar, beat), midi, length * BEAT, bar >= 22 ? 1 : 0.9);
    // The tune ends on the chord the film has been heading for.
    [77, 81, 84].forEach((midi, i) => players.sing(at(PARTS.name), midi, 3.5 * BEAT, 0.8 - i * 0.1));
  }

  // --- What the picture plays ----------------------------------------------------------------------
  const voices = {
    // A bell: the sound of a mark landing.
    pluck({ t, step, gain = 1, pan = 0 }) {
      const f = stepHz(step);
      const env = struck(t, 0.5 * gain, 0.9, 0.004);
      const cut = filter("lowpass", 6000);
      cut.frequency.setValueAtTime(6000, t);
      cut.frequency.exponentialRampToValueAtTime(1500, t + 0.5);
      for (const [mult, level, type] of [[1, 1, "triangle"], [2, 0.3, "sine"], [3, 0.1, "sine"], [4.2, 0.05, "sine"]]) {
        const g = ac.createGain();
        g.gain.value = level;
        tone(type, f * mult, t, 1).connect(g).connect(env);
      }
      const p = placed(pan);
      env.connect(cut).connect(p);
      p.connect(mix);
      p.connect(echo);
      p.connect(room);
    },
    // A word, a key, a line of text: a short dry tap.
    tick({ t, gain = 1, pan = 0 }) {
      const p = placed(pan);
      hissAt(t, 0.06).connect(filter("bandpass", 2400, 1.4)).connect(struck(t, 0.3 * gain, 0.05, 0.002)).connect(p);
      p.connect(mix);
      p.connect(room);
    },
    // The dot travelling: air, rising and falling.
    whoosh({ t, length = 0.9 }) {
      const sweep = filter("bandpass", 260, 0.9);
      sweep.frequency.setValueAtTime(260, t);
      sweep.frequency.exponentialRampToValueAtTime(2600, t + length * 0.55);
      sweep.frequency.exponentialRampToValueAtTime(500, t + length);
      const env = ac.createGain();
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(0.24, t + length * 0.5);
      env.gain.linearRampToValueAtTime(0, t + length);
      hissAt(t, length).connect(sweep).connect(env);
      env.connect(mix);
      env.connect(room);
    },
    // The dot sliding along its line: one note bent from where it was to where it lands.
    glide({ t, from, to, length = 0.8 }) {
      const env = ac.createGain();
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(0.07, t + 0.08);
      env.gain.setValueAtTime(0.07, t + Math.max(0.09, length - 0.1));
      env.gain.linearRampToValueAtTime(0, t + length + 0.25);
      for (const [mult, level, type] of [[0.5, 1, "sine"], [1, 0.3, "triangle"]]) {
        const osc = tone(type, stepHz(from) * mult, t, length + 0.3);
        osc.frequency.setValueAtTime(stepHz(from) * mult, t);
        osc.frequency.exponentialRampToValueAtTime(stepHz(to) * mult, t + length);
        const g = ac.createGain();
        g.gain.value = level;
        osc.connect(g).connect(env);
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
        const osc = tone(type, f0, t, length + 0.6);
        osc.frequency.setValueAtTime(f0, t);
        osc.frequency.exponentialRampToValueAtTime(f1, t + length);
        const g = ac.createGain();
        g.gain.value = level;
        osc.connect(g).connect(env);
      }
      env.connect(mix);
    },
    // Reading, counting: a thin bright air that comes and goes.
    shimmer({ t, length }) {
      const env = ac.createGain();
      env.gain.setValueAtTime(0, t);
      env.gain.linearRampToValueAtTime(0.03, t + 0.5);
      env.gain.setValueAtTime(0.03, t + Math.max(0.6, length - 0.5));
      env.gain.linearRampToValueAtTime(0, t + Math.max(0.7, length));
      hissAt(t, length).connect(filter("highpass", 6500)).connect(env);
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

// Where the sound sits, to check a render without ears: the loudness of the whole, of its low end
// (the kick and the bass) and of its top (the hats, the air), bar by bar, in dB.
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
