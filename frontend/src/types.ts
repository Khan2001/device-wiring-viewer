export interface Project {
  id: number;
  name: string;
  code: string;
  description: string;
}

export interface Room {
  id: number;
  project_id: number;
  name: string;
  code: string;
  width: number;
  height: number;
  note: string;
}

export interface Cabinet {
  id: number;
  room_id: number;
  name: string;
  code: string;
  height_u: number;
  x: number;
  y: number;
  note: string;
}

export interface Device {
  id: number;
  cabinet_id: number;
  name: string;
  code: string;
  category: string;
  vendor: string;
  model: string;
  management_ip: string;
  start_u: number;
  height_u: number;
  side: string;
  status: string;
  note: string;
  image_url: string;
  canvas_width: number;
  canvas_height: number;
  cell_width: number;
  cell_height: number;
}

export interface Port {
  id: number;
  device_id: number;
  name: string;
  port_type: string;
  side: string;
  position: number;
  grid_x: number;
  grid_y: number;
  note: string;
}

export interface PortBatchCreate {
  prefix: string;
  start_number: number;
  count: number;
  port_type: string;
  side: string;
  position_start: number;
  note: string;
}

export interface Connection {
  id: number;
  source_port_id: number;
  target_port_id: number;
  name: string;
  cable_type: string;
  color: string;
  note: string;
}

export interface ViewItem {
  id: number;
  room_id: number;
  object_type: string;
  object_id: number;
  x: number;
  y: number;
  width: number;
  height: number;
}
