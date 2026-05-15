/**
 * CrossConnect connection grid JS.
 * Depends on: WO_ID, CAN_EDIT, CABLE_TYPES, PURPOSES, ACTIONS, FABRICS,
 *             INSTALL_STATUSES (set inline by the template).
 */

// ── Expand / collapse ─────────────────────────────────────────────────────
let gridExpanded = false;

function toggleExpand() {
  gridExpanded = !gridExpanded;
  const grid = document.getElementById('conn-grid');
  const btn  = document.getElementById('expand-btn');
  grid.classList.toggle('grid-expanded', gridExpanded);
  btn.innerHTML = gridExpanded
    ? '<i class="bi bi-arrows-collapse me-1"></i>Collapse Columns'
    : '<i class="bi bi-arrows-expand me-1"></i>Expand Columns';
}

// ── Dirty tracking ────────────────────────────────────────────────────────
const dirtyRows = new Set();

function markDirty(el) {
  const row = el.closest('tr');
  if (!row) return;
  row.classList.add('row-dirty');
  row.dataset.dirty = 'true';
  dirtyRows.add(row.dataset.id);
  document.getElementById('save-btn').disabled = false;
}

// ── Add rows ──────────────────────────────────────────────────────────────
function addRows(n) {
  const tbody = document.getElementById('conn-body');
  for (let i = 0; i < n; i++) {
    tbody.insertAdjacentHTML('beforeend', buildEmptyRow());
  }
  // Mark all new rows dirty immediately so Save picks them up
  tbody.querySelectorAll('tr[data-id="new"]').forEach(r => {
    r.classList.add('row-dirty');
    r.dataset.dirty = 'true';
    dirtyRows.add('new');
  });
  document.getElementById('save-btn').disabled = false;
  // Scroll to last row
  tbody.lastElementChild?.scrollIntoView({block:'nearest'});
}

let _newRowSeq = 0;

function buildEmptyRow() {
  const seq = ++_newRowSeq;
  const actionOpts = ACTIONS.map(a => `<option value="${a}">${a}</option>`).join('');
  const fabricOpts = FABRICS.map(f => `<option value="${f}">${f || '—'}</option>`).join('');
  const cableOpts  = CABLE_TYPES.map(t => `<option value="${t}">${t}</option>`).join('');
  const purposeOpts = PURPOSES.map(p => `<option value="${p}">${p}</option>`).join('');
  const statusOpts = INSTALL_STATUSES.map(s => `<option value="${s}">${s.replace('_',' ')}</option>`).join('');

  return `
<tr class="conn-row row-dirty" id="newrow-${seq}" data-id="new" data-seq="${seq}" data-dirty="true">
  <td class="td-device"><select class="grid-select conn-field" data-field="action" onchange="markDirty(this)">${actionOpts}</select></td>
  <td class="td-device"><select class="grid-select conn-field" data-field="fabric" onchange="markDirty(this);updateFabricTint(this)">${fabricOpts}</select></td>
  <td class="td-device"><select class="grid-select conn-field" data-field="purpose" onchange="markDirty(this)">${purposeOpts}</select></td>
  <td class="td-device"><input class="grid-input conn-field" data-field="system_name_raw" oninput="markDirty(this)" placeholder="System"></td>
  <td class="td-device"><input class="grid-input conn-field" data-field="device_name_raw" oninput="markDirty(this)" placeholder="Device"></td>
  <td class="td-device"><input class="grid-input conn-field" data-field="device_rack_name_raw" oninput="markDirty(this)" placeholder="Rack*"></td>
  <td class="td-device"><input class="grid-input conn-field" data-field="device_rack_u" type="number" min="1" max="54" oninput="markDirty(this)" style="max-width:52px" placeholder="U*"></td>
  <td class="td-device"><input class="grid-input conn-field mono" data-field="device_slot" oninput="markDirty(this)" style="max-width:52px" placeholder="Slot*"></td>
  <td class="td-device"><input class="grid-input conn-field mono" data-field="device_port" oninput="markDirty(this)" style="max-width:52px" placeholder="Port*"></td>
  <td class="td-dev-patch col-patch"><input class="grid-input conn-field" data-field="device_patch_rack_name_raw" oninput="markDirty(this)"></td>
  <td class="td-dev-patch col-patch"><input class="grid-input conn-field" data-field="device_patch_ru" type="number" min="1" max="54" oninput="markDirty(this)" style="max-width:52px"></td>
  <td class="td-dev-patch col-patch"><input class="grid-input conn-field mono" data-field="device_patch_side" oninput="markDirty(this)" style="max-width:36px" placeholder="L/R"></td>
  <td class="td-dev-patch col-patch"><input class="grid-input conn-field mono" data-field="device_patch_module" oninput="markDirty(this)" style="max-width:48px"></td>
  <td class="td-dev-patch col-patch"><input class="grid-input conn-field mono" data-field="device_patch_port" oninput="markDirty(this)" style="max-width:48px"></td>
  <td class="td-sw-patch col-patch"><input class="grid-input conn-field" data-field="switch_patch_rack_name_raw" oninput="markDirty(this)"></td>
  <td class="td-sw-patch col-patch"><input class="grid-input conn-field" data-field="switch_patch_ru" type="number" min="1" max="54" oninput="markDirty(this)" style="max-width:52px"></td>
  <td class="td-sw-patch col-patch"><input class="grid-input conn-field mono" data-field="switch_patch_side" oninput="markDirty(this)" style="max-width:36px" placeholder="L/R"></td>
  <td class="td-sw-patch col-patch"><input class="grid-input conn-field mono" data-field="switch_patch_module" oninput="markDirty(this)" style="max-width:48px"></td>
  <td class="td-sw-patch col-patch"><input class="grid-input conn-field mono" data-field="switch_patch_port" oninput="markDirty(this)" style="max-width:48px"></td>
  <td class="td-switch"><input class="grid-input conn-field" data-field="switch_name_raw" oninput="markDirty(this)" placeholder="Switch"></td>
  <td class="td-switch"><input class="grid-input conn-field" data-field="switch_rack_name_raw" oninput="markDirty(this)" placeholder="Rack*"></td>
  <td class="td-switch"><input class="grid-input conn-field" data-field="switch_rack_u" type="number" min="1" max="54" oninput="markDirty(this)" style="max-width:52px" placeholder="U*"></td>
  <td class="td-switch"><input class="grid-input conn-field mono" data-field="switch_slot" oninput="markDirty(this)" style="max-width:52px" placeholder="Slot*"></td>
  <td class="td-switch"><input class="grid-input conn-field mono" data-field="switch_port" oninput="markDirty(this)" style="max-width:52px" placeholder="Port*"></td>
  <td class="td-switch"><select class="grid-select conn-field" data-field="cable_type" onchange="markDirty(this)">${cableOpts}</select></td>
  <input type="hidden" class="conn-field" data-field="device_serial" value="">
  <input type="hidden" class="conn-field" data-field="device_grid" value="">
  <input type="hidden" class="conn-field" data-field="switch_serial" value="">
  <input type="hidden" class="conn-field" data-field="switch_grid" value="">
  <input type="hidden" class="conn-field" data-field="port_description" value="">
  <td class="col-extra"><input class="grid-input conn-field mono" data-field="vlan_vsan" oninput="markDirty(this)"></td>
  <td class="col-extra"><input class="grid-input conn-field" data-field="comments" oninput="markDirty(this)"></td>
  <td class="seg-length text-muted">—</td>
  <td class="seg-length text-muted">—</td>
  <td class="seg-length text-muted">—</td>
  <td><select class="grid-select conn-field" data-field="install_status" onchange="markDirty(this)">${statusOpts}</select></td>
  <td><input class="grid-input conn-field" data-field="install_notes" oninput="markDirty(this)"></td>
  <td class="row-error-cell text-danger" style="white-space:nowrap;min-width:20px" title=""></td>
  <td class="text-end">
    <button class="btn btn-outline-secondary btn-sm py-0 px-1" title="Remove unsaved row"
            onclick="removeNewRow(this)">
      <i class="bi bi-x-lg" style="font-size:.75rem"></i>
    </button>
  </td>
</tr>`;
}

function removeNewRow(btn) {
  btn.closest('tr').remove();
  if (!document.querySelectorAll('tr[data-id="new"]').length &&
      !document.querySelectorAll('tr.row-dirty:not([data-id="new"])').length) {
    document.getElementById('save-btn').disabled = true;
  }
}

// ── Fabric tint ───────────────────────────────────────────────────────────
function updateFabricTint(el) {
  const row = el.closest('tr');
  row.classList.remove('fabric-a', 'fabric-b');
  if (el.value === 'A') row.classList.add('fabric-a');
  if (el.value === 'B') row.classList.add('fabric-b');
}

// ── Collect row form data ─────────────────────────────────────────────────
function rowToFormData(row) {
  const data = {};
  row.querySelectorAll('.conn-field').forEach(el => {
    data[el.dataset.field] = el.value;
  });
  return data;
}

// ── Save all dirty rows ───────────────────────────────────────────────────
async function saveAllDirty() {
  const btn = document.getElementById('save-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving…';

  const rows = document.querySelectorAll('tr.conn-row.row-dirty');
  let errorCount = 0;

  for (const row of rows) {
    const rowId = row.dataset.id;
    const data  = rowToFormData(row);
    const isNew = rowId === 'new';
    const url   = isNew
      ? `/work-orders/${WO_ID}/connections`
      : `/work-orders/${WO_ID}/connections/${rowId}/edit`;

    const formBody = new URLSearchParams(data).toString();
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: formBody,
      });
      const json = await resp.json();
      if (json.ok) {
        row.classList.remove('row-dirty');
        row.dataset.dirty = 'false';
        dirtyRows.delete(rowId);
        if (isNew && json.id) {
          row.dataset.id = json.id;
          row.id = `row-${json.id}`;
          // Update delete button
          const delBtn = row.querySelector('button[onclick*="deleteRow"]');
          if (delBtn) delBtn.setAttribute('onclick', `deleteRow(${json.id}, this)`);
          // Swap remove-unsaved button for delete button
          row.querySelector('button[onclick*="removeNewRow"]')?.setAttribute(
            'onclick', `deleteRow(${json.id}, this)`
          );
        }
        if (json.warnings?.length) {
          showToast(json.warnings.join('\n'), 'warning');
        }
      } else {
        errorCount++;
        highlightErrors(row, json.errors || []);
        showToast(json.errors?.join('\n') || 'Save failed', 'danger');
      }
    } catch (e) {
      errorCount++;
      showToast('Network error saving row', 'danger');
    }
  }

  if (errorCount === 0) {
    btn.innerHTML = '<i class="bi bi-floppy me-1"></i>Save Changes';
  } else {
    btn.disabled = false;
    btn.innerHTML = `<i class="bi bi-floppy me-1"></i>Save Changes (${errorCount} error${errorCount>1?'s':''})`;
  }
}

function highlightErrors(row, errors) {
  // Red border on the row
  row.querySelectorAll('.grid-input, .grid-select').forEach(el => {
    el.style.outline = errors.length ? '1px solid #dc3545' : '';
  });
}

// ── Save install status inline (no Save button needed) ───────────────────
async function saveInstallStatus(el, connId) {
  const status = el.value;
  const row = el.closest('tr');
  // Also grab install_notes from same row
  const notes = row.querySelector('[data-field="install_notes"]')?.value || '';
  const body = new URLSearchParams({install_status: status, install_notes: notes,
    // Must include all mandatory fields to not wipe them — easiest: send full row
    ...rowToFormData(row)
  }).toString();
  try {
    const resp = await fetch(`/work-orders/${WO_ID}/connections/${connId}/edit`, {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body,
    });
    const json = await resp.json();
    if (!json.ok) showToast(json.errors?.join('\n') || 'Save failed', 'danger');
  } catch (e) {
    showToast('Network error', 'danger');
  }
}

// ── Delete row ────────────────────────────────────────────────────────────
async function deleteRow(connId, btn) {
  if (!confirm('Delete this connection row?')) return;
  try {
    const resp = await fetch(`/work-orders/${WO_ID}/connections/${connId}/delete`, {
      method: 'POST',
    });
    const json = await resp.json();
    if (json.ok) {
      btn.closest('tr').remove();
    } else {
      showToast('Delete failed', 'danger');
    }
  } catch(e) {
    showToast('Network error', 'danger');
  }
}

// ── Toast ─────────────────────────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container') || createToastContainer();
  const id = 'toast-' + Date.now();
  const html = `
<div id="${id}" class="toast align-items-center text-bg-${type} border-0" role="alert">
  <div class="d-flex">
    <div class="toast-body small" style="white-space:pre-wrap">${msg}</div>
    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
  </div>
</div>`;
  container.insertAdjacentHTML('beforeend', html);
  const el = document.getElementById(id);
  new bootstrap.Toast(el, {delay: type === 'warning' ? 6000 : 4000}).show();
  el.addEventListener('hidden.bs.toast', () => el.remove());
}

function createToastContainer() {
  const div = document.createElement('div');
  div.id = 'toast-container';
  div.className = 'toast-container position-fixed bottom-0 end-0 p-3';
  div.style.zIndex = 9999;
  document.body.appendChild(div);
  return div;
}

// ── Tab / Enter navigation ────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (!['Tab','Enter'].includes(e.key)) return;
  const active = document.activeElement;
  if (!active?.closest('tr.conn-row')) return;

  const row = active.closest('tr');
  const inputs = [...row.querySelectorAll('.grid-input:not([readonly]), .grid-select')];
  const idx = inputs.indexOf(active);

  if (e.key === 'Enter') {
    e.preventDefault();
    // Move to same column in next row
    const rows = [...document.querySelectorAll('tr.conn-row')];
    const nextRow = rows[rows.indexOf(row) + 1];
    if (nextRow) {
      const nextInputs = [...nextRow.querySelectorAll('.grid-input:not([readonly]), .grid-select')];
      nextInputs[idx]?.focus();
    }
  }
  // Tab is browser default — let it walk through cells naturally
});

// ── CSV/TSV importer Alpine component ────────────────────────────────────
function csvImporter() {
  return {
    preview: [],
    headers: [],
    importResult: null,
    rawRows: [],

    // Map from our field names to possible CSV column headers
    FIELD_MAP: {
      action:                 ['action'],
      fabric:                 ['fabric'],
      port_description:       ['port description','port_description'],
      cable_type:             ['cable type','cable_type','connection type','connection_type'],
      purpose:                ['purpose'],
      system_name_raw:        ['system name','system_name','system'],
      device_name_raw:        ['device name','device_name'],
      device_serial:          ['device serial','device_serial'],
      device_rack_name_raw:   ['device rack','device_rack'],
      device_grid:            ['device grid','device_grid'],
      device_rack_u:          ['device rack u','device_rack_u','device u'],
      device_slot:            ['device slot','device_slot'],
      device_port:            ['device port','device_port'],
      device_patch_rack_name_raw: ['device patch rack','device_patch_rack'],
      device_patch_ru:        ['device patch ru','device_patch_ru'],
      device_patch_side:      ['device patch side','device_patch_side'],
      device_patch_module:    ['device patch module','device_patch_module'],
      device_patch_port:      ['device patch port','device_patch_port'],
      switch_patch_rack_name_raw: ['switch patch rack','lan patch rack','san patch rack','switch_patch_rack'],
      switch_patch_ru:        ['switch patch ru','lan patch ru','san patch ru'],
      switch_patch_side:      ['switch patch side','lan patch side'],
      switch_patch_module:    ['switch patch module','lan patch module','san patch module'],
      switch_patch_port:      ['switch patch port','lan patch port','san patch port'],
      switch_name_raw:        ['switch name','switch_name','lan switch name','san switch name'],
      switch_serial:          ['switch serial','switch_serial','lan switch serial','san switch serial'],
      switch_rack_name_raw:   ['switch rack','switch_rack','lan switch rack','san switch rack'],
      switch_grid:            ['switch grid','lan switch grid'],
      switch_rack_u:          ['switch rack u','switch_rack_u','lan switch rack u','san switch rack u'],
      switch_slot:            ['switch slot','switch_slot','lan switch slot','san switch slot'],
      switch_port:            ['switch port','switch_port','lan switch port','san switch port'],
      vlan_vsan:              ['vlan','vsan','vlan/vsan'],
      comments:               ['comments'],
    },

    parseFile(evt) {
      const file = evt.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = e => {
        const text = e.target.result;
        const sep = text.includes('\t') ? '\t' : ',';
        const lines = text.split(/\r?\n/).filter(l => l.trim());
        if (!lines.length) return;

        // Parse headers
        const rawHeaders = lines[0].split(sep).map(h => h.trim().replace(/^["']|["']$/g,'').toLowerCase());
        this.headers = rawHeaders;

        // Build field → col index map
        const colMap = {};
        Object.entries(this.FIELD_MAP).forEach(([field, aliases]) => {
          const idx = rawHeaders.findIndex(h => aliases.includes(h));
          if (idx !== -1) colMap[field] = idx;
        });

        // Parse data rows, skip repeated header rows
        this.rawRows = [];
        this.preview = [];
        for (let i = 1; i < lines.length; i++) {
          const cells = lines[i].split(sep).map(c => c.trim().replace(/^["']|["']$/g,''));
          // Skip rows that look like a repeated header
          if (cells[0]?.toLowerCase() === 'action') continue;
          const row = {};
          rawHeaders.forEach((h, ci) => { row[h] = cells[ci] || ''; });
          // Map to our field names
          const mapped = {};
          Object.entries(colMap).forEach(([field, ci]) => {
            mapped[field] = cells[ci] || '';
          });
          // Basic validation
          const errs = [];
          if (!['A','R','C'].includes((mapped.action||'').toUpperCase())) errs.push('Invalid ACTION');
          mapped._errors = errs;
          this.rawRows.push(mapped);
          this.preview.push({...row, _errors: errs});
        }
      };
      reader.readAsText(file);
    },

    async submit() {
      if (!this.rawRows.length) return;
      const clean = this.rawRows.map(r => { const {_errors,...rest} = r; return rest; });
      try {
        const resp = await fetch(`/work-orders/${WO_ID}/connections/bulk`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({rows: clean}),
        });
        const json = await resp.json();
        const msg = `Imported ${json.created} row(s).` +
          (json.skipped?.length ? ` ${json.skipped.length} skipped (duplicate switch ports).` : '');
        this.importResult = {message: msg, skipped: json.skipped};
        if (json.created > 0) {
          // Reload page to show new rows
          setTimeout(() => window.location.reload(), 1500);
        }
      } catch(e) {
        this.importResult = {message: 'Import failed: network error', skipped: [1]};
      }
    },

    reset() {
      this.preview = [];
      this.headers = [];
      this.rawRows = [];
      this.importResult = null;
    }
  };
}

// Wire the modal submit button to the Alpine component's submit()
document.addEventListener('DOMContentLoaded', () => {
  document.querySelector('[\\@click="$dispatch(\'import-submit\')"]')
    ?.addEventListener('click', () => {
      // Find Alpine component on the modal body
      const modalBody = document.querySelector('#importModal .modal-body[x-data]');
      if (modalBody && modalBody._x_dataStack) {
        modalBody._x_dataStack[0].submit();
      }
    });
});

// ── Issue-time validation error highlighting ──────────────────────────────
// VALIDATION_ERRORS is injected by the template as:
//   [{id: 3, errors: ["DEVICE RACK U must be 1–54", ...]}, ...]
document.addEventListener('DOMContentLoaded', () => {
  if (typeof VALIDATION_ERRORS === 'undefined' || !VALIDATION_ERRORS.length) return;

  VALIDATION_ERRORS.forEach(({id, errors}) => {
    const row = document.getElementById(`row-${id}`);
    if (!row) return;

    // Red left border on the row
    row.style.borderLeft = '3px solid #dc3545';

    // Populate the error indicator cell with a tooltip icon
    const errCell = row.querySelector('.row-error-cell');
    if (errCell) {
      errCell.innerHTML = '<i class="bi bi-exclamation-triangle-fill text-danger"></i>';
      errCell.title = errors.join('\n');
      errCell.style.cursor = 'help';
    }

    // Highlight specific fields that have errors
    const fieldMap = {
      'ACTION':           'action',
      'CABLE TYPE':       'cable_type',
      'PURPOSE':          'purpose',
      'DEVICE RACK':      'device_rack_name_raw',
      'DEVICE RACK U':    'device_rack_u',
      'DEVICE SLOT':      'device_slot',
      'DEVICE PORT':      'device_port',
      'SWITCH RACK':      'switch_rack_name_raw',
      'SWITCH RACK U':    'switch_rack_u',
      'SWITCH SLOT':      'switch_slot',
      'SWITCH PORT':      'switch_port',
    };
    errors.forEach(msg => {
      Object.entries(fieldMap).forEach(([label, field]) => {
        if (msg.includes(label)) {
          const el = row.querySelector(`[data-field="${field}"]`);
          if (el) el.style.outline = '2px solid #dc3545';
        }
      });
    });
  });

  // Scroll the first error row into view
  const firstErrorId = VALIDATION_ERRORS[0]?.id;
  if (firstErrorId) {
    document.getElementById(`row-${firstErrorId}`)?.scrollIntoView({behavior:'smooth', block:'center'});
  }
});
