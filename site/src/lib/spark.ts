// A sparkline: one thin line, coloured by whether the period ended up or down, with the last
// point marked. Its numbers are in the table next to it, so it carries no axis.
import { svg } from "./dom";

export function sparkline(values: number[], width = 96, height = 28): SVGSVGElement {
  const s = svg("svg", { width, height, viewBox: `0 0 ${width} ${height}`, "aria-hidden": "true", class: "inline-block align-middle" });
  if (values.length < 2) return s;
  const lo = Math.min(...values), hi = Math.max(...values);
  const x = (i: number) => 2 + (i / (values.length - 1)) * (width - 4);
  const y = (v: number) => 2 + (hi === lo ? (height - 4) / 2 : ((hi - v) / (hi - lo)) * (height - 4));
  const up = values[values.length - 1] >= values[0];
  s.append(svg("path", { d: values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" "), fill: "none", class: up ? "stroke-up" : "stroke-down", "stroke-width": 1.25, "stroke-linejoin": "round" }));
  s.append(svg("circle", { cx: x(values.length - 1), cy: y(values[values.length - 1]), r: 2.25, class: up ? "fill-up" : "fill-down" }));
  return s;
}
