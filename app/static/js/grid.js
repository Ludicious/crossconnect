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
  const newRows = [];
  for (let i = 0; i < n; i++) {
    tbody.insertAdjacentHTML('beforeend', buildEmptyRow());
    newRows.push(tbody.lastElementChild);
  }
  // Mark only the freshly added rows dirty
  newRows.forEach(r => {
    r.classList.add('row-dirty');
    r.dataset.dirty = 'true';
    dirtyRows.add('new');
  });
  document.getElementById('save-btn').disabled = false;
  tbody.lastElementChild?.scrollIntoView({block:'nearest'});
  // Attach autocomplete — deferred so _attachRowAutocomplete is guaranteed defined
  // (it lives later in this file; setTimeout(0) yields to let the full script finish)
  setTimeout(() => {
    newRows.forEach(r => _attachRowAutocomplete(r));
  }, 0);
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
  <td class="td-cb" style="width:24px;padding:4px 2px;vertical-align:middle"><input type="checkbox" class="row-cb form-check-input" onchange="updateBulkToolbar()"></td>
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
  <td class="col-extra"><select class="grid-select conn-field" data-field="fiber_mode" onchange="markDirty(this)"><option value="">—</option><option value="singlemode">SM</option><option value="multimode">MM</option></select></td>
  <td class="col-extra"><input class="grid-input conn-field mono" data-field="lag_id" oninput="markDirty(this)" style="max-width:52px"></td>
  <td class="col-extra"><input class="grid-input conn-field" data-field="lag_member_index" type="number" min="1" oninput="markDirty(this)" style="max-width:44px"></td>
  <td class="seg-length text-muted" data-seg="1">—</td>
  <td class="seg-length text-muted" data-seg="2">—</td>
  <td class="seg-length text-muted" data-seg="3">—</td>
  <td><select class="grid-select conn-field" data-field="install_status" onchange="markDirty(this)">${statusOpts}</select></td>
  <td><input class="grid-input conn-field" data-field="install_notes" oninput="markDirty(this)"></td>
  <td class="row-error-cell text-danger" style="white-space:nowrap;min-width:20px" title=""></td>
  <td class="text-end" style="white-space:nowrap">
    <button class="btn btn-outline-secondary btn-sm py-0 px-1 me-1" title="Duplicate row"
            onclick="duplicateRow(this)">
      <i class="bi bi-copy" style="font-size:.75rem"></i>
    </button>
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
  const notes = row.querySelector('[data-field="install_notes"]')?.value || '';

  // Use the dedicated install-status endpoint — works for all roles,
  // does not reset status back to pending, works on issued + in_progress WOs.
  const body = new URLSearchParams({install_status: status, install_notes: notes}).toString();
  try {
    const resp = await fetch(`/work-orders/${WO_ID}/connections/${connId}/install-status`, {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body,
    });
    const json = await resp.json();
    if (json.ok) {
      // Visual feedback — briefly highlight the cell green
      el.style.transition = 'background 0.3s';
      el.style.background = 'rgba(34,197,94,0.2)';
      setTimeout(() => { el.style.background = ''; }, 800);
    } else {
      showToast(json.errors?.join('\n') || 'Status save failed', 'danger');
      // Revert the select to previous value if we know it
    }
  } catch (e) {
    showToast('Network error saving status', 'danger');
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
      cable_type:             ['cable type','cable_type','connection type','connection_type','type'],
      purpose:                ['purpose'],
      system_name_raw:        ['system name','system_name','system'],
      device_name_raw:        ['device name','device_name','side_a_device','a device'],
      device_serial:          ['device serial','device_serial'],
      device_rack_name_raw:   ['device rack','device_rack'],
      device_grid:            ['device grid','device_grid'],
      device_rack_u:          ['device rack u','device_rack_u','device u'],
      device_slot:            ['device slot','device_slot'],
      device_port:            ['device port','device_port','side_a_name','a port'],
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
      switch_name_raw:        ['switch name','switch_name','lan switch name','san switch name','side_b_device','b device'],
      switch_serial:          ['switch serial','switch_serial','lan switch serial','san switch serial'],
      switch_rack_name_raw:   ['switch rack','switch_rack','lan switch rack','san switch rack'],
      switch_grid:            ['switch grid','lan switch grid'],
      switch_rack_u:          ['switch rack u','switch_rack_u','lan switch rack u','san switch rack u'],
      switch_slot:            ['switch slot','switch_slot','lan switch slot','san switch slot'],
      switch_port:            ['switch port','switch_port','lan switch port','san switch port','side_b_name','b port'],
      vlan_vsan:              ['vlan','vsan','vlan/vsan'],
      lag_id:                 ['lag id','lag_id','port channel','port_channel'],
      fiber_mode:             ['fiber mode','fiber_mode'],
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
      const hydrate = document.getElementById('csvHydrateCheck')?.checked || false;
      try {
        const resp = await fetch(`/work-orders/${WO_ID}/connections/bulk`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({rows: clean, hydrate_inventory: hydrate}),
        });
        const json = await resp.json();
        let msg = `Imported ${json.created} row(s).` +
          (json.skipped?.length ? ` ${json.skipped.length} skipped (duplicate switch ports).` : '');
        if (json.hydration) {
          const h = json.hydration;
          const parts = [];
          if (h.racks_created)    parts.push(`${h.racks_created} rack(s)`);
          if (h.systems_created)  parts.push(`${h.systems_created} system(s)`);
          if (h.devices_created)  parts.push(`${h.devices_created} device(s)`);
          if (h.switches_created) parts.push(`${h.switches_created} switch(es)`);
          if (parts.length) msg += ` Added ${parts.join(', ')} to inventory.`;
        }
        if (json.hydration_error) msg += ` (Inventory hydration error: ${json.hydration_error})`;
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

  // Attach to document.body with position:fixed so overflow:hidden/auto containers
  // don't clip it (the table scroll container would otherwise cut it off).
  const dropdown = document.createElement('div');
  dropdown.className = 'cc-dropdown';
  dropdown.style.cssText = 'position:fixed;z-index:9999;display:none;min-width:220px;max-width:320px';
  document.body.appendChild(dropdown);

  state = { dropdown, results: [], idx: -1 };
  _acState.set(input, state);
  return state;
}

function _acReposition(input) {
  const state = _acState.get(input);
  if (!state || state.dropdown.style.display === 'none') return;
  const rect = input.getBoundingClientRect();
  const dd = state.dropdown;
  // Position below the input; flip up if it would overflow the viewport bottom
  const spaceBelow = window.innerHeight - rect.bottom;
  const ddHeight = Math.min(220, dd.scrollHeight || 220);
  if (spaceBelow < ddHeight && rect.top > ddHeight) {
    dd.style.top = (rect.top - ddHeight) + 'px';
  } else {
    dd.style.top = rect.bottom + 'px';
  }
  dd.style.left = rect.left + 'px';
  dd.style.width = Math.max(rect.width, 220) + 'px';
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
  _acReposition(input);
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

// Reposition open dropdowns when the table scrolls or window resizes
document.addEventListener('scroll', () => {
  _acState.forEach((state, input) => {
    if (state.dropdown.style.display !== 'none') _acReposition(input);
  });
}, true);  // capture phase catches scroll on any ancestor

window.addEventListener('resize', () => {
  _acState.forEach((state, input) => {
    if (state.dropdown.style.display !== 'none') _acReposition(input);
  });
});

// Run on page load for existing rows, and expose for new rows
document.addEventListener('DOMContentLoaded', attachGridAutocomplete);

// autocomplete is now attached inside addRows() directly

// ── Track last interacted row (for Dup × N) ──────────────────────────────
let _lastInteractedRow = null;
document.addEventListener('focusin', e => {
  const row = e.target.closest('tr.conn-row');
  if (row) _lastInteractedRow = row;
});

// ── Port auto-increment ───────────────────────────────────────────────────
function _incrementPort(val) {
  if (!val) return val;
  const m = val.match(/^(.*?)(\d+)$/);
  if (!m) return val;
  return m[1] + (parseInt(m[2], 10) + 1);
}

// ── Duplicate a single row ────────────────────────────────────────────────
const _PORT_INC  = ['device_port','switch_port','device_patch_port','switch_patch_port'];
const _INT_INC   = ['lag_member_index'];

function duplicateRow(btn) {
  const srcRow = btn.closest('tr');
  const tbody  = document.getElementById('conn-body');

  // Capture current field values
  const vals = {};
  srcRow.querySelectorAll('.conn-field').forEach(el => {
    vals[el.dataset.field] = el.value;
  });

  // Increment port fields
  _PORT_INC.forEach(f => { if (vals[f]) vals[f] = _incrementPort(vals[f]); });
  _INT_INC.forEach(f => {
    const v = parseInt(vals[f], 10);
    if (!isNaN(v)) vals[f] = String(v + 1);
  });

  // Build empty row and insert
  tbody.insertAdjacentHTML('beforeend', buildEmptyRow());
  const newRow = tbody.lastElementChild;

  // Fill values
  newRow.querySelectorAll('.conn-field').forEach(el => {
    if (vals[el.dataset.field] !== undefined) el.value = vals[el.dataset.field];
  });

  // Fabric tint
  const fabricEl = newRow.querySelector('[data-field="fabric"]');
  if (fabricEl) updateFabricTint(fabricEl);

  // Already marked dirty by buildEmptyRow; ensure save btn enabled
  document.getElementById('save-btn').disabled = false;

  setTimeout(() => _attachRowAutocomplete(newRow), 0);
  newRow.scrollIntoView({ block: 'nearest' });
}

// ── Duplicate last interacted row × N ────────────────────────────────────
function _duplicateRowDirect(srcRow) {
  // Like duplicateRow(btn) but takes the <tr> directly
  const fakeBtn = { closest: () => srcRow };
  duplicateRow(fakeBtn);
}

function duplicateLast() {
  const n = Math.min(24, Math.max(1, parseInt(document.getElementById('dup-n')?.value, 10) || 4));
  if (!_lastInteractedRow) {
    const rows = document.querySelectorAll('tr.conn-row');
    if (!rows.length) { showToast('No rows to duplicate', 'warning'); return; }
    _lastInteractedRow = rows[rows.length - 1];
  }
  for (let i = 0; i < n; i++) _duplicateRowDirect(_lastInteractedRow);
}

// ── Checkbox / bulk selection ─────────────────────────────────────────────
// Returns only checkboxes in currently visible rows.
function _visibleRowCbs() {
  return [...document.querySelectorAll('tr.conn-row .row-cb')]
    .filter(cb => cb.closest('tr').style.display !== 'none');
}

// Called by individual row checkboxes — updates bar + select-all header state.
// Does NOT write back to selectAll.checked when called from selectAllRows.
function updateBulkToolbar() {
  const visibleCbs = _visibleRowCbs();
  const checked    = visibleCbs.filter(cb => cb.checked);
  const bar        = document.getElementById('bulk-edit-bar');
  const countEl    = document.getElementById('bulk-selected-count');
  const selectAll  = document.getElementById('select-all-cb');

  if (bar)     bar.classList.toggle('d-none', checked.length === 0);
  if (countEl) countEl.textContent = `${checked.length} row${checked.length === 1 ? '' : 's'} selected`;
  // Only update select-all header state when individual rows are toggled
  // (selectAllRows manages it directly to avoid feedback loops)
  if (selectAll) {
    selectAll.indeterminate = checked.length > 0 && checked.length < visibleCbs.length;
    if (!selectAll._fromSelectAll) {
      selectAll.checked = checked.length > 0 && checked.length === visibleCbs.length;
    }
  }
}

function selectAllRows(cb) {
  const shouldCheck = cb.checked;
  const selectAll   = document.getElementById('select-all-cb');
  const visibleCbs  = _visibleRowCbs();

  // Guard flag prevents updateBulkToolbar from overwriting the header checkbox
  if (selectAll) selectAll._fromSelectAll = true;
  visibleCbs.forEach(el => { el.checked = shouldCheck; });
  if (selectAll) {
    selectAll._fromSelectAll = false;
    selectAll.indeterminate = false;
    selectAll.checked = shouldCheck;
  }

  // Update bar / count directly
  const n   = shouldCheck ? visibleCbs.length : 0;
  const bar = document.getElementById('bulk-edit-bar');
  const countEl = document.getElementById('bulk-selected-count');
  if (bar)     bar.classList.toggle('d-none', n === 0);
  if (countEl) countEl.textContent = `${n} row${n === 1 ? '' : 's'} selected`;
}

function clearSelection() {
  document.querySelectorAll('.row-cb').forEach(el => { el.checked = false; });
  const selectAll = document.getElementById('select-all-cb');
  if (selectAll) { selectAll.checked = false; selectAll.indeterminate = false; }
  updateBulkToolbar();
}

// ── Bulk field apply ──────────────────────────────────────────────────────
function applyBulkEdit() {
  const field = document.getElementById('bulk-field-select')?.value || '';
  const value = document.getElementById('bulk-value-input')?.value ?? '';

  if (!field) { showToast('Select a field first', 'warning'); return; }

  // Validate against known value sets for enum fields
  const knownSets = {
    action:         new Set(typeof ACTIONS !== 'undefined' ? ACTIONS : []),
    cable_type:     new Set(typeof CABLE_TYPES !== 'undefined' ? CABLE_TYPES : []),
    purpose:        new Set(typeof PURPOSES !== 'undefined' ? PURPOSES : []),
    fabric:         new Set(typeof FABRICS !== 'undefined' ? FABRICS : []),
    fiber_mode:     new Set(['', 'singlemode', 'multimode']),
    install_status: new Set(typeof INSTALL_STATUSES !== 'undefined' ? INSTALL_STATUSES : []),
  };
  if (knownSets[field] && !knownSets[field].has(value)) {
    showToast(`"${value}" is not a valid value for ${field}`, 'warning');
    return;
  }

  const checked = [...document.querySelectorAll('.row-cb:checked')]
    .filter(cb => cb.closest('tr').style.display !== 'none');
  if (!checked.length) return;

  checked.forEach(cb => {
    const row = cb.closest('tr');
    const el  = row?.querySelector(`[data-field="${field}"]`);
    if (el) {
      el.value = value;
      markDirty(el);
      if (field === 'fabric') updateFabricTint(el);
    }
  });

  showToast(`Applied "${value}" to ${checked.length} row(s)`, 'success');
}

// ── Client-side filter / search ───────────────────────────────────────────
const _FILTER_FIELDS = [
  'system_name_raw','device_name_raw','switch_name_raw',
  'device_rack_name_raw','switch_rack_name_raw',
  'device_port','switch_port','device_slot','switch_slot',
];

function applyFilters() {
  const text   = (document.getElementById('filter-text')?.value  || '').trim().toLowerCase();
  const action = (document.getElementById('filter-action')?.value || '');
  const status = (document.getElementById('filter-status')?.value || '');

  const hasFilter = text || action || status;
  document.getElementById('filter-clear-link')?.classList.toggle('d-none', !hasFilter);

  document.querySelectorAll('tr.conn-row').forEach(row => {
    // Never hide unsaved / dirty rows
    if (row.dataset.dirty === 'true' || row.dataset.id === 'new') {
      row.style.display = '';
      return;
    }

    let show = true;

    if (text) {
      const rowText = _FILTER_FIELDS
        .map(f => (row.querySelector(`[data-field="${f}"]`)?.value || '').toLowerCase())
        .join(' ');
      if (!rowText.includes(text)) show = false;
    }

    if (action && show) {
      const el  = row.querySelector('[data-field="action"]');
      const val = (el?.value || el?.textContent || '').trim();
      if (val !== action) show = false;
    }

    if (status && show) {
      const el  = row.querySelector('[data-field="install_status"]');
      const val = (el?.value || '').trim();
      if (val !== status) show = false;
    }

    row.style.display = show ? '' : 'none';
  });
}

function clearFilters() {
  const t = document.getElementById('filter-text');
  const a = document.getElementById('filter-action');
  const s = document.getElementById('filter-status');
  if (t) t.value = '';
  if (a) a.value = '';
  if (s) s.value = '';
  document.getElementById('filter-clear-link')?.classList.add('d-none');
  document.querySelectorAll('tr.conn-row').forEach(r => { r.style.display = ''; });
  // Reset stale checkbox state from the previous filter
  document.querySelectorAll('.row-cb').forEach(cb => { cb.checked = false; });
  const selectAll = document.getElementById('select-all-cb');
  if (selectAll) { selectAll.checked = false; selectAll.indeterminate = false; }
  updateBulkToolbar();
}
