(() => {
  const D = window.KQ029;
  const ROOT = '../../../';
  const states = [
    ['normal', 'Normal', null],
    ['selected', 'Selected', 'static/images/kidquest/shared/overlays/overlay_selection--base.svg'],
    ['valid', 'Placement valid', 'static/images/kidquest/shared/overlays/overlay_valid--base.svg'],
    ['invalid', 'Placement invalid', 'static/images/kidquest/shared/overlays/overlay_invalid--base.svg'],
    ['locked', 'Locked / dimmed', null],
    ['productive', 'Productive badge', null],
  ];
  const productive = new Set(['garden', 'bakery', 'market_stall']);
  let selectedTheme = D.themes[0].id;
  const el = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) key === 'class' ? node.className = value : node.setAttribute(key, value);
    children.flat().forEach((child) => node.append(child instanceof Node ? child : document.createTextNode(String(child))));
    return node;
  };
  const entry = (theme, logical) => D.manifests[theme].find((item) => item.extraction.logical_id === logical);
  function stage(theme, logical, geometry = false, state = 'normal', overlay = null) {
    const item = entry(theme, logical);
    const ex = item.extraction;
    const box = el('div', { class: `sprite-stage ${state === 'locked' ? 'locked' : ''}` });
    box.append(el('img', { class: 'sprite', src: ROOT + item.runtime_path, alt: ex.accessible_label }));
    if (geometry) {
      const fp = ex.footprint_rect;
      const footprint = el('span', { class: 'footprint' });
      Object.assign(footprint.style, { left: fp.x1 / 2 + 'px', top: fp.y1 / 2 + 'px', width: (fp.x2 - fp.x1) / 2 + 'px', height: (fp.y2 - fp.y1) / 2 + 'px' });
      box.append(footprint);
      const anchor = el('span', { class: 'anchor-mark', title: `anchor ${ex.anchor.x},${ex.anchor.y}` });
      Object.assign(anchor.style, { left: ex.anchor.x / 2 + 'px', top: ex.anchor.y / 2 + 'px' });
      box.append(anchor);
      ex.entrances.forEach((point) => {
        const mark = el('span', { class: 'entrance-mark', title: `${point.side} ${point.x},${point.y}` });
        Object.assign(mark.style, { left: point.x / 2 + 'px', top: point.y / 2 + 'px' });
        box.append(mark);
      });
    }
    if (overlay) box.append(el('img', { class: 'state-overlay', src: ROOT + overlay, alt: '' }));
    if (state === 'productive' && productive.has(logical)) box.append(el('span', { class: 'productive-badge', 'aria-label': 'Produktif' }, '✓'));
    return box;
  }
  function renderCrossTheme() {
    const rows = D.slots.map((slot) => {
      const logical = slot.logical_id;
      return el('div', { class: 'building-row' },
        el('div', { class: 'building-heading' }, el('strong', {}, `${slot.slot}. ${logical}`), `${slot.footprint.width}×${slot.footprint.height} · ${slot.entrances.map((x) => x.side).join('+')}`),
        ...D.themes.map((theme) => el('div', { class: 'building-card' }, el('h3', {}, `${theme.name} · ${theme.labels[logical]}`), stage(theme.id, logical, true)))
      );
    });
    document.getElementById('cross-theme-out').replaceChildren(...rows);
  }
  function renderStates() {
    const groups = D.slots.map((slot) => el('div', { class: 'state-card' },
      el('h3', {}, `${D.themes.find((t) => t.id === selectedTheme).labels[slot.logical_id]} · ${slot.logical_id}`),
      el('div', { class: 'state-grid' }, ...states.map(([id, label, overlay]) => el('div', {}, stage(selectedTheme, slot.logical_id, false, id, overlay),
        el('div', { class: 'state-note' }, id === 'productive' && !productive.has(slot.logical_id) ? `${label}: tidak berlaku` : label))))
    ));
    document.getElementById('states-out').replaceChildren(...groups);
  }
  function controls() {
    document.getElementById('theme-switch').replaceChildren(...D.themes.map((theme) => {
      const button = el('button', { type: 'button', 'aria-pressed': String(theme.id === selectedTheme) }, theme.name);
      button.addEventListener('click', () => { selectedTheme = theme.id; controls(); renderStates(); });
      return button;
    }));
  }
  controls(); renderCrossTheme(); renderStates();
  window.__kq029Gallery = { ready: true };
})();
