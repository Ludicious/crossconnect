# CrossConnect — Task Tracker

Replaces the Notion "CrossConnect – Wired Right" workspace (not accessible from work machine).
Same fields as the old Notion Tasks DB: **Type** (Feature/Refactor/UX/Tech debt/Investigation),
**Priority** (P0-critical/P1-high/P2-normal/P3-nice to have), **Phase**, **Notes**.

GitHub Issues remain bugs-only. Everything else — features, UX, tech debt — lives here.

---

## In Progress

- **Patch panel lifecycle / port occupancy / trunk modeling — scope (c), full build.** Started 2026-09-03. Design locked (see `DESIGN_DECISIONS.md`). Building in three sessions: (1) schema + migrations + deletion/purge semantics, (2) derived occupancy + red-port state + uniqueness constraint, (3) trunk entity + lazy discovery + blast-radius guard. Dev DB being wiped and recreated between session 1 and the test import.

---

## Up Next

| Task | Type | Priority | Phase | Notes |
|---|---|---|---|---|
| Excel export matching template | Feature | — | Unscoped | **Needs confirmation.** Old handoff doc described this as Phase 8, but the actual Phase 8 commit (`bf3d271`) was PDF export via WeasyPrint, not this. Label export (Phase 7, Brother P-touch) exists but is a different feature. Confirm whether this is still wanted, and if so scope it fresh. |
| Clickable row/object affordance (underline/cursor treatment) | UX | P2-normal | Cross-cutting | Reported 2026-09-03. Merges with existing "UX clickability affordances" backlog item below — likely a quick CSS/cursor pass, no backend involved. Good candidate for a same-session quick win. |
| Settings page 404s | Bug? | — | — | Reported 2026-09-03. Repros as a hard 404, not a missing-feature gap — per project convention this should move to **GitHub Issues** once confirmed. Logged here temporarily since it came in as part of this batch. Needs a quick check: is this a genuinely unbuilt route, or a broken link to the existing Admin tuning page? |
| Excel import: select which worksheets to import | Feature | P1-high | Unscoped | Reported 2026-09-03. Current import pulls every worksheet in the workbook. Real-world workbooks mix unrelated sheets (IP assignments, LAN X-connect, WAN X-connect) — importing all of them corrupted inventory data on first real-world test. Needs a sheet-picker UI + import service change to accept a sheet allowlist. **Next up now that bulk delete has shipped** — this closes out the original bad-import root cause. |
| Rack detail page shows soft-deleted devices/switches forever (display bug, not a delete bug) | Bug | P1-high | — | Diagnosed 2026-09-03. What looked like "device delete button does nothing" is actually a display bug: `get_rack()` (`inventory.py:115-121`) does `joinedload(Rack.devices)`/`joinedload(Rack.switches)` with **no `deleted_at` filter**, unlike `list_devices()`/`list_switches()`/`get_rack_elevation()`, which correctly filter. Delete itself works fully (verified: 302, `deleted_at` set, appears in recycle bin Devices tab) — the rack detail page and its device/switch counts just never reflect it. Cheap, safe, well-scoped fix: add the same filter already used elsewhere. Ready to build — no design decision needed. |
| Recycle-bin purge has no cascade policy — crashes on some entity pairs, silently corrupts data on others | Bug | P0-critical | — | Diagnosed 2026-09-03, connects to the earlier rack-hard-delete cascade bug (same root defect, more callers found). `purge_all()`/`hard_delete_*()` in `recycle_bin.py` are pure delete-with-no-checks — no ordering, no dependency check, unlike `delete_rack()`/`delete_system()` which guard the *first* soft-delete. Three distinct failure modes found: **(a)** Rack↔Device/Switch — `NOT NULL constraint failed` crash, purge aborts, nothing corrupted (same mechanism as the earlier-flagged bug). **(b)** System↔Device — **silent, unsafe "success"**: purging a system with active (non-deleted) devices sets their `system_id` to `NULL` with no error, no confirmation, no audit entry — this is the serious one, it corrupts live inventory data rather than just failing loudly. **(c)** Rack/Device/Switch/System↔Connection — no ORM relationship declared, so SQLite's own FK enforcement rejects the raw `DELETE` — loud failure, safe. **Recommended fix (from diagnosis):** extend the existing "block while children exist" guard from the soft-delete path to the purge path too, checking for *any* remaining child rows (active or soft-deleted-and-unpurged) — turns all three failure modes into the same clean itemized error the normal delete flow already gives. **Now folded into the patch panel/occupancy design (see above)** — the architecture panel locked in "no more silent NULL-out; either block the purge or require explicit reassignment." Build this as part of that work rather than separately. |
| Patch panel lifecycle + port occupancy + trunk modeling | Feature | P0-critical | Unscoped | **Design resolved 2026-09-03 via 5-persona architecture panel — ready to scope into build phases.** Full design recap saved separately; key decisions: PatchPanel gets `deleted_at` + recycle-bin support; `delete_rack()` blocks only on active panels with active connections, not on panel existence alone (this is what unblocks the 48/54 Ohio DC racks). Purge cascade fixed — no more silent `device.system_id` NULL-out, either block or require explicit reassignment. WO cancellation gets same soft-delete behavior as completion for A/C-action rows. **Port state is 4-state, not binary:** green=open, yellow=pending (draft/issued WO), blue=in use (in_progress/complete WO), red=broken. Green/yellow/blue are derived from active connection rows; **red is the one deliberate stored exception** — sparse table (panel_id, port, created_at, set_by, note) since a broken port has no connection row to derive from. New connection against a red port = warn + log override, not block. Patch cables/jumpers stay unmodeled (a bad jumper is a port-state problem, not an entity). Trunks get a lightweight entity, **lazily populated** via `discovered_via_connection_id` — no backfill of existing undocumented trunks; trunk records survive deletion of the connection that discovered them. Rack-delete blast-radius guard checks discovered trunks landing in other racks/DCs — explicitly best-effort, undiscovered trunks stay invisible (accepted tradeoff). Inter-DC ISL trunks out of scope by design. Admin page for outstanding red ports, sorted by age outstanding. |
| Active panel+port uniqueness constraint — **must ship with v1** | Feature | P0-critical | — | Panel's single biggest flagged risk 2026-09-03: without it, two active connection rows (or two separate drafts) can silently claim the same patch port — draft/issued double-booking. Occupancy is not trustworthy until this exists, so it ships with the first occupancy work, not later. Must be mirrored for **both** device-side and switch-side patch ports. **Implementation is already settled by the environment:** SQLite has no native partial unique constraint, so this follows the existing switch-port-uniqueness precedent — service-layer check is primary, any DB index is for lookup speed only. Scoped to active, non-deleted, non-R rows, same as the switch-port check. |
| Build sequencing decision: scope (a), (b), or (c) | Investigation / Product decision | — | — | **DECIDED 2026-09-03: going with (c) — full scope.** Rationale: pilot data is disposable (it was deliberately garbage data used for testing, and it did its job — surfaced 4 real defects in an afternoon). No need to sequence around preserving it, so no reason to ship the partial (a) and live with untrustworthy occupancy in between. Approach: do all schema/migration work up front, wipe and recreate the dev DB, then re-run a test import against the new schema. **Caveat:** migrations must still be real, forward-applying migrations — the demo machine syncs via `update.sh` (`git pull` + `alembic upgrade head`) against an existing DB that isn't being recreated. Confirm whether demo-machine data is also disposable. |
| "System 2" error during bulk rack delete — not reproducible | Investigation | — | — | Reported 2026-09-03, investigated same day: traced the full call path for bulk rack delete and confirmed it never touches System code at all — the "Cannot delete system with existing devices" string only exists in `delete_system()`. Reproduced rack-with-devices delete live and got the correct rack-scoped error message instead. Likely explanation: the two error banners use identical styling, and a system-delete attempt (see guard item above) shortly before a rack bulk-delete attempt could be misattributed. No fix pending — if this recurs, capture the exact click sequence or a screenshot with the URL bar visible so it can be re-investigated with something concrete to check. |
| Consider a "Purge Everything" convenience action for full bad-import cleanup | Feature | P3-nice to have | — | Suggested 2026-09-03 as part of the purge-cascade diagnosis. Would sequence Connections → Devices/Switches → Systems → Racks correctly in one transaction, rather than requiring an admin to discover the right tab order by trial and error (as happened here). Worth doing once the cascade-policy fix above lands, not before — no point building a convenience wrapper around logic that's still unsafe. |
| debug_sim: `recycle_bin_enabled` toggle helper isn't test-scoped | Tech debt | P3-nice to have | — | Found 2026-09-03. `_set_rb(db, ...)` in `debug_sim.py` persists to the real `app_settings` row, not test-scoped state — a crash between an off/on toggle pair leaves the setting stuck for the next run, unrelated to whatever actually crashed. Not a product bug, just a test-writing hazard. Fix: wrap toggle blocks in try/finally, or scope the setting properly for tests. |



---

## Backlog

| Task | Type | Priority | Phase | Notes |
|---|---|---|---|---|
| Work-order-free connection import | Feature | — | Unscoped | GitHub #6. Inventory-centric pivot — needs a design/architecture session (5-persona panel pattern) before coding. |
| Inventory navigation restructure | UX | P3-nice to have | — | Reported 2026-09-03. Current layout (datacenters left, systems right, racks nested under DC click-through) isn't intuitive. Real IA rework, not a quick fix — needs its own design pass, possibly worth the 5-persona architecture panel treatment given it touches core navigation. Don't bundle with the quick clickability-affordance fix above. |
| Batch save endpoint | Refactor | — | Cross-cutting | Perf improvement for large imports. Re-link `_raw` fields to inventory FKs post-hydration. |
| IBM Power slot format | Investigation | — | Cross-cutting | Evaluation for label rendering. |
| UX clickability affordances across tables | UX | — | Cross-cutting | General polish pass, not yet scoped per-table. |
| Cross-distro install script (Debian/Ubuntu + RHEL/CentOS) | Feature | — | Phase 11 | Fully scoped, not started. |
| pytest wrapper + `test_cable_length.py` | Tech debt | — | Phase 11 | Fully scoped, not started. |
| systemd unit | Feature | — | Phase 11 | Fully scoped, not started. |
| `DEPLOY.md` | Tech debt | — | Phase 11 | Fully scoped, not started. |
| In-app documentation page (how-tos, FAQ, security reference) | Feature | — | Phase 11 / Backlog | Listed under both Phase 11 and general backlog in old handoff — treat as one item. |
| Device type import/export via `.xlsx` template | Feature | — | Backlog | |
| NetBox as inventory source-of-truth via API | Feature | — | Future/strategic | CrossConnect would handle the work-order workflow layer on top. Confirmed rationale: NetBox evaluation showed it handles inventory/physical cabling well but lacks work-order lifecycle + per-row install status. |

---

## Done

_Verified against `git log` and `debug_sim` (172/172 passing as of last update, 2026-09-03)._

| Task | Phase | Notes |
|---|---|---|
| Bulk/multi-select delete — connection grid, racks, systems | — | Grid reuses existing checkbox/select-all/filter infra (Phase 6) — new `bulkDeleteSelected()` in `grid.js` + `POST /work-orders/{id}/connections/bulk-delete`, resolves by primary key server-side so re-submitting already-deleted ids is a safe no-op. Racks/systems had no prior multi-select — added generic `toggleSelectAll`/`updateBulkDeleteBtn`/`confirmBulkDelete` to `app.js`, plain HTML forms + `form="..."` attribute to avoid nested-form conflicts with existing per-row delete forms. `delete_racks_bulk()`/`delete_systems_bulk()` loop over the existing single-delete functions (reusing validation + `recycle_bin_enabled` gating) and return `{deleted, skipped}` so partial failures surface instead of vanishing silently. |
| Rack list delete button (dc_detail.html was missing the delete form entirely) | — | Template omission, not a status/role gap — `/inventory/racks/{id}/delete` route already worked. |
| Work order delete button (detail.html had no delete action for any status) | — | `delete_work_order()` restricts to `draft`/`cancelled` — button now gated on `wo.status in ['draft','cancelled']`. Deletion of `issued`/`in_progress` orders remains unsupported by design, not a bug. |
| Systems recycle-bin support (soft-delete, restore, purge, admin UI tab) | — | Migration `f1a2b3c4d5e6`. Mirrors existing Rack/Device/Switch pattern: `deleted_at`/`deleted_by` columns, query filters, `recycle_bin.py` + `_ENTITY_MAP` registration, `admin.py` branches, new Systems tab in `recycle_bin.html`. Verified end-to-end via live HTTP session (curl + cookie jar) against a scratch DB — full flow: create/cancel/delete WO, create/delete/restore system, confirm recycle-bin listing and post-restore reappearance in Inventory. |
| Foundation — models, migrations, auth, layout | Phase 1 | |
| Inventory CRUD + autocomplete | Phase 2 | |
| Device types, LAG fields, fiber mode, parent/child devices | Phase 2b | |
| Work order CRUD + connection editor grid | Phase 3 | |
| Issue validation with per-row error highlighting | Phase 3b | |
| Cable length service | Phase 4 | |
| Report view, DC tech status flow, debug sim, bug fixes | Phase 5 | |
| Install status save fix for DC techs (dedicated endpoint) | Phase 5i | |
| Nav links, RU label fix, switch device type autocomplete, change_req_number field | Phase 5.1 | |
| Audit log UI, connection_templates schema, device type badge | Phase 6 | |
| Grid enhancements — row duplication, bulk edit, filter | Phase 6 | |
| CSV rack and device import with preview/commit flow | Phase 6 | |
| Rack elevation view — tabular read-only layout | Phase 6 | |
| PDF export of work orders via WeasyPrint | Phase 8 | Confirmed working on new machine after installing `libglib2.0-0` + pango/cairo deps. |
| Rack elevation, port adjacency analysis, port utilization | Phase 9 | |
| Admin panel, recycle bin, backup/restore, tuning page | Phase 10 | |
| Excel import — NetBox column alias support, canonical template download | Phase 7 | |
| Excel label export for Brother P-touch (LAN/SAN by purpose) | Phase 7 | |
| Optional inventory hydration from connection import | Phase 7 | |
| Rack elevation order, LAN label comma, patch panel hydration, purpose alias map fixes | Phase 7 | |
| Rack browser page — list racks with stats, nav link | Phase 7 | Current HEAD (`79b7c89`) as of tracker creation. |

---

## Notes on this tracker

- Update **Status** by moving rows between sections (In Progress / Up Next / Backlog / Done), not by adding a Status column — keeps it scannable.
- When closing out a work session, move finished items to Done and note the commit hash if useful.
- Bugs still go to GitHub Issues, not here.
- Last reconciled against `git log` and `debug_sim`: see commit `79b7c89` (Phase 7: rack browser page).