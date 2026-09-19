from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


CONNECTION_COLORS = {"#202124", "#6b7280", "#d64545", "#2864c7"}
DEFAULT_CONNECTION_COLOR = "#6b7280"


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=60)
    description: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = None


class ProjectRead(ORMModel):
    id: int
    name: str
    code: str
    description: str


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=60)
    width: int = Field(default=1200, ge=400)
    height: int = Field(default=800, ge=300)
    note: str = ""


class RoomUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    width: Optional[int] = Field(default=None, ge=400)
    height: Optional[int] = Field(default=None, ge=300)
    note: Optional[str] = None


class RoomRead(ORMModel):
    id: int
    project_id: int
    name: str
    code: str
    width: int
    height: int
    note: str


class CabinetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=60)
    height_u: int = Field(default=42, ge=1, le=100)
    x: int = Field(default=80, ge=0)
    y: int = Field(default=80, ge=0)
    note: str = ""


class CabinetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    height_u: Optional[int] = Field(default=None, ge=1, le=100)
    x: Optional[int] = Field(default=None, ge=0)
    y: Optional[int] = Field(default=None, ge=0)
    note: Optional[str] = None


class CabinetRead(ORMModel):
    id: int
    room_id: int
    name: str
    code: str
    height_u: int
    x: int
    y: int
    note: str


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=60)
    category: str = "交换机"
    vendor: str = ""
    model: str = ""
    management_ip: str = ""
    start_u: int = Field(default=1, ge=1)
    height_u: int = Field(default=1, ge=1, le=100)
    side: str = "front"
    status: str = "在用"
    note: str = ""
    image_url: str = ""
    canvas_width: int = Field(default=8, ge=2, le=40)
    canvas_height: int = Field(default=3, ge=2, le=20)
    cell_width: int = Field(default=64, ge=24, le=240)
    cell_height: int = Field(default=52, ge=24, le=180)


class DeviceRead(ORMModel):
    id: int
    cabinet_id: int
    name: str
    code: str
    category: str
    vendor: str
    model: str
    management_ip: str
    start_u: int
    height_u: int
    side: str
    status: str
    note: str
    image_url: str
    canvas_width: int
    canvas_height: int
    cell_width: int
    cell_height: int


class PortCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    port_type: str = "网口"
    side: str = "front"
    position: int = Field(default=0, ge=0)
    grid_x: int = Field(default=0, ge=0, le=40)
    grid_y: int = Field(default=0, ge=0, le=20)
    note: str = ""


class PortBatchCreate(BaseModel):
    prefix: str = Field(default="PORT-", min_length=1, max_length=60)
    start_number: int = Field(default=1, ge=0)
    count: int = Field(default=24, ge=1, le=256)
    port_type: str = "网口"
    side: str = "front"
    position_start: int = Field(default=0, ge=0)
    note: str = ""


class PortRead(ORMModel):
    id: int
    device_id: int
    name: str
    port_type: str
    side: str
    position: int
    note: str
    grid_x: int
    grid_y: int


class ConnectionCreate(BaseModel):
    source_port_id: int
    target_port_id: int
    name: str = ""
    cable_type: str = "网线"
    color: str = DEFAULT_CONNECTION_COLOR
    note: str = ""

    @field_validator("color", mode="before")
    @classmethod
    def normalize_color(cls, value: str) -> str:
        return value if value in CONNECTION_COLORS else DEFAULT_CONNECTION_COLOR


class CabinetImport(CabinetCreate):
    id: int


class DeviceImport(DeviceCreate):
    id: int
    cabinet_id: int


class PortImport(PortCreate):
    id: int
    device_id: int


class ConnectionImport(ConnectionCreate):
    id: int


class ViewItemImport(BaseModel):
    id: int
    object_type: str
    object_id: int
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(default=120, ge=1)
    height: int = Field(default=200, ge=1)


class ProjectImport(BaseModel):
    project: ProjectCreate
    room: RoomCreate
    cabinets: list[CabinetImport] = Field(default_factory=list)
    devices: list[DeviceImport] = Field(default_factory=list)
    ports: list[PortImport] = Field(default_factory=list)
    connections: list[ConnectionImport] = Field(default_factory=list)
    view_items: list[ViewItemImport] = Field(default_factory=list)


class ConnectionRead(ORMModel):
    id: int
    source_port_id: int
    target_port_id: int
    name: str
    cable_type: str
    color: str
    note: str


class ViewItemRead(ORMModel):
    id: int
    room_id: int
    object_type: str
    object_id: int
    x: int
    y: int
    width: int
    height: int


class ViewItemUpdate(BaseModel):
    object_type: str
    object_id: int
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(default=120, ge=1)
    height: int = Field(default=200, ge=1)
