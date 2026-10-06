// The stage every cover is shot on: a sky, its light, the air, the ground and the camera's
// finishing (bloom, vignette, grain, rain). A scene (scenes.js) only puts things on it.
//
// The tone of a piece of news is told by the light, never by an arrow or a colour code: a low
// warm sun breaking in for bullish, a cold wet dusk under heavy cloud for bearish, the flat light
// of an overcast day for neutral.

import * as THREE from "three";
import { Reflector } from "three/addons/objects/Reflector.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

export const W = 1920, H = 1080;  // rendered at this size, saved at two thirds of it

export const TONES = {
  bullish: {
    sun: 0xffb26e, sunPower: 4.6, elevation: 7, hemi: [0x8ea2c2, 0x2b2420, 0.55], fog: [0xc79468, 0.0034],
    sky: { top: 0x15213a, mid: 0x82605a, horizon: 0xffb86c, clouds: 0.3, cloud: 0xffc9a0, shade: 0x5a4650 },
    exposure: 1.0, wet: 0.3, bloom: 0.55, rain: 0,
  },
  bearish: {
    sun: 0x9fb6d8, sunPower: 0.9, elevation: 32, hemi: [0x55657f, 0x0c0e12, 0.6], fog: [0x36434f, 0.0058],
    sky: { top: 0x0a0e15, mid: 0x1c2734, horizon: 0x40505f, clouds: 0.9, cloud: 0x5a6a7e, shade: 0x161d27 },
    exposure: 0.95, wet: 0.95, bloom: 0.35, rain: 1,
  },
  neutral: {
    sun: 0xf3f1ea, sunPower: 2.3, elevation: 44, hemi: [0xb4bcc6, 0x2b2d2f, 0.7], fog: [0xaab0b5, 0.0042],
    sky: { top: 0x5f6a75, mid: 0x8f989f, horizon: 0xb9bfc3, clouds: 0.66, cloud: 0xd6dadd, shade: 0x6f7780 },
    exposure: 0.9, wet: 0.5, bloom: 0.25, rain: 0,
  },
};

export function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let x = Math.imul(s ^ (s >>> 15), 1 | s);
    x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

// --- The sky -----------------------------------------------------------------------------------

const SKY = /* glsl */ `
  uniform vec3 top, mid, horizon, sunColor, cloudColor, shade, sunDir, haze;
  uniform float clouds;
  varying vec3 dir;
  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
  }
  float fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 6; i++) { v += a * noise(p); p = p * 2.03 + 17.0; a *= 0.5; } return v; }
  void main() {
    vec3 d = normalize(dir);
    float h = max(d.y, 0.0);
    vec3 col = mix(horizon, mid, smoothstep(0.0, 0.22, h));
    col = mix(col, top, smoothstep(0.16, 0.85, h));
    float facing = max(dot(d, sunDir), 0.0);
    col += sunColor * (pow(facing, 1400.0) * 4.0 + pow(facing, 60.0) * 0.45 + pow(facing, 5.0) * 0.16);
    // Clouds: layers of noise on the dome, lit where they face the sun and dark where they do not.
    vec2 uv = d.xz / (d.y + 0.22) * 1.25;
    float cover = smoothstep(1.0 - clouds * 0.92, 1.25 - clouds * 0.6, fbm(uv + 3.0) + 0.42 * fbm(uv * 2.7));
    vec3 lit = mix(shade, cloudColor, clamp(0.25 + pow(facing, 2.0) * 0.9 + fbm(uv * 3.1) * 0.35, 0.0, 1.0));
    col = mix(col, lit, cover * smoothstep(-0.02, 0.12, d.y) * 0.88);
    // At the horizon the sky is the colour of the air, so the ground runs into it without a line.
    col = mix(haze, col, smoothstep(-0.01, 0.075, d.y) * 0.9 + 0.1 * pow(facing, 30.0));
    gl_FragColor = vec4(col, 1.0);
  }`;

function dome(tone, sunDir) {
  const u = (hex) => ({ value: new THREE.Color(hex) });
  return new THREE.Mesh(new THREE.SphereGeometry(4000, 48, 24), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: { top: u(tone.sky.top), mid: u(tone.sky.mid), horizon: u(tone.sky.horizon), sunColor: u(tone.sun), cloudColor: u(tone.sky.cloud),
      shade: u(tone.sky.shade), haze: u(tone.fog[0]), sunDir: { value: sunDir }, clouds: { value: tone.sky.clouds } },
    vertexShader: "varying vec3 dir; void main() { dir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    fragmentShader: SKY,
  }));
}

// What a wet ground gives back is not a mirror's image: it is smeared, most of all up and down.
const SMEAR = {
  name: "SmearedReflection",
  vertexShader: "uniform mat4 textureMatrix; varying vec4 vUv; void main() { vUv = textureMatrix * vec4(position, 1.0); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse;
    uniform float blur;
    varying vec4 vUv;
    void main() {
      vec2 uv = vUv.xy / vUv.w;
      vec3 sum = vec3(0.0);
      float total = 0.0;
      for (int i = -10; i <= 10; i++) {
        float k = float(i) / 10.0, weight = 1.0 - abs(k) * 0.8;
        sum += texture2D(tDiffuse, uv + vec2(k * blur * 0.16, k * blur)).rgb * weight;
        total += weight;
      }
      gl_FragColor = vec4(sum / total, 1.0);
    }`,
};

// --- Textures made on the spot -----------------------------------------------------------------

function canvasTexture(w, h, paint, repeat) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  paint(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  if (repeat) (t.wrapS = t.wrapT = THREE.RepeatWrapping), t.repeat.set(...repeat);
  return t;
}

// The windows of a building at a distance: a grid, some of them lit.
export function windows(seed, cols, rows, lit, warm = true) {
  const r = rng(seed);
  return canvasTexture(cols * 16, rows * 20, (g, w, h) => {
    g.fillStyle = "#07090b";
    g.fillRect(0, 0, w, h);
    for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
      const on = r() < lit;
      const v = 0.55 + r() * 0.45;
      g.fillStyle = on ? (warm ? `rgba(255,${190 + r() * 40 | 0},${120 + r() * 50 | 0},${v})` : `rgba(${170 + r() * 40 | 0},${205 + r() * 30 | 0},255,${v})`) : `rgba(40,52,66,${0.25 + r() * 0.3})`;
      g.fillRect(x * 16 + 3, y * 20 + 4, 10, 12);
    }
  });
}

// A pattern of fine lines or dots, for metal that is not a plain slab.
export function pattern(kind, color = "#15171a", line = "#000000") {
  return canvasTexture(128, 128, (g, w, h) => {
    g.fillStyle = color;
    g.fillRect(0, 0, w, h);
    g.fillStyle = g.strokeStyle = line;
    if (kind === "dots") for (let y = 4; y < h; y += 8) for (let x = (y / 8) % 2 ? 4 : 8; x < w; x += 8) g.fillRect(x, y, 3, 3);
    if (kind === "ribs") for (let x = 0; x < w; x += 16) g.fillRect(x, 0, 6, h);
    if (kind === "tiles") { g.lineWidth = 2; g.strokeRect(1, 1, w - 2, h - 2); }
  });
}

// The wear on a surface: blotches lighter and darker than its colour, the streaks rain leaves
// running down it, the speckle of asphalt, the joints of cut stone. As a colour map it stops a
// wall being one flat tone; as a roughness map it makes the wet shine unevenly, in puddles.
export function wear(seed, { spots = 60, size = [18, 118], streaks = 0, joints = 0, speckle = 0, depth = 1, repeat } = {}) {
  const r = rng(seed);
  return canvasTexture(512, 512, (g, w, h) => {
    g.fillStyle = "#f2f2f2";
    g.fillRect(0, 0, w, h);
    for (let i = 0; i < spots; i++) {
      const [x, y, reach, dark] = [r() * w, r() * h, size[0] + r() * (size[1] - size[0]), r() < 0.7];
      const spot = g.createRadialGradient(x, y, 0, x, y, reach);
      spot.addColorStop(0, dark ? `rgba(30,30,30,${Math.min(0.9, (0.05 + r() * 0.1) * depth)})` : `rgba(255,255,255,${0.1 + r() * 0.2})`);
      spot.addColorStop(1, dark ? "rgba(30,30,30,0)" : "rgba(255,255,255,0)");
      g.fillStyle = spot;
      g.fillRect(x - reach, y - reach, reach * 2, reach * 2);
    }
    for (let i = 0; i < 120 * streaks; i++) {
      const [x, y, len] = [r() * w, r() * h * 0.6, 40 + r() * 220];
      const run = g.createLinearGradient(0, y, 0, y + len);
      run.addColorStop(0, `rgba(30,30,30,${0.06 + r() * 0.14})`);
      run.addColorStop(1, "rgba(30,30,30,0)");
      g.fillStyle = run;
      g.fillRect(x, y, 1.5 + r() * 5, len);
    }
    for (let i = 0; i < 9000 * speckle; i++) {
      g.fillStyle = r() < 0.6 ? `rgba(0,0,0,${0.1 + r() * 0.25})` : `rgba(255,255,255,${0.1 + r() * 0.2})`;
      g.fillRect(r() * w, r() * h, 1 + r() * 1.6, 1 + r() * 1.6);
    }
    if (joints) {
      g.strokeStyle = "rgba(20,20,20,0.55)";
      g.lineWidth = 1.5;
      for (let j = 0; j <= joints; j++) {
        const y = (j / joints) * h;
        g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke();
        for (let x = (j % 2) * (w / joints); x <= w; x += (w / joints) * 2) { g.beginPath(); g.moveTo(x, y); g.lineTo(x, y + h / joints); g.stroke(); }
      }
    }
  }, repeat);
}

// --- The stage ---------------------------------------------------------------------------------

export function stage(canvas, toneName, seed) {
  const tone = TONES[toneName];
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setSize(W, H, false);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = tone.exposure;

  const scene = new THREE.Scene();
  const fog = new THREE.FogExp2(tone.fog[0], tone.fog[1]);
  scene.fog = fog;

  // Where the sun stands, as a bearing from straight ahead (the scenes look down -z): 0 is in
  // front of the camera, 90 to its right, 180 behind it. By default ahead and a little to the
  // left, so things are lit from behind; a scene that wants its light elsewhere says so (sunAt).
  const sunDir = new THREE.Vector3();
  const sunAt = (bearing, elevation = tone.elevation) => {
    const [el, az] = [THREE.MathUtils.degToRad(elevation), THREE.MathUtils.degToRad(bearing)];
    sunDir.set(Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el)).normalize();
  };
  sunAt(-22);
  scene.add(dome(tone, sunDir));
  scene.environmentIntensity = toneName === "bullish" ? 0.55 : 0.7;

  const sun = new THREE.DirectionalLight(tone.sun, tone.sunPower);
  sun.position.copy(sunDir).multiplyScalar(400);
  sun.castShadow = true;
  sun.shadow.mapSize.set(4096, 4096);
  Object.assign(sun.shadow.camera, { left: -260, right: 260, top: 260, bottom: -260, near: 1, far: 1200 });
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.6;
  scene.add(sun, new THREE.HemisphereLight(tone.hemi[0], tone.hemi[1], tone.hemi[2]));

  const camera = new THREE.PerspectiveCamera(42, W / H, 0.5, 6000);

  // Materials every scene shares, already wet or dry as the weather is.
  const wet = tone.wet;
  const stains = wear(seed + 1, { streaks: 1 });
  const courses = wear(seed + 2, { streaks: 0.6, joints: 6 });
  const asphalt = wear(seed + 3, { speckle: 1, repeat: [260, 260] });
  const puddles = wear(seed + 4, { spots: 16, size: [10, 44], depth: 7, repeat: [34, 34] });
  const mat = {
    // The ground: asphalt that holds puddles, or (given how often its slab repeats) a paved floor.
    ground: (color = 0x24272b, repeat) => new THREE.MeshStandardMaterial({ color, metalness: 0.02, roughness: THREE.MathUtils.lerp(1, 0.6, wet),
      map: repeat ? wear(seed + 5, { joints: 1, speckle: 0.3, repeat }) : asphalt, roughnessMap: repeat ? null : puddles }),
    metal: (color = 0x1c1f23, roughness = 0.45) => new THREE.MeshStandardMaterial({ color, roughness: Math.max(0.12, roughness - wet * 0.2), metalness: 0.75, roughnessMap: stains }),
    paint: (color, roughness = 0.6) => new THREE.MeshStandardMaterial({ color, roughness: Math.max(0.15, roughness - wet * 0.25), metalness: 0.15, map: stains }),
    concrete: (color = 0x6c6f73) => new THREE.MeshStandardMaterial({ color, roughness: THREE.MathUtils.lerp(0.95, 0.5, wet), metalness: 0, map: stains }),
    stone: (color = 0xb9b2a4) => new THREE.MeshStandardMaterial({ color, roughness: THREE.MathUtils.lerp(0.92, 0.55, wet), metalness: 0, map: courses }),
    water: (color = 0x0e1318) => new THREE.MeshStandardMaterial({ color, roughness: 0.2, metalness: 0 }),
    glass: (color = 0x0d1218) => new THREE.MeshStandardMaterial({ color, roughness: 0.06, metalness: 0.95 }),
    glow: (color, power = 2) => new THREE.MeshStandardMaterial({ color: 0x000000, emissive: color, emissiveIntensity: power }),
    facade: (seed, cols, rows, lit, warm) => {
      const map = windows(seed, cols, rows, lit, warm);
      return new THREE.MeshStandardMaterial({ color: 0x1a1f26, roughness: 0.2, metalness: 0.7, emissive: 0xffffff, emissiveMap: map, emissiveIntensity: toneName === "neutral" ? 0.55 : 1.5, map });
    },
  };

  const put = (geometry, material, x = 0, y = 0, z = 0, cast = true) => {
    const m = new THREE.Mesh(geometry, material);
    m.position.set(x, y, z);
    m.castShadow = cast;
    m.receiveShadow = true;
    scene.add(m);
    return m;
  };
  const box = (w, h, d, material, x = 0, y = 0, z = 0) => put(new THREE.BoxGeometry(w, h, d), material, x, y + h / 2, z);
  const cyl = (r, h, material, x = 0, y = 0, z = 0, top = r, sides = 32) => put(new THREE.CylinderGeometry(top, r, h, sides), material, x, y + h / 2, z);
  // A thin member between two points: a strut, a cable, a pipe.
  const beam = (a, b, r, material, sides = 6) => {
    const [p, q] = [new THREE.Vector3(...a), new THREE.Vector3(...b)];
    const m = put(new THREE.CylinderGeometry(r, r, p.distanceTo(q), sides), material, ...p.clone().lerp(q, 0.5).toArray());
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), q.clone().sub(p).normalize());
    return m;
  };
  // The ground. What is wet gives back what stands on it: a mirror lies under the ground, which
  // lets it show through where the water gathers. A polished floor does the same all over (shine),
  // and the smoother the surface the less the image is smeared (blur).
  const ground = (material, size = 4000, shine = wet * wet * 0.55, blur = 0.035) => {
    const mirror = new Reflector(new THREE.PlaneGeometry(size, size), { textureWidth: 2048, textureHeight: 1152,
      shader: { ...SMEAR, uniforms: { tDiffuse: { value: null }, textureMatrix: { value: null }, color: { value: null }, blur: { value: blur } } } });
    mirror.rotation.x = -Math.PI / 2;
    mirror.position.y = -0.03;
    mirror.material.depthWrite = false;   // the ground over it is never fought for the same depth
    mirror.renderOrder = 1;
    scene.add(mirror);
    Object.assign(material, { transparent: true, opacity: 1 - shine, alphaMap: material.roughnessMap });
    const m = put(new THREE.PlaneGeometry(size, size), material, 0, 0, 0, false);
    m.rotation.x = -Math.PI / 2;
    return m;
  };
  const lamp = (color, power, x, y, z, reach = 60) => {
    const l = new THREE.PointLight(color, power, reach, 1.6);
    l.position.set(x, y, z);
    scene.add(l);
    return l;
  };

  // span is how far around what the camera looks at the sun's shadows are worked out.
  function shoot(out, { from, at, fov = 42, span = 260, indoors = false }) {
    // What shiny things reflect is this same sky, with the sun where the scene has put it.
    const skyScene = new THREE.Scene();
    skyScene.add(dome(tone, sunDir));
    scene.environment = new THREE.PMREMGenerator(renderer).fromScene(skyScene, 0.02, 1, 5000).texture;
    Object.assign(sun.shadow.camera, { left: -span, right: span, top: span, bottom: -span });
    camera.fov = fov;
    camera.position.set(...from);
    camera.lookAt(...at);
    camera.updateProjectionMatrix();
    sun.target.position.set(...at);
    sun.position.copy(sunDir).multiplyScalar(400).add(sun.target.position);
    scene.add(sun.target);
    const composer = new EffectComposer(renderer);
    composer.setSize(W, H);
    composer.addPass(new RenderPass(scene, camera));
    // Corners and contacts darken, as they do where light does not reach: it seats things on the ground.
    const occlusion = new GTAOPass(scene, camera, W, H);
    occlusion.updateGtaoMaterial({ radius: span / 110, distanceExponent: 1.4, thickness: 1.2, scale: 1.3, samples: 16 });
    composer.addPass(occlusion);
    composer.addPass(new UnrealBloomPass(new THREE.Vector2(W, H), tone.bloom, 0.4, 0.98));
    composer.addPass(new OutputPass());
    composer.render();
    finish(out, canvas, tone, seed, tone.rain && !indoors);
  }
  return { THREE, scene, tone, toneName, mat, put, box, cyl, beam, ground, lamp, shoot, sunAt, r: rng(seed), fog, sunDir };
}

// What the lens and the film add: darker corners, grain, and rain when it rains.
function finish(out, source, tone, seed, rain) {
  const g = out.getContext("2d");
  g.imageSmoothingQuality = "high";
  g.drawImage(source, 0, 0, out.width, out.height);
  const [w, h] = [out.width, out.height];
  const r = rng(seed * 7 + 1);
  if (rain) {
    g.lineCap = "round";
    for (let i = 0; i < 520; i++) {
      const [x, y, len] = [r() * w * 1.1, r() * h, 14 + r() * 46];
      g.strokeStyle = `rgba(205,220,235,${0.035 + r() * 0.11})`;
      g.lineWidth = 0.6 + r() * 0.9;
      g.beginPath();
      g.moveTo(x, y);
      g.lineTo(x - len * 0.2, y + len);
      g.stroke();
    }
  }
  const corner = g.createRadialGradient(w / 2, h * 0.48, h * 0.34, w / 2, h * 0.5, h * 0.98);
  corner.addColorStop(0, "rgba(0,0,0,0)");
  corner.addColorStop(1, "rgba(0,0,0,0.5)");
  g.fillStyle = corner;
  g.fillRect(0, 0, w, h);
  const noise = g.getImageData(0, 0, w, h);
  for (let i = 0; i < noise.data.length; i += 4) {
    const n = (r() - 0.5) * 16;
    noise.data[i] += n;
    noise.data[i + 1] += n;
    noise.data[i + 2] += n;
  }
  g.putImageData(noise, 0, 0);
}
