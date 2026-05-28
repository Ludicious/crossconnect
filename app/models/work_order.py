from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Date, DateTime, ForeignKey, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class ConnectionTemplate(Base):
    """
    Reusable field-preset for the connection grid.
    datacenter_id=NULL means global; set means DC-specific.
    field_presets is a JSON string (e.g. {"purpose":"data","cable_type":"LC_Fiber"}).
    """
    __tablename__ = "connection_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    field_presets: Mapped[str] = mapped_column(Text, nullable=False)
    datacenter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("datacenters.id"), nullable=True
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

# Valid transitions enforced in service layer, not DB:
#   draft → issued → in_progress → complete
#                 ↘ cancelled
#   issued → draft  (architect pull-back, reversible per spec)
VALID_STATUSES = {"draft", "issued", "in_progress", "complete", "cancelled"}
VALID_WORK_TYPES = {"install", "decommission", "move", "audit", "other"}


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    datacenter_id: Mapped[int] = mapped_column(
        ForeignKey("datacenters.id"), nullable=False
    )
    work_type: Mapped[str] = mapped_column(String(32), nullable=False, default="install")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    change_req_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    datacenter: Mapped["Datacenter"] = relationship(  # type: ignore[name-defined]
        "Datacenter", back_populates="work_orders"
    )
    creator: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="work_orders", foreign_keys="[WorkOrder.created_by]"
    )
    connections: Mapped[list["Connection"]] = relationship(  # type: ignore[name-defined]
        "Connection", back_populates="work_order"
    )
    deleter: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys="[WorkOrder.deleted_by]"
    )
