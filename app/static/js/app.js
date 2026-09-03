// ── Autocomplete Alpine.js component ─────────────────────────────────────
// Usage: x-data="autocomplete('/inventory/autocomplete/systems', null, '')"
//
// Parameters:
//   url       — endpoint returning [{id, label, ...}]
//   initId    — pre-selected id (for edit forms), or null
//   initLabel — pre-selected display label (for edit forms), or ''
//
// The component also supports inline creation: when the user types something
// not in the list and clicks "Create: ...", a POST is made to url.replace
// '/autocomplete/', '/') + '/new' with {name: query}, and the returned
// {id, name} is selected.  The server must handle that stub creation.
//
// For Phase 2 the inline-create on device forms goes to /inventory/systems/new
// via a redirect — kept simple until Phase 3 needs true inline creation.

function autocomplete(url, initId, initLabel) {
  return {
    url,
    query: initLabel || '',
    selectedId: initId || '',
    results: [],
    open: false,

    async search() {
      if (this.query.length === 0) { this.results = []; this.open = false; return; }
      const resp = await fetch(`${this.url}?q=${encodeURIComponent(this.query)}`);
      this.results = await resp.json();
      this.open = true;
    },

    pick(r) {
      this.query = r.label || r.name;
      this.selectedId = r.id;
      this.open = false;
    },

    hide() {
      // Delay so mousedown on an item fires first
      setTimeout(() => { this.open = false; }, 150);
    },

    createNew() {
      // For now: open the system/new form in the same tab.
      // Phase 3 will upgrade this to an inline modal that returns the new id.
      const base = this.url.replace('/autocomplete/', '/').replace(/\/+$/, '');
      window.location.href = `${base}/new`;
    }
  }
}

// ── Bulk select (inventory list views: racks, systems) ───────────────────
// Usage: row checkboxes carry class="<cbClass>" and a form="<formId>" attribute
// pointing at a hidden <form> elsewhere on the page; a header checkbox calls
// toggleSelectAll(cbClass, this.checked), and the submit button is
// id="<cbClass>-delete-btn" (disabled until something's checked).
function toggleSelectAll(cbClass, checked) {
  document.querySelectorAll('.' + cbClass).forEach(cb => { cb.checked = checked; });
  updateBulkDeleteBtn(cbClass);
}

function updateBulkDeleteBtn(cbClass) {
  const count = document.querySelectorAll('.' + cbClass + ':checked').length;
  const btn = document.getElementById(cbClass + '-delete-btn');
  if (btn) btn.disabled = count === 0;
}

function confirmBulkDelete(form, cbClass, label) {
  const count = document.querySelectorAll('.' + cbClass + ':checked').length;
  if (count === 0) return false;
  return confirm(`Delete ${count} selected ${label}${count === 1 ? '' : 's'}? This cannot be undone.`);
}
