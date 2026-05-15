"""
Cable length calculation service.

A connection has up to 4 endpoints:
    device  →  device_patch  →  switch_patch  →  switch

This produces up to 3 segments:
    seg1: device       → device_patch   (or device → switch if no patches at all)
    seg2: device_patch → switch_patch   (or device_patch → switch if no switch_patch;
                                          or device → switch_patch if no device_patch)
    seg3: switch_patch → switch

Segment is NULL when it doesn't apply to this connection's topology.

Per-segment result values:
    "2.0"          — computed length in metres (rounded up to nearest standard)
    "cross-cabinet"— endpoints in different racks, length undetermined
    "incomplete"   — required RU or rack data is missing
    "exceeds_max"  — computed raw length > 30m (data entry error)
    None           — segment not applicable
"""

import math
from typing import Optional
from sqlalchemy.orm import Session

from app.models.connection import Connection
from app.models.settings import AppSetting

# ── Constants ─────────────────────────────────────────────────────────────
INCHES_PER_METER = 39.3701
MAX_PLAUSIBLE_METERS = 30.0        # hard ceiling before we call it exceeds_max
RU_HEIGHT_INCHES = 1.75            # 1U = 1.75 inches


# ── Settings helpers ──────────────────────────────────────────────────────

def _load_settings(db: Session) -> dict:
    rows = db.query(AppSetting).filter(
        AppSetting.key.in_([
            "cable_slack_inches_per_end",
            "cable_standard_lengths_m",
        ])
    ).all()
    s = {r.key: r.value for r in rows}
    return {
        "slack_inches_per_end": float(s.get("cable_slack_inches_per_end", "18")),
        "standard_lengths": [
            float(x.strip())
            for x in s.get("cable_standard_lengths_m", "0.5,1,2,3,5,7,10").split(",")
            if x.strip()
        ],
    }


# ── Core calculation ──────────────────────────────────────────────────────

def _round_up_to_standard(meters: float, standards: list[float]) -> Optional[str]:
    """
    Round UP to the nearest value in standards.
    Returns "exceeds_max" if meters > MAX_PLAUSIBLE_METERS or exceeds all standards.
    """
    if meters > MAX_PLAUSIBLE_METERS:
        return "exceeds_max"
    for length in sorted(standards):
        if length >= meters:
            return str(int(length)) if length == int(length) else str(length)
    # Larger than all standard lengths but under MAX_PLAUSIBLE_METERS
    return "exceeds_max"


def _calc_segment(
    rack_a: Optional[str],
    ru_a: Optional[int],
    rack_b: Optional[str],
    ru_b: Optional[int],
    slack_inches: float,
    standards: list[float],
) -> Optional[str]:
    """
    Calculate one segment given rack names and RU positions of two endpoints.
    Returns a result string or None if the segment shouldn't exist (both fields absent).
    """
    # If both endpoints have no rack/RU at all, segment is not applicable
    if not rack_a and not ru_a and not rack_b and not ru_b:
        return None

    # Missing required data
    if not rack_a or ru_a is None or not rack_b or ru_b is None:
        return "incomplete"

    # Different racks — cross-cabinet, length undetermined
    if rack_a.strip().lower() != rack_b.strip().lower():
        return "cross-cabinet"

    # Same rack — compute
    ru_diff_inches = abs(ru_a - ru_b) * RU_HEIGHT_INCHES
    total_inches = ru_diff_inches + (2 * slack_inches)
    total_meters = total_inches / INCHES_PER_METER
    return _round_up_to_standard(total_meters, standards)


# ── Endpoint topology resolver ─────────────────────────────────────────────

def _has_device_patch(c: Connection) -> bool:
    return bool(c.device_patch_rack_name_raw or c.device_patch_ru)


def _has_switch_patch(c: Connection) -> bool:
    return bool(c.switch_patch_rack_name_raw or c.switch_patch_ru)


def compute_segments(c: Connection, slack: float, standards: list[float]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Returns (seg1, seg2, seg3).

    Topology routing:
    ┌──────────┬──────────────┬──────────────────────────────────────────────────┐
    │ dev_patch│ sw_patch     │ Routing                                          │
    ├──────────┼──────────────┼──────────────────────────────────────────────────┤
    │ No       │ No           │ seg1 = dev→sw,   seg2 = null, seg3 = null        │
    │ Yes      │ No           │ seg1 = dev→dp,   seg2 = dp→sw, seg3 = null       │
    │ No       │ Yes          │ seg1 = dev→sp,   seg2 = null,  seg3 = sp→sw      │
    │ Yes      │ Yes          │ seg1 = dev→dp,   seg2 = dp→sp, seg3 = sp→sw      │
    └──────────┴──────────────┴──────────────────────────────────────────────────┘
    """
    has_dp = _has_device_patch(c)
    has_sp = _has_switch_patch(c)

    dev_rack = c.device_rack_name_raw
    dev_ru   = c.device_rack_u
    dp_rack  = c.device_patch_rack_name_raw
    dp_ru    = c.device_patch_ru
    sp_rack  = c.switch_patch_rack_name_raw
    sp_ru    = c.switch_patch_ru
    sw_rack  = c.switch_rack_name_raw
    sw_ru    = c.switch_rack_u

    if not has_dp and not has_sp:
        # Direct: device → switch
        seg1 = _calc_segment(dev_rack, dev_ru, sw_rack, sw_ru, slack, standards)
        return seg1, None, None

    if has_dp and not has_sp:
        # device → device_patch → switch
        seg1 = _calc_segment(dev_rack, dev_ru, dp_rack, dp_ru, slack, standards)
        seg2 = _calc_segment(dp_rack, dp_ru, sw_rack, sw_ru, slack, standards)
        return seg1, seg2, None

    if not has_dp and has_sp:
        # device → switch_patch → switch
        seg1 = _calc_segment(dev_rack, dev_ru, sp_rack, sp_ru, slack, standards)
        seg3 = _calc_segment(sp_rack, sp_ru, sw_rack, sw_ru, slack, standards)
        return seg1, None, seg3

    # has_dp and has_sp: device → device_patch → switch_patch → switch
    seg1 = _calc_segment(dev_rack, dev_ru, dp_rack, dp_ru, slack, standards)
    seg2 = _calc_segment(dp_rack, dp_ru, sp_rack, sp_ru, slack, standards)
    seg3 = _calc_segment(sp_rack, sp_ru, sw_rack, sw_ru, slack, standards)
    return seg1, seg2, seg3


# ── Public API ─────────────────────────────────────────────────────────────

def calculate_and_store(db: Session, conn: Connection) -> Connection:
    """
    Compute cable lengths for a single connection and write back to DB.
    Called automatically after every connection save.
    """
    cfg = _load_settings(db)
    seg1, seg2, seg3 = compute_segments(
        conn,
        slack=cfg["slack_inches_per_end"],
        standards=cfg["standard_lengths"],
    )
    conn.seg1_length = seg1
    conn.seg2_length = seg2
    conn.seg3_length = seg3
    db.commit()
    return conn


def recalculate_work_order(db: Session, wo_id: int) -> int:
    """
    Recalculate all connections in a work order (e.g. after settings change).
    Returns count of rows updated.
    """
    from app.models.connection import Connection
    cfg = _load_settings(db)
    conns = db.query(Connection).filter(
        Connection.work_order_id == wo_id,
        Connection.deleted_at.is_(None),
    ).all()
    for c in conns:
        seg1, seg2, seg3 = compute_segments(c, cfg["slack_inches_per_end"], cfg["standard_lengths"])
        c.seg1_length = seg1
        c.seg2_length = seg2
        c.seg3_length = seg3
    db.commit()
    return len(conns)


def recalculate_all(db: Session) -> int:
    """Recalculate every non-deleted connection. Used after global settings change."""
    from app.models.connection import Connection
    cfg = _load_settings(db)
    conns = db.query(Connection).filter(Connection.deleted_at.is_(None)).all()
    for c in conns:
        seg1, seg2, seg3 = compute_segments(c, cfg["slack_inches_per_end"], cfg["standard_lengths"])
        c.seg1_length = seg1
        c.seg2_length = seg2
        c.seg3_length = seg3
    db.commit()
    return len(conns)
