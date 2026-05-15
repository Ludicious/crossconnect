from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Integer, Text, DateTime, ForeignKey, Boolean,
    UniqueConstraint, Index, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

# install_status values
INSTALL_STATUSES = {"pending", "done", "blocked", "change_required"}

# action values
ACTIONS = {"A", "R", "C"}

# fabric values (nullable)
FABRICS = {"A", "B"}

# cable_type values
CABLE_TYPES = {"RJ45", "LC_Fiber", "DAC", "other"}

# purpose values
PURPOSES = {"management", "data", "storage", "other"}


class Connection(Base):
    """
    One row in a work order — device → (device patch) → (switch patch) → switch.

    Cable length columns store either a numeric string like "2.0" (metres),
    "cross-cabinet", "incomplete", "exceeds_max", or NULL when the segment
    doesn't apply.  They are computed by the cable_length service and written
    back; they are never edited by users.

    Switch-port uniqueness: (switch_id, switch_slot, switch_port) must be
    unique across non-deleted, non-R rows.  Enforced via UniqueConstraint
    with a partial-index workaround at the DB layer and re-validated in the
    service layer (SQLite doesn't support partial unique constraints natively,
    so service-layer validation is the primary gate).

    Device-port duplicate warning: (device_id, device_slot, device_port) is
    checked in the service layer and raises a warning (not a hard block) when
    the same port appears in two different work orders by the same architect.
    """

    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_id: Mapped[int] = mapped_column(
        ForeignKey("work_orders.id"), nullable=False
    )

    # ── Core action fields ────────────────────────────────────────────────
    action: Mapped[str] = mapped_column(String(1), nullable=False)   # A/R/C
    fabric: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)  # A/B
    port_description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    cable_type: Mapped[str] = mapped_column(String(16), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)

    # ── Device side ───────────────────────────────────────────────────────
    # system_id: FK to systems table; also store free-text name for rows
    # entered before the system exists in inventory (import path).
    system_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("systems.id"), nullable=True
    )
    system_name_raw: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    device_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("devices.id"), nullable=True
    )
    device_name_raw: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    device_serial: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # rack + RU stored redundantly here so we can compute cable lengths
    # without joining back to the device table (device may be a stub)
    device_rack_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("racks.id"), nullable=True
    )
    device_rack_name_raw: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    device_grid: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    device_rack_u: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    device_slot: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    device_port: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # ── Device patch panel ────────────────────────────────────────────────
    device_patch_rack_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("racks.id"), nullable=True
    )
    device_patch_rack_name_raw: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    device_patch_ru: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    device_patch_side: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    device_patch_module: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    device_patch_port: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # ── Switch patch panel ────────────────────────────────────────────────
    switch_patch_rack_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("racks.id"), nullable=True
    )
    switch_patch_rack_name_raw: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    switch_patch_ru: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    switch_patch_side: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    switch_patch_module: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    switch_patch_port: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # ── Switch side ───────────────────────────────────────────────────────
    switch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("switches.id"), nullable=True
    )
    switch_name_raw: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    switch_serial: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    switch_rack_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("racks.id"), nullable=True
    )
    switch_rack_name_raw: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    switch_grid: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    switch_rack_u: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    switch_slot: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    switch_port: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # ── VLAN/VSAN + misc ──────────────────────────────────────────────────
    vlan_vsan: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Install status (DC tech updates) ─────────────────────────────────
    install_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    install_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Computed cable lengths (service writes these, UI shows read-only) ─
    # Values: "2.0" (metres as string), "cross-cabinet", "incomplete",
    # "exceeds_max", or NULL when segment doesn't apply.
    seg1_length: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    seg2_length: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    seg3_length: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # ── Soft delete ───────────────────────────────────────────────────────
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # ── Audit timestamps ──────────────────────────────────────────────────
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────
    work_order: Mapped["WorkOrder"] = relationship(  # type: ignore[name-defined]
        "WorkOrder", back_populates="connections"
    )
    system: Mapped[Optional["System"]] = relationship("System")  # type: ignore[name-defined]
    device: Mapped[Optional["Device"]] = relationship("Device")  # type: ignore[name-defined]
    switch: Mapped[Optional["Switch"]] = relationship("Switch")  # type: ignore[name-defined]

    # ── Indexes ───────────────────────────────────────────────────────────
    # Partial unique constraint on switch port: enforced in service layer
    # (SQLite has no native partial unique constraints); the index below
    # speeds up the service-layer duplicate check.
    __table_args__ = (
        Index(
            "ix_conn_switch_port_lookup",
            "switch_id", "switch_slot", "switch_port",
        ),
        Index(
            "ix_conn_device_port_lookup",
            "device_id", "device_slot", "device_port",
        ),
        Index("ix_conn_work_order", "work_order_id"),
        Index("ix_conn_deleted_at", "deleted_at"),
    )
