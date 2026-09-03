# CrossConnect — Task Tracker

Replaces the Notion "CrossConnect – Wired Right" workspace (not accessible from work machine).
Same fields as the old Notion Tasks DB: **Type** (Feature/Refactor/UX/Tech debt/Investigation),
**Priority** (P0-critical/P1-high/P2-normal/P3-nice to have), **Phase**, **Notes**.

GitHub Issues remain bugs-only. Everything else — features, UX, tech debt — lives here.

---

## In Progress

_(nothing currently — update this section as work starts)_

---

## Up Next

| Task | Type | Priority | Phase | Notes |
|---|---|---|---|---|
| Excel export matching template | Feature | — | Unscoped | **Needs confirmation.** Old handoff doc described this as Phase 8, but the actual Phase 8 commit (`bf3d271`) was PDF export via WeasyPrint, not this. Label export (Phase 7, Brother P-touch) exists but is a different feature. Confirm whether this is still wanted, and if so scope it fresh. |
| Clickable row/object affordance (underline/cursor treatment) | UX | P2-normal | Cross-cutting | Reported 2026-09-03. Merges with existing "UX clickability affordances" backlog item below — likely a quick CSS/cursor pass, no backend involved. Good candidate for a same-session quick win. |
| Settings page 404s | Bug? | — | — | Reported 2026-09-03. Repros as a hard 404, not a missing-feature gap — per project convention this should move to **GitHub Issues** once confirmed. Logged here temporarily since it came in as part of this batch. Needs a quick check: is this a genuinely unbuilt route, or a broken link to the existing Admin tuning page? |
| Excel import: select which worksheets to import | Feature | P1-high | Unscoped | Reported 2026-09-03. Current import pulls every worksheet in the workbook. Real-world workbooks mix unrelated sheets (IP assignments, LAN X-connect, WAN X-connect) — importing all of them corrupted inventory data on first real-world test. Needs a sheet-picker UI + import service change to accept a sheet allowlist. High priority — already caused a data cleanup problem (see next two items). |
| Delete work order / rack / device / switch — expose in UI | Bug? / UX | P2-normal | — | Investigated 2026-09-03 via Claude Code. Backend is fully wired: soft-delete routes exist (`inventory.py:452,545,615`, `work_orders.py:254`), gated by `recycle_bin_enabled`, and the admin recycle-bin UI (list/restore/purge, `admin.py:225-310` + `recycle_bin.html`) works end-to-end. **But** screenshots from this session show no delete action on the rack list view or the work order detail page (Cancelled WO only showed "Open"). Contradiction not yet resolved — next step is checking the specific templates (work order detail, rack edit/detail) to see whether the delete action is on a different page, gated by a status/permission condition, or genuinely unwired in those templates. Do this check before writing any code — likely a small template fix once found. |
| Add systems to recycle-bin (soft-delete support) | Feature | P1-high | — | Investigated 2026-09-03 via Claude Code — fully scoped, mirrors existing Rack/Device/Switch pattern exactly: (1) migration adding `deleted_at`/`deleted_by` + deleter relationship to `System` model, (2) fix `delete_system()` (`inventory.py:219-225`) to check `recycle_bin_enabled` and soft-delete instead of unconditional `db.delete()`, (3) add `System.deleted_at.is_(None)` filters everywhere systems are queried, (4) add `list_deleted_systems`/`restore_system`/`hard_delete_system` to `recycle_bin.py` + register in `_ENTITY_MAP`, (5) add `"systems"` to `admin.py` `VALID_TABS` + wire restore/delete branches, (6) add a Systems tab to `recycle_bin.html`. Well-defined, low-risk, good candidate for its own focused session. Elevated priority — currently blocking test-data cleanup. |
| Batch delete of connection grid rows | Feature | P2-normal | — | Reported 2026-09-03. After a bad import, invalid connection rows can only be deleted one-by-one with a confirm prompt each time. Need multi-select + bulk delete in the grid itself (distinct from the admin recycle-bin purge, which operates on already-soft-deleted items). |

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

_Verified against `git log` and `debug_sim` (139/139 passing as of this tracker's creation)._

| Task | Phase | Notes |
|---|---|---|
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