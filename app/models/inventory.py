from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Integer, Boolean, Text, DateTime, ForeignKey, func, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Datacenter(Base):
    __tablename__ = "datacenters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    has_grid_system: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    racks: Mapped[list["Rack"]] = relationship("Rack", back_populates="datacenter", cascade="all, delete-orphan")
    contacts: Mapped[list["DCContact"]] = relationship("DCContact", back_populates="datacenter", cascade="all, delete-orphan")
    work_orders: Mapped[list] = relationship("WorkOrder", back_populates="datacenter")


class DCContact(Base):
    __tablename__ = "dc_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    datacenter_id: Mapped[int] = mapped_column(ForeignKey("datacenters.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    datacenter: Mapped["Datacenter"] = relationship("Datacenter", back_populates="contacts")


class Rack(Base):
    __tablename__ = "racks"

    id: Mapped[int] = mapped_column(primary_key=True)
    datacenter_id: Mapped[int] = mapped_column(ForeignKey("datacenters.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    grid_position: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    total_ru: Mapped[int] = mapped_column(Integer, default=42)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    datacenter: Mapped["Datacenter"] = relationship("Datacenter", back_populates="racks")
    devices: Mapped[list["Device"]] = relationship("Device", back_populates="rack")
    switches: Mapped[list["Switch"]] = relationship("Switch", back_populates="rack")
    patch_panels: Mapped[list["PatchPanel"]] = relationship("PatchPanel", back_populates="rack")
    deleter: Mapped[Optional["User"]] = relationship("User", foreign_keys="[Rack.deleted_by]")

    __table_args__ = (
        UniqueConstraint("datacenter_id", "name", name="uq_rack_name_per_dc"),
    )


class DeviceType(Base):
    """
    Manufacturer/model template. Devices reference this for consistent
    RU height, slot count, and category.  All three categories (server,
    storage, switch) share one table; switch device types can also be
    assigned to Switch records via switch_type_id.
    """
    __tablename__ = "device_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    manufacturer: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    # server / storage / switch
    category: Mapped[str] = mapped_column(String(16), nullable=False, default="server")
    rack_u: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Non-null means this chassis can host child devices; value = number of slots
    slot_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Total switchport capacity — only meaningful for switch device types
    port_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    devices: Mapped[list["Device"]] = relationship("Device", back_populates="device_type",
                                                    foreign_keys="Device.device_type_id")
    switches: Mapped[list["Switch"]] = relationship("Switch", back_populates="device_type")

    __table_args__ = (
        UniqueConstraint("manufacturer", "model", name="uq_device_type_mfg_model"),
    )


class System(Base):
    """
    Optional logical parent grouping devices (e.g. a storage cluster or blade chassis).
    Devices may have system_id=NULL for standalone 1-2U servers.
    """
    __tablename__ = "systems"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    system_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    devices: Mapped[list["Device"]] = relationship("Device", back_populates="system")
    deleter: Mapped[Optional["User"]] = relationship("User", foreign_keys="[System.deleted_by]")


class Device(Base):
    """Physical storage or server node — never a switch. system_id is optional."""
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[Optional[int]] = mapped_column(ForeignKey("systems.id"), nullable=True)
    node_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rack_id: Mapped[int] = mapped_column(ForeignKey("racks.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    serial: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    starting_ru: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Device type template (optional — can be a stub without one)
    device_type_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("device_types.id"), nullable=True
    )
    # Parent chassis (e.g. UCS blade references its UCS chassis)
    parent_device_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("devices.id"), nullable=True
    )
    slot_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    system: Mapped[Optional["System"]] = relationship("System", back_populates="devices")
    rack: Mapped["Rack"] = relationship("Rack", back_populates="devices")
    device_type: Mapped[Optional["DeviceType"]] = relationship(
        "DeviceType", back_populates="devices", foreign_keys=[device_type_id]
    )
    parent_device: Mapped[Optional["Device"]] = relationship(
        "Device", remote_side="Device.id", foreign_keys="Device.parent_device_id",
        backref="child_devices"
    )
    deleter: Mapped[Optional["User"]] = relationship("User", foreign_keys="[Device.deleted_by]")


class Switch(Base):
    """SAN or LAN switch — never a server or storage device."""
    __tablename__ = "switches"

    id: Mapped[int] = mapped_column(primary_key=True)
    rack_id: Mapped[int] = mapped_column(ForeignKey("racks.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    serial: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    switch_role: Mapped[str] = mapped_column(String(8), nullable=False, default="LAN")
    starting_ru: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    switch_type_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("device_types.id"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    rack: Mapped["Rack"] = relationship("Rack", back_populates="switches")
    device_type: Mapped[Optional["DeviceType"]] = relationship(
        "DeviceType", back_populates="switches"
    )
    deleter: Mapped[Optional["User"]] = relationship("User", foreign_keys="[Switch.deleted_by]")


class PatchPanel(Base):
    """Patch panel — module/port details stay free-form on Connection rows (v1)."""
    __tablename__ = "patch_panels"

    id: Mapped[int] = mapped_column(primary_key=True)
    rack_id: Mapped[int] = mapped_column(ForeignKey("racks.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    starting_ru: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    rack: Mapped["Rack"] = relationship("Rack", back_populates="patch_panels")
