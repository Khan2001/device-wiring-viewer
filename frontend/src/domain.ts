import type { Cabinet, Connection, Device, Port, Room } from "./types";

/** Shared page-level state types. API resource types remain in types.ts. */
export type ViewMode = "room" | "cabinet" | "device";
export type ServiceState = "checking" | "ok" | "error";
export type DeviceFace = "front" | "back";
export type SearchResults = {
  rooms: Room[];
  cabinets: Cabinet[];
  devices: Device[];
  ports: Port[];
};

export type ConnectionForm = Pick<
  Connection,
  "source_port_id" | "target_port_id" | "name" | "cable_type" | "color" | "note"
>;
