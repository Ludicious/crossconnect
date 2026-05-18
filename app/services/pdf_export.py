"""
PDF export service — generates a print-ready work order PDF via WeasyPrint.

generate_work_order_pdf(db, wo_id) -> bytes
    Raises ValueError if the work order is not found.

sanitize_filename(name) -> str
    Convert a WO name to a safe filename component.
"""
import re
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.services.work_orders import get_work_order, list_connections

# ── Action / status colours (print-safe) ─────────────────────────────────────

_ACTION_COLORS = {"A": "#16a34a", "R": "#dc2626", "C": "#d97706"}
_ACTION_LABELS = {"A": "Add", "R": "Remove", "C": "Change"}
_STATUS_COLORS = {
    "done":            "#16a34a",
    "blocked":         "#dc2626",
    "change_required": "#d97706",
    "pending":         "#6b7280",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "export"


def _esc(val) -> str:
    if val is None:
        return ""
    return (str(val)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _device_cell(c) -> str:
    parts = []
    if c.device_rack_name_raw:
        parts.append(_esc(c.device_rack_name_raw))
    if c.device_rack_u:
        parts.append(f"U{c.device_rack_u}")
    if c.device_slot:
        parts.append(_esc(c.device_slot))
    if c.device_port:
        parts.append(f":{_esc(c.device_port)}")
    return " ".join(parts) if parts else "—"


def _switch_cell(c) -> str:
    parts = []
    if c.switch_rack_name_raw:
        parts.append(_esc(c.switch_rack_name_raw))
    if c.switch_rack_u:
        parts.append(f"U{c.switch_rack_u}")
    if c.switch_slot:
        parts.append(_esc(c.switch_slot))
    if c.switch_port:
        parts.append(f":{_esc(c.switch_port)}")
    return " ".join(parts) if parts else "—"


def _dev_patch_cell(c) -> str:
    parts = []
    if c.device_patch_rack_name_raw:
        parts.append(_esc(c.device_patch_rack_name_raw))
    if c.device_patch_ru:
        parts.append(f"RU{c.device_patch_ru}")
    if c.device_patch_side:
        parts.append(_esc(c.device_patch_side))
    if c.device_patch_module:
        parts.append(f"Mod{_esc(c.device_patch_module)}")
    if c.device_patch_port:
        parts.append(f":{_esc(c.device_patch_port)}")
    return " ".join(parts) if parts else "—"


def _sw_patch_cell(c) -> str:
    parts = []
    if c.switch_patch_rack_name_raw:
        parts.append(_esc(c.switch_patch_rack_name_raw))
    if c.switch_patch_ru:
        parts.append(f"RU{c.switch_patch_ru}")
    if c.switch_patch_side:
        parts.append(_esc(c.switch_patch_side))
    if c.switch_patch_module:
        parts.append(f"Mod{_esc(c.switch_patch_module)}")
    if c.switch_patch_port:
        parts.append(f":{_esc(c.switch_patch_port)}")
    return " ".join(parts) if parts else "—"


def _seg_cell(c) -> str:
    segs = [s for s in (c.seg1_length, c.seg2_length, c.seg3_length) if s]
    return " / ".join(segs) if segs else "—"


# ── HTML builder ──────────────────────────────────────────────────────────────

_CSS = """
@page {
    size: A4 landscape;
    margin: 1cm;
    @bottom-left {
        content: "FOOTER_LEFT";
        font-size: 7pt;
        color: #6b7280;
        font-family: Arial, Helvetica, sans-serif;
    }
    @bottom-right {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 7pt;
        color: #6b7280;
        font-family: Arial, Helvetica, sans-serif;
    }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: Arial, Helvetica, sans-serif;
    font-size: 8pt;
    color: #1a1a1a;
    background: #fff;
}

/* ── Header ── */
.header {
    background: #1e3a5f;
    color: #fff;
    padding: 10px 14px 8px;
    margin-bottom: 8px;
    border-radius: 3px;
}
.wordmark { font-size: 14pt; font-weight: bold; letter-spacing: -0.5px; }
.wordmark span { color: #7eb8d4; }
.wo-title  { font-size: 11pt; font-weight: bold; margin-top: 4px; }
.wo-meta {
    font-size: 7.5pt;
    color: #b8d0e8;
    margin-top: 4px;
    display: flex;
    gap: 18px;
    flex-wrap: wrap;
}
.notes-box {
    margin-top: 6px;
    padding: 4px 8px;
    background: rgba(255,255,255,0.08);
    border-left: 3px solid #7eb8d4;
    font-size: 7.5pt;
    color: #d0e4f0;
    white-space: pre-wrap;
}

/* ── Status badge in header ── */
.badge {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 7pt;
    font-weight: bold;
    text-transform: uppercase;
    vertical-align: middle;
}
.badge-draft      { background: #6b7280; color: #fff; }
.badge-issued     { background: #2563eb; color: #fff; }
.badge-in_progress { background: #d97706; color: #fff; }
.badge-complete   { background: #16a34a; color: #fff; }
.badge-cancelled  { background: #dc2626; color: #fff; }

/* ── Summary bar ── */
.summary {
    display: flex;
    gap: 5px;
    margin-bottom: 8px;
    flex-wrap: wrap;
}
.stat-box {
    flex: 1;
    min-width: 52px;
    border: 1px solid #e2e8f0;
    border-radius: 3px;
    padding: 4px 6px;
    text-align: center;
}
.stat-label { font-size: 6pt; color: #6b7280; text-transform: uppercase; }
.stat-value { font-size: 11pt; font-weight: bold; color: #1e3a5f; line-height: 1.2; }
.action-A  { color: #16a34a; }
.action-R  { color: #dc2626; }
.action-C  { color: #d97706; }
.s-done           { color: #16a34a; }
.s-blocked        { color: #dc2626; }
.s-change_required { color: #d97706; }
.s-pending        { color: #6b7280; }

/* ── Section title ── */
.section-title {
    font-size: 7.5pt;
    font-weight: bold;
    color: #1e3a5f;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 4px;
    padding-bottom: 2px;
    border-bottom: 1.5px solid #1e3a5f;
}

/* ── Tables ── */
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 7pt;
}
thead th {
    background: #1e3a5f;
    color: #fff;
    padding: 3px 4px;
    text-align: left;
    font-weight: bold;
    white-space: nowrap;
}
tbody tr:nth-child(even) td { background: #f8fafc; }
tbody tr:nth-child(odd)  td { background: #ffffff; }
td {
    padding: 2.5px 4px;
    border-bottom: 1px solid #e8edf2;
    vertical-align: top;
}

/* ── Inline badges ── */
.ab {
    display: inline-block;
    padding: 1px 5px;
    border-radius: 2px;
    font-weight: bold;
    font-size: 6.5pt;
    color: #fff;
}
.ab-A { background: #16a34a; }
.ab-R { background: #dc2626; }
.ab-C { background: #d97706; }
.sb {
    display: inline-block;
    padding: 1px 4px;
    border-radius: 2px;
    font-size: 6pt;
    font-weight: bold;
    color: #fff;
}
.sb-done           { background: #16a34a; }
.sb-blocked        { background: #dc2626; }
.sb-change_required { background: #d97706; }
.sb-pending        { background: #6b7280; }

.seg { font-family: monospace; font-size: 6.5pt; white-space: nowrap; }
.empty { color: #6b7280; font-style: italic; padding: 8px 0; }
.patch-section { margin-top: 14px; }
"""


def _build_html(wo, connections: list, generated_by: str) -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    footer_left = f"Generated by CrossConnect · {now_str} · {generated_by}"

    css = _CSS.replace("FOOTER_LEFT", footer_left.replace('"', "'"))

    total = len(connections)
    action_counts  = Counter(c.action          for c in connections)
    status_counts  = Counter(c.install_status  for c in connections)
    purpose_counts = Counter(c.purpose         for c in connections)

    has_patch = any(
        (c.device_patch_port or c.switch_patch_port)
        for c in connections
    )

    # ── Header ────────────────────────────────────────────────────────────
    dc_code  = _esc(wo.datacenter.code if wo.datacenter else "—")
    creator  = _esc(wo.creator.display_name if wo.creator else "—")
    target   = wo.target_date.strftime("%Y-%m-%d") if wo.target_date else "—"
    created  = wo.created_at.strftime("%Y-%m-%d") if wo.created_at else "—"
    status_s = wo.status.replace("_", " ").title()

    header = f"""<div class="header">
  <div class="wordmark">Cross<span>Connect</span></div>
  <div class="wo-title">
    {_esc(wo.name)}&nbsp;
    <span class="badge badge-{wo.status}">{_esc(status_s)}</span>
  </div>
  <div class="wo-meta">
    <span><b>WO-{wo.id}</b></span>
    <span>DC: {dc_code}</span>
    <span>Type: {_esc(wo.work_type.capitalize())}</span>
    <span>Target: {_esc(target)}</span>
    <span>Created: {_esc(created)}</span>
    <span>By: {creator}</span>
  </div>
  {"<div class='notes-box'>" + _esc(wo.notes) + "</div>" if wo.notes else ""}
</div>"""

    # ── Summary ───────────────────────────────────────────────────────────
    def stat(label: str, value, css_cls: str = "") -> str:
        cls = f' class="stat-value {css_cls}"' if css_cls else ' class="stat-value"'
        return (f'<div class="stat-box">'
                f'<div{cls}>{value}</div>'
                f'<div class="stat-label">{label}</div>'
                f'</div>')

    summary_parts = [stat("Total", total)]
    for act in ("A", "R", "C"):
        summary_parts.append(stat(_ACTION_LABELS[act], action_counts.get(act, 0), f"action-{act}"))
    for st in ("pending", "done", "blocked", "change_required"):
        lbl = st.replace("_", " ").title()
        summary_parts.append(stat(lbl, status_counts.get(st, 0), f"s-{st}"))
    for pur in sorted(purpose_counts):
        summary_parts.append(stat(pur.capitalize(), purpose_counts[pur]))

    summary = '<div class="summary">' + "".join(summary_parts) + "</div>"

    # ── Connection table ──────────────────────────────────────────────────
    rows_html = ""
    if connections:
        for c in connections:
            act = c.action or ""
            st  = c.install_status or "pending"
            rows_html += (
                f"<tr>"
                f"<td>{c.id}</td>"
                f"<td><span class='ab ab-{act}'>{_esc(act)}</span></td>"
                f"<td>{_esc(c.fabric or '')}</td>"
                f"<td>{_esc(c.purpose or '')}</td>"
                f"<td>{_esc(c.cable_type or '')}</td>"
                f"<td>{_device_cell(c)}</td>"
                f"<td>{_switch_cell(c)}</td>"
                f"<td class='seg'>{_seg_cell(c)}</td>"
                f"<td><span class='sb sb-{st}'>{_esc(st.replace('_', ' '))}</span></td>"
                f"<td>{_esc(c.install_notes or c.comments or '')}</td>"
                f"</tr>"
            )
    else:
        rows_html = '<tr><td colspan="10" class="empty">No connections in this work order.</td></tr>'

    conn_table = (
        '<div class="section-title">Connections</div>'
        "<table><thead><tr>"
        "<th>#</th><th>Act</th><th>Fab</th><th>Purpose</th><th>Cable</th>"
        "<th>Device (Rack / U / Slot:Port)</th>"
        "<th>Switch (Rack / U / Slot:Port)</th>"
        "<th>Segments</th><th>Install</th><th>Notes</th>"
        f"</tr></thead><tbody>{rows_html}</tbody></table>"
    )

    # ── Patch panel table (conditional) ──────────────────────────────────
    patch_section = ""
    if has_patch:
        patch_conns = [c for c in connections if c.device_patch_port or c.switch_patch_port]
        patch_rows = ""
        for c in patch_conns:
            act = c.action or ""
            patch_rows += (
                f"<tr>"
                f"<td>{c.id}</td>"
                f"<td><span class='ab ab-{act}'>{_esc(act)}</span></td>"
                f"<td>{_dev_patch_cell(c)}</td>"
                f"<td>{_sw_patch_cell(c)}</td>"
                f"</tr>"
            )
        patch_section = (
            '<div class="patch-section">'
            '<div class="section-title">Patch Panel Detail</div>'
            "<table><thead><tr>"
            "<th>Conn #</th><th>Act</th>"
            "<th>Device Patch (Rack / RU / Side / Mod:Port)</th>"
            "<th>Switch Patch (Rack / RU / Side / Mod:Port)</th>"
            f"</tr></thead><tbody>{patch_rows}</tbody></table>"
            "</div>"
        )

    return (
        "<!DOCTYPE html><html><head>"
        '<meta charset="UTF-8">'
        f"<style>{css}</style>"
        f"</head><body>{header}{summary}{conn_table}{patch_section}</body></html>"
    )


# ── Public API ────────────────────────────────────────────────────────────────

def generate_work_order_pdf(db: Session, wo_id: int) -> bytes:
    """
    Generate a PDF for the given work order.
    Fetches WO + all non-deleted connections via existing service functions.
    Returns raw PDF bytes. Raises ValueError if the WO is not found.
    """
    from weasyprint import HTML as WeasyprintHTML  # imported lazily so tests can import this module without WeasyPrint

    wo = get_work_order(db, wo_id)
    if not wo:
        raise ValueError(f"Work order {wo_id} not found")

    connections = list_connections(db, wo_id)
    generated_by = wo.creator.display_name if wo.creator else "Unknown"

    html_str = _build_html(wo, connections, generated_by)
    return WeasyprintHTML(string=html_str).write_pdf()
