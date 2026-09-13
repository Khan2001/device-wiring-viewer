from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .db import create_tables, database_is_ready, get_db
from .models import Cabinet, Connection, Device, Port, Project, Room, ViewItem
from .schemas import (
    CabinetCreate, CabinetRead, CabinetUpdate,
    ConnectionCreate, ConnectionRead,
    DeviceCreate, DeviceRead,
    PortBatchCreate, PortCreate, PortRead,
    ProjectCreate, ProjectImport, ProjectRead, ProjectUpdate,
    RoomCreate, RoomRead, RoomUpdate,
    ViewItemImport, ViewItemRead, ViewItemUpdate,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    if database_is_ready():
        create_tables()
    yield


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="对象编号已存在，或数据仍被其他对象引用。",
        ) from error


def get_or_404(db: Session, model, object_id: int):
    instance = db.get(model, object_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="对象不存在。")
    return instance


def imported_project_code(db: Session, code: str) -> str:
    if db.scalar(select(Project).where(Project.code == code)) is None:
        return code
    base = code[:48]
    suffix = 1
    while db.scalar(select(Project).where(Project.code == f"{base}-IMP{suffix}")) is not None:
        suffix += 1
    return f"{base}-IMP{suffix}"


def validate_device_position(
    cabinet: Cabinet, payload: DeviceCreate, db: Session, device_id: Optional[int] = None
) -> None:
    if payload.start_u + payload.height_u - 1 > cabinet.height_u:
        raise HTTPException(status_code=422, detail="设备超出机柜 U 位范围。")
    devices = db.scalars(select(Device).where(Device.cabinet_id == cabinet.id)).all()
    for device in devices:
        if device_id is not None and device.id == device_id:
            continue
        overlaps = (
            payload.start_u <= device.start_u + device.height_u - 1
            and device.start_u <= payload.start_u + payload.height_u - 1
        )
        if overlaps:
            raise HTTPException(status_code=422, detail=f"设备与 {device.name} 的 U 位重叠。")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "backend"}


@app.get("/api/health/db")
def database_health() -> dict[str, str]:
    return {"status": "ok" if database_is_ready() else "error", "service": "database"}


@app.get("/api/projects", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)):
    return db.scalars(select(Project).order_by(Project.id)).all()


@app.post("/api/projects", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(**payload.model_dump())
    db.add(project)
    commit_or_conflict(db)
    db.refresh(project)
    return project


@app.post("/api/projects/import", response_model=ProjectRead, status_code=201)
def import_project(payload: ProjectImport, db: Session = Depends(get_db)):
    project_data = payload.project.model_dump()
    project_data["code"] = imported_project_code(db, project_data["code"])
    project_data["name"] = f"{project_data['name']}（导入）"[:120]
    project = Project(**project_data)
    db.add(project)
    db.flush()

    room = Room(project_id=project.id, **payload.room.model_dump())
    db.add(room)
    db.flush()

    cabinet_ids: dict[int, int] = {}
    for cabinet_data in payload.cabinets:
        cabinet = Cabinet(room_id=room.id, **cabinet_data.model_dump(exclude={"id"}))
        db.add(cabinet)
        db.flush()
        cabinet_ids[cabinet_data.id] = cabinet.id

    device_ids: dict[int, int] = {}
    for device_data in payload.devices:
        cabinet_id = cabinet_ids.get(device_data.cabinet_id)
        if cabinet_id is None:
            db.rollback()
            raise HTTPException(status_code=422, detail="导入数据包含不存在的机柜引用。")
        device_payload = DeviceCreate.model_validate(device_data.model_dump(exclude={"id", "cabinet_id"}))
        validate_device_position(
            db.get(Cabinet, cabinet_id),
            device_payload,
            db,
        )
        device = Device(cabinet_id=cabinet_id, **device_payload.model_dump())
        db.add(device)
        db.flush()
        device_ids[device_data.id] = device.id

    port_ids: dict[int, int] = {}
    for port_data in payload.ports:
        device_id = device_ids.get(port_data.device_id)
        if device_id is None:
            db.rollback()
            raise HTTPException(status_code=422, detail="导入数据包含不存在的设备接口引用。")
        port = Port(
            device_id=device_id,
            **port_data.model_dump(exclude={"id", "device_id"}),
        )
        db.add(port)
        db.flush()
        port_ids[port_data.id] = port.id

    for connection_data in payload.connections:
        source_id = port_ids.get(connection_data.source_port_id)
        target_id = port_ids.get(connection_data.target_port_id)
        if source_id is None or target_id is None:
            db.rollback()
            raise HTTPException(status_code=422, detail="导入数据包含不存在的连接端口引用。")
        if source_id == target_id:
            db.rollback()
            raise HTTPException(status_code=422, detail="不能连接同一个接口。")
        db.add(
            Connection(
                source_port_id=source_id,
                target_port_id=target_id,
                **connection_data.model_dump(exclude={"id", "source_port_id", "target_port_id"}),
            )
        )

    for view_item_data in payload.view_items:
        if view_item_data.object_type != "cabinet":
            continue
        object_id = cabinet_ids.get(view_item_data.object_id)
        if object_id is None:
            db.rollback()
            raise HTTPException(status_code=422, detail="导入数据包含不存在的画布对象引用。")
        db.add(
            ViewItem(
                room_id=room.id,
                object_type=view_item_data.object_type,
                object_id=object_id,
                x=view_item_data.x,
                y=view_item_data.y,
                width=view_item_data.width,
                height=view_item_data.height,
            )
        )

    commit_or_conflict(db)
    db.refresh(project)
    return project


@app.patch("/api/projects/{project_id}", response_model=ProjectRead)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = get_or_404(db, Project, project_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    commit_or_conflict(db)
    db.refresh(project)
    return project


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = get_or_404(db, Project, project_id)
    db.delete(project)
    commit_or_conflict(db)


@app.get("/api/projects/{project_id}/rooms", response_model=list[RoomRead])
def list_rooms(project_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Project, project_id)
    return db.scalars(select(Room).where(Room.project_id == project_id).order_by(Room.id)).all()


@app.post("/api/projects/{project_id}/rooms", response_model=RoomRead, status_code=201)
def create_room(project_id: int, payload: RoomCreate, db: Session = Depends(get_db)):
    get_or_404(db, Project, project_id)
    room = Room(project_id=project_id, **payload.model_dump())
    db.add(room)
    commit_or_conflict(db)
    db.refresh(room)
    return room


@app.patch("/api/rooms/{room_id}", response_model=RoomRead)
def update_room(room_id: int, payload: RoomUpdate, db: Session = Depends(get_db)):
    room = get_or_404(db, Room, room_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(room, key, value)
    commit_or_conflict(db)
    db.refresh(room)
    return room


@app.delete("/api/rooms/{room_id}", status_code=204)
def delete_room(room_id: int, db: Session = Depends(get_db)):
    room = get_or_404(db, Room, room_id)
    db.delete(room)
    commit_or_conflict(db)


@app.get("/api/rooms/{room_id}/cabinets", response_model=list[CabinetRead])
def list_cabinets(room_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Room, room_id)
    return db.scalars(select(Cabinet).where(Cabinet.room_id == room_id).order_by(Cabinet.id)).all()


@app.post("/api/rooms/{room_id}/cabinets", response_model=CabinetRead, status_code=201)
def create_cabinet(room_id: int, payload: CabinetCreate, db: Session = Depends(get_db)):
    get_or_404(db, Room, room_id)
    cabinet = Cabinet(room_id=room_id, **payload.model_dump())
    db.add(cabinet)
    commit_or_conflict(db)
    db.refresh(cabinet)
    return cabinet


@app.patch("/api/cabinets/{cabinet_id}", response_model=CabinetRead)
def update_cabinet(cabinet_id: int, payload: CabinetUpdate, db: Session = Depends(get_db)):
    cabinet = get_or_404(db, Cabinet, cabinet_id)
    if payload.height_u is not None:
        devices = db.scalars(select(Device).where(Device.cabinet_id == cabinet.id)).all()
        for device in devices:
            if device.start_u + device.height_u - 1 > payload.height_u:
                raise HTTPException(
                    status_code=422,
                    detail=f"机柜高度不能低于设备 {device.name} 的占用范围。",
                )
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(cabinet, key, value)
    commit_or_conflict(db)
    db.refresh(cabinet)
    return cabinet


@app.delete("/api/cabinets/{cabinet_id}", status_code=204)
def delete_cabinet(cabinet_id: int, db: Session = Depends(get_db)):
    cabinet = get_or_404(db, Cabinet, cabinet_id)
    db.delete(cabinet)
    commit_or_conflict(db)


@app.get("/api/cabinets/{cabinet_id}/devices", response_model=list[DeviceRead])
def list_devices(cabinet_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Cabinet, cabinet_id)
    return db.scalars(select(Device).where(Device.cabinet_id == cabinet_id).order_by(Device.start_u)).all()


@app.get("/api/projects/{project_id}/devices", response_model=list[DeviceRead])
def list_project_devices(project_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Project, project_id)
    query = (
        select(Device)
        .join(Device.cabinet)
        .join(Cabinet.room)
        .where(Room.project_id == project_id)
        .order_by(Device.id)
    )
    return db.scalars(query).all()


@app.get("/api/projects/{project_id}/ports", response_model=list[PortRead])
def list_project_ports(project_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Project, project_id)
    query = (
        select(Port)
        .join(Port.device)
        .join(Device.cabinet)
        .join(Cabinet.room)
        .where(Room.project_id == project_id)
        .order_by(Port.device_id, Port.position, Port.id)
    )
    return db.scalars(query).all()


@app.post("/api/cabinets/{cabinet_id}/devices", response_model=DeviceRead, status_code=201)
def create_device(cabinet_id: int, payload: DeviceCreate, db: Session = Depends(get_db)):
    cabinet = get_or_404(db, Cabinet, cabinet_id)
    validate_device_position(cabinet, payload, db)
    device = Device(cabinet_id=cabinet_id, **payload.model_dump())
    db.add(device)
    commit_or_conflict(db)
    db.refresh(device)
    return device


@app.patch("/api/devices/{device_id}", response_model=DeviceRead)
def update_device(device_id: int, payload: DeviceCreate, db: Session = Depends(get_db)):
    device = get_or_404(db, Device, device_id)
    cabinet = get_or_404(db, Cabinet, device.cabinet_id)
    validate_device_position(cabinet, payload, db, device_id)
    for key, value in payload.model_dump().items():
        setattr(device, key, value)
    commit_or_conflict(db)
    db.refresh(device)
    return device


@app.delete("/api/devices/{device_id}", status_code=204)
def delete_device(device_id: int, db: Session = Depends(get_db)):
    device = get_or_404(db, Device, device_id)
    db.delete(device)
    commit_or_conflict(db)


@app.post("/api/devices/{device_id}/image", response_model=DeviceRead)
async def upload_device_image(
    device_id: int, image: UploadFile = File(...), db: Session = Depends(get_db)
):
    device = get_or_404(db, Device, device_id)
    allowed = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    suffix = allowed.get(image.content_type or "")
    if suffix is None:
        raise HTTPException(status_code=415, detail="只支持 JPG、PNG 或 WebP 图片。")
    if device.image_url:
        old_file = Path(settings.upload_dir) / Path(device.image_url).name
        old_file.unlink(missing_ok=True)
    filename = f"device-{device.id}-{uuid4().hex}{suffix}"
    destination = Path(settings.upload_dir) / filename
    destination.write_bytes(await image.read())
    device.image_url = f"/api/uploads/{filename}"
    commit_or_conflict(db)
    db.refresh(device)
    return device


@app.delete("/api/devices/{device_id}/image", response_model=DeviceRead)
def delete_device_image(device_id: int, db: Session = Depends(get_db)):
    device = get_or_404(db, Device, device_id)
    if device.image_url:
        image_path = Path(settings.upload_dir) / Path(device.image_url).name
        image_path.unlink(missing_ok=True)
        device.image_url = ""
        commit_or_conflict(db)
        db.refresh(device)
    return device


@app.get("/api/uploads/{filename}")
def get_upload(filename: str):
    path = Path(settings.upload_dir) / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在。")
    return FileResponse(path)


@app.get("/api/devices/{device_id}/ports", response_model=list[PortRead])
def list_ports(device_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Device, device_id)
    return db.scalars(select(Port).where(Port.device_id == device_id).order_by(Port.position, Port.id)).all()


@app.post("/api/devices/{device_id}/ports", response_model=PortRead, status_code=201)
def create_port(device_id: int, payload: PortCreate, db: Session = Depends(get_db)):
    device = get_or_404(db, Device, device_id)
    if payload.grid_x >= device.canvas_width or payload.grid_y >= device.canvas_height:
        raise HTTPException(status_code=422, detail="接口坐标超出设备画布范围。")
    port = Port(device_id=device_id, **payload.model_dump())
    db.add(port)
    commit_or_conflict(db)
    db.refresh(port)
    return port


@app.post("/api/devices/{device_id}/ports/bulk", response_model=list[PortRead], status_code=201)
def create_ports_bulk(device_id: int, payload: PortBatchCreate, db: Session = Depends(get_db)):
    device = get_or_404(db, Device, device_id)
    if payload.count > device.canvas_width * device.canvas_height:
        raise HTTPException(status_code=422, detail="接口数量超过设备画布可容纳的网格数量。")
    ports = [
        Port(
            device_id=device_id,
            name=f"{payload.prefix}{payload.start_number + index}",
            port_type=payload.port_type,
            position=payload.position_start + index,
            grid_x=index % device.canvas_width,
            grid_y=index // device.canvas_width,
            note=payload.note,
        )
        for index in range(payload.count)
    ]
    db.add_all(ports)
    commit_or_conflict(db)
    for port in ports:
        db.refresh(port)
    return ports


@app.patch("/api/ports/{port_id}", response_model=PortRead)
def update_port(port_id: int, payload: PortCreate, db: Session = Depends(get_db)):
    port = get_or_404(db, Port, port_id)
    device = get_or_404(db, Device, port.device_id)
    if payload.grid_x >= device.canvas_width or payload.grid_y >= device.canvas_height:
        raise HTTPException(status_code=422, detail="接口坐标超出设备画布范围。")
    for key, value in payload.model_dump().items():
        setattr(port, key, value)
    commit_or_conflict(db)
    db.refresh(port)
    return port


@app.delete("/api/ports/{port_id}", status_code=204)
def delete_port(port_id: int, db: Session = Depends(get_db)):
    port = get_or_404(db, Port, port_id)
    connections = db.scalars(
        select(Connection).where(
            (Connection.source_port_id == port_id) | (Connection.target_port_id == port_id)
        )
    ).all()
    if connections:
        raise HTTPException(status_code=409, detail="接口仍有连接，请先删除连接。")
    db.delete(port)
    commit_or_conflict(db)


@app.get("/api/projects/{project_id}/connections", response_model=list[ConnectionRead])
def list_connections(project_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Project, project_id)
    query = (
        select(Connection).join(Connection.source_port).join(Port.device)
        .join(Device.cabinet).join(Cabinet.room)
        .where(Room.project_id == project_id).order_by(Connection.id)
    )
    return db.scalars(query).all()


@app.get("/api/projects/{project_id}/search")
def search_project(project_id: int, q: str, db: Session = Depends(get_db)):
    get_or_404(db, Project, project_id)
    term = f"%{q.strip()}%"
    rooms = db.scalars(
        select(Room).where(
            Room.project_id == project_id,
            (Room.name.ilike(term) | Room.code.ilike(term) | Room.note.ilike(term)),
        )
    ).all()
    cabinets = db.scalars(
        select(Cabinet).join(Cabinet.room).where(
            Room.project_id == project_id,
            (Cabinet.name.ilike(term) | Cabinet.code.ilike(term) | Cabinet.note.ilike(term)),
        )
    ).all()
    devices = db.scalars(
        select(Device)
        .join(Device.cabinet)
        .join(Cabinet.room)
        .where(
            Room.project_id == project_id,
            (
                Device.name.ilike(term)
                | Device.code.ilike(term)
                | Device.category.ilike(term)
                | Device.vendor.ilike(term)
                | Device.model.ilike(term)
                | Device.management_ip.ilike(term)
                | Device.note.ilike(term)
            ),
        )
    ).all()
    ports = db.scalars(
        select(Port)
        .join(Port.device)
        .join(Device.cabinet)
        .join(Cabinet.room)
        .where(
            Room.project_id == project_id,
            (Port.name.ilike(term) | Port.port_type.ilike(term) | Port.note.ilike(term)),
        )
    ).all()
    return {
        "rooms": [RoomRead.model_validate(item).model_dump() for item in rooms],
        "cabinets": [CabinetRead.model_validate(item).model_dump() for item in cabinets],
        "devices": [DeviceRead.model_validate(item).model_dump() for item in devices],
        "ports": [PortRead.model_validate(item).model_dump() for item in ports],
    }


@app.post("/api/connections", response_model=ConnectionRead, status_code=201)
def create_connection(payload: ConnectionCreate, db: Session = Depends(get_db)):
    if payload.source_port_id == payload.target_port_id:
        raise HTTPException(status_code=422, detail="不能连接同一个接口。")
    get_or_404(db, Port, payload.source_port_id)
    get_or_404(db, Port, payload.target_port_id)
    connection = Connection(**payload.model_dump())
    db.add(connection)
    commit_or_conflict(db)
    db.refresh(connection)
    return connection


@app.patch("/api/connections/{connection_id}", response_model=ConnectionRead)
def update_connection(connection_id: int, payload: ConnectionCreate, db: Session = Depends(get_db)):
    connection = get_or_404(db, Connection, connection_id)
    if payload.source_port_id == payload.target_port_id:
        raise HTTPException(status_code=422, detail="不能连接同一个接口。")
    for key, value in payload.model_dump().items():
        setattr(connection, key, value)
    commit_or_conflict(db)
    db.refresh(connection)
    return connection


@app.delete("/api/connections/{connection_id}", status_code=204)
def delete_connection(connection_id: int, db: Session = Depends(get_db)):
    connection = get_or_404(db, Connection, connection_id)
    db.delete(connection)
    commit_or_conflict(db)


@app.get("/api/rooms/{room_id}/view-items", response_model=list[ViewItemRead])
def list_view_items(room_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Room, room_id)
    return db.scalars(select(ViewItem).where(ViewItem.room_id == room_id)).all()


@app.put("/api/rooms/{room_id}/view-items", response_model=ViewItemRead)
def upsert_view_item(room_id: int, payload: ViewItemUpdate, db: Session = Depends(get_db)):
    get_or_404(db, Room, room_id)
    item = db.scalar(
        select(ViewItem).where(
            ViewItem.room_id == room_id,
            ViewItem.object_type == payload.object_type,
            ViewItem.object_id == payload.object_id,
        )
    )
    if item is None:
        item = ViewItem(room_id=room_id, **payload.model_dump())
        db.add(item)
    else:
        for key, value in payload.model_dump().items():
            setattr(item, key, value)
    commit_or_conflict(db)
    db.refresh(item)
    return item
