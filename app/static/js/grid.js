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
  // Mark only the newly added rows dirty (those without _acAttached yet)
  const allNewRows = [...tbody.querySelectorAll('tr[data-id="new"]')];
  const freshRows = allNewRows.slice(allNewRows.length - n);
  freshRows.forEach(r => {
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
  <td class="seg-length text-muted" data-seg="1">—</td>
  <td class="seg-length text-muted" data-seg="2">—</td>
  <td class="seg-length text-muted" data-seg="3">—</td>
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


// ── Update seg length cells in a row ─────────────────────────────────────
function _updateSegCells(row, seg1, seg2, seg3) {
  [[1, seg1], [2, seg2], [3, seg3]].forEach(([n, val]) => {
    const cell = row.querySelector(`[data-seg="${n}"]`);
    if (!cell) return;
    cell.className = 'seg-length';  // reset
    if (!val) {
      cell.textContent = '—';
      cell.classList.add('text-muted');
    } else if (val === 'cross-cabinet') {
      cell.textContent = val; cell.classList.add('seg-cross');
    } else if (val === 'incomplete') {
      cell.textContent = val; cell.classList.add('seg-incomplete');
    } else if (val === 'exceeds_max') {
      cell.textContent = val; cell.classList.add('seg-exceeds');
    } else {
      cell.textContent = val; cell.classList.add('seg-numeric');
    }
  });
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
          const delBtn = row.querySelector('button[onclick*="deleteRow"]');
          if (delBtn) delBtn.setAttribute('onclick', `deleteRow(${json.id}, this)`);
          row.querySelector('button[onclick*="removeNewRow"]')?.setAttribute(
            'onclick', `deleteRow(${json.id}, this)`
          );
          // Re-attach autocomplete to the now-persisted row
          _attachRowAutocomplete(row);
        }
        // Update seg length cells from server response
        _updateSegCells(row, json.seg1, json.seg2, json.seg3);
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

// ── Grid autocomplete ─────────────────────────────────────────────────────
//
// Attaches a dropdown to grid input cells. Configured per-field in
// attachGridAutocomplete() below.
//
// When the user picks a result, onPick(result, row) is called to fill
// sibling cells in the same row automatically.

const _acState = new WeakMap();  // input el → {dropdown, results, idx}

function _acDropdown(input) {
  let state = _acState.get(input);
  if (state) return state;

  const dropdown = document.createElement('div');
  dropdown.className = 'cc-dropdown';
  dropdown.style.cssText = 'position:absolute;z-index:2000;display:none;min-width:220px';
  input.parentElement.style.position = 'relative';
  input.parentElement.appendChild(dropdown);

  state = { dropdown, results: [], idx: -1 };
  _acState.set(input, state);
  return state;
}

function _acShow(input, results) {
  const state = _acDropdown(input);
  state.results = results;
  state.idx = -1;
  const d = state.dropdown;

  if (!results.length) { d.style.display = 'none'; return; }

  d.innerHTML = results.map((r, i) =>
    `<div class="cc-dropdown-item" data-idx="${i}">${r.label || r.name}</div>`
  ).join('');

  d.querySelectorAll('.cc-dropdown-item').forEach(el => {
    el.addEventListener('mousedown', e => {
      e.preventDefault();
      const r = results[parseInt(el.dataset.idx)];
      _acHide(input);
      input.value = r.name || r.label;
      markDirty(input);
      const onPick = input._acOnPick;
      if (onPick) onPick(r, input.closest('tr'));
    });
  });

  d.style.display = 'block';
}

function _acHide(input) {
  const state = _acState.get(input);
  if (state) state.dropdown.style.display = 'none';
}

function _acNavigate(input, e) {
  const state = _acState.get(input);
  if (!state || state.dropdown.style.display === 'none') return false;
  const items = state.dropdown.querySelectorAll('.cc-dropdown-item');
  if (!items.length) return false;

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    state.idx = Math.min(state.idx + 1, items.length - 1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    state.idx = Math.max(state.idx - 1, 0);
  } else if (e.key === 'Enter' && state.idx >= 0) {
    e.preventDefault();
    items[state.idx].dispatchEvent(new MouseEvent('mousedown'));
    return true;
  } else if (e.key === 'Escape') {
    _acHide(input);
    return true;
  } else {
    return false;
  }

  items.forEach((el, i) => el.classList.toggle('cc-dropdown-item-active', i === state.idx));
  return true;
}

async function _acSearch(url, q) {
  if (!q || q.length < 1) return [];
  try {
    const r = await fetch(`${url}?q=${encodeURIComponent(q)}`);
    return await r.json();
  } catch { return []; }
}

let _acTimer = null;
function _acAttach(input, url, onPick) {
  input._acOnPick = onPick;
  _acDropdown(input);  // init state

  input.addEventListener('input', () => {
    clearTimeout(_acTimer);
    _acTimer = setTimeout(async () => {
      const results = await _acSearch(url, input.value.trim());
      _acShow(input, results);
    }, 180);
  });

  input.addEventListener('focus', async () => {
    if (input.value.trim().length >= 1) {
      const results = await _acSearch(url, input.value.trim());
      _acShow(input, results);
    }
  });

  input.addEventListener('blur', () => {
    setTimeout(() => _acHide(input), 160);
  });

  input.addEventListener('keydown', e => _acNavigate(input, e));
}

// ── Field fill helpers ────────────────────────────────────────────────────

function _setField(row, fieldName, value) {
  if (value === null || value === undefined || value === '') return;
  const el = row.querySelector(`[data-field="${fieldName}"]`);
  if (el && !el.value) {   // only fill if currently empty — don't overwrite
    el.value = value;
    markDirty(el);
  }
}

function _forceField(row, fieldName, value) {
  if (value === null || value === undefined) return;
  const el = row.querySelector(`[data-field="${fieldName}"]`);
  if (el) { el.value = value; markDirty(el); }
}

// ── Attach autocomplete to all grid rows ──────────────────────────────────

function attachGridAutocomplete() {
  if (!CAN_EDIT) return;

  document.querySelectorAll('tr.conn-row').forEach(row => {
    _attachRowAutocomplete(row);
  });
}

function _attachRowAutocomplete(row) {
  // System name
  const sysInput = row.querySelector('[data-field="system_name_raw"]');
  if (sysInput && !sysInput._acAttached) {
    sysInput._acAttached = true;
    sysInput.dataset.acAttached = '1';
    _acAttach(sysInput, '/inventory/autocomplete/systems', (r, row) => {
      // system pick: no auto-fill (system doesn't carry rack info directly)
    });
  }

  // Device name → fills device_rack_name_raw, device_rack_u, device_serial, system_name_raw
  const devInput = row.querySelector('[data-field="device_name_raw"]');
  if (devInput && !devInput._acAttached) {
    devInput._acAttached = true;
    devInput.dataset.acAttached = '1';
    _acAttach(devInput, '/inventory/autocomplete/devices', (r, row) => {
      _setField(row, 'device_rack_name_raw', r.rack);
      _setField(row, 'device_rack_u', r.rack_u);
      _setField(row, 'device_serial', r.serial);
      _setField(row, 'system_name_raw', r.system);
    });
  }

  // Device rack name (standalone — no fill, just autocomplete)
  const devRackInput = row.querySelector('[data-field="device_rack_name_raw"]');
  if (devRackInput && !devRackInput._acAttached) {
    devRackInput._acAttached = true;
    _acAttach(devRackInput, '/inventory/autocomplete/racks', (r, row) => {
      // rack pick: no cascade needed
    });
  }

  // Device patch rack
  const dpRackInput = row.querySelector('[data-field="device_patch_rack_name_raw"]');
  if (dpRackInput && !dpRackInput._acAttached) {
    dpRackInput._acAttached = true;
    _acAttach(dpRackInput, '/inventory/autocomplete/racks', () => {});
  }

  // Switch patch rack
  const spRackInput = row.querySelector('[data-field="switch_patch_rack_name_raw"]');
  if (spRackInput && !spRackInput._acAttached) {
    spRackInput._acAttached = true;
    _acAttach(spRackInput, '/inventory/autocomplete/racks', () => {});
  }

  // Switch name → fills switch_rack_name_raw, switch_rack_u, switch_serial
  const swInput = row.querySelector('[data-field="switch_name_raw"]');
  if (swInput && !swInput._acAttached) {
    swInput._acAttached = true;
    swInput.dataset.acAttached = '1';
    _acAttach(swInput, '/inventory/autocomplete/switches', (r, row) => {
      _setField(row, 'switch_rack_name_raw', r.rack);
      _setField(row, 'switch_rack_u', r.rack_u);
      _setField(row, 'switch_serial', r.serial);
      // After filling rack fields, trigger cable length preview update
      markDirty(row.querySelector('[data-field="switch_rack_name_raw"]') || swInput);
    });
  }

  // Switch rack name (standalone)
  const swRackInput = row.querySelector('[data-field="switch_rack_name_raw"]');
  if (swRackInput && !swRackInput._acAttached) {
    swRackInput._acAttached = true;
    _acAttach(swRackInput, '/inventory/autocomplete/racks', () => {});
  }
}

// Active dropdown CSS
const _acStyle = document.createElement('style');
_acStyle.textContent = `.cc-dropdown-item-active { background-color: rgba(61,142,240,.25) !important; }`;
document.head.appendChild(_acStyle);

// Run on page load for existing rows, and expose for new rows
document.addEventListener('DOMContentLoaded', attachGridAutocomplete);

// Patch addRows to attach autocomplete to new rows after they're added
const _origAddRows = addRows;
window.addRows = function(n) {
  _origAddRows(n);
  // Attach autocomplete only to rows that don't have it yet (_acAttached flag not set)
  document.querySelectorAll('tr.conn-row').forEach(row => {
    const needs = row.querySelector('[data-field="device_name_raw"]:not([data-ac-attached])') ||
                  row.querySelector('[data-field="switch_name_raw"]:not([data-ac-attached])');
    if (needs) _attachRowAutocomplete(row);
  });
};
