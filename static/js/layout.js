(() => {
  const source = document.getElementById('workspace-layout-state');
  const controls = document.querySelector('[data-layout-controls]');
  if (!source || !controls) return;
  const saved = JSON.parse(source.textContent);
  const widgets = [...document.querySelectorAll('[data-layout-widget]')];
  if (!widgets.length) return;
  const known = new Set(widgets.map(widget => widget.dataset.layoutWidget));
  const hidden = new Set((Array.isArray(saved.hidden) ? saved.hidden : []).filter(id => known.has(id)));
  const collapsed = new Set((Array.isArray(saved.collapsed) ? saved.collapsed : []).filter(id => known.has(id)));
  const options = controls.querySelector('[data-layout-options]');
  const status = controls.querySelector('[data-layout-status]');
  const retry = controls.querySelector('[data-layout-retry]');
  const edit = controls.querySelector('[data-layout-edit]');
  const panel = document.getElementById('layout-options');
  const choices = new Map();
  const endpoint = document.querySelector('[data-layout-save-url]').dataset.layoutSaveUrl;
  const csrf = document.querySelector('input[name=csrfmiddlewaretoken]').value;
  let queue = Promise.resolve();
  let revision = 0;

  const isVisible = widget => !hidden.has(widget.dataset.layoutWidget);
  const reflow = () => {
    widgets.forEach(widget => { widget.hidden = !isVisible(widget); });
    document.querySelectorAll('[data-layout-column]').forEach(column => {
      const members = column.matches('[data-layout-widget]') ? [column] : [...column.querySelectorAll('[data-layout-widget]')];
      column.hidden = !members.some(isVisible);
    });
    document.querySelectorAll('[data-layout-columns]').forEach(columns => {
      const count = [...columns.children].filter(column => !column.hidden).length;
      columns.classList.toggle('layout-one-column', count === 1);
      columns.hidden = count === 0;
    });
    document.querySelectorAll('[data-layout-group]').forEach(group => {
      group.hidden = ![...group.querySelectorAll('[data-layout-widget]')].some(isVisible);
    });
    document.querySelectorAll('[data-layout-metrics]').forEach(group => {
      group.dataset.visibleCount = [...group.querySelectorAll('[data-layout-widget]')].filter(isVisible).length;
    });
    widgets.forEach(widget => { choices.get(widget.dataset.layoutWidget).checked = isVisible(widget); });
  };

  const persist = () => {
    const payload = {page: saved.page, hidden: [...hidden], collapsed: [...collapsed]};
    const current = ++revision;
    status.textContent = 'Saving layout…';
    retry.hidden = true;
    // Serial writes preserve the order of rapid edits, including reset/retry.
    queue = queue.then(async () => {
      try {
        const response = await fetch(endpoint, {
          method: 'POST', credentials: 'same-origin',
          headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
          body: JSON.stringify(payload),
        });
        if (!response.ok || !(await response.json()).saved) throw new Error('Save failed');
        if (current === revision) status.textContent = 'Layout saved';
      } catch {
        if (current === revision) {
          status.textContent = 'Layout not saved. Retry when your connection is available.';
          retry.hidden = false;
        }
      }
    });
  };

  widgets.forEach(widget => {
    const id = widget.dataset.layoutWidget;
    const title = widget.dataset.layoutTitle;
    const label = document.createElement('label');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = !hidden.has(id);
    label.append(checkbox, document.createTextNode(title));
    options.append(label);
    choices.set(id, checkbox);
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) hidden.delete(id); else hidden.add(id);
      reflow(); persist();
    });
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'layout-hide-button';
    remove.textContent = 'Hide';
    remove.setAttribute('aria-label', 'Hide ' + title);
    remove.addEventListener('click', event => {
      event.preventDefault(); event.stopPropagation();
      hidden.add(id); reflow(); persist(); edit.focus();
    });
    widget.append(remove);
    if (widget.matches('details')) {
      widget.open = !collapsed.has(id);
      widget.addEventListener('toggle', () => {
        const wasCollapsed = collapsed.has(id);
        if (wasCollapsed === !widget.open) return;
        if (widget.open) collapsed.delete(id); else collapsed.add(id);
        persist();
      });
    }
  });

  edit.addEventListener('click', () => {
    const editing = edit.getAttribute('aria-expanded') !== 'true';
    edit.setAttribute('aria-expanded', String(editing));
    edit.textContent = editing ? 'Done editing' : 'Edit layout';
    panel.hidden = !editing;
    document.querySelector('main').classList.toggle('layout-editing', editing);
  });
  const setSummaries = open => {
    widgets.filter(widget => widget.matches('details')).forEach(widget => {
      if (open) collapsed.delete(widget.dataset.layoutWidget); else collapsed.add(widget.dataset.layoutWidget);
      widget.open = open;
    });
    persist();
  };
  controls.querySelector('[data-layout-collapse-all]').addEventListener('click', () => setSummaries(false));
  controls.querySelector('[data-layout-expand-all]').addEventListener('click', () => setSummaries(true));
  controls.querySelector('[data-layout-reset]').addEventListener('click', () => {
    hidden.clear(); collapsed.clear();
    widgets.filter(widget => widget.matches('details')).forEach(widget => { widget.open = true; });
    reflow(); persist();
  });
  retry.addEventListener('click', persist);
  reflow();
  controls.hidden = false;
})();
