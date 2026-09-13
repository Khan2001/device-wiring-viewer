<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { UploadFile } from "element-plus";
import {
  ArrowRight,
  Connection as ConnectionIcon,
  Delete,
  Edit,
  Expand,
  Link,
  MapLocation,
  Plus,
  Search,
  Setting,
  ZoomIn,
  ZoomOut
} from "@element-plus/icons-vue";
import { api, uploadImage } from "./api";
import type {
  Cabinet,
  Connection,
  Device,
  Port,
  PortBatchCreate,
  Project,
  Room,
  ViewItem
} from "./types";

type ViewMode = "room" | "cabinet" | "device";
type ServiceState = "checking" | "ok" | "error";
type SearchResults = { rooms: Room[]; cabinets: Cabinet[]; devices: Device[]; ports: Port[] };

const apiState = ref<ServiceState>("checking");
const dbState = ref<ServiceState>("checking");
const loading = ref(true);
const saving = ref(false);
const viewMode = ref<ViewMode>("room");
const zoom = ref(1);
const pan = ref({ x: 0, y: 0 });
const snapToGrid = ref(true);
const svgRef = ref<SVGSVGElement>();

const projects = ref<Project[]>([]);
const rooms = ref<Room[]>([]);
const cabinets = ref<Cabinet[]>([]);
const devices = ref<Device[]>([]);
const ports = ref<Port[]>([]);
const allDevices = ref<Device[]>([]);
const allPorts = ref<Port[]>([]);
const connections = ref<Connection[]>([]);
const viewItems = ref<ViewItem[]>([]);
const selectedCabinet = ref<Cabinet>();
const selectedDevice = ref<Device>();
const selectedPort = ref<Port>();
const connectionDialog = ref(false);
const editingConnectionId = ref(0);
const portDragState = ref<{ source: Port; point: { x: number; y: number } }>();
const suppressNextPortClick = ref(false);
const searchQuery = ref("");
const searchResults = ref<SearchResults>();
const searchOpen = ref(false);
const topologyDialog = ref(false);
const topologyRootPort = ref<Port>();
const importInput = ref<HTMLInputElement>();

const projectDialog = ref(false);
const roomDialog = ref(false);
const cabinetDialog = ref(false);
const deviceDialog = ref(false);
const portDialog = ref(false);
const portBatchDialog = ref(false);
const projectForm = ref({ name: "", code: "", description: "" });
const roomForm = ref({ name: "", code: "", width: 1200, height: 800, note: "" });
const cabinetForm = ref({ name: "", code: "", height_u: 42, note: "" });
const deviceForm = ref({
  name: "",
  code: "",
  category: "交换机",
  vendor: "",
  model: "",
  management_ip: "",
  start_u: 1,
  height_u: 1,
  side: "front",
  status: "在用",
  note: "",
  image_url: "",
  canvas_width: 8,
  canvas_height: 3
});
const portForm = ref({
  name: "",
  port_type: "网口",
  position: 0,
  grid_x: 0,
  grid_y: 0,
  note: ""
});
const portBatchForm = ref<PortBatchCreate>({
  prefix: "PORT-",
  start_number: 1,
  count: 24,
  port_type: "网口",
  position_start: 0,
  note: ""
});
const connectionForm = ref({
  source_port_id: 0,
  target_port_id: 0,
  name: "",
  cable_type: "网线",
  color: "#2f7d87",
  note: ""
});
const editingIds = ref({ project: 0, room: 0, cabinet: 0, device: 0, port: 0 });
const GRID_SIZE = 20;
const CABINET_CANVAS_SIZE = { width: 132, height: 270 };
const DEVICE_CELL = { width: 64, height: 52 };
const DEVICE_PADDING = { x: 36, y: 92 };
const VIEW_STATE_PREFIX = "device-wiring-view:";

const currentProject = computed(() => projects.value[0]);
const currentRoom = computed(() => rooms.value[0]);
const serviceReady = computed(() => apiState.value === "ok" && dbState.value === "ok");
const serviceLabel = computed(() =>
  apiState.value === "checking" || dbState.value === "checking"
    ? "检查中"
    : serviceReady.value
      ? "已连接"
      : "连接异常"
);
const roomTitle = computed(() => currentRoom.value?.name ?? "未创建机房");
const cabinetDevices = computed(() =>
  selectedCabinet.value
    ? devices.value.filter((device) => device.cabinet_id === selectedCabinet.value?.id)
    : []
);
const selectedDevicePorts = computed(() =>
  selectedDevice.value
    ? ports.value
        .filter((port) => port.device_id === selectedDevice.value?.id)
        .sort((left, right) => left.position - right.position || left.id - right.id)
    : []
);
const allPortsWithDevices = computed(() =>
  allPorts.value.map((port) => ({
    port,
    device: allDevices.value.find((device) => device.id === port.device_id)
  }))
);
const connectionTargetPorts = computed(() =>
  allPortsWithDevices.value
    .filter(({ port }) => port.device_id !== selectedDevice.value?.id)
    .slice(0, 200)
);
const visibleConnections = computed(() =>
  selectedDevice.value
    ? connections.value.filter((connection) =>
        selectedDevicePorts.value.some(
          (port) => port.id === connection.source_port_id || port.id === connection.target_port_id
        )
      )
    : connections.value
);
const connectedPortIds = computed(() => {
  const ids = new Set<number>();
  connections.value.forEach((connection) => {
    ids.add(connection.source_port_id);
    ids.add(connection.target_port_id);
  });
  return ids;
});
const deviceCanvasWidth = computed(() =>
  Math.max(360, (selectedDevice.value?.canvas_width ?? 8) * DEVICE_CELL.width + DEVICE_PADDING.x * 2)
);
const deviceCanvasHeight = computed(() =>
  Math.max(260, (selectedDevice.value?.canvas_height ?? 3) * DEVICE_CELL.height + DEVICE_PADDING.y + 64)
);
const topologySteps = computed(() => {
  const root = topologyRootPort.value;
  if (!root) return [];
  const steps: Array<{
    depth: number;
    port: Port;
    device?: Device;
    connection?: Connection;
    direction: "起点" | "上一跳" | "下一跳";
  }> = [];
  const queue = [{ portId: root.id, depth: 0, connection: undefined as Connection | undefined }];
  const visited = new Set<number>([root.id]);
  while (queue.length && steps.length < 24) {
    const current = queue.shift()!;
    const port = allPorts.value.find((item) => item.id === current.portId);
    if (!port) continue;
    steps.push({
      depth: current.depth,
      port,
      device: allDevices.value.find((item) => item.id === port.device_id),
      connection: current.connection,
      direction:
        current.depth === 0
          ? "起点"
          : current.connection?.source_port_id === current.portId
            ? "下一跳"
            : "上一跳"
    });
    if (current.depth >= 0) {
      connections.value
        .filter((connection) =>
          connection.source_port_id === current.portId || connection.target_port_id === current.portId
        )
        .forEach((connection) => {
          const peerId =
            connection.source_port_id === current.portId
              ? connection.target_port_id
              : connection.source_port_id;
          if (!visited.has(peerId)) {
            visited.add(peerId);
            queue.push({ portId: peerId, depth: current.depth + 1, connection });
          }
        });
    }
  }
  return steps;
});

function viewStateKey(roomId = currentRoom.value?.id): string {
  return roomId ? `${VIEW_STATE_PREFIX}${roomId}` : "";
}

function persistViewState(): void {
  const key = viewStateKey();
  if (!key) return;
  localStorage.setItem(
    key,
    JSON.stringify({ zoom: zoom.value, pan: pan.value })
  );
}

function restoreViewState(): void {
  const key = viewStateKey();
  if (!key) return;
  try {
    const saved = JSON.parse(localStorage.getItem(key) ?? "null") as
      | { zoom?: number; pan?: { x?: number; y?: number } }
      | null;
    if (!saved) return;
    if (typeof saved.zoom === "number" && saved.zoom >= 0.55 && saved.zoom <= 2.2) {
      zoom.value = saved.zoom;
    }
    if (
      saved.pan &&
      typeof saved.pan.x === "number" &&
      typeof saved.pan.y === "number"
    ) {
      pan.value = { x: saved.pan.x, y: saved.pan.y };
    }
  } catch {
    localStorage.removeItem(key);
  }
}

async function checkHealth(): Promise<void> {
  apiState.value = "checking";
  dbState.value = "checking";
  try {
    const apiHealth = await api.get<{ status: string }>("/api/health");
    apiState.value = apiHealth.status === "ok" ? "ok" : "error";
  } catch {
    apiState.value = "error";
  }
  try {
    const dbHealth = await api.get<{ status: string }>("/api/health/db");
    dbState.value = dbHealth.status === "ok" ? "ok" : "error";
  } catch {
    dbState.value = "error";
  }
}

async function loadWorkspace(): Promise<void> {
  loading.value = true;
  try {
    projects.value = await api.get<Project[]>("/api/projects");
    if (!projects.value.length) {
      const project = await api.post<Project>("/api/projects", {
        name: "默认项目",
        code: "DEFAULT",
        description: "机房设备可视化项目"
      });
      projects.value = [project];
    }
    rooms.value = await api.get<Room[]>(`/api/projects/${currentProject.value.id}/rooms`);
    if (!rooms.value.length) {
      const room = await api.post<Room>(`/api/projects/${currentProject.value.id}/rooms`, {
        name: "机房 A",
        code: "ROOM-A",
        width: 1200,
        height: 800,
        note: "默认机房"
      });
      rooms.value = [room];
    }
    cabinets.value = await api.get<Cabinet[]>(`/api/rooms/${currentRoom.value.id}/cabinets`);
    viewItems.value = await api.get<ViewItem[]>(`/api/rooms/${currentRoom.value.id}/view-items`);
    const cabinetLayouts = new Map(
      viewItems.value
        .filter((item) => item.object_type === "cabinet")
        .map((item) => [item.object_id, item])
    );
    cabinets.value = cabinets.value.map((cabinet) => {
      const layout = cabinetLayouts.get(cabinet.id);
      return layout ? { ...cabinet, x: layout.x, y: layout.y } : cabinet;
    });
    connections.value = await api.get<Connection[]>(
      `/api/projects/${currentProject.value.id}/connections`
    );
    allDevices.value = await api.get<Device[]>(
      `/api/projects/${currentProject.value.id}/devices`
    );
    allPorts.value = await api.get<Port[]>(
      `/api/projects/${currentProject.value.id}/ports`
    );
    devices.value = allDevices.value;
    ports.value = allPorts.value;
    if (selectedCabinet.value) {
      selectedCabinet.value = cabinets.value.find((item) => item.id === selectedCabinet.value?.id);
    }
    if (selectedDevice.value) {
      selectedDevice.value = allDevices.value.find((item) => item.id === selectedDevice.value?.id);
      ports.value = selectedDevice.value
        ? allPorts.value.filter((port) => port.device_id === selectedDevice.value?.id)
        : allPorts.value;
    }
    restoreViewState();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载工作区失败。");
  } finally {
    loading.value = false;
  }
}

async function loadCabinet(cabinet: Cabinet): Promise<void> {
  selectedCabinet.value = cabinet;
  selectedDevice.value = undefined;
  devices.value = await api.get<Device[]>(`/api/cabinets/${cabinet.id}/devices`);
  ports.value = allPorts.value;
  viewMode.value = "cabinet";
}

async function selectDevice(device: Device): Promise<void> {
  selectedDevice.value = device;
  ports.value = allPorts.value.length
    ? allPorts.value.filter((port) => port.device_id === device.id)
    : await api.get<Port[]>(`/api/devices/${device.id}/ports`);
  viewMode.value = "device";
  selectedPort.value = undefined;
}

async function backToCabinet(): Promise<void> {
  selectedDevice.value = undefined;
  selectedPort.value = undefined;
  if (selectedCabinet.value) await loadCabinet(selectedCabinet.value);
}

function resetView(): void {
  zoom.value = 1;
  pan.value = { x: 0, y: 0 };
  persistViewState();
}

function fitCanvas(): void {
  const room = currentRoom.value;
  if (!room || !cabinets.value.length) {
    resetView();
    return;
  }
  const padding = 80;
  const minX = Math.min(...cabinets.value.map((cabinet) => cabinet.x));
  const minY = Math.min(...cabinets.value.map((cabinet) => cabinet.y));
  const maxX = Math.max(
    ...cabinets.value.map((cabinet) => cabinet.x + CABINET_CANVAS_SIZE.width)
  );
  const maxY = Math.max(
    ...cabinets.value.map((cabinet) => cabinet.y + CABINET_CANVAS_SIZE.height)
  );
  const contentWidth = Math.max(maxX - minX + padding * 2, 1);
  const contentHeight = Math.max(maxY - minY + padding * 2, 1);
  const nextZoom = Math.min(room.width / contentWidth, room.height / contentHeight);
  zoom.value = Math.min(2.2, Math.max(0.55, Number(nextZoom.toFixed(2))));
  pan.value = {
    x: room.width / 2 - ((minX + maxX) / 2) * zoom.value,
    y: room.height / 2 - ((minY + maxY) / 2) * zoom.value
  };
  persistViewState();
}

function svgPoint(event: MouseEvent): { x: number; y: number } {
  const svg = svgRef.value;
  const matrix = svg?.getScreenCTM();
  if (!svg || !matrix) return { x: 0, y: 0 };
  const point = svg.createSVGPoint();
  point.x = event.clientX;
  point.y = event.clientY;
  const transformed = point.matrixTransform(matrix.inverse());
  return { x: transformed.x, y: transformed.y };
}

function canvasPoint(event: PointerEvent): { x: number; y: number } {
  const point = svgPoint(event);
  return {
    x: Math.round((point.x - pan.value.x) / zoom.value),
    y: Math.round((point.y - pan.value.y) / zoom.value)
  };
}

function zoomCanvas(delta: number, event?: WheelEvent): void {
  const previousZoom = zoom.value;
  const nextZoom = Math.min(2.2, Math.max(0.55, Number((previousZoom + delta).toFixed(2))));
  if (event && nextZoom !== previousZoom) {
    const pointer = svgPoint(event);
    const worldPoint = {
      x: (pointer.x - pan.value.x) / previousZoom,
      y: (pointer.y - pan.value.y) / previousZoom
    };
    zoom.value = nextZoom;
    pan.value = {
      x: pointer.x - worldPoint.x * nextZoom,
      y: pointer.y - worldPoint.y * nextZoom
    };
    persistViewState();
    return;
  }
  zoom.value = nextZoom;
  persistViewState();
}

function setViewMode(mode: ViewMode): void {
  viewMode.value = mode;
  if (mode === "room") {
    selectedDevice.value = undefined;
    selectedPort.value = undefined;
  }
}

let dragState: { id: number; offsetX: number; offsetY: number } | undefined;
function beginCabinetDrag(event: PointerEvent, cabinet: Cabinet): void {
  event.stopPropagation();
  const point = canvasPoint(event);
  dragState = { id: cabinet.id, offsetX: point.x - cabinet.x, offsetY: point.y - cabinet.y };
  selectedCabinet.value = cabinet;
  window.addEventListener("pointermove", moveCabinet);
  window.addEventListener("pointerup", endCabinetDrag, { once: true });
}

function moveCabinet(event: PointerEvent): void {
  if (!dragState) return;
  const cabinet = cabinets.value.find((item) => item.id === dragState?.id);
  if (!cabinet) return;
  const point = canvasPoint(event);
  const rawX = point.x - dragState.offsetX;
  const rawY = point.y - dragState.offsetY;
  const snappedX = snapToGrid.value ? Math.round(rawX / GRID_SIZE) * GRID_SIZE : rawX;
  const snappedY = snapToGrid.value ? Math.round(rawY / GRID_SIZE) * GRID_SIZE : rawY;
  const room = currentRoom.value;
  const maxX = Math.max(0, (room?.width ?? 1200) - CABINET_CANVAS_SIZE.width);
  const maxY = Math.max(0, (room?.height ?? 800) - CABINET_CANVAS_SIZE.height);
  cabinet.x = Math.round(Math.min(maxX, Math.max(0, snappedX)));
  cabinet.y = Math.round(Math.min(maxY, Math.max(0, snappedY)));
}

async function saveCabinetLayout(cabinet: Cabinet): Promise<void> {
  const room = currentRoom.value;
  if (!room) return;
  const layout = await api.put<ViewItem>(`/api/rooms/${room.id}/view-items`, {
    object_type: "cabinet",
    object_id: cabinet.id,
    x: cabinet.x,
    y: cabinet.y,
    width: CABINET_CANVAS_SIZE.width,
    height: CABINET_CANVAS_SIZE.height
  });
  const existingIndex = viewItems.value.findIndex((item) => item.id === layout.id);
  viewItems.value =
    existingIndex >= 0
      ? viewItems.value.map((item) => (item.id === layout.id ? layout : item))
      : [...viewItems.value, layout];
}

async function endCabinetDrag(): Promise<void> {
  window.removeEventListener("pointermove", moveCabinet);
  if (!dragState) return;
  const cabinet = cabinets.value.find((item) => item.id === dragState?.id);
  dragState = undefined;
  if (!cabinet) return;
  try {
    saving.value = true;
    const saved = await api.patch<Cabinet>(`/api/cabinets/${cabinet.id}`, {
      x: cabinet.x,
      y: cabinet.y
    });
    cabinets.value = cabinets.value.map((item) => (item.id === saved.id ? saved : item));
    await saveCabinetLayout(saved);
    ElMessage.success("机柜位置已保存");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存位置失败。");
  } finally {
    saving.value = false;
  }
}

let deviceDragState: { id: number; startY: number; startU: number } | undefined;
function beginDeviceDrag(event: PointerEvent, device: Device): void {
  event.stopPropagation();
  if (!selectedCabinet.value) return;
  deviceDragState = { id: device.id, startY: event.clientY, startU: device.start_u };
  selectedDevice.value = device;
  window.addEventListener("pointermove", moveDevice);
  window.addEventListener("pointerup", endDeviceDrag, { once: true });
}

function moveDevice(event: PointerEvent): void {
  if (!deviceDragState || !selectedCabinet.value) return;
  const device = cabinetDevices.value.find((item) => item.id === deviceDragState?.id);
  if (!device) return;
  const deltaU = Math.round((event.clientY - deviceDragState.startY) / (15 * zoom.value)) * -1;
  const nextU = Math.max(
    1,
    Math.min(selectedCabinet.value.height_u - device.height_u + 1, deviceDragState.startU + deltaU)
  );
  const collision = cabinetDevices.value.some((other) => {
    if (other.id === device.id) return false;
    return (
      nextU <= other.start_u + other.height_u - 1 &&
      other.start_u <= nextU + device.height_u - 1
    );
  });
  if (!collision) device.start_u = nextU;
}

async function endDeviceDrag(): Promise<void> {
  window.removeEventListener("pointermove", moveDevice);
  if (!deviceDragState) return;
  const device = cabinetDevices.value.find((item) => item.id === deviceDragState?.id);
  deviceDragState = undefined;
  if (!device) return;
  try {
    saving.value = true;
    const saved = await api.patch<Device>(`/api/devices/${device.id}`, {
      name: device.name,
      code: device.code,
      category: device.category,
      vendor: device.vendor,
      model: device.model,
      management_ip: device.management_ip,
      start_u: device.start_u,
      height_u: device.height_u,
      side: device.side,
      status: device.status,
      note: device.note,
      image_url: device.image_url,
      canvas_width: device.canvas_width,
      canvas_height: device.canvas_height
    });
    devices.value = devices.value.map((item) => (item.id === saved.id ? saved : item));
    allDevices.value = allDevices.value.map((item) => (item.id === saved.id ? saved : item));
    selectedDevice.value = saved;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "设备位置保存失败。");
  } finally {
    saving.value = false;
  }
}

function startPan(event: PointerEvent): void {
  if (event.button !== 0 || (event.target as Element)?.closest(".canvas-object")) {
    return;
  }
  const start = { x: event.clientX, y: event.clientY, panX: pan.value.x, panY: pan.value.y };
  const move = (current: PointerEvent) => {
    pan.value = {
      x: start.panX + (current.clientX - start.x) / zoom.value,
      y: start.panY + (current.clientY - start.y) / zoom.value
    };
    persistViewState();
  };
  const end = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", end);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", end);
}

function openProjectDialog(): void {
  editingIds.value.project = currentProject.value?.id ?? 0;
  projectForm.value = {
    name: currentProject.value?.name ?? "",
    code: currentProject.value?.code ?? "",
    description: currentProject.value?.description ?? ""
  };
  projectDialog.value = true;
}

function openRoomDialog(): void {
  editingIds.value.room = currentRoom.value?.id ?? 0;
  roomForm.value = {
    name: currentRoom.value?.name ?? "",
    code: currentRoom.value?.code ?? "",
    width: currentRoom.value?.width ?? 1200,
    height: currentRoom.value?.height ?? 800,
    note: currentRoom.value?.note ?? ""
  };
  roomDialog.value = true;
}

function openCabinetDialog(cabinet?: Cabinet): void {
  editingIds.value.cabinet = cabinet?.id ?? 0;
  cabinetForm.value = {
    name: cabinet?.name ?? `机柜 ${String(cabinets.value.length + 1).padStart(2, "0")}`,
    code: cabinet?.code ?? `RACK-${String(cabinets.value.length + 1).padStart(2, "0")}`,
    height_u: cabinet?.height_u ?? 42,
    note: cabinet?.note ?? ""
  };
  cabinetDialog.value = true;
}

function openDeviceDialog(device?: Device): void {
  editingIds.value.device = device?.id ?? 0;
  deviceForm.value = {
    name: device?.name ?? "新设备",
    code: device?.code ?? `DEV-${String(cabinetDevices.value.length + 1).padStart(2, "0")}`,
    category: device?.category ?? "交换机",
    vendor: device?.vendor ?? "",
    model: device?.model ?? "",
    management_ip: device?.management_ip ?? "",
    start_u: device?.start_u ?? 1,
    height_u: device?.height_u ?? 1,
    side: device?.side ?? "front",
    status: device?.status ?? "在用",
    note: device?.note ?? "",
    image_url: device?.image_url ?? "",
    canvas_width: device?.canvas_width ?? 8,
    canvas_height: device?.canvas_height ?? 3
  };
  deviceDialog.value = true;
}

function openPortDialog(port?: Port): void {
  if (!selectedDevice.value) return;
  editingIds.value.port = port?.id ?? 0;
  portForm.value = {
    name: port?.name ?? `PORT-${String(selectedDevicePorts.value.length + 1).padStart(2, "0")}`,
    port_type: port?.port_type ?? "网口",
    position: port?.position ?? selectedDevicePorts.value.length,
    grid_x: port?.grid_x ?? selectedDevicePorts.value.length % (selectedDevice.value.canvas_width || 8),
    grid_y: port?.grid_y ?? Math.floor(selectedDevicePorts.value.length / (selectedDevice.value.canvas_width || 8)),
    note: port?.note ?? ""
  };
  portDialog.value = true;
}

function openPortBatchDialog(): void {
  if (!selectedDevice.value) return;
  const isFiberBox = selectedDevice.value.category === "光纤盒";
  portBatchForm.value = {
    prefix: isFiberBox ? "PORT-F-" : "PORT-",
    start_number: 1,
    count: 24,
    port_type: isFiberBox ? "光口" : "网口",
    position_start: selectedDevicePorts.value.length,
    note: ""
  };
  portBatchDialog.value = true;
}

async function saveProject(): Promise<void> {
  try {
    if (editingIds.value.project) {
      const project = await api.patch<Project>(`/api/projects/${editingIds.value.project}`, {
        name: projectForm.value.name,
        description: projectForm.value.description
      });
      projects.value = [project];
    } else {
      projects.value = [await api.post<Project>("/api/projects", projectForm.value)];
    }
    projectDialog.value = false;
    ElMessage.success("项目已保存");
    await loadWorkspace();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "项目保存失败。");
  }
}

async function saveRoom(): Promise<void> {
  try {
    const payload = roomForm.value;
    const room = editingIds.value.room
      ? await api.patch<Room>(`/api/rooms/${editingIds.value.room}`, payload)
      : await api.post<Room>(`/api/projects/${currentProject.value.id}/rooms`, payload);
    rooms.value = [room];
    roomDialog.value = false;
    ElMessage.success("机房已保存");
    await loadWorkspace();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "机房保存失败。");
  }
}

async function saveCabinet(): Promise<void> {
  try {
    const payload = cabinetForm.value;
    const cabinet = editingIds.value.cabinet
      ? await api.patch<Cabinet>(`/api/cabinets/${editingIds.value.cabinet}`, payload)
      : await api.post<Cabinet>(`/api/rooms/${currentRoom.value.id}/cabinets`, {
          ...payload,
          x: 80 + cabinets.value.length * 170,
          y: 110
        });
    cabinets.value = editingIds.value.cabinet
      ? cabinets.value.map((item) => (item.id === cabinet.id ? cabinet : item))
      : [...cabinets.value, cabinet];
    await saveCabinetLayout(cabinet);
    cabinetDialog.value = false;
    selectedCabinet.value = cabinet;
    ElMessage.success("机柜已保存");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "机柜保存失败。");
  }
}

async function saveDevice(): Promise<void> {
  if (!selectedCabinet.value) return;
  try {
    const device = editingIds.value.device
      ? await api.patch<Device>(`/api/devices/${editingIds.value.device}`, deviceForm.value)
      : await api.post<Device>(`/api/cabinets/${selectedCabinet.value.id}/devices`, deviceForm.value);
    devices.value = editingIds.value.device
      ? devices.value.map((item) => (item.id === device.id ? device : item))
      : [...devices.value, device];
    allDevices.value = editingIds.value.device
      ? allDevices.value.map((item) => (item.id === device.id ? device : item))
      : [...allDevices.value, device];
    deviceDialog.value = false;
    selectedDevice.value = device;
    ports.value = await api.get<Port[]>(`/api/devices/${device.id}/ports`);
    ElMessage.success("设备已保存");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "设备保存失败。");
  }
}

async function savePort(): Promise<void> {
  if (!selectedDevice.value) return;
  try {
    const port = editingIds.value.port
      ? await api.patch<Port>(`/api/ports/${editingIds.value.port}`, portForm.value)
      : await api.post<Port>(`/api/devices/${selectedDevice.value.id}/ports`, portForm.value);
    ports.value = editingIds.value.port
      ? ports.value.map((item) => (item.id === port.id ? port : item))
      : [...ports.value, port];
    allPorts.value = editingIds.value.port
      ? allPorts.value.map((item) => (item.id === port.id ? port : item))
      : [...allPorts.value, port];
    portDialog.value = false;
    ElMessage.success("接口已保存");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "接口保存失败。");
  }
}

async function savePortBatch(): Promise<void> {
  if (!selectedDevice.value) return;
  try {
    const created = await api.post<Port[]>(
      `/api/devices/${selectedDevice.value.id}/ports/bulk`,
      portBatchForm.value
    );
    ports.value = [...ports.value, ...created];
    allPorts.value = [...allPorts.value, ...created];
    portBatchDialog.value = false;
    ElMessage.success(`已生成 ${created.length} 个接口`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "批量生成接口失败。");
  }
}

async function removePort(port: Port): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除接口 ${port.name} 吗？已连接接口需要先删除连接。`,
      "删除接口",
      {
        type: "warning",
        confirmButtonText: "删除",
        cancelButtonText: "取消"
      }
    );
    await api.delete(`/api/ports/${port.id}`);
    ports.value = ports.value.filter((item) => item.id !== port.id);
    allPorts.value = allPorts.value.filter((item) => item.id !== port.id);
    portDialog.value = false;
    ElMessage.success("接口已删除");
  } catch (error) {
    if (error instanceof Error) ElMessage.error(error.message);
  }
}

function openConnectionDialog(source?: Port, target?: Port): void {
  if (!source || !target) return;
  editingConnectionId.value = 0;
  connectionForm.value = {
    source_port_id: source.id,
    target_port_id: target.id,
    name: `${source.name} → ${target.name}`,
    cable_type: source.port_type === "光口" || target.port_type === "光口" ? "光纤" : "网线",
    color: source.port_type === "光口" || target.port_type === "光口" ? "#b46a34" : "#2f7d87",
    note: ""
  };
  connectionDialog.value = true;
}

function openConnectionEditor(connection: Connection): void {
  editingConnectionId.value = connection.id;
  connectionForm.value = {
    source_port_id: connection.source_port_id,
    target_port_id: connection.target_port_id,
    name: connection.name,
    cable_type: connection.cable_type,
    color: connection.color,
    note: connection.note
  };
  connectionDialog.value = true;
}

function openPortTopology(port: Port): void {
  topologyRootPort.value = port;
  topologyDialog.value = true;
}

function openConnectionTopology(connection: Connection): void {
  const port = allPorts.value.find((item) => item.id === connection.source_port_id);
  if (port) openPortTopology(port);
}

async function focusTopologyPort(port: Port): Promise<void> {
  const device = allDevices.value.find((item) => item.id === port.device_id);
  const cabinet = device ? cabinets.value.find((item) => item.id === device.cabinet_id) : undefined;
  if (device && cabinet) {
    await loadCabinet(cabinet);
    await selectDevice(device);
    selectedPort.value = port;
  }
  topologyDialog.value = false;
}

async function saveConnection(): Promise<void> {
  try {
    const connection = editingConnectionId.value
      ? await api.patch<Connection>(
          `/api/connections/${editingConnectionId.value}`,
          connectionForm.value
        )
      : await api.post<Connection>("/api/connections", connectionForm.value);
    connections.value = editingConnectionId.value
      ? connections.value.map((item) => (item.id === connection.id ? connection : item))
      : [...connections.value, connection];
    connectionDialog.value = false;
    ElMessage.success(editingConnectionId.value ? "连接已更新" : "连接已保存");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "连接保存失败。");
  }
}

async function removeConnection(connection: Connection): Promise<void> {
  try {
    await ElMessageBox.confirm("确定删除这条连接吗？", "删除连接", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消"
    });
    await api.delete(`/api/connections/${connection.id}`);
    connections.value = connections.value.filter((item) => item.id !== connection.id);
    ElMessage.success("连接已删除");
  } catch {
    // Cancelled deletion is intentionally silent.
  }
}

async function search(): Promise<void> {
  if (!searchQuery.value.trim() || !currentProject.value) {
    searchResults.value = undefined;
    return;
  }
  try {
    searchResults.value = await api.get<SearchResults>(
      `/api/projects/${currentProject.value.id}/search?q=${encodeURIComponent(searchQuery.value)}`
    );
    searchOpen.value = true;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "搜索失败。");
  }
}

async function focusSearchDevice(device: Device): Promise<void> {
  const cabinet = cabinets.value.find((item) => item.id === device.cabinet_id);
  if (cabinet) {
    await loadCabinet(cabinet);
    await selectDevice(device);
  }
  searchOpen.value = false;
}

async function focusSearchCabinet(cabinet: Cabinet): Promise<void> {
  await loadCabinet(cabinet);
  searchOpen.value = false;
}

function focusSearchRoom(room: Room): void {
  if (currentRoom.value?.id === room.id) setViewMode("room");
  searchOpen.value = false;
}

async function focusSearchPort(port: Port): Promise<void> {
  const device = allDevices.value.find((item) => item.id === port.device_id);
  const cabinet = device ? cabinets.value.find((item) => item.id === device.cabinet_id) : undefined;
  if (device && cabinet) {
    await loadCabinet(cabinet);
    await selectDevice(device);
    selectedPort.value = port;
  }
  searchOpen.value = false;
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function exportProject(): void {
  const payload = {
    project: currentProject.value,
    room: currentRoom.value,
    cabinets: cabinets.value,
    devices: allDevices.value,
    ports: allPorts.value,
    connections: connections.value,
    view_items: viewItems.value
  };
  downloadBlob(
    new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
    `${currentProject.value?.code ?? "project"}-export.json`
  );
}

function chooseImport(): void {
  importInput.value?.click();
}

async function onImportSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text()) as unknown;
    const project = await api.post<Project>("/api/projects/import", payload);
    projects.value = [project];
    rooms.value = [];
    cabinets.value = [];
    devices.value = [];
    ports.value = [];
    allDevices.value = [];
    allPorts.value = [];
    connections.value = [];
    viewItems.value = [];
    selectedCabinet.value = undefined;
    selectedDevice.value = undefined;
    selectedPort.value = undefined;
    viewMode.value = "room";
    await loadWorkspace();
    ElMessage.success("项目已导入");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "项目导入失败。");
  } finally {
    input.value = "";
  }
}

function exportSvg(): void {
  const svg = svgRef.value;
  if (!svg) return;
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(currentRoom.value?.width ?? 1200));
  clone.setAttribute("height", String(currentRoom.value?.height ?? 800));
  const cssRules = Array.from(document.styleSheets).flatMap((sheet) => {
    try {
      return Array.from(sheet.cssRules).map((rule) => rule.cssText);
    } catch {
      return [];
    }
  });
  const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
  style.textContent = cssRules.join("\n");
  clone.insertBefore(style, clone.firstChild);
  downloadBlob(
    new Blob([new XMLSerializer().serializeToString(clone)], {
      type: "image/svg+xml;charset=utf-8"
    }),
    `${currentProject.value?.code ?? "project"}-view.svg`
  );
}

async function exportPng(): Promise<void> {
  const svg = svgRef.value;
  if (!svg) return;
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const width = currentRoom.value?.width ?? 1200;
  const height = currentRoom.value?.height ?? 800;
  clone.setAttribute("width", String(width));
  clone.setAttribute("height", String(height));
  const cssRules = Array.from(document.styleSheets).flatMap((sheet) => {
    try {
      return Array.from(sheet.cssRules).map((rule) => rule.cssText);
    } catch {
      return [];
    }
  });
  const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
  style.textContent = cssRules.join("\n");
  clone.insertBefore(style, clone.firstChild);
  const svgBlob = new Blob([new XMLSerializer().serializeToString(clone)], {
    type: "image/svg+xml;charset=utf-8"
  });
  const imageUrl = URL.createObjectURL(svgBlob);
  try {
    const image = new Image();
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error("SVG 转 PNG 失败。"));
      image.src = imageUrl;
    });
    const scale = Math.min(2, 4000 / Math.max(width, height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("浏览器不支持 PNG 导出。");
    context.fillStyle = "#f8fbfb";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("PNG 导出失败。");
    downloadBlob(blob, `${currentProject.value?.code ?? "project"}-view.png`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "PNG 导出失败。");
  } finally {
    URL.revokeObjectURL(imageUrl);
  }
}

async function onImageSelected(event: Event | UploadFile): Promise<void> {
  const file = event instanceof Event
    ? (event.target as HTMLInputElement).files?.[0]
    : event.raw;
  if (!file || !selectedDevice.value) return;
  try {
    const response = await uploadImage(`/api/devices/${selectedDevice.value.id}/image`, file);
    const device = (await response.json()) as Device;
    selectedDevice.value = device;
    devices.value = devices.value.map((item) => (item.id === device.id ? device : item));
    allDevices.value = allDevices.value.map((item) => (item.id === device.id ? device : item));
    ElMessage.success("设备图片已上传");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "图片上传失败。");
  } finally {
    if (event instanceof Event) (event.target as HTMLInputElement).value = "";
  }
}

async function removeDeviceImage(): Promise<void> {
  if (!selectedDevice.value?.image_url) return;
  try {
    await ElMessageBox.confirm("确定删除当前设备图片吗？", "删除图片", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消"
    });
    const device = await api.delete<Device>(`/api/devices/${selectedDevice.value.id}/image`);
    selectedDevice.value = device;
    devices.value = devices.value.map((item) => (item.id === device.id ? device : item));
    allDevices.value = allDevices.value.map((item) => (item.id === device.id ? device : item));
    ElMessage.success("设备图片已删除");
  } catch (error) {
    if (error instanceof Error) ElMessage.error(error.message);
  }
}

async function removeSelectedDevice(): Promise<void> {
  if (!selectedDevice.value) return;
  const deviceId = selectedDevice.value.id;
  const devicePortIds = allPorts.value
    .filter((port) => port.device_id === deviceId)
    .map((port) => port.id);
  try {
    await ElMessageBox.confirm("删除设备会同时删除它的接口，是否继续？", "删除设备", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消"
    });
    await api.delete(`/api/devices/${deviceId}`);
    devices.value = devices.value.filter((item) => item.id !== deviceId);
    allDevices.value = allDevices.value.filter((item) => item.id !== deviceId);
    allPorts.value = allPorts.value.filter((port) => port.device_id !== deviceId);
    connections.value = connections.value.filter(
      (connection) =>
        !devicePortIds.includes(connection.source_port_id) &&
        !devicePortIds.includes(connection.target_port_id)
    );
    selectedDevice.value = undefined;
    ports.value = [];
    ElMessage.success("设备已删除");
  } catch {
    // Cancelled deletion is intentionally silent.
  }
}

function statusLabel(state: ServiceState): string {
  return state === "checking" ? "检查中" : state === "ok" ? "正常" : "异常";
}

function portPoint(port: Port): { x: number; y: number } {
  return {
    x: DEVICE_PADDING.x + (port.grid_x + 0.5) * DEVICE_CELL.width,
    y: DEVICE_PADDING.y + (port.grid_y + 0.5) * DEVICE_CELL.height
  };
}

function portPointFor(port: Port): { x: number; y: number } {
  return portPoint(port);
}

function portLabel(port: Port): string {
  const device = allDevices.value.find((item) => item.id === port.device_id);
  return `${device?.name ?? "未知设备"} · ${port.name}`;
}

function connectionPeer(connection: Connection): string {
  const localPortIds = new Set(selectedDevicePorts.value.map((port) => port.id));
  const peerId = localPortIds.has(connection.source_port_id)
    ? connection.target_port_id
    : connection.source_port_id;
  const port = allPorts.value.find((item) => item.id === peerId);
  return port ? portLabel(port) : "未找到对端接口";
}

function connectionEndpoint(connection: Connection): { local?: Port; peer?: Port } {
  const localPortIds = new Set(selectedDevicePorts.value.map((port) => port.id));
  const localId = localPortIds.has(connection.source_port_id)
    ? connection.source_port_id
    : connection.target_port_id;
  const peerId = localId === connection.source_port_id
    ? connection.target_port_id
    : connection.source_port_id;
  return {
    local: allPorts.value.find((port) => port.id === localId),
    peer: allPorts.value.find((port) => port.id === peerId)
  };
}

function connectionLine(connection: Connection, index: number): {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
} {
  const endpoint = connectionEndpoint(connection);
  const local = endpoint.local ? portPointFor(endpoint.local) : { x: 80, y: 255 };
  const peerIsLocal = endpoint.peer && endpoint.peer.device_id === selectedDevice.value?.id;
  if (peerIsLocal && endpoint.peer) {
    const peer = portPointFor(endpoint.peer);
    return { x1: local.x, y1: local.y, x2: peer.x, y2: peer.y };
  }
  return {
    x1: local.x,
    y1: local.y,
    x2: deviceCanvasWidth.value - 28,
    y2: 116 + index * 34
  };
}

function deviceCanvasPoint(event: PointerEvent): { x: number; y: number } {
  const point = svgPoint(event);
  const world = {
    x: (point.x - pan.value.x) / zoom.value,
    y: (point.y - pan.value.y) / zoom.value
  };
  return { x: world.x - 110, y: world.y - 105 };
}

function beginPortConnection(event: PointerEvent, port: Port): void {
  event.stopPropagation();
  portDragState.value = {
    source: port,
    point: portPointFor(port)
  };
  selectedPort.value = port;
  window.addEventListener("pointermove", movePortConnection);
  window.addEventListener("pointerup", endPortConnection, { once: true });
}

function movePortConnection(event: PointerEvent): void {
  if (!portDragState.value) return;
  portDragState.value.point = deviceCanvasPoint(event);
}

function endPortConnection(event: PointerEvent): void {
  window.removeEventListener("pointermove", movePortConnection);
  const drag = portDragState.value;
  portDragState.value = undefined;
  if (!drag) return;
  const targetElement = (event.target as Element | null)?.closest("[data-port-id]");
  const targetId = Number(targetElement?.getAttribute("data-port-id"));
  const target = selectedDevicePorts.value.find((port) => port.id === targetId);
  if (target && target.id !== drag.source.id) {
    suppressNextPortClick.value = true;
    openConnectionDialog(drag.source, target);
    selectedPort.value = undefined;
  }
}

function selectCanvasPort(port: Port): void {
  if (suppressNextPortClick.value) {
    suppressNextPortClick.value = false;
    return;
  }
  if (selectedPort.value && selectedPort.value.id !== port.id) {
    openConnectionDialog(selectedPort.value, port);
    selectedPort.value = undefined;
  } else {
    selectedPort.value = port;
  }
}

function selectConnectionTarget(port: Port): void {
  if (!selectedPort.value || selectedPort.value.id === port.id) return;
  openConnectionDialog(selectedPort.value, port);
  selectedPort.value = undefined;
}

function handleShortcut(event: KeyboardEvent): void {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    ElMessage.success("当前编辑已即时保存");
    return;
  }
  if (event.key === "Escape") {
    selectedPort.value = undefined;
    portDragState.value = undefined;
  }
}

onMounted(async () => {
  window.addEventListener("keydown", handleShortcut);
  await checkHealth();
  await loadWorkspace();
});

watch([zoom, () => pan.value.x, () => pan.value.y], persistViewState);

onUnmounted(() => {
  window.removeEventListener("keydown", handleShortcut);
});
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">DW</div>
        <div>
          <p class="eyebrow">设备接线台账</p>
          <h1>二维可视化编辑器</h1>
        </div>
      </div>
      <div class="top-actions">
        <el-tag :type="saving ? 'warning' : serviceReady ? 'success' : 'danger'" effect="plain">
          {{ saving ? "保存中" : serviceLabel }}
        </el-tag>
        <el-input
          v-model="searchQuery"
          class="search-input"
          clearable
          placeholder="搜索设备、IP、接口"
          @keyup.enter="search"
        >
          <template #append><el-button aria-label="搜索" @click="search"><el-icon><Search /></el-icon></el-button></template>
        </el-input>
        <el-button size="small" plain @click="exportProject"><el-icon><Link /></el-icon>导出 JSON</el-button>
        <el-button size="small" plain @click="chooseImport"><el-icon><Plus /></el-icon>导入 JSON</el-button>
        <el-button size="small" plain @click="exportSvg"><el-icon><MapLocation /></el-icon>导出 SVG</el-button>
        <el-button size="small" plain @click="exportPng"><el-icon><MapLocation /></el-icon>导出 PNG</el-button>
        <el-tooltip content="检查服务状态">
          <el-button size="small" circle plain aria-label="检查服务" @click="checkHealth"><el-icon><Setting /></el-icon></el-button>
        </el-tooltip>
        <input ref="importInput" class="hidden-input" type="file" accept="application/json,.json" @change="onImportSelected" />
      </div>
    </header>

    <main class="workspace">
      <aside class="sidebar">
        <div class="sidebar-head">
          <div>
            <p class="eyebrow">Workspace</p>
            <h2>{{ currentProject?.name ?? "项目" }}</h2>
          </div>
          <el-tooltip content="编辑项目">
            <el-button circle size="small" aria-label="编辑项目" @click="openProjectDialog"><el-icon><Edit /></el-icon></el-button>
          </el-tooltip>
        </div>

        <el-button class="full-button" type="primary" @click="openRoomDialog">
          <el-icon><MapLocation /></el-icon>
          {{ currentRoom ? "编辑机房" : "新建机房" }}
        </el-button>

        <div v-if="currentRoom" class="tree">
          <div class="tree-node room-node" :class="{ active: viewMode === 'room' }" @click="setViewMode('room')">
            <span class="node-icon">⌂</span>
            <span class="node-copy"><strong>{{ currentRoom.name }}</strong><small>{{ currentRoom.code }}</small></span>
            <span class="node-count">{{ cabinets.length }}</span>
          </div>
          <div class="tree-children">
            <div
              v-for="cabinet in cabinets"
              :key="cabinet.id"
              class="tree-node"
              :class="{ active: selectedCabinet?.id === cabinet.id && viewMode === 'cabinet' }"
              @click="loadCabinet(cabinet)"
            >
              <span class="node-icon cabinet-icon">▥</span>
              <span class="node-copy"><strong>{{ cabinet.code }}</strong><small>{{ cabinet.name }}</small></span>
              <el-tooltip content="编辑机柜">
                <el-button text circle size="small" aria-label="编辑机柜" @click.stop="openCabinetDialog(cabinet)"><el-icon><Edit /></el-icon></el-button>
              </el-tooltip>
            </div>
          </div>
        </div>
        <el-button class="full-button add-button" plain @click="openCabinetDialog()"><el-icon><Plus /></el-icon>新建机柜</el-button>

        <div class="sidebar-footer">
          <div class="service-line"><span class="status-dot" :class="`status-${apiState}`"></span> API {{ statusLabel(apiState) }}</div>
          <div class="service-line"><span class="status-dot" :class="`status-${dbState}`"></span> 数据库 {{ statusLabel(dbState) }}</div>
        </div>
      </aside>

      <section class="main-panel">
        <div class="toolbar">
          <div>
            <el-breadcrumb separator="/">
              <el-breadcrumb-item>{{ currentProject?.name }}</el-breadcrumb-item>
              <el-breadcrumb-item @click="setViewMode('room')">{{ roomTitle }}</el-breadcrumb-item>
              <el-breadcrumb-item v-if="selectedCabinet" @click="setViewMode('cabinet')">{{ selectedCabinet.code }}</el-breadcrumb-item>
              <el-breadcrumb-item v-if="viewMode === 'device' && selectedDevice">{{ selectedDevice.name }}</el-breadcrumb-item>
            </el-breadcrumb>
            <p class="view-hint">{{ viewMode === "room" ? "机房平面图 · 拖动机柜调整位置" : viewMode === "cabinet" ? "机柜视图 · 拖动设备调整 U 位" : "设备面板 · 端口可用于创建连接" }}</p>
          </div>
          <div class="toolbar-actions">
            <el-button-group>
              <el-button :type="viewMode === 'room' ? 'primary' : 'default'" @click="setViewMode('room')">机房</el-button>
              <el-button :type="viewMode === 'cabinet' ? 'primary' : 'default'" :disabled="!selectedCabinet" @click="setViewMode('cabinet')">机柜</el-button>
              <el-button :type="viewMode === 'device' ? 'primary' : 'default'" :disabled="!selectedDevice" @click="setViewMode('device')">设备</el-button>
            </el-button-group>
            <el-tooltip content="缩小">
              <el-button circle aria-label="缩小" @click="zoomCanvas(-0.1)"><el-icon><ZoomOut /></el-icon></el-button>
            </el-tooltip>
            <span class="zoom-value">{{ Math.round(zoom * 100) }}%</span>
            <el-tooltip content="放大">
              <el-button circle aria-label="放大" @click="zoomCanvas(0.1)"><el-icon><ZoomIn /></el-icon></el-button>
            </el-tooltip>
            <el-switch v-model="snapToGrid" inline-prompt active-text="吸附" inactive-text="自由" />
            <el-tooltip content="适配画布">
              <el-button plain aria-label="适配画布" @click="fitCanvas"><el-icon><Expand /></el-icon>适配</el-button>
            </el-tooltip>
          </div>
        </div>

        <div v-loading="loading" class="canvas-shell">
          <svg
            ref="svgRef"
            class="workspace-canvas"
            :viewBox="`0 0 ${currentRoom?.width ?? 1200} ${currentRoom?.height ?? 800}`"
            @pointerdown="startPan"
            @wheel.prevent="zoomCanvas($event.deltaY > 0 ? -0.1 : 0.1, $event)"
          >
            <defs>
              <pattern id="room-grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e2ebed" stroke-width="1" />
              </pattern>
            </defs>
            <g :transform="`translate(${pan.x} ${pan.y}) scale(${zoom})`">
              <rect class="room-surface" x="0" y="0" :width="currentRoom?.width ?? 1200" :height="currentRoom?.height ?? 800" rx="6" />
              <g v-if="viewMode === 'room'">
                <g v-for="cabinet in cabinets" :key="cabinet.id" class="canvas-object cabinet-object" :class="{ selected: selectedCabinet?.id === cabinet.id }" :transform="`translate(${cabinet.x} ${cabinet.y})`" @pointerdown="beginCabinetDrag($event, cabinet)" @dblclick.stop="loadCabinet(cabinet)" @click.stop="selectedCabinet = cabinet">
                  <rect class="cabinet-body" width="132" height="270" rx="4" />
                  <rect class="cabinet-top" width="132" height="35" rx="4" />
                  <text class="cabinet-code" x="14" y="23">{{ cabinet.code }}</text>
                  <text class="cabinet-name" x="66" y="55" text-anchor="middle">{{ cabinet.name }}</text>
                  <rect v-for="n in Math.min(cabinet.height_u, 12)" :key="n" class="rack-slot" x="16" :y="65 + (n - 1) * 15" width="100" height="9" rx="2" />
                  <text class="cabinet-meta" x="66" y="252" text-anchor="middle">{{ cabinet.height_u }}U · 双击进入</text>
                </g>
                <text v-if="!cabinets.length" class="empty-canvas" x="600" y="380" text-anchor="middle">从左侧新建第一个机柜</text>
              </g>
              <g v-else-if="viewMode === 'cabinet' && selectedCabinet" class="rack-view" transform="translate(90 45)">
                <rect class="rack-frame" width="390" height="690" rx="5" />
                <text class="rack-title" x="20" y="32">{{ selectedCabinet.code }} · {{ selectedCabinet.name }}</text>
                <g v-for="unit in selectedCabinet.height_u" :key="unit">
                  <line class="rack-line" x1="20" :y1="48 + (unit - 1) * 15" x2="370" :y2="48 + (unit - 1) * 15" />
                  <text class="rack-u" x="31" :y="60 + (unit - 1) * 15">{{ selectedCabinet.height_u - unit + 1 }}</text>
                </g>
                <g v-for="device in cabinetDevices" :key="device.id" class="canvas-object device-rack-item" :transform="`translate(52 ${48 + (selectedCabinet.height_u - device.start_u - device.height_u + 1) * 15})`" @pointerdown="beginDeviceDrag($event, device)" @click.stop="selectDevice(device)">
                  <rect class="device-bar" :class="{ selected: selectedDevice?.id === device.id, 'device-back': device.side === 'back' }" width="295" :height="Math.max(18, device.height_u * 15 - 2)" rx="3" />
                  <text class="device-label" x="12" y="14">{{ device.name }}</text>
                  <text class="device-u" x="280" y="14" text-anchor="end">{{ device.height_u }}U · {{ device.side === "back" ? "背" : "正" }}</text>
                </g>
                <text v-if="!cabinetDevices.length" class="empty-rack" x="195" y="350" text-anchor="middle">点击右侧添加设备</text>
              </g>
              <g v-else-if="viewMode === 'device' && selectedDevice" class="device-view" transform="translate(110 105)">
                <defs>
                  <marker id="connection-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
                    <path d="M0,0 L8,4 L0,8 Z" fill="#83939b" />
                  </marker>
                </defs>
                <rect class="device-panel" :width="deviceCanvasWidth" :height="deviceCanvasHeight" rx="6" />
                <rect class="device-panel-head" :width="deviceCanvasWidth" height="62" rx="6" />
                <text class="device-panel-title" x="24" y="28">{{ selectedDevice.name }}</text>
                <text class="device-panel-subtitle" x="24" y="48">{{ selectedDevice.code }} · {{ selectedDevice.category }} · {{ selectedDevice.vendor || "未填写厂商" }}</text>
                <image v-if="selectedDevice.image_url" :href="selectedDevice.image_url" :x="deviceCanvasWidth - 135" y="10" width="110" height="42" preserveAspectRatio="xMidYMid slice" />
                <g class="device-grid">
                  <line
                    v-for="column in selectedDevice.canvas_width + 1"
                    :key="`grid-x-${column}`"
                    :x1="DEVICE_PADDING.x + (column - 1) * DEVICE_CELL.width"
                    :y1="DEVICE_PADDING.y"
                    :x2="DEVICE_PADDING.x + (column - 1) * DEVICE_CELL.width"
                    :y2="DEVICE_PADDING.y + selectedDevice.canvas_height * DEVICE_CELL.height"
                  />
                  <line
                    v-for="row in selectedDevice.canvas_height + 1"
                    :key="`grid-y-${row}`"
                    :x1="DEVICE_PADDING.x"
                    :y1="DEVICE_PADDING.y + (row - 1) * DEVICE_CELL.height"
                    :x2="DEVICE_PADDING.x + selectedDevice.canvas_width * DEVICE_CELL.width"
                    :y2="DEVICE_PADDING.y + (row - 1) * DEVICE_CELL.height"
                  />
                </g>
                <g v-for="port in selectedDevicePorts" :key="port.id" class="port-handle canvas-object" :data-port-id="port.id" @pointerdown="beginPortConnection($event, port)" @click.stop="selectCanvasPort(port)">
                  <circle :cx="portPoint(port).x" :cy="portPoint(port).y" r="10" :class="{ 'port-selected': selectedPort?.id === port.id, 'port-connected': connectedPortIds.has(port.id) }" />
                  <text class="port-name" :x="portPoint(port).x" :y="portPoint(port).y + 25" text-anchor="middle">{{ port.name }}</text>
                </g>
                <line
                  v-if="portDragState"
                  class="connection-preview"
                  :x1="portPointFor(portDragState.source).x"
                  :y1="portPointFor(portDragState.source).y"
                  :x2="portDragState.point.x"
                  :y2="portDragState.point.y"
                />
                <g v-for="(connection, index) in visibleConnections" :key="connection.id">
                  <line
                    class="connection-line"
                    :stroke="connection.color"
                    :x1="connectionLine(connection, index).x1"
                    :y1="connectionLine(connection, index).y1"
                    :x2="connectionLine(connection, index).x2"
                    :y2="connectionLine(connection, index).y2"
                    :marker-end="connectionEndpoint(connection).peer?.device_id === selectedDevice?.id ? undefined : 'url(#connection-arrow)'"
                    @click.stop="openConnectionEditor(connection)"
                  />
                  <text class="connection-label" :x="deviceCanvasWidth - 42" :y="119 + index * 34" text-anchor="end" @click.stop="openConnectionEditor(connection)">{{ connection.name || connectionPeer(connection) }}</text>
                </g>
                <text v-if="!selectedDevicePorts.length" class="empty-device" :x="deviceCanvasWidth / 2" :y="deviceCanvasHeight / 2" text-anchor="middle">在右侧添加接口</text>
                <text v-else-if="!selectedPort" class="device-instruction" :x="deviceCanvasWidth / 2" :y="deviceCanvasHeight - 28" text-anchor="middle">点击接口选择起点，再点击目标接口创建连接</text>
                <text v-else class="device-instruction selected-instruction" :x="deviceCanvasWidth / 2" :y="deviceCanvasHeight - 28" text-anchor="middle">已选择 {{ selectedPort.name }}，请点击目标接口</text>
              </g>
            </g>
          </svg>
          <div class="canvas-legend">
            <span><i class="legend-cabinet"></i>机柜</span>
            <span><i class="legend-device"></i>设备</span>
            <span><i class="legend-selected"></i>已选中</span>
            <span>滚轮缩放 · 空白处拖动</span>
          </div>
        </div>
      </section>

      <aside class="inspector">
        <template v-if="viewMode === 'room'">
          <div class="inspector-head">
            <div><p class="eyebrow">当前对象</p><h2>{{ currentRoom?.name ?? "机房" }}</h2></div>
            <el-tooltip content="编辑机房">
              <el-button circle size="small" aria-label="编辑机房" @click="openRoomDialog"><el-icon><Edit /></el-icon></el-button>
            </el-tooltip>
          </div>
          <div class="summary-block">
            <span>机房编号</span><strong>{{ currentRoom?.code }}</strong>
            <span>机柜数量</span><strong>{{ cabinets.length }}</strong>
            <span>画布尺寸</span><strong>{{ currentRoom?.width }} × {{ currentRoom?.height }}</strong>
          </div>
          <div class="inspector-section">
            <div class="section-title"><span>机柜列表</span><el-button text type="primary" @click="openCabinetDialog()"><el-icon><Plus /></el-icon>添加</el-button></div>
            <button v-for="cabinet in cabinets" :key="cabinet.id" class="object-row" type="button" @click="loadCabinet(cabinet)">
              <span class="row-symbol">▥</span><span><strong>{{ cabinet.code }}</strong><small>{{ cabinet.name }} · {{ cabinet.height_u }}U</small></span><span>›</span>
            </button>
          </div>
        </template>
        <template v-else-if="selectedDevice">
          <div class="inspector-head">
            <div><p class="eyebrow">设备详情</p><h2>{{ selectedDevice.name }}</h2></div>
            <el-tooltip content="编辑设备">
              <el-button circle size="small" aria-label="编辑设备" @click="openDeviceDialog(selectedDevice)"><el-icon><Edit /></el-icon></el-button>
            </el-tooltip>
          </div>
          <div class="device-badge">{{ selectedDevice.category }} · {{ selectedDevice.status }}</div>
          <div v-if="selectedDevice.image_url" class="device-photo">
            <img :src="selectedDevice.image_url" :alt="`${selectedDevice.name} 图片`" />
          </div>
          <el-upload
            class="image-upload"
            action="#"
            :auto-upload="false"
            :show-file-list="false"
            accept="image/png,image/jpeg,image/webp"
            @change="onImageSelected"
          >
            <el-button plain size="small"><el-icon><Plus /></el-icon>上传设备图片</el-button>
          </el-upload>
          <el-button v-if="selectedDevice.image_url" class="image-delete" text type="danger" size="small" @click="removeDeviceImage">删除图片</el-button>
          <div class="summary-block">
            <span>设备编号</span><strong>{{ selectedDevice.code }}</strong>
            <span>厂商 / 型号</span><strong>{{ selectedDevice.vendor || "未填写" }} {{ selectedDevice.model }}</strong>
            <span>管理地址</span><strong>{{ selectedDevice.management_ip || "未填写" }}</strong>
            <span>机柜位置</span><strong>U{{ selectedDevice.start_u }} · {{ selectedDevice.height_u }}U · {{ selectedDevice.side === "back" ? "背面" : "正面" }}</strong>
          </div>
          <p class="note-box">{{ selectedDevice.note || "暂无设备备注。" }}</p>
          <div class="inspector-section">
            <div class="section-title">
              <span>接口 · {{ selectedDevicePorts.length }}</span>
              <span class="section-actions">
                <el-button text type="primary" @click="openPortDialog()"><el-icon><Plus /></el-icon>添加</el-button>
                <el-button text type="primary" @click="openPortBatchDialog"><el-icon><ConnectionIcon /></el-icon>批量生成</el-button>
              </span>
            </div>
            <div v-for="port in selectedDevicePorts" :key="port.id" class="object-row port-row">
              <span class="port-dot" :class="{ connected: connectedPortIds.has(port.id) }"></span>
              <button class="row-main-button" type="button" @click="openPortDialog(port)">
                <strong>{{ port.name }}</strong>
                <small>{{ port.port_type }} · {{ connectedPortIds.has(port.id) ? "已连接" : "未连接" }}{{ port.note ? ` · ${port.note}` : "" }}</small>
              </button>
              <el-tooltip content="查看链路">
                <el-button text circle size="small" aria-label="查看链路" @click="openPortTopology(port)"><el-icon><ConnectionIcon /></el-icon></el-button>
              </el-tooltip>
            </div>
            <el-empty v-if="!selectedDevicePorts.length" description="还没有接口" :image-size="50" />
          </div>
          <div class="inspector-section">
            <div class="section-title"><span>连接 · {{ visibleConnections.length }}</span></div>
            <div v-for="connection in visibleConnections" :key="connection.id" class="connection-row">
              <span class="connection-swatch" :style="{ backgroundColor: connection.color }"></span>
              <span><strong>{{ connection.name || "未命名连接" }}</strong><small>{{ connectionPeer(connection) }}</small></span>
              <el-tooltip content="查看上下游">
                <el-button text circle size="small" aria-label="查看上下游" @click="openConnectionTopology(connection)"><el-icon><ConnectionIcon /></el-icon></el-button>
              </el-tooltip>
              <el-button text type="danger" size="small" @click="removeConnection(connection)"><el-icon><Delete /></el-icon>删除</el-button>
            </div>
            <el-empty v-if="!visibleConnections.length" description="暂无连接" :image-size="45" />
          </div>
          <div class="inspector-section">
            <div class="section-title"><span>拖线目标</span><small>可拖到目标接口</small></div>
            <button
              v-for="{ port, device } in connectionTargetPorts"
              :key="`target-${port.id}`"
              class="object-row port-row"
              type="button"
              :data-port-id="port.id"
              @pointerup="portDragState && selectConnectionTarget(port)"
              @click="selectConnectionTarget(port)"
            >
              <span class="port-dot"></span><span><strong>{{ port.name }}</strong><small>{{ device?.name ?? "未知设备" }} · {{ port.port_type }}</small></span><el-icon><ArrowRight /></el-icon>
            </button>
            <p v-if="!connectionTargetPorts.length" class="target-empty">当前项目没有其他设备接口。</p>
          </div>
          <el-button class="full-button danger-button" plain @click="removeSelectedDevice"><el-icon><Delete /></el-icon>删除设备</el-button>
        </template>
        <template v-else-if="selectedCabinet">
          <div class="inspector-head">
            <div><p class="eyebrow">机柜详情</p><h2>{{ selectedCabinet.name }}</h2></div>
            <el-tooltip content="编辑机柜">
              <el-button circle size="small" aria-label="编辑机柜" @click="openCabinetDialog(selectedCabinet)"><el-icon><Edit /></el-icon></el-button>
            </el-tooltip>
          </div>
          <div class="device-badge">机柜 · {{ selectedCabinet.height_u }}U</div>
          <div class="summary-block"><span>机柜编号</span><strong>{{ selectedCabinet.code }}</strong><span>设备数量</span><strong>{{ cabinetDevices.length }}</strong></div>
          <p class="note-box">{{ selectedCabinet.note || "暂无机柜备注。" }}</p>
          <div class="inspector-section">
            <div class="section-title"><span>设备</span><el-button text type="primary" @click="openDeviceDialog()"><el-icon><Plus /></el-icon>添加</el-button></div>
            <button v-for="device in cabinetDevices" :key="device.id" class="object-row" type="button" @click="selectDevice(device)">
              <span class="row-symbol device-symbol">□</span><span><strong>{{ device.name }}</strong><small>{{ device.category }} · U{{ device.start_u }}</small></span><span>›</span>
            </button>
            <el-empty v-if="!cabinetDevices.length" description="添加第一台设备" :image-size="50" />
          </div>
        </template>
        <el-empty v-else description="选择一个对象开始编辑" :image-size="70" />
      </aside>
    </main>

    <el-dialog v-model="projectDialog" title="项目设置" width="460px">
      <el-form label-position="top">
        <el-form-item label="项目名称"><el-input v-model="projectForm.name" /></el-form-item>
        <el-form-item label="项目编号"><el-input v-model="projectForm.code" :disabled="Boolean(editingIds.project)" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="projectForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="projectDialog = false">取消</el-button><el-button type="primary" @click="saveProject">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="roomDialog" title="机房设置" width="460px">
      <el-form label-position="top">
        <el-form-item label="机房名称"><el-input v-model="roomForm.name" /></el-form-item>
        <el-form-item label="机房编号"><el-input v-model="roomForm.code" :disabled="Boolean(editingIds.room)" /></el-form-item>
        <div class="form-grid"><el-form-item label="画布宽度"><el-input-number v-model="roomForm.width" :min="400" /></el-form-item><el-form-item label="画布高度"><el-input-number v-model="roomForm.height" :min="300" /></el-form-item></div>
        <el-form-item label="备注"><el-input v-model="roomForm.note" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="roomDialog = false">取消</el-button><el-button type="primary" @click="saveRoom">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="cabinetDialog" :title="editingIds.cabinet ? '编辑机柜' : '新建机柜'" width="460px">
      <el-form label-position="top">
        <div class="form-grid"><el-form-item label="机柜名称"><el-input v-model="cabinetForm.name" /></el-form-item><el-form-item label="机柜编号"><el-input v-model="cabinetForm.code" /></el-form-item></div>
        <el-form-item label="机柜高度"><el-input-number v-model="cabinetForm.height_u" :min="1" :max="100" /><span class="unit-label">U</span></el-form-item>
        <el-form-item label="备注"><el-input v-model="cabinetForm.note" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="cabinetDialog = false">取消</el-button><el-button type="primary" @click="saveCabinet">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="deviceDialog" :title="editingIds.device ? '编辑设备' : '新建设备'" width="620px">
      <el-form label-position="top">
        <div class="form-grid"><el-form-item label="设备名称"><el-input v-model="deviceForm.name" /></el-form-item><el-form-item label="设备编号"><el-input v-model="deviceForm.code" /></el-form-item></div>
        <div class="form-grid"><el-form-item label="分类"><el-select v-model="deviceForm.category" class="wide-input"><el-option label="交换机" value="交换机" /><el-option label="路由器" value="路由器" /><el-option label="服务器" value="服务器" /><el-option label="配线架" value="配线架" /><el-option label="其他" value="其他" /></el-select></el-form-item><el-form-item label="状态"><el-select v-model="deviceForm.status" class="wide-input"><el-option label="在用" value="在用" /><el-option label="备用" value="备用" /><el-option label="故障" value="故障" /><el-option label="停用" value="停用" /></el-select></el-form-item></div>
        <div class="form-grid"><el-form-item label="厂商"><el-input v-model="deviceForm.vendor" /></el-form-item><el-form-item label="型号"><el-input v-model="deviceForm.model" /></el-form-item></div>
        <div class="form-grid"><el-form-item label="管理 IP"><el-input v-model="deviceForm.management_ip" /></el-form-item><el-form-item label="面"><el-select v-model="deviceForm.side" class="wide-input"><el-option label="正面" value="front" /><el-option label="背面" value="back" /></el-select></el-form-item></div>
        <div class="form-grid"><el-form-item label="起始 U 位"><el-input-number v-model="deviceForm.start_u" :min="1" /></el-form-item><el-form-item label="占用高度"><el-input-number v-model="deviceForm.height_u" :min="1" /></el-form-item></div>
        <div class="form-grid"><el-form-item label="设备网格列"><el-input-number v-model="deviceForm.canvas_width" :min="2" :max="40" /></el-form-item><el-form-item label="设备网格行"><el-input-number v-model="deviceForm.canvas_height" :min="2" :max="20" /></el-form-item></div>
        <el-form-item label="设备图片地址"><el-input v-model="deviceForm.image_url" placeholder="可填写服务器图片地址" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="deviceForm.note" type="textarea" :rows="4" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="deviceDialog = false">取消</el-button><el-button type="primary" @click="saveDevice">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="portDialog" :title="editingIds.port ? '编辑接口' : '新增接口'" width="460px">
      <el-form label-position="top">
        <div class="form-grid"><el-form-item label="接口名称"><el-input v-model="portForm.name" /></el-form-item><el-form-item label="接口类型"><el-select v-model="portForm.port_type" class="wide-input"><el-option label="网口" value="网口" /><el-option label="光口" value="光口" /><el-option label="电源口" value="电源口" /><el-option label="串口" value="串口" /></el-select></el-form-item></div>
        <div class="form-grid">
          <el-form-item label="显示顺序"><el-input-number v-model="portForm.position" :min="0" /></el-form-item>
          <el-form-item label="网格列"><el-input-number v-model="portForm.grid_x" :min="0" :max="(selectedDevice?.canvas_width ?? 8) - 1" /></el-form-item>
        </div>
        <el-form-item label="网格行"><el-input-number v-model="portForm.grid_y" :min="0" :max="(selectedDevice?.canvas_height ?? 3) - 1" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="portForm.note" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button
          v-if="editingIds.port"
          type="danger"
          plain
          @click="removePort(selectedDevicePorts.find((item) => item.id === editingIds.port)!)"
        >删除接口</el-button>
        <span class="dialog-spacer"></span>
        <el-button @click="portDialog = false">取消</el-button>
        <el-button type="primary" @click="savePort">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="portBatchDialog" title="批量生成接口" width="500px">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="名称前缀"><el-input v-model="portBatchForm.prefix" /></el-form-item>
          <el-form-item label="起始编号"><el-input-number v-model="portBatchForm.start_number" :min="0" /></el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="数量"><el-input-number v-model="portBatchForm.count" :min="1" :max="256" /></el-form-item>
          <el-form-item label="起始顺序"><el-input-number v-model="portBatchForm.position_start" :min="0" /></el-form-item>
        </div>
        <el-form-item label="接口类型"><el-select v-model="portBatchForm.port_type" class="wide-input"><el-option label="网口" value="网口" /><el-option label="光口" value="光口" /><el-option label="电源口" value="电源口" /><el-option label="串口" value="串口" /></el-select></el-form-item>
        <el-form-item label="统一备注"><el-input v-model="portBatchForm.note" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="portBatchDialog = false">取消</el-button><el-button type="primary" @click="savePortBatch">生成接口</el-button></template>
    </el-dialog>

    <el-dialog v-model="connectionDialog" :title="editingConnectionId ? '编辑连接' : '创建连接'" width="520px">
      <el-form label-position="top">
        <el-form-item label="起始接口">
          <el-select v-model="connectionForm.source_port_id" class="wide-input" filterable>
            <el-option v-for="{ port } in allPortsWithDevices" :key="port.id" :label="portLabel(port)" :value="port.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标接口">
          <el-select v-model="connectionForm.target_port_id" class="wide-input" filterable>
            <el-option v-for="{ port } in allPortsWithDevices" :key="port.id" :label="portLabel(port)" :value="port.id" />
          </el-select>
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="连接名称"><el-input v-model="connectionForm.name" /></el-form-item>
          <el-form-item label="线缆类型"><el-select v-model="connectionForm.cable_type" class="wide-input"><el-option label="网线" value="网线" /><el-option label="光纤" value="光纤" /><el-option label="电源线" value="电源线" /><el-option label="其他" value="其他" /></el-select></el-form-item>
        </div>
        <el-form-item label="线路颜色"><el-color-picker v-model="connectionForm.color" show-alpha /></el-form-item>
        <el-form-item label="备注"><el-input v-model="connectionForm.note" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button v-if="editingConnectionId" type="danger" plain @click="removeConnection(connections.find((item) => item.id === editingConnectionId)!)">删除连接</el-button>
        <span class="dialog-spacer"></span>
        <el-button @click="connectionDialog = false">取消</el-button><el-button type="primary" @click="saveConnection">{{ editingConnectionId ? "保存修改" : "保存连接" }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="topologyDialog" title="接口链路" width="620px">
      <el-descriptions v-if="topologyRootPort" :column="2" border size="small" class="topology-summary">
        <el-descriptions-item label="起点设备">{{ allDevices.find((item) => item.id === topologyRootPort?.device_id)?.name }}</el-descriptions-item>
        <el-descriptions-item label="起点接口">{{ topologyRootPort.name }}</el-descriptions-item>
      </el-descriptions>
      <el-divider content-position="left">上一跳 / 下一跳</el-divider>
      <el-empty v-if="topologySteps.length <= 1" description="该接口暂无连接链路" />
      <el-timeline v-else class="topology-timeline">
        <el-timeline-item v-for="step in topologySteps" :key="step.port.id" :type="step.depth === 0 ? 'primary' : 'success'">
          <div class="topology-step">
            <el-tag size="small" :type="step.depth === 0 ? 'primary' : 'info'">{{ step.direction }}</el-tag>
            <button class="topology-link" type="button" @click="focusTopologyPort(step.port)">
              {{ step.device?.name ?? "未知设备" }} · {{ step.port.name }}
            </button>
            <span v-if="step.connection" class="topology-connection">
              {{ step.connection.name || "未命名连接" }} · {{ step.connection.cable_type }}
            </span>
          </div>
        </el-timeline-item>
      </el-timeline>
      <template #footer><el-button @click="topologyDialog = false">关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="searchOpen" title="搜索结果" width="560px">
      <div v-if="searchResults" class="search-results">
        <button v-for="room in searchResults.rooms" :key="`room-${room.id}`" class="search-result" type="button" @click="focusSearchRoom(room)">
          <span class="row-symbol">⌂</span>
          <span><strong>{{ room.name }}</strong><small>机房 · {{ room.code }}</small></span>
          <span>›</span>
        </button>
        <button v-for="cabinet in searchResults.cabinets" :key="`cabinet-${cabinet.id}`" class="search-result" type="button" @click="focusSearchCabinet(cabinet)">
          <span class="row-symbol">▥</span>
          <span><strong>{{ cabinet.name }}</strong><small>机柜 · {{ cabinet.code }}</small></span>
          <span>›</span>
        </button>
        <button v-for="device in searchResults.devices" :key="`device-${device.id}`" class="search-result" type="button" @click="focusSearchDevice(device)">
          <span class="row-symbol device-symbol">□</span>
          <span><strong>{{ device.name }}</strong><small>{{ device.code }} · {{ device.category }} · {{ device.management_ip || "无管理 IP" }}</small></span>
          <span>›</span>
        </button>
        <button v-for="port in searchResults.ports" :key="`port-${port.id}`" class="search-result" type="button" @click="focusSearchPort(port)">
          <span class="port-dot connected"></span>
          <span><strong>{{ port.name }}</strong><small>接口 · {{ port.port_type }}{{ port.note ? ` · ${port.note}` : "" }}</small></span>
          <span>›</span>
        </button>
        <div v-if="!searchResults.rooms.length && !searchResults.cabinets.length && !searchResults.devices.length && !searchResults.ports.length" class="search-empty">没有找到匹配对象，可尝试搜索名称、编号、IP 或备注。</div>
      </div>
      <template #footer><el-button @click="searchOpen = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>
