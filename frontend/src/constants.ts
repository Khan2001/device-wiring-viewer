/** Stable layout and persistence values shared by the canvas views. */
export const CONNECTION_COLORS = [
  { label: "黑色", value: "#202124" },
  { label: "灰色", value: "#6b7280" },
  { label: "红色", value: "#d64545" },
  { label: "蓝色", value: "#2864c7" }
] as const;

export const DEFAULT_CONNECTION_COLOR = CONNECTION_COLORS[1].value;

export const GRID_SIZE = 20;
export const CABINET_CANVAS_SIZE = { width: 132, height: 270 };
export const ROOM_MIN_SIZE = { width: 900, height: 600 };
export const ROOM_PADDING = { x: 100, y: 90 };
export const RACK_UNIT_PX = 20;
export const DEVICE_CELL = { width: 64, height: 52 };
export const DEVICE_PADDING = { x: 36, y: 92 };
export const VIEW_STATE_PREFIX = "device-wiring-view:";
