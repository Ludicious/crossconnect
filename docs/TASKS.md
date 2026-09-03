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

---

## Backlog

| Task | Type | Priority | Phase | Notes |
|---|---|---|---|---|
| Work-order-free connection import | Feature | — | Unscoped | GitHub #6. Inventory-centric pivot — needs a design/architecture session (5-persona panel pattern) before coding. |
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