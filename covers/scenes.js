// The places the news covers show: one per scope (a sector, or Macro). Each is built from plain
// solids on the stage (stage.js) and returns where the camera stands, for its two views. Nothing
// in them is a real place, a brand or a person.

import { pattern } from "./stage.js";

const PALETTE = [0x7a2f25, 0x23445c, 0x2f5143, 0x6b6257, 0x8a6a2d, 0x3b3f45];  // muted paints: rust, blue, green, grey, ochre, slate

// A lattice mast: four legs that lean in, tied by rings of struts.
function mast(s, x, z, height, foot, head, material, levels = 7) {
  const corner = (k, y) => { const w = foot + (head - foot) * (y / height); return [x + (k % 2 ? w : -w), y, z + (k > 1 ? w : -w)]; };
  for (let k = 0; k < 4; k++) s.beam(corner(k, 0), corner(k, height), 0.16, material);
  for (let i = 1; i <= levels; i++) {
    const y = (height * i) / levels, below = (height * (i - 1)) / levels;
    for (const [a, b] of [[0, 1], [1, 3], [3, 2], [2, 0]]) {
      s.beam(corner(a, y), corner(b, y), 0.09, material, 4);
      s.beam(corner(a, below), corner(b, y), 0.07, material, 4);
    }
  }
}

// What stands on the horizon, so that it is not a ruled line: the blocks of a town, far off.
function town(s, z, { from = -620, to = 620, count = 90, low = 8, high = 52, clear = 0 } = {}) {
  const fronts = [0, 1, 2].map((i) => s.mat.facade(900 + i, 10, 16, 0.08 + i * 0.07, i !== 1));
  for (let i = 0; i < count; i++) {
    const [x, w, h] = [from + s.r() * (to - from), 9 + s.r() * 16, low + s.r() * s.r() * (high - low)];
    if (Math.abs(x) < clear) continue;
    s.box(w, h, w, fronts[i % 3], x, 0, z - s.r() * 70);
  }
}

// Or a line of trees: dark rounded masses, one against another.
function trees(s, z, { from = -620, to = 620, count = 150 } = {}) {
  const leaf = new s.THREE.MeshStandardMaterial({ color: 0x1b2217, roughness: 1 });
  for (let i = 0; i < count; i++) {
    const [x, size] = [from + s.r() * (to - from), 3 + s.r() * 6];
    const tree = s.put(new s.THREE.IcosahedronGeometry(size, 1), leaf, x, size * 0.7, z - s.r() * 40);
    tree.scale.set(1 + s.r() * 0.7, 0.75 + s.r() * 0.7, 1);
  }
}

// The lamps of a room take the tone the sky gives outdoors: warm, flat white, or dim and cold.
const ROOM = { bullish: [0xffdfb8, 1], neutral: [0xe9eef3, 0.9], bearish: [0x86a4d4, 0.5] };

export const SCENES = {
  // A data hall: two rows of racks down an aisle, a door at the far end.
  Technology(s, view) {
    const { THREE, box, mat, r } = s;
    const [light, power] = ROOM[s.toneName];
    s.ground(mat.ground(0x1b1d20, [600, 600]), 4000, 0.34, 0.007);
    const door = new THREE.MeshStandardMaterial({ color: 0x23262a, roughness: 0.5, metalness: 0.8 });
    const frame = mat.metal(0x0d0e10, 0.55);
    // The lights on the machines: mostly green when the day is good, amber when it is not.
    const leds = { bullish: [0x39d98a, 0x39d98a, 0x39d98a, 0x58a6ff], neutral: [0x39d98a, 0x58a6ff, 0xffb347, 0x39d98a], bearish: [0xffb347, 0xffb347, 0xff6b4a, 0x58a6ff] }[s.toneName];
    for (let i = 0; i < 46; i++) for (const side of [-1, 1]) {
      const z = 6 - i * 1.25;
      box(1.2, 4.4, 1.15, frame, side * 2.7, 0, z);
      box(0.06, 4.0, 1.0, door, side * 2.08, 0.2, z);
      for (let k = 0; k < 6; k++) if (r() < 0.75)
        box(0.03, 0.045, 0.08, mat.glow(leds[(r() * 4) | 0], 4), side * 2.04, 0.5 + r() * 3.4, z - 0.4 + r() * 0.8);
    }
    box(9, 0.3, 64, mat.metal(0x101113, 0.7), 0, 5.2, -25);      // the ceiling
    for (const side of [-1, 1]) box(0.4, 5.4, 64, frame, side * 4.6, 0, -25);  // the walls behind the racks
    box(9.6, 5.4, 0.4, frame, 0, 0, -52.5);                      // the end wall, and its door ajar
    box(1.5, 2.7, 0.1, mat.glow(light, 2.2 * power), 0, 0, -52.2);
    for (let i = 0; i < 9; i++) {
      box(1.4, 0.05, 0.5, mat.glow(light, 1.5 * power), 0, 5.12, 2 - i * 6);
      s.lamp(light, 17 * power, 0, 4.6, 2 - i * 6, 14);
    }
    return view === 1 ? { from: [0, 1.35, 9.5], at: [0, 2.1, -30], fov: 50, span: 40, indoors: true }
      : { from: [-1.35, 2.5, 8.5], at: [1.4, 1.5, -22], fov: 44, span: 40, indoors: true };
  },

  // Masts and dishes on a bare hilltop.
  "Communication Services"(s, view) {
    const { THREE, mat, put, r } = s;
    const hill = put(new THREE.SphereGeometry(900, 96, 48), mat.concrete(0x2b2c2a), 0, -893, -30, false);
    hill.receiveShadow = true;
    const steel = mat.metal(0x24272b, 0.5);
    for (const [x, z, h] of [[-9, -34, 46], [12, -52, 58], [34, -30, 38]]) {
      mast(s, x, z, h, 3.2, 0.7, steel, 9);
      for (let i = 0; i < 4; i++) {
        const y = h * (0.55 + i * 0.11), turn = r() * Math.PI * 2;
        const dish = put(new THREE.SphereGeometry(1.5 + r(), 32, 16, 0, Math.PI * 2, 0, 1.05), mat.paint(0xcfd2d4, 0.5), x + Math.cos(turn) * 1.6, y, z + Math.sin(turn) * 1.6);
        dish.rotation.set(Math.PI / 2, 0, -turn + Math.PI / 2);
        dish.material.side = THREE.DoubleSide;
      }
      for (let k = 0; k < 3; k++) s.box(0.35, 2.6, 0.2, mat.paint(0xdadcde, 0.5), x + (k - 1) * 1.1, h - 4, z + 0.9);
      s.box(0.2, 0.2, 0.2, mat.glow(0xff3b30, 6), x, h + 0.3, z);
    }
    s.box(7, 3, 5, mat.concrete(0x4a4c4f), 3, 6.2, -40);
    return view === 1 ? { from: [-4, 8.6, 6], at: [9, 34, -46], fov: 46, span: 120 } : { from: [46, 9.5, 12], at: [8, 30, -44], fov: 40, span: 120 };
  },

  // A shopping street: lit shopfronts under dark floors, cars at the kerb, nobody about.
  "Consumer Cyclical"(s, view) {
    const { box, mat, r } = s;
    const lit = s.toneName === "neutral" ? 0.6 : 1;
    s.ground(mat.ground(0x191b1e));
    box(0.14, 0.02, 220, mat.paint(0xbfc2c4, 0.7), 0, 0.01, -70);
    for (const side of [-1, 1]) {
      box(5, 0.22, 240, mat.concrete(0x55585c), side * 10.5, 0, -80);
      let z = 20;
      for (let i = 0; i < 16; i++) {
        const [w, h] = [9 + r() * 9, 16 + r() * 22];
        box(8, h, w - 0.3, mat.facade(100 + i + side * 7, 6, Math.round(h / 3.4), 0.22 + r() * 0.2, r() < 0.7), side * 17, 4.4, z - w / 2);
        box(8.2, 4.4, w - 0.3, mat.metal(0x0b0c0e, 0.4), side * 17, 0, z - w / 2);
        const shop = [0xffd9a0, 0xfff1d6, 0xbfe3ff, 0xffc98a][(r() * 4) | 0];
        box(0.1, 3.0, w - 2.2, mat.glow(shop, 1.15 * lit), side * 12.85, 0.6, z - w / 2);
        if (i < 7) s.lamp(shop, 9 * lit, side * 11.6, 2.2, z - w / 2, 14);
        z -= w;
      }
      for (let i = 0; i < 9; i++) {
        const z0 = 8 - i * 9.5 - r() * 3, paint = mat.paint([0x15171a, 0x5d1f1a, 0x1f3550, 0x9a9da1, 0x2b2d30][(r() * 5) | 0], 0.25);
        box(1.9, 0.75, 4.5, paint, side * 6.6, 0.35, z0);
        box(1.7, 0.62, 2.3, mat.glass(0x0a0d11), side * 6.6, 1.1, z0 - 0.2);
        for (const dz of [-1.45, 1.45]) for (const dx of [-0.95, 0.95]) s.cyl(0.36, 0.24, mat.paint(0x08090a, 0.8), side * 6.6 + dx, 0, z0 + dz).rotation.z = Math.PI / 2;
      }
      for (let i = 0; i < 7; i++) {
        s.cyl(0.09, 6.2, mat.metal(0x16181b), side * 8.4, 0, 6 - i * 17);
        box(1.3, 0.12, 0.3, mat.glow(0xffe2b0, 2.6 * lit), side * 7.8, 6.2, 6 - i * 17);
        s.lamp(0xffd9a0, 12 * lit, side * 7.7, 5.9, 6 - i * 17, 16);
      }
    }
    return view === 1 ? { from: [0.6, 1.55, 16], at: [0, 6.5, -60], fov: 46, span: 120 } : { from: [9.4, 1.7, 15], at: [-6, 5.5, -50], fov: 42, span: 120 };
  },

  // A supermarket aisle: full shelves, a polished floor, the entrance bright at the far end.
  "Consumer Defensive"(s, view) {
    const { box, mat, r } = s;
    const [light, power] = ROOM[s.toneName];
    s.sunAt(3, Math.min(s.tone.elevation, 10));
    s.ground(mat.ground(0x8d8a84, [500, 500]), 4000, 0.22, 0.009);
    const steel = mat.metal(0x8f9296, 0.55);
    const goods = [0x8c3b2e, 0xb08a3a, 0x2f5d73, 0x3e6b4a, 0xd9d2c4, 0x5b4a6b, 0xa65f2b, 0x1f2a36, 0xc9b28a].map((c) => mat.paint(c, 0.55));
    for (const side of [-1, 1]) {
      box(0.9, 4.1, 58, mat.paint(0xdcd9d2, 0.8), side * 2.85, 0, -22);
      for (let level = 0; level < 5; level++) {
        box(1.1, 0.06, 58, steel, side * 2.4, 0.35 + level * 0.78, -22);
        for (let z = 6.6; z > -50; ) {
          const [w, h, m] = [0.16 + r() * 0.3, 0.3 + r() * 0.36, goods[(r() * goods.length) | 0]];
          const run = 2 + ((r() * 5) | 0);
          for (let k = 0; k < run; k++, z -= w + 0.02) box(0.5, h, w, m, side * 2.2, 0.41 + level * 0.78, z);
          z -= r() < 0.15 ? 0.4 : 0.05;
        }
      }
    }
    box(8, 0.3, 62, mat.paint(0xe9e7e2, 0.9), 0, 5.4, -22);
    for (let i = 0; i < 10; i++) {
      box(0.22, 0.06, 3.6, mat.glow(light, 1.7 * power), 0, 5.3, 4 - i * 5.6);
      s.lamp(light, 12 * power, 0, 4.9, 4 - i * 5.6, 13);
    }
    return view === 1 ? { from: [0.2, 1.45, 8.6], at: [0, 1.9, -30], fov: 50, span: 40, indoors: true }
      : { from: [1.25, 2.7, 8.2], at: [-1.7, 1.2, -18], fov: 44, span: 40, indoors: true };
  },

  // A financial district across the water: towers of glass in the haze, their lights on the harbour.
  "Financial Services"(s, view) {
    const { box, mat, r } = s;
    s.ground(mat.water(), 4000, 0.66, 0.014);
    const fronts = [0, 1, 2, 3].map((i) => mat.facade(300 + i, 14, 46, 0.1 + i * 0.07, i % 2 === 0));
    for (let i = 0; i < 64; i++) {
      const x = -260 + r() * 520, z = -92 - r() * 120;
      const w = 9 + r() * 13, h = (22 + r() * r() * 110) * (1.05 - Math.abs(x) / 340);
      const front = fronts[(r() * 4) | 0];
      box(w, h, w * (0.7 + r() * 0.5), front, x, 2, z);
      if (r() < 0.55) box(w * 0.62, h * 0.18, w * 0.5, front, x, h + 2, z);      // a setback at the top
      if (r() < 0.3) s.cyl(0.16, 9 + r() * 14, mat.metal(0x16181b), x, h * 1.18 + 2, z);
    }
    box(640, 2, 10, mat.concrete(0x2a2d31), 0, 0, -84);                          // the quay, and its lamps
    for (let i = 0; i < 46; i++) box(0.25, 0.25, 0.25, mat.glow(0xffd9a0, 5), -290 + i * 12.8, 2.6, -80);
    return view === 1 ? { from: [0, 2.6, 70], at: [4, 30, -140], fov: 40 } : { from: [-150, 3, 40], at: [30, 34, -150], fov: 34 };
  },

  // A laboratory bench before a tall window: racks of vials with the light coming through them.
  Healthcare(s, view) {
    const { THREE, box, mat, r } = s;
    s.sunAt(view === 1 ? -17 : 15, Math.min(s.tone.elevation, 13));
    s.ground(mat.ground(0x24272b));
    town(s, -230, { count: 60 });
    const dark = mat.metal(0x14161a, 0.5);
    box(140, 9.6, 2, mat.paint(0x2a2d31, 0.8), 0, 0, -9);                        // the wall under the window
    box(140, 0.5, 3, mat.paint(0xd9d6cf, 0.6), 0, 9.6, -9);                      // its sill
    for (let i = -7; i <= 7; i++) box(0.4, 44, 0.4, dark, i * 10 + 4, 10, -9);   // the mullions
    box(140, 0.4, 0.4, dark, 0, 24, -9);
    box(140, 0.6, 16, mat.metal(0xa4a9ae, 0.25), 0, 9.4, 0);                     // the bench: brushed steel
    const glass = new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.03, metalness: 0, transmission: 1, thickness: 0.3, ior: 1.45 });
    const shine = { bullish: 0.16, neutral: 0.07, bearish: 0.04 }[s.toneName];    // the light a liquid holds when it is behind it
    const liquids = [0x7fb6c9, 0xc9a04a, 0x94bfa0, 0xc47f78, 0xb7b9cf, 0xd6c394].map((c) =>
      new THREE.MeshStandardMaterial({ color: c, roughness: 0.15, emissive: c, emissiveIntensity: shine }));
    const plate = mat.paint(0xe6e8ea, 0.5);
    for (const x0 of [-13, 0, 13]) {                                             // three racks of tubes
      box(10.4, 0.18, 4.6, plate, x0, 10, -2);
      box(10.4, 0.12, 4.6, plate, x0, 11.5, -2);
      for (let row = 0; row < 5; row++) for (let i = 0; i < 12; i++) {
        if (r() < 0.12) continue;
        const [x, z] = [x0 - 4.7 + i * 0.86, -3.8 + row * 0.9];
        s.cyl(0.28, 2.7, glass, x, 10.18, z, 0.28, 20);
        s.cyl(0.22, 0.6 + r() * 1.5, liquids[(i + row * 2 + (r() * 2 | 0)) % liquids.length], x, 10.22, z, 0.22, 16);
      }
    }
    for (const [x, z, size, k] of [[-21.5, -3, 1, 1], [-6.6, 3.2, 1.25, 0], [6.4, 2.6, 0.9, 3], [21, -2.4, 1.3, 2], [8.4, 4.4, 0.7, 4]]) {   // flasks
      s.cyl(1.5 * size, 2.4 * size, glass, x, 10, z, 0.38 * size, 32);
      s.cyl(0.38 * size, 1.1 * size, glass, x, 10 + 2.4 * size, z, 0.42 * size, 24);
      s.cyl(1.38 * size, 1.0 * size, liquids[k], x, 10.04, z, 0.93 * size, 32);
    }
    return view === 1 ? { from: [-6.5, 11.7, 9.6], at: [1.5, 11.25, -4], fov: 30, span: 40, indoors: true }
      : { from: [7.5, 13.2, 10], at: [-2.5, 10.9, -2.5], fov: 34, span: 40, indoors: true };
  },

  // A container port: stacks on the quay, gantry cranes over them.
  Industrials(s, view) {
    const { THREE, box, mat, r } = s;
    s.sunAt(view === 1 ? -52 : -38);
    s.ground(mat.ground(0x25282b));
    const ribs = pattern("ribs", "#f2f2f2", "#b9b9b9");
    ribs.wrapS = ribs.wrapT = THREE.RepeatWrapping;
    ribs.repeat.set(24, 1);
    const paints = PALETTE.map((color) => new THREE.MeshStandardMaterial({ color, roughness: 0.6, metalness: 0.3, map: ribs }));
    for (let block = 0; block < 5; block++) for (let col = 0; col < 7; col++) {
      const high = 1 + ((r() * 5) | 0);
      for (let k = 0; k < high; k++) for (let n = 0; n < 3; n++)
        box(2.44, 2.59, 12.19, paints[(r() * paints.length) | 0], -42 + block * 21 + n * 2.5, k * 2.62, -18 - col * 13);
    }
    const steel = mat.paint(0x9a3c2b, 0.5);
    for (const x of [-52, 2, 58]) {
      for (const dx of [-14, 14]) for (const dz of [-7, 7]) box(1.6, 62, 1.6, steel, x + dx, 0, -128 + dz);
      for (const y of [20, 40]) for (const dz of [-7, 7]) s.beam([x - 14, y, -128 + dz], [x + 14, y + 20, -128 + dz], 0.35, steel);
      box(30, 2.2, 16, steel, x, 60, -128);
      box(3.4, 3.4, 110, steel, x, 64, -108);
      box(5, 4, 6, mat.metal(0x1b1d20), x, 60, -92);
      s.beam([x - 14, 62, -128], [x, 86, -128], 0.5, steel);
      s.beam([x + 14, 62, -128], [x, 86, -128], 0.5, steel);
      s.beam([x, 86, -128], [x, 66, -56], 0.3, steel);
      for (const dz of [-150, -60]) s.lamp(0xffe6c0, 220, x, 58, dz, 110);
      box(0.6, 0.3, 0.6, mat.glow(0xffe0b0, 6), x, 59, -92);
    }
    box(260, 16, 30, mat.paint(0x18222c, 0.5), 20, 0, -176);                     // a ship alongside, and its bridge
    box(60, 14, 16, mat.paint(0xd7d4cc, 0.7), 90, 16, -178);
    return view === 1 ? { from: [-8, 1.9, 34], at: [4, 30, -120], fov: 46 } : { from: [-120, 46, 40], at: [10, 24, -110], fov: 40 };
  },

  // A refinery: columns with their platforms, spheres of gas, pipe racks, a flare.
  Energy(s, view) {
    const { THREE, box, mat, put, r } = s;
    s.ground(mat.ground(0x1f2124));
    trees(s, -330);
    const steel = mat.metal(0x767b80, 0.4), dark = mat.metal(0x2a2d31, 0.5);
    for (const [x, z, rad, h] of [[-30, -70, 2.6, 62], [-14, -80, 3.4, 78], [6, -64, 2.2, 48], [24, -86, 3, 70], [44, -72, 2.4, 54], [-52, -92, 3, 58]]) {
      s.cyl(rad, h, steel, x, 0, z);
      put(new THREE.SphereGeometry(rad, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2), steel, x, h, z);
      for (let y = 10; y < h; y += 9 + r() * 4) {
        const ring = put(new THREE.TorusGeometry(rad + 1.1, 0.14, 6, 36), dark, x, y + 1.1, z);
        ring.rotation.x = Math.PI / 2;
        s.cyl(rad + 1.2, 0.12, dark, x, y, z);
        if (r() < 0.7) s.lamp(0xffe2b0, 40, x + rad + 1, y + 1.6, z + rad, 24), box(0.22, 0.22, 0.22, mat.glow(0xffe2b0, 6), x + rad + 0.8, y + 1.8, z + rad);
      }
      s.beam([x + rad + 0.8, 0, z], [x + rad + 0.8, h, z], 0.22, dark);
    }
    for (const [x, z] of [[70, -50], [88, -66], [72, -84]]) {
      put(new THREE.SphereGeometry(9, 40, 24), mat.paint(0xcfd2d4, 0.45), x, 12.5, z);
      for (let k = 0; k < 6; k++) s.cyl(0.4, 12, dark, x + Math.cos(k) * 7.4, 0, z + Math.sin(k) * 7.4);
    }
    for (let i = 0; i < 9; i++) {
      for (const dx of [-4, 4]) box(0.45, 9, 0.45, dark, -70 + i * 17, 0, -40 + dx);
      box(0.45, 0.45, 9, dark, -70 + i * 17, 8.6, -40);
    }
    for (let k = 0; k < 7; k++) s.beam([-74, 8.9 + (k % 2) * 1.1, -43.4 + k * 1.1], [70, 8.9 + (k % 2) * 1.1, -43.4 + k * 1.1], 0.34 + (k % 3) * 0.1, k % 3 ? steel : mat.paint(0x8a6a2d, 0.5), 10);
    s.cyl(0.9, 96, dark, -84, 0, -120);                                          // the flare stack and its flame
    for (const [dy, size, lean] of [[0, 1.5, 0], [2.6, 1.25, 0.7], [5, 0.85, 1.7]])
      put(new THREE.SphereGeometry(size, 16, 12), mat.glow(0xff9b3d, 6), -84 + lean, 97.5 + dy, -120, false).scale.set(1, 1.7, 1);
    s.lamp(0xff9b3d, 900, -84, 102, -120, 220);
    return view === 1 ? { from: [-6, 2.4, 20], at: [4, 30, -76], fov: 46 } : { from: [112, 26, 34], at: [-10, 26, -80], fov: 40 };
  },

  // Pylons carrying their lines across a plain, one behind another.
  Utilities(s, view) {
    const { THREE, mat, put } = s;
    s.ground(mat.ground(0x24261f));
    trees(s, -420, { from: -900, to: 900, count: 220 });
    const steel = mat.metal(0x3a3e43, 0.5), wire = mat.metal(0x111214, 0.6);
    const pylons = Array.from({ length: 8 }, (_, i) => [-6 + i * 5, -30 - i * 92]);
    const arms = [[22, 34], [16, 44], [10, 54]];
    pylons.forEach(([x, z]) => {
      mast(s, x, z, 58, 5.4, 0.9, steel, 9);
      for (const [reach, y] of arms) {
        s.beam([x - reach, y, z], [x + reach, y, z], 0.2, steel);
        for (const side of [-1, 1]) { s.beam([x + side * reach, y, z], [x, y + 5, z], 0.11, steel, 4); s.beam([x + side * reach, y, z], [x + side * reach, y - 2.6, z], 0.07, wire, 4); }
      }
    });
    for (let i = 0; i < pylons.length - 1; i++) for (const [reach, y] of arms) for (const side of [-1, 1]) {
      const [a, b] = [pylons[i], pylons[i + 1]];
      const curve = new THREE.CatmullRomCurve3([0, 0.25, 0.5, 0.75, 1].map((k) =>
        new THREE.Vector3(a[0] + (b[0] - a[0]) * k + side * reach, y - 2.6 - Math.sin(k * Math.PI) * 9, a[1] + (b[1] - a[1]) * k)));
      put(new THREE.TubeGeometry(curve, 28, 0.085, 5), wire, 0, 0, 0, false);
    }
    return view === 1 ? { from: [-30, 2.6, 34], at: [8, 34, -150], fov: 44 } : { from: [44, 14, 30], at: [-6, 36, -170], fov: 36 };
  },

  // Homes going up: finished blocks, one still a frame, tower cranes among them.
  "Real Estate"(s, view) {
    const { box, mat, r } = s;
    s.ground(mat.ground(0x2a2b28));
    town(s, -300, { high: 40 });
    const slab = mat.concrete(0x8d8f90), steel = mat.paint(0xb8962e, 0.5);
    [[-60, -110, 26, 84, 20], [-22, -150, 30, 110, 22], [66, -120, 26, 74, 20], [104, -170, 30, 96, 22], [-104, -180, 28, 66, 22]].forEach(([x, z, w, h, d], i) => {
      box(w, h, d, mat.facade(500 + i, Math.round(w / 2.2), Math.round(h / 3.1), 0.2 + r() * 0.2, true), x, 0, z);
      for (let y = 3.1; y < h; y += 3.1) box(w + 2.4, 0.18, d + 2.4, slab, x, y, z);
    });
    for (let y = 0; y < 62; y += 3.4) {   // the block still going up: slabs and columns, no walls yet
      box(28, 0.3, 20, slab, 22, y, -84);
      for (const dx of [-13, -4.4, 4.4, 13]) for (const dz of [-9, 0, 9]) box(0.5, 3.4, 0.5, slab, 22 + dx, y, -84 + dz);
    }
    for (const [x, z, h, jib, turn] of [[44, -74, 96, 62, 0.5], [-40, -128, 132, 70, -0.9]]) {
      mast(s, x, z, h, 1.5, 1.5, steel, Math.round(h / 6));
      const [cx, cz] = [Math.cos(turn), Math.sin(turn)];
      s.beam([x - cx * 18, h, z - cz * 18], [x + cx * jib, h, z + cz * jib], 0.6, steel);
      s.beam([x, h + 12, z], [x + cx * jib, h + 0.6, z + cz * jib], 0.14, steel, 4);
      s.beam([x, h + 12, z], [x - cx * 18, h + 0.6, z - cz * 18], 0.14, steel, 4);
      s.beam([x, h, z], [x, h + 12, z], 0.4, steel);
      box(5, 4, 4, mat.concrete(0x55585c), x - cx * 16, h - 4, z - cz * 16);
      s.beam([x + cx * jib * 0.7, h, z + cz * jib * 0.7], [x + cx * jib * 0.7, h - 44, z + cz * jib * 0.7], 0.06, mat.metal(0x111214), 4);
      box(0.4, 0.4, 0.4, mat.glow(0xff3b30, 7), x, h + 12.4, z);
    }
    return view === 1 ? { from: [-8, 2.6, 30], at: [14, 52, -110], fov: 48 } : { from: [150, 40, 60], at: [0, 44, -120], fov: 38 };
  },

  // A mine's surface works: heaps of ore, the conveyors that feed them, the headframe over the shaft.
  "Basic Materials"(s, view) {
    const { THREE, box, mat, put } = s;
    s.sunAt(view === 1 ? -26 : 20);
    s.ground(mat.ground(0x2c2824));
    trees(s, -360);
    const steel = mat.metal(0x3a3d41, 0.55), stains = mat.concrete().map;
    const heap = (x, z, rad, h, color) => {
      const cone = new THREE.ConeGeometry(rad, h, 72, 14);
      const p = cone.attributes.position;
      for (let i = 0; i < p.count; i++) {   // no heap is a clean cone: its foot wanders and its top is blunt
        const k = 1 - (p.getY(i) + h / 2) / h, a = Math.atan2(p.getZ(i), p.getX(i));
        const bulge = 1 + k * (0.035 * Math.sin(a * 3 + x) + 0.03 * Math.sin(a * 7 + z) + 0.02 * Math.sin(a * 13));
        p.setXYZ(i, p.getX(i) * bulge, p.getY(i) - (k < 0.08 ? (0.08 - k) * h * 0.5 : 0), p.getZ(i) * bulge);
      }
      cone.computeVertexNormals();
      put(cone, new THREE.MeshStandardMaterial({ color, roughness: 0.97, map: stains }), x, h / 2, z);
    };
    for (const [x, z, rad, h, color, feed] of [[-52, -96, 34, 27, 0x5d4c3b, -1], [22, -126, 46, 36, 0x3b3835, 1], [96, -92, 30, 23, 0x7b5d3f, 1], [-124, -150, 40, 30, 0x45413d, -1]]) {
      heap(x, z, rad, h, color);
      // The conveyor that feeds it: a gallery climbing on trestles to above its top.
      const [top, foot] = [[x, h + 5, z], [x + feed * 86, 5, z + 26]];
      s.beam(foot, top, 1.5, steel, 4);
      for (const k of [0.3, 0.62, 0.92]) {
        const at = foot.map((v, i) => v + (top[i] - v) * k);
        for (const lean of [-3.4, 3.4]) s.beam([at[0], at[1], at[2]], [at[0] + lean * 0.4, 0, at[2] + lean], 0.3, steel, 4);
      }
      box(3.4, 3, 3.4, steel, x, h + 3.6, z);
      box(0.3, 0.3, 0.3, mat.glow(0xffe2b0, 6), x, h + 7, z);
    }
    mast(s, 160, -170, 74, 7, 3.2, steel, 9);                                    // the headframe, its wheels and its stays
    for (const dx of [-2.2, 2.2]) put(new THREE.TorusGeometry(5, 0.45, 8, 40), steel, 160 + dx, 76, -170).rotation.y = Math.PI / 2;
    for (const dx of [-3, 3]) s.beam([160 + dx, 72, -170], [160 + dx, 0, -124], 0.5, steel, 4);
    box(46, 20, 28, mat.paint(0x3f4347, 0.7), 150, 0, -214);
    for (const [x, z, turn] of [[-8, -52, 0.3], [40, -66, -0.5], [-84, -60, 1.1]]) {  // haul trucks
      const truck = box(4.6, 2.8, 8, mat.paint(0xc99a1e, 0.5), x, 1.5, z);
      truck.rotation.y = turn;
      box(4.2, 1.8, 2.4, mat.metal(0x1d1f22, 0.4), x + Math.sin(turn) * 3.6, 4.3, z + Math.cos(turn) * 3.6).rotation.y = turn;
    }
    return view === 1 ? { from: [-18, 2.6, 30], at: [6, 22, -110], fov: 44 } : { from: [150, 28, 44], at: [-14, 16, -112], fov: 38 };
  },

  // The front of a central bank: steps, a row of columns, a pediment.
  Macro(s, view) {
    const { THREE, box, mat, put } = s;
    s.sunAt(view === 1 ? -118 : -152);                           // low and from the left: it rakes the columns
    s.ground(mat.ground(0x26282b, [300, 300]), 4000, s.tone.wet * 0.3, 0.02);
    town(s, -230, { clear: 70, high: 60 });
    const stone = mat.stone(0xc2baa9), shade = mat.stone(0x8f8778);
    for (let i = 0; i < 9; i++) box(96 - i * 2.4, 0.5, 26 - i * 1.3, stone, 0, i * 0.5, -40 + i * 0.65);
    for (let i = 0; i < 10; i++) {
      const x = -36 + i * 8;
      s.cyl(1.55, 1.1, stone, x, 4.5, -31.5, 1.75, 24);
      s.cyl(1.3, 22, stone, x, 5.6, -31.5, 1.12, 24);
      box(3.5, 1.1, 3.5, stone, x, 27.6, -31.5);
    }
    box(84, 4.4, 9, stone, 0, 28.7, -33.5);
    box(88, 1.1, 10.4, shade, 0, 33.1, -33.5);
    const gable = new THREE.Shape([new THREE.Vector2(-44, 0), new THREE.Vector2(44, 0), new THREE.Vector2(0, 13)]);
    put(new THREE.ExtrudeGeometry(gable, { depth: 9.6, bevelEnabled: false }), stone, 0, 34.2, -38.3);
    box(86, 40, 22, shade, 0, 4.5, -52);                         // the building behind the colonnade
    for (let i = 0; i < 9; i++) box(3.4, 12, 0.5, mat.glass(0x07090b), -32 + i * 8, 9, -40.6);
    box(7, 15, 0.6, mat.metal(0x2c241a, 0.4), 0, 4.5, -40.4);
    if (s.toneName === "bearish") for (let i = 0; i < 9; i++) s.lamp(0xffd9a8, 70, -32 + i * 8, 22, -37, 26);  // the lights of the porch
    return view === 1 ? { from: [-44, 2.4, 14], at: [6, 24, -40], fov: 48, span: 110 } : { from: [4, 1.9, 38], at: [0, 22, -40], fov: 52, span: 110 };
  },
};
