(() => {
  document.documentElement.classList.add('enhanced');
  document.querySelectorAll('[data-print]').forEach(button => button.addEventListener('click', () => window.print()));
  document.querySelectorAll('[data-page-size]').forEach(select => select.addEventListener('change', () => select.form.requestSubmit()));
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      const search = document.querySelector('#global-search');
      if (search) { event.preventDefault(); search.focus(); }
    }
  });
  const sidebar = document.querySelector('.workspace-sidebar');
  const toggle = document.querySelector('[data-menu-toggle]');
  const overlay = document.querySelector('[data-menu-close]');
  const mobile = window.matchMedia('(max-width: 767px)');
  const setMenu = open => {
    if (!sidebar) return;
    document.body.classList.toggle('navigation-open', open && mobile.matches);
    toggle.setAttribute('aria-expanded', String(open && mobile.matches));
    toggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    overlay.hidden = !(open && mobile.matches);
    sidebar.inert = mobile.matches && !open;
    document.querySelector('main').inert = open && mobile.matches;
  };
  if (toggle) {
    toggle.addEventListener('click', () => setMenu(toggle.getAttribute('aria-expanded') !== 'true'));
    overlay.addEventListener('click', () => { setMenu(false); toggle.focus(); });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') { setMenu(false); toggle.focus(); }
    });
    mobile.addEventListener('change', () => setMenu(false));
    setMenu(false);
  }
  document.querySelectorAll('[data-roster-filter]').forEach(input => {
    input.addEventListener('input', () => {
      const query = input.value.toLowerCase().trim();
      document.querySelectorAll('[data-roster-row]').forEach(row => {
        row.hidden = !row.dataset.rosterRow.toLowerCase().includes(query);
      });
    });
  });
  document.querySelectorAll('[data-record-entry]').forEach(form => {
    form.addEventListener('invalid', () => {
      document.querySelectorAll('[data-roster-row]').forEach(row => { row.hidden = false; });
      const filter = document.querySelector('[data-roster-filter]');
      if (filter) filter.value = '';
    }, true);
    const summary = document.querySelector('[data-entry-summary]');
    const update = () => {
      if (!summary) return;
      const statuses = {present: 0, absent: 0, late: 0, excused: 0};
      form.querySelectorAll('input[type=radio]:checked').forEach(input => { if (input.value in statuses) statuses[input.value]++; });
      Object.entries(statuses).forEach(([name, value]) => { const node = summary.querySelector('[data-count="'+name+'"]'); if (node) node.textContent = value; });
      const filled = [...form.querySelectorAll('[data-score-input]')].filter(input => input.value !== '').length;
      const node = summary.querySelector('[data-score-count]');
      if (node) node.textContent = filled;
    };
    form.addEventListener('input', update); update();
    const markPresent = form.querySelector('[data-mark-present]');
    if (markPresent) markPresent.addEventListener('click', () => {
      form.querySelectorAll('fieldset.radio-status').forEach(group => {
        if (!group.querySelector('input:checked')) group.querySelector('input[value=present]').checked = true;
      });
      update();
    });
    form.addEventListener('reset', () => setTimeout(update, 0));
  });
})();
