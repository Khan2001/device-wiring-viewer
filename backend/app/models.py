from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    rooms: Mapped[list["Room"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(60))
    width: Mapped[int] = mapped_column(Integer, default=1200)
    height: Mapped[int] = mapped_column(Integer, default=800)
    note: Mapped[str] = mapped_column(Text, default="")
    project: Mapped[Project] = relationship(back_populates="rooms")
    cabinets: Mapped[list["Cabinet"]] = relationship(back_populates="room", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_room_project_code"),)


class Cabinet(Base):
    __tablename__ = "cabinets"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(60))
    height_u: Mapped[int] = mapped_column(Integer, default=42)
    x: Mapped[int] = mapped_column(Integer, default=80)
    y: Mapped[int] = mapped_column(Integer, default=80)
    note: Mapped[str] = mapped_column(Text, default="")
    room: Mapped[Room] = relationship(back_populates="cabinets")
    devices: Mapped[list["Device"]] = relationship(back_populates="cabinet", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("room_id", "code", name="uq_cabinet_room_code"),)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    cabinet_id: Mapped[int] = mapped_column(ForeignKey("cabinets.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(60))
    category: Mapped[str] = mapped_column(String(60), default="交换机")
    vendor: Mapped[str] = mapped_column(String(120), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    management_ip: Mapped[str] = mapped_column(String(120), default="")
    start_u: Mapped[int] = mapped_column(Integer, default=1)
    height_u: Mapped[int] = mapped_column(Integer, default=1)
    side: Mapped[str] = mapped_column(String(20), default="front")
    status: Mapped[str] = mapped_column(String(30), default="在用")
    note: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    canvas_width: Mapped[int] = mapped_column(Integer, default=8)
    canvas_height: Mapped[int] = mapped_column(Integer, default=3)
    cell_width: Mapped[int] = mapped_column(Integer, default=64)
    cell_height: Mapped[int] = mapped_column(Integer, default=52)
    cabinet: Mapped[Cabinet] = relationship(back_populates="devices")
    ports: Mapped[list["Port"]] = relationship(back_populates="device", cascade="all, delete-orphan")


class Port(Base):
    __tablename__ = "ports"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    port_type: Mapped[str] = mapped_column(String(40), default="网口")
    side: Mapped[str] = mapped_column(String(20), default="front")
    position: Mapped[int] = mapped_column(Integer, default=0)
    grid_x: Mapped[int] = mapped_column(Integer, default=0)
    grid_y: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    device: Mapped[Device] = relationship(back_populates="ports")


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_port_id: Mapped[int] = mapped_column(ForeignKey("ports.id", ondelete="CASCADE"))
    target_port_id: Mapped[int] = mapped_column(ForeignKey("ports.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120), default="")
    cable_type: Mapped[str] = mapped_column(String(60), default="网线")
    color: Mapped[str] = mapped_column(String(20), default="#6b7280")
    note: Mapped[str] = mapped_column(Text, default="")
    source_port: Mapped[Port] = relationship(foreign_keys=[source_port_id])
    target_port: Mapped[Port] = relationship(foreign_keys=[target_port_id])


class ViewItem(Base):
    __tablename__ = "view_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    object_type: Mapped[str] = mapped_column(String(30))
    object_id: Mapped[int] = mapped_column(Integer)
    x: Mapped[int] = mapped_column(Integer, default=0)
    y: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int] = mapped_column(Integer, default=120)
    height: Mapped[int] = mapped_column(Integer, default=200)
    __table_args__ = (UniqueConstraint("room_id", "object_type", "object_id", name="uq_view_item_object"),)
