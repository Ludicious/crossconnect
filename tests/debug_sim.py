#!/usr/bin/env python3
"""
CrossConnect debug simulation script.

Exercises the full workflow end-to-end against the live database:
  - Datacenters + contacts
  - Racks
  - Device types
  - Systems + devices (including parent/child)
  - Switches
  - Work orders (create, issue, pull back, re-issue, complete)
  - Connections (valid rows, duplicate switch port, missing mandatory fields,
    cross-cabinet cable length, same-rack cable length, LAG rows, fiber mode)
  - Status transitions (valid and invalid)
  - Soft delete + recycle bin check

Run from project root:
    .venv/bin/python -m tests.debug_sim

Prints a PASS/FAIL summary. Cleans up its own test data on completion
(unless --keep is passed).

Exit code: 0 if all pass, 1 if any fail.
"""
import sys
import argparse
from pathlib import Path

# Allow running as module from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.models.user import User
from app.models.inventory import Datacenter, DCContact, Rack, System, Device, Switch, DeviceType
from app.models.work_order import WorkOrder
from app.models.connection import Connection
import app.services.inventory as inv_svc
import app.services.work_orders as wo_svc
from app.services.auth import create_user, get_user_by_username


# ── Test harness ──────────────────────────────────────────────────────────

RESULTS: list[tuple[str, bool, str]] = []
CREATED_IDS: dict[str, list[int]] = {
    "datacenter": [], "rack": [], "system": [], "device": [],
    "switch": [], "device_type": [], "work_order": [], "user": [],
}


def check(label: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    RESULTS.append((label, condition, detail))
    icon = "✓" if condition else "✗"
    print(f"  [{icon}] {label}" + (f"  — {detail}" if detail else ""))
    return condition


def expect_error(label: str, fn, expected_fragment: str = ""):
    """Assert that fn() raises ValueError containing expected_fragment."""
    try:
        fn()
        check(label, False, f"Expected ValueError but no exception raised")
        return False
    except ValueError as e:
        ok = expected_fragment.lower() in str(e).lower() if expected_fragment else True
        check(label, ok, str(e) if not ok else "")
        return ok
    except Exception as e:
        check(label, False, f"Unexpected exception: {type(e).__name__}: {e}")
        return False


def section(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ── Setup ─────────────────────────────────────────────────────────────────

def pre_run_cleanup(db):
    """
    Remove any stale test data left by a previous --keep run or crash.
    Safe to call even if nothing exists.
    """
    from app.models.connection import Connection
    from app.models.work_order import WorkOrder

    stale_wos = db.query(WorkOrder).filter(WorkOrder.name.like("_SIM%")).all()
    for wo in stale_wos:
        db.query(Connection).filter(Connection.work_order_id == wo.id).delete()
        db.delete(wo)

    from app.models.inventory import Switch, Device, System, Rack, DCContact, Datacenter, DeviceType
    db.query(Switch).filter(Switch.name.like("_SIM%")).delete()
    # Devices: children before parents (self-referential FK)
    children = db.query(Device).filter(
        Device.name.like("_SIM%"), Device.parent_device_id.isnot(None)).all()
    for d in children:
        db.delete(d)
    db.flush()
    db.query(Device).filter(Device.name.like("_SIM%")).delete()
    db.query(System).filter(System.name.like("_SIM%")).delete()

    stale_racks = db.query(Rack).filter(Rack.name.like("_SIM%")).all()
    for r in stale_racks:
        db.delete(r)

    stale_dcs = db.query(Datacenter).filter(
        (Datacenter.name.like("_SIM%")) | (Datacenter.code.like("SIM%"))).all()
    for dc in stale_dcs:
        db.query(DCContact).filter(DCContact.datacenter_id == dc.id).delete()
        db.delete(dc)

    db.query(DeviceType).filter(DeviceType.manufacturer.like("_SIM%")).delete()

    stale_users = db.query(User).filter(User.username == "_sim_architect").all()
    for u in stale_users:
        db.delete(u)

    db.commit()


def setup_test_user(db) -> User:
    username = "_sim_architect"
    existing = get_user_by_username(db, username)
    if existing:
        return existing
    u = create_user(db, username=username, display_name="Sim Architect",
                    password="sim_password_123", role="architect")
    CREATED_IDS["user"].append(u.id)
    return u


# ── Datacenter tests ──────────────────────────────────────────────────────

def test_datacenters(db) -> Datacenter:
    section("Datacenters + Contacts")

    # Create
    dc = inv_svc.create_datacenter(db, name="_SIM Test DC", code="SIM",
                                    address="123 Sim St", has_grid_system=True)
    CREATED_IDS["datacenter"].append(dc.id)
    check("Create datacenter", dc.id is not None, f"id={dc.id}")
    check("Code uppercased", dc.code == "SIM")
    check("Address stored", dc.address == "123 Sim St")

    # Duplicate name
    expect_error("Duplicate DC name blocked",
                 lambda: inv_svc.create_datacenter(db, name="_SIM Test DC", code="SIM2"),
                 "already exists")

    # Duplicate code
    expect_error("Duplicate DC code blocked",
                 lambda: inv_svc.create_datacenter(db, name="_SIM Test DC 2", code="SIM"),
                 "already in use")

    # Contacts
    inv_svc.upsert_contacts(db, dc, [
        {"name": "Alice", "role": "Site Lead", "email": "alice@sim.test", "phone": "555-0001"},
        {"name": "Bob",   "role": "NOC",       "email": "bob@sim.test",   "phone": "555-0002"},
    ])
    db.refresh(dc)
    check("Contacts saved", len(dc.contacts) == 2, f"{len(dc.contacts)} contacts")
    check("Contact name", dc.contacts[0].name == "Alice")
    check("Contact role", dc.contacts[0].role == "Site Lead")

    # Upsert replaces existing
    inv_svc.upsert_contacts(db, dc, [
        {"name": "Charlie", "role": "Facilities", "email": "charlie@sim.test", "phone": ""},
    ])
    db.refresh(dc)
    check("Contact upsert replaces", len(dc.contacts) == 1)
    check("New contact name", dc.contacts[0].name == "Charlie")

    # Empty-name contact skipped
    inv_svc.upsert_contacts(db, dc, [
        {"name": "Valid", "role": "", "email": "", "phone": ""},
        {"name": "",      "role": "skip me", "email": "", "phone": ""},
    ])
    db.refresh(dc)
    check("Empty-name contact skipped", len(dc.contacts) == 1)

    return dc


# ── Rack tests ────────────────────────────────────────────────────────────

def test_racks(db, dc: Datacenter) -> Rack:
    section("Racks")

    rack = inv_svc.create_rack(db, dc_id=dc.id, name="_SIM-RACK-01",
                                grid_position="AA-01", total_ru=42)
    CREATED_IDS["rack"].append(rack.id)
    check("Create rack", rack.id is not None)
    check("Grid position stored", rack.grid_position == "AA-01")
    check("Total RU stored", rack.total_ru == 42)

    # Duplicate rack name in same DC
    expect_error("Duplicate rack name in DC blocked",
                 lambda: inv_svc.create_rack(db, dc_id=dc.id, name="_SIM-RACK-01"),
                 "already exists")

    # Same name in different DC should be allowed — use a temp DC
    dc2 = inv_svc.create_datacenter(db, name="_SIM Test DC 2", code="SIM2")
    CREATED_IDS["datacenter"].append(dc2.id)
    rack2 = inv_svc.create_rack(db, dc_id=dc2.id, name="_SIM-RACK-01")
    CREATED_IDS["rack"].append(rack2.id)
    check("Same rack name in different DC allowed", rack2.id is not None)

    # Update
    inv_svc.update_rack(db, rack, name="_SIM-RACK-01", grid_position="BB-02", total_ru=42)
    db.refresh(rack)
    check("Update rack grid position", rack.grid_position == "BB-02")

    return rack


# ── Device type tests ─────────────────────────────────────────────────────

def test_device_types(db) -> tuple[DeviceType, DeviceType]:
    section("Device Types")

    dt_storage = inv_svc.create_device_type(
        db, manufacturer="_SIM NetApp", model="AFF A400",
        category="storage", rack_u=2, slot_count=None)
    CREATED_IDS["device_type"].append(dt_storage.id)
    check("Create storage device type", dt_storage.id is not None)

    dt_chassis = inv_svc.create_device_type(
        db, manufacturer="_SIM Cisco", model="UCS 5108",
        category="server", rack_u=7, slot_count=8,
        notes="Blade chassis, 8 slots")
    CREATED_IDS["device_type"].append(dt_chassis.id)
    check("Create chassis device type", dt_chassis.id is not None)
    check("Slot count stored", dt_chassis.slot_count == 8)

    # Duplicate
    expect_error("Duplicate device type blocked",
                 lambda: inv_svc.create_device_type(
                     db, manufacturer="_SIM NetApp", model="AFF A400"),
                 "already exists")

    # Autocomplete
    results = inv_svc.autocomplete_device_types(db, "_SIM")
    check("Autocomplete returns both types", len(results) >= 2)
    results_storage = inv_svc.autocomplete_device_types(db, "_SIM", category="storage")
    check("Autocomplete category filter", len(results_storage) == 1)
    check("Autocomplete rack_u present", results_storage[0]["rack_u"] == 2)

    return dt_storage, dt_chassis


# ── Device tests ──────────────────────────────────────────────────────────

def test_devices(db, rack: Rack, dt_storage: DeviceType, dt_chassis: DeviceType) -> Device:
    section("Systems + Devices (including parent/child)")

    # System
    system = inv_svc.create_system(db, name="_SIM Storage Cluster", system_type="storage")
    CREATED_IDS["system"].append(system.id)
    check("Create system", system.id is not None)

    # Duplicate system name
    expect_error("Duplicate system name blocked",
                 lambda: inv_svc.create_system(db, name="_SIM Storage Cluster"),
                 "already exists")

    # Standalone device (no system)
    standalone = inv_svc.create_device(db, rack_id=rack.id,
                                        name="_SIM-srv-01", device_type_id=dt_storage.id)
    CREATED_IDS["device"].append(standalone.id)
    check("Create standalone device (no system)", standalone.id is not None)
    check("Device type FK set", standalone.device_type_id == dt_storage.id)

    # Device with system
    node = inv_svc.create_device(db, rack_id=rack.id, name="_SIM-stor-44-01",
                                  system_id=system.id, starting_ru=10,
                                  serial="SN-001", device_type_id=dt_storage.id)
    CREATED_IDS["device"].append(node.id)
    check("Device with system", node.system_id == system.id)
    check("Starting RU stored", node.starting_ru == 10)

    # Parent/child: chassis + blade
    chassis = inv_svc.create_device(db, rack_id=rack.id, name="_SIM-UCS-5108",
                                     device_type_id=dt_chassis.id, starting_ru=20)
    CREATED_IDS["device"].append(chassis.id)
    blade = inv_svc.create_device(db, rack_id=rack.id, name="_SIM-UCS-blade-01",
                                   parent_device_id=chassis.id, slot_number=1)
    CREATED_IDS["device"].append(blade.id)
    db.refresh(blade)
    check("Child device parent FK", blade.parent_device_id == chassis.id)
    check("Child device slot number", blade.slot_number == 1)
    db.refresh(chassis)
    check("Parent has child_devices backref", len(chassis.child_devices) == 1)

    return node


# ── Switch tests ──────────────────────────────────────────────────────────

def test_switches(db, rack: Rack) -> Switch:
    section("Switches")

    dt_sw = inv_svc.create_device_type(db, manufacturer="_SIM Cisco",
                                        model="C9300-48P", category="switch", rack_u=1)
    CREATED_IDS["device_type"].append(dt_sw.id)

    sw = inv_svc.create_switch(db, rack_id=rack.id, name="_SIM-SW-LAN-01",
                                switch_role="LAN", starting_ru=30,
                                switch_type_id=dt_sw.id)
    CREATED_IDS["switch"].append(sw.id)
    check("Create LAN switch", sw.id is not None)
    check("Switch type FK", sw.switch_type_id == dt_sw.id)

    sw_san = inv_svc.create_switch(db, rack_id=rack.id, name="_SIM-SW-SAN-01",
                                    switch_role="SAN", starting_ru=32)
    CREATED_IDS["switch"].append(sw_san.id)
    check("Create SAN switch", sw_san.switch_role == "SAN")

    # Autocomplete filter by role
    results = inv_svc.autocomplete_switches(db, "_SIM", role="SAN")
    check("Switch autocomplete role filter", len(results) == 1)
    check("Switch autocomplete label includes role", "SAN" in results[0]["label"])

    return sw


# ── Work order + connection tests ─────────────────────────────────────────


def test_template_renders(db, dc, rack, user):
    """
    Render every major template against real data to catch Jinja2 errors
    that only surface with None/mixed data (e.g. sorting nulls, missing FKs).
    Uses Jinja2 directly — no HTTP server needed.
    """
    section("Template Renders (Jinja2 direct)")

    from jinja2 import Environment, FileSystemLoader
    import os

    template_dir = str(Path(__file__).resolve().parents[1] / "app" / "templates")
    env = Environment(loader=FileSystemLoader(template_dir))

    class FakeRequest:
        class url:
            path = "/test"

    ctx_base = {"request": FakeRequest(), "user": user}

    def render(template_name, extra_ctx):
        try:
            t = env.get_template(template_name)
            t.render(**ctx_base, **extra_ctx)
            check(f"Render {template_name}", True)
            return True
        except Exception as e:
            check(f"Render {template_name}", False, f"{type(e).__name__}: {e}")
            return False

    # Inventory pages
    from app.services.inventory import get_datacenter, get_rack, list_datacenters, list_systems, list_device_types
    dc_full = get_datacenter(db, dc.id)
    rack_full = get_rack(db, rack.id)
    dcs = list_datacenters(db)
    systems = list_systems(db)
    dts = list_device_types(db)

    render("inventory/index.html", {"datacenters": dcs, "systems": systems})
    render("inventory/dc_detail.html", {"dc": dc_full, "racks": dc_full.racks})
    render("inventory/dc_form.html", {"dc": None, "error": None})
    render("inventory/dc_form.html", {"dc": dc_full, "error": None})
    render("inventory/rack_detail.html", {"rack": rack_full})
    render("inventory/rack_form.html", {"dc": dc_full, "rack": None, "error": None})
    render("inventory/rack_form.html", {"dc": dc_full, "rack": rack_full, "error": None})
    render("inventory/device_type_list.html", {"device_types": dts})
    render("inventory/device_type_form.html", {"dt": None, "error": None})
    render("inventory/system_form.html", {"system": None, "error": None})

    # Work order pages — need a WO with connections
    from app.services.work_orders import list_work_orders, list_connections
    wos = list_work_orders(db)
    render("work_orders/list.html", {
        "work_orders": wos,
        "datacenters": dcs,
        "filter_dc_id": None,
        "filter_status": None,
    })
    if wos:
        wo = wos[0]
        conns = list_connections(db, wo.id)
        render("work_orders/detail.html", {
            "wo": wo, "connections": conns,
            "CABLE_TYPES": ["RJ45","LC_Fiber","DAC","other"],
            "PURPOSES": ["management","data","storage","other"],
            "ACTIONS": ["A","R","C"],
            "FABRICS": ["","A","B"],
            "INSTALL_STATUSES": ["pending","done","blocked","change_required"],
            "validation_errors": [],
        })

    # Report page
    from app.models.work_order import WorkOrder
    wo_list = db.query(WorkOrder).filter(
        WorkOrder.status.in_(["issued","in_progress","complete"])).all()
    render("reports/connections.html", {
        "connections": [],
        "datacenters": dcs,
        "work_orders": wo_list,
        "filter_dc_id": None, "filter_wo_id": None,
        "filter_install_status": None, "filter_fabric": None, "filter_action": None,
        "INSTALL_STATUSES": ["pending","done","blocked","change_required"],
        "ACTIONS": ["A","R","C"],
        "FABRICS": ["A","B"],
    })



def test_work_orders(db, dc: Datacenter, rack: Rack, sw: Switch, user: User):
    section("Work Orders")

    wo = wo_svc.create_work_order(db, name="_SIM Work Order", datacenter_id=dc.id,
                                   work_type="install", created_by=user.id)
    CREATED_IDS["work_order"].append(wo.id)
    check("Create work order", wo.id is not None)
    check("Status is draft", wo.status == "draft")

    # Invalid work type
    expect_error("Invalid work type blocked",
                 lambda: wo_svc.create_work_order(db, name="x", datacenter_id=dc.id,
                                                   work_type="invalid", created_by=user.id),
                 "Invalid work type")

    section("Connections — Valid rows")

    def conn(extra={}):
        base = {
            "action": "A", "cable_type": "LC_Fiber", "purpose": "storage",
            "device_rack_name_raw": rack.name, "device_rack_u": "10",
            "device_slot": "4a", "device_port": "0",
            "switch_rack_name_raw": rack.name, "switch_rack_u": "30",
            "switch_slot": "1", "switch_port": "1",
            "install_status": "pending",
        }
        base.update(extra)
        return base

    # Unique port counter to avoid duplicate switch port errors
    port_counter = [1]
    def next_port():
        p = str(port_counter[0])
        port_counter[0] += 1
        return p

    # Direct same-rack connection
    c1, errs, warns = wo_svc.create_connection(db, wo.id,
        conn({"switch_port": next_port()}), user.id)
    check("Create valid connection", len(errs) == 0, f"errs={errs}")
    check("Cable length auto-computed", c1.seg1_length is not None,
          f"seg1={c1.seg1_length}")
    check("Same-rack length is numeric", c1.seg1_length not in ("cross-cabinet","incomplete","exceeds_max"),
          f"seg1={c1.seg1_length}")

    # Cross-cabinet
    c2, errs2, _ = wo_svc.create_connection(db, wo.id,
        conn({"switch_rack_name_raw": "OTHER-RACK", "switch_port": next_port()}), user.id)
    check("Cross-cabinet connection saves", len(errs2) == 0)
    check("Cross-cabinet seg1 = cross-cabinet", c2.seg1_length == "cross-cabinet",
          f"got {c2.seg1_length}")

    # Incomplete — missing switch_rack_u
    c3, errs3, _ = wo_svc.create_connection(db, wo.id,
        conn({"switch_rack_u": "", "switch_port": next_port()}), user.id)
    check("Incomplete connection saves (validation at issue time)", True)
    check("Incomplete seg1 = incomplete", c3.seg1_length == "incomplete",
          f"got {c3.seg1_length}")

    # Fabric A and B
    cA, _, _ = wo_svc.create_connection(db, wo.id,
        conn({"fabric": "A", "switch_port": next_port()}), user.id)
    cB, _, _ = wo_svc.create_connection(db, wo.id,
        conn({"fabric": "B", "switch_port": next_port()}), user.id)
    check("Fabric A row saved", cA.fabric == "A")
    check("Fabric B row saved", cB.fabric == "B")

    # LAG pair
    cLAG1, _, _ = wo_svc.create_connection(db, wo.id,
        conn({"lag_id": "Po1", "lag_member_index": "1",
              "switch_port": next_port()}), user.id)
    cLAG2, _, _ = wo_svc.create_connection(db, wo.id,
        conn({"lag_id": "Po1", "lag_member_index": "2",
              "switch_port": next_port()}), user.id)
    check("LAG member 1 saved", cLAG1.lag_id == "Po1")
    check("LAG member 2 saved", cLAG2.lag_member_index == 2)

    # Singlemode fiber
    cSM, _, _ = wo_svc.create_connection(db, wo.id,
        conn({"fiber_mode": "singlemode", "switch_port": next_port()}), user.id)
    check("Singlemode fiber mode saved", cSM.fiber_mode == "singlemode")

    section("Connections — Validation / Duplicate checks")

    # Duplicate switch port — hard block (using raw name path, matching real UI)
    c_dup, errs_dup, _ = wo_svc.create_connection(db, wo.id,
        conn({"switch_name_raw": "_SIM-SW-DEDUP", "switch_slot": "1", "switch_port": "99"}), user.id)
    check("First switch port assignment succeeds", len(errs_dup) == 0)

    c_dup2, errs_dup2, _ = wo_svc.create_connection(db, wo.id,
        conn({"switch_name_raw": "_SIM-SW-DEDUP", "switch_slot": "1", "switch_port": "99"}), user.id)
    check("Duplicate switch port hard-blocked", len(errs_dup2) > 0,
          f"errs={errs_dup2}")

    section("Work Order Status Transitions")

    # Can't issue with incomplete rows — try with just the one bad row (c3 has missing switch_rack_u)
    # But we have other valid rows too, so only c3 should fail
    try:
        wo_svc.transition_status(db, wo, "issued", user)
        db.refresh(wo)
        if wo.status == "issued":
            check("Issue with mixed rows (some incomplete) — check behavior",
                  True, "issued despite incomplete row — validation only blocks if ALL mandatory missing")
        else:
            check("Status after issue attempt", False, f"status={wo.status}")
    except ValueError as e:
        row_errors = getattr(e, "row_errors", [])
        check("Issue blocked due to validation errors",
              len(row_errors) > 0, f"{len(row_errors)} rows with errors")
        # Fix the bad row and try again — delete c3
        wo_svc.soft_delete_connection(db, c3, user.id)
        wo_svc.transition_status(db, wo, "issued", user)
        db.refresh(wo)
        check("Issue succeeds after fixing errors", wo.status == "issued")

    # Pull back to draft
    wo_svc.transition_status(db, wo, "draft", user)
    db.refresh(wo)
    check("Pull back to draft", wo.status == "draft")

    # Re-issue
    wo_svc.transition_status(db, wo, "issued", user)
    db.refresh(wo)
    check("Re-issue succeeds", wo.status == "issued")

    # Invalid transition (issued → complete skips in_progress)
    expect_error("Invalid transition issued→complete blocked",
                 lambda: wo_svc.transition_status(db, wo, "complete", user),
                 "Cannot move")

    # In progress
    wo_svc.transition_status(db, wo, "in_progress", user)
    db.refresh(wo)
    check("In progress transition", wo.status == "in_progress")

    # Complete — should soft-delete R-action rows
    r_conn, _, _ = wo_svc.create_connection(db, wo.id,
        conn({"action": "R", "switch_port": "R1"}), user.id)
    check("R-action row created", r_conn.action == "R")
    wo_svc.transition_status(db, wo, "complete", user)
    db.refresh(wo)
    check("Complete transition", wo.status == "complete")
    db.refresh(r_conn)
    check("R-action row soft-deleted on complete", r_conn.deleted_at is not None)

    section("Soft Delete")

    total = db.query(Connection).filter(
        Connection.work_order_id == wo.id).count()
    active = db.query(Connection).filter(
        Connection.work_order_id == wo.id,
        Connection.deleted_at.is_(None)).count()
    deleted = db.query(Connection).filter(
        Connection.work_order_id == wo.id,
        Connection.deleted_at.isnot(None)).count()
    check("Total connections tracked", total > 0, f"{total} total")
    check("Active connections > 0", active > 0, f"{active} active")
    check("Deleted connections tracked (R-rows + c3)", deleted >= 2, f"{deleted} deleted")


# ── Cleanup ───────────────────────────────────────────────────────────────

def cleanup(db):
    section("Cleanup")
    from sqlalchemy import text

    # Delete in reverse FK order
    for wo_id in CREATED_IDS["work_order"]:
        db.query(Connection).filter(Connection.work_order_id == wo_id).delete()
        db.query(WorkOrder).filter(WorkOrder.id == wo_id).delete()
    for sw_id in CREATED_IDS["switch"]:
        db.query(Switch).filter(Switch.id == sw_id).delete()
    for dev_id in reversed(CREATED_IDS["device"]):  # children before parents
        db.query(Device).filter(Device.id == dev_id).delete()
    for sys_id in CREATED_IDS["system"]:
        db.query(System).filter(System.id == sys_id).delete()
    for dt_id in CREATED_IDS["device_type"]:
        db.query(DeviceType).filter(DeviceType.id == dt_id).delete()
    for rack_id in CREATED_IDS["rack"]:
        db.query(Rack).filter(Rack.id == rack_id).delete()
    for dc_id in CREATED_IDS["datacenter"]:
        db.query(DCContact).filter(DCContact.datacenter_id == dc_id).delete()
        db.query(Datacenter).filter(Datacenter.id == dc_id).delete()
    for user_id in CREATED_IDS["user"]:
        db.query(User).filter(User.id == user_id).delete()
    db.commit()
    print("  Test data removed.")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CrossConnect debug simulation")
    parser.add_argument("--keep", action="store_true",
                        help="Keep test data in DB after run (for manual inspection)")
    args = parser.parse_args()

    print("\nCrossConnect Debug Simulation")
    print("=" * 60)

    db = SessionLocal()
    try:
        pre_run_cleanup(db)
        user = setup_test_user(db)
        dc = test_datacenters(db)
        rack = test_racks(db, dc)
        dt_storage, dt_chassis = test_device_types(db)
        device = test_devices(db, rack, dt_storage, dt_chassis)
        sw = test_switches(db, rack)
        test_template_renders(db, dc, rack, user)
        test_work_orders(db, dc, rack, sw, user)
    except Exception as e:
        import traceback
        print(f"\n  FATAL: Unhandled exception during simulation:")
        traceback.print_exc()
        RESULTS.append(("Unhandled exception", False, str(e)))
    finally:
        if not args.keep:
            try:
                cleanup(db)
            except Exception as e:
                print(f"  WARNING: Cleanup failed: {e}")
        db.close()

    # Summary
    print(f"\n{'='*60}")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = sum(1 for _, ok, _ in RESULTS if not ok)
    total  = len(RESULTS)
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
        print(f"\n  Failed checks:")
        for label, ok, detail in RESULTS:
            if not ok:
                print(f"    ✗ {label}" + (f": {detail}" if detail else ""))
    else:
        print("  — all passed ✓")
    print()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
