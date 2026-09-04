# CrossConnect — Design Decisions

Replaces the Notion "Design Decisions" page (not accessible from work machine).
One section per significant architecture decision, newest first.

---

## Patch panel lifecycle, port occupancy, and trunk modeling

**Date:** 2026-09-03
**Method:** 5-persona architecture panel (DC infrastructure architect, DBA, DC technician, software-architect skeptic, risk/data-integrity reviewer)
**Status:** Design agreed, not yet built

### What prompted this

Three connected problems surfaced during pilot-data cleanup:

1. `PatchPanel` has no `deleted_at` / recycle-bin support, and `delete_rack()` blocked unconditionally on `rack.patch_panels` being non-empty. In the Ohio DC pilot data, **48 of 54 racks have exactly one patch panel each** — so almost no rack could be deleted, singly or in bulk.
2. Purge/cascade had no policy. System↔Device purge silently NULLed `device.system_id` on live, non-deleted devices — no error, no audit trail.
3. No clear decomm workflow: when a node is removed, the patch ports it occupied should free up, but it was unclear whether the app modeled that at all.

### Core design

**Patch panels are persistent inventory. Port occupancy is derived, not stored — with one deliberate exception.**

- A patch panel is rack infrastructure, like the rack itself. It persists through system/device decomm.
- A port (e.g. `A2`) is a **coordinate** on a panel, not an asset. Not a record.
- Occupancy is computed from active connection rows referencing panel + port.
- Decomm therefore needs no cascade logic: the connection row goes R-action → soft-deleted on WO complete → the port is free again, because "occupied" was never stored as state.

### Decisions locked in

**Deletion / lifecycle**
- `PatchPanel` gets `deleted_at` + recycle-bin support, matching the other entity types.
- `delete_rack()` blocks only on **active (non-deleted) panels with active connections** — not on panel existence alone. This is what unblocks the 48 racks.
- Purge cascade fixed: no more silent NULL-out of `device.system_id`. Either block the purge or require explicit reassignment.
- WO **cancellation** gets the same soft-delete behavior as WO completion for A/C-action rows. No separate handling needed.

**Port state — 4-state model, not binary**

| State | Meaning | Source |
|---|---|---|
| 🟢 Green | Open — no active connection | Derived |
| 🟡 Yellow | Pending — active connection on a draft/issued WO | Derived |
| 🔵 Blue | In use — connection on an in_progress/complete WO | Derived |
| 🔴 Red | Broken/failed — manually flagged | **Stored** |

- Red is the **one deliberate exception** to "never stored." A broken port has no connection row to derive from. Small sparse table: `panel_id`, `port`, `created_at`, `set_by`, optional `note`.
- New connection against a red port = **warn, not block**. Rare enough that a hard block isn't worth the friction — let the tech test and override. Log that the warning fired and was overridden.
- Admin/reporting page for outstanding red ports, **sorted by how long they've been outstanding**, so a flagged port doesn't sit invisible in an unwalked cabinet.

**Not modeled**
- Patch cables / jumpers stay unmodeled. They connect node → panel port and have no standalone value. A bad jumper is a port-state problem on the panel it terminates at, not a new entity.

**Trunks (panel-to-panel structured cabling)**
- Get their own lightweight entity, **lazily populated** — matching how the tool already works (cabinets populate as work orders touch them, not upfront).
- **No backfill** attempted for the existing hundreds/thousands of undocumented trunks.
- Each trunk record carries a `discovered_via_connection_id` pointer. Once created, the trunk is independent of any connection row and **survives deletion of the row that discovered it**.
- Rack-delete blast-radius guard checks discovered trunks landing in other racks/DCs. Explicitly **best-effort** — trunks nobody has patched through yet remain invisible until discovered. Accepted tradeoff.
- **Inter-DC ISL trunks are out of scope** for the guard. They aren't tied to a cabinet/patch panel in the current setup, so they fall outside the Trunk entity by design, not by omission.

**Uniqueness constraint — required, not optional**
- Active `panel + port` uniqueness must be enforced, mirrored for **both** device-side and switch-side patch ports.
- Without it, two active rows (or two separate drafts) can silently claim the same port.
- **Implementation is settled by the environment:** SQLite has no native partial unique constraint, so this follows the existing switch-port-uniqueness precedent — **service-layer check is primary, DB index is for lookup speed only**. Scoped to active, non-deleted, non-R rows.

### Scope options as presented

- **(a) Minimum viable** — `deleted_at` + fixed `delete_rack()` + fixed purge cascade + WO-cancel semantics. Unblocks the pilot's immediate breakage. Does **not** make occupancy trustworthy on its own (no uniqueness check yet).
- **(b) Proposal as written** — (a) + derived occupancy (green/yellow/blue) + sparse red-status table + uniqueness constraint.
- **(c)** — (b) + trunk modeling (empty table, lazy population via connection discovery, rack/cross-rack delete guard scoped to discovered trunks only).

**Panel's read:** (a) alone leaves occupancy correctness unresolved and shouldn't be described as "fixing occupancy" — it only fixes deletion. (b) and (c) together are a reasonably scoped, **additive build, not a remodel**, given the lazy-discovery approach for trunks.

### Single biggest open risk going into build

**Draft/issued double-booking.** Two people can currently claim the same port before the uniqueness constraint exists. This is the one item in the design that is fully specified but **not a guarantee until implemented** — treat as must-ship-with-v1, not a nice-to-have.

### Open question

Build sequencing: ship (a) immediately to unblock cleanup and follow with (b)+(c), or go straight to (b) as v1 given the uniqueness constraint is a must-ship?