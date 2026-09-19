import type { Connection, Port } from "./types";
import { DEVICE_CELL, DEVICE_PADDING } from "./constants";

export type Point = { x: number; y: number };
export type ConnectionCurve = { d: string; anchor?: Point; arrow?: string };

/** Keeps SVG coordinate rules independent from Vue rendering and interaction code. */
export function portPoint(port: Port): Point {
  return {
    x: DEVICE_PADDING.x + (port.grid_x + 0.5) * DEVICE_CELL.width,
    y: DEVICE_PADDING.y + (port.grid_y + 0.5) * DEVICE_CELL.height
  };
}

function arrowPolygon(tip: Point, from: Point): string {
  const angle = Math.atan2(tip.y - from.y, tip.x - from.x);
  const length = 10;
  const halfWidth = 4.5;
  const base = {
    x: tip.x - Math.cos(angle) * length,
    y: tip.y - Math.sin(angle) * length
  };
  const normal = { x: -Math.sin(angle), y: Math.cos(angle) };
  const left = { x: base.x + normal.x * halfWidth, y: base.y + normal.y * halfWidth };
  const right = { x: base.x - normal.x * halfWidth, y: base.y - normal.y * halfWidth };
  return `${tip.x},${tip.y} ${left.x},${left.y} ${right.x},${right.y}`;
}

function externalAnchor(index: number, total: number, canvasWidth: number): Point {
  const minGap = 92;
  const sidePadding = 48;
  const rowGap = 30;
  const columns = Math.max(1, Math.min(total || 1, Math.floor((canvasWidth - sidePadding * 2) / minGap)));
  const row = Math.floor(index / columns);
  const column = index % columns;
  const rowStart = row * columns;
  const columnsInRow = Math.max(1, Math.min(columns, (total || 1) - rowStart));
  const usableWidth = Math.max(1, canvasWidth - sidePadding * 2);
  return {
    x: sidePadding + ((column + 1) * usableWidth) / (columnsInRow + 1),
    y: 76 - row * rowGap
  };
}

/** Build stable SVG paths for local curves and external upward routes. */
export function connectionCurve(
  connection: Connection,
  index: number,
  ports: Port[],
  visiblePorts: Port[],
  canvasWidth: number,
  externalTotal = 0
): ConnectionCurve {
  const source = ports.find((port) => port.id === connection.source_port_id);
  const target = ports.find((port) => port.id === connection.target_port_id);
  const sourceLocal = source && visiblePorts.some((port) => port.id === source.id);
  const targetLocal = target && visiblePorts.some((port) => port.id === target.id);
  const anchor = externalAnchor(index, externalTotal, canvasWidth);

  if (sourceLocal && source && targetLocal && target) {
    const sourcePoint = portPoint(source);
    const targetPoint = portPoint(target);
    const midpoint = {
      x: (sourcePoint.x + targetPoint.x) / 2,
      y: (sourcePoint.y + targetPoint.y) / 2
    };
    const control = {
      x: midpoint.x + ((index % 5) - 2) * 26,
      y: midpoint.y - 46
    };
    return {
      d: `M ${sourcePoint.x} ${sourcePoint.y} Q ${control.x} ${control.y} ${targetPoint.x} ${targetPoint.y}`,
      arrow: arrowPolygon(targetPoint, control)
    };
  }

  const localPort = sourceLocal ? source : targetLocal ? target : undefined;
  if (!localPort) return { d: `M ${anchor.x} ${anchor.y} L ${anchor.x} ${anchor.y}`, anchor };
  const point = portPoint(localPort);
  const control = { x: point.x, y: Math.max(anchor.y + 22, 98) };
  return {
    d: `M ${point.x} ${point.y} Q ${control.x} ${control.y} ${anchor.x} ${anchor.y}`,
    anchor,
    arrow: arrowPolygon(anchor, control)
  };
}
