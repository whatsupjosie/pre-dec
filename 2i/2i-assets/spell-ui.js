/* 2i's spell check, on the page: underlines, right-click fixes, and the panel.
 *
 * The checking itself is spell.js. This file only shows its answers and lets
 * the writer act on them. It never edits the manuscript by itself: every change
 * is a suggestion the writer clicked, and it goes in the way a typed change
 * does, so Undo takes it back.
 *
 * WHY THE BROWSER'S OWN SPELL CHECK IS TURNED OFF
 * Josie: "it cannot use the internet. No browser. It's standalone." Chrome and
 * Edge download their dictionaries when first asked. With 2i's check on as well
 * the page would show two sets of underlines that disagree.
 *
 * HOW THE UNDERLINES ARE DRAWN
 * A <textarea> cannot underline one word in itself. So each manuscript textarea
 * gets a see-through copy laid exactly over it -- same font, padding and wrap,
 * its text invisible -- in which only the misspelled words are underlined. It
 * takes no clicks, so typing and selecting go straight through it. The live
 * writing surface is ordinary page text, so it uses the browser's Custom
 * Highlight API instead, which underlines without touching the text at all.
 */
(function installSpellUi(){
  'use strict';
  const S = window.TwoiSpell;
  if (!S) return;
  const doc = document;
  const el = (tag, text, parent) => {
    const node = doc.createElement(tag);
    if (text != null) node.textContent = text;
    if (parent) parent.append(node);
    return node;
  };

  const sheet = el('style', `
    .twoi-spell-mirror{position:absolute;margin:0;pointer-events:none;color:transparent;background:none;
      overflow:hidden;white-space:pre-wrap;box-sizing:border-box;border-style:solid;border-color:transparent;visibility:hidden}
    .twoi-spell-mirror.on{visibility:visible}
    .twoi-spell-mirror .twoi-misspelled{text-decoration:underline wavy #d63a3a;text-decoration-skip-ink:none;text-underline-offset:2px}
    ::highlight(twoi-misspelled){text-decoration:underline wavy #d63a3a;text-underline-offset:2px}
    .twoi-spell-menu{position:fixed;z-index:100000;min-width:180px;max-width:300px;padding:4px;background:#2a2118;color:#f3e6c8;
      border:1px solid #8a6d3b;border-radius:6px;box-shadow:0 6px 20px rgba(0,0,0,.45);font:14px/1.3 system-ui,sans-serif}
    .twoi-spell-menu button{display:block;width:100%;text-align:left;background:none;border:0;color:inherit;padding:6px 10px;
      border-radius:4px;cursor:pointer;font:inherit}
    .twoi-spell-menu button:hover,.twoi-spell-menu button:focus-visible{background:#4a3a24;outline:none}
    .twoi-spell-menu button[disabled]{opacity:.55;cursor:default}
    .twoi-spell-menu hr{border:0;border-top:1px solid #5a4727;margin:4px 0}
    .twoi-spell-menu .twoi-spell-first{font-weight:600}
    #twoiSpelling{position:fixed;right:16px;top:64px;margin:0;width:min(360px,calc(100vw - 32px));max-height:calc(100vh - 96px);
      overflow:auto;padding:12px 14px;background:#2a2118;color:#f3e6c8;border:1px solid #8a6d3b;border-radius:8px;
      box-shadow:0 10px 30px rgba(0,0,0,.5);font:14px/1.35 system-ui,sans-serif;z-index:99990}
    #twoiSpelling h2{margin:0 0 6px;font-size:16px}
    #twoiSpelling .twoi-spell-row{padding:8px 0;border-top:1px solid #4a3a24}
    #twoiSpelling .twoi-spell-word{font-weight:700;color:#ffb3a8}
    #twoiSpelling .twoi-spell-chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}
    #twoiSpelling button{background:#4a3a24;color:inherit;border:1px solid #6d5630;border-radius:5px;padding:3px 9px;cursor:pointer;font:inherit}
    #twoiSpelling button:hover,#twoiSpelling button:focus-visible{background:#6d5630}
    #twoiSpelling .twoi-spell-credit{font-size:12px;opacity:.7;margin:10px 0 6px}
  `, doc.head);
  void sheet;

  const bridge = () => window.TwoiDictionary && typeof window.TwoiDictionary.replaceAt === 'function'
    ? window.TwoiDictionary : null;
  const richSurface = () => window.twoiRichSurface && window.twoiRichSurface.active && window.twoiRichSurface.active()
    ? window.twoiRichSurface : null;

  // ------------------------------------------------------- the right-click menu
  let menu = null;
  function closeMenu(){ if (menu) { menu.remove(); menu = null; } }
  doc.addEventListener('pointerdown', event => { if (menu && !menu.contains(event.target)) closeMenu(); }, true);
  doc.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); }, true);
  window.addEventListener('blur', closeMenu);
  window.addEventListener('resize', closeMenu);

  function showMenu(x, y, word, apply){
    closeMenu();
    menu = el('div', null, doc.body);
    menu.className = 'twoi-spell-menu';
    menu.setAttribute('role', 'menu');
    const item = (label, action, cls) => {
      const b = el('button', label, menu);
      b.type = 'button';
      b.setAttribute('role', 'menuitem');
      if (cls) b.className = cls;
      if (action) b.onclick = () => { closeMenu(); action(); };
      else b.disabled = true;
      return b;
    };
    const options = S.suggest(word);
    if (!options.length) item('No suggestions', null);
    options.forEach((option, i) => item(option, () => apply.replace(option), i === 0 ? 'twoi-spell-first' : ''));
    el('hr', null, menu);
    item('Ignore “' + word + '”', () => S.ignore(word));
    item('Add “' + word + '” to my dictionary', () => S.add(word));
    const box = menu.getBoundingClientRect();
    menu.style.left = Math.max(4, Math.min(x, window.innerWidth - box.width - 4)) + 'px';
    menu.style.top = Math.max(4, Math.min(y, window.innerHeight - box.height - 4)) + 'px';
    menu.querySelector('button:not([disabled])')?.focus();
  }

  // ------------------------------------------------ underlines over a textarea
  const COPY = ['fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'fontVariant', 'fontStretch', 'fontKerning',
    'fontFeatureSettings', 'letterSpacing', 'wordSpacing', 'textTransform', 'textIndent', 'lineHeight', 'textAlign',
    'direction', 'tabSize', 'overflowWrap', 'wordBreak', 'hyphens', 'textRendering', 'paddingTop', 'paddingLeft',
    'paddingBottom', 'borderTopWidth', 'borderLeftWidth', 'borderBottomWidth', 'borderRightWidth'];
  const watching = [];

  function watchTextarea(area){
    if (!area || area.dataset.twoiSpell) return;
    area.dataset.twoiSpell = '1';
    area.spellcheck = false;
    area.setAttribute('spellcheck', 'false');
    const mirror = el('div', null, null);
    mirror.className = 'twoi-spell-mirror';
    mirror.setAttribute('aria-hidden', 'true');
    let shown = null, marks = [], timer = 0;

    // Put the see-through copy exactly over the textarea. False when the textarea is not on screen.
    function layout(){
      if (area.offsetParent === null || area.offsetWidth === 0) { mirror.classList.remove('on'); return false; }
      const parent = area.offsetParent;
      if (mirror.parentNode !== parent) parent.append(mirror);
      const cs = getComputedStyle(area);
      for (const key of COPY) mirror.style[key] = cs[key];
      const bar = Math.max(0, area.offsetWidth - area.clientWidth - parseFloat(cs.borderLeftWidth) - parseFloat(cs.borderRightWidth));
      mirror.style.paddingRight = (parseFloat(cs.paddingRight) + bar) + 'px';
      mirror.style.left = area.offsetLeft + 'px';
      mirror.style.top = area.offsetTop + 'px';
      mirror.style.width = area.offsetWidth + 'px';
      mirror.style.height = area.offsetHeight + 'px';
      mirror.classList.add('on');
      return true;
    }
    function draw(){
      timer = 0;
      if (!S.isReady() || !layout()) return;
      const value = area.value;
      if (value !== shown) {
        shown = value;
        marks = S.misspellings(value);
        const parts = doc.createDocumentFragment();
        let at = 0;
        marks.forEach((m, i) => {
          if (m.start > at) parts.append(doc.createTextNode(value.slice(at, m.start)));
          const span = el('span', value.slice(m.start, m.end), parts);
          span.className = 'twoi-misspelled';
          span.dataset.i = String(i);
          at = m.end;
        });
        // A zero-width space at the end so a final line break takes up a line, as it does in the textarea.
        parts.append(doc.createTextNode(value.slice(at) + '​'));
        mirror.replaceChildren(parts);
      }
      mirror.scrollTop = area.scrollTop;
    }
    function soon(){
      // While typing, show the plain text at once so no underline sits on the wrong word,
      // and draw the underlines once the writer pauses.
      if (S.isReady() && mirror.classList.contains('on') && area.value !== shown) {
        mirror.textContent = area.value + '​';
        shown = null;
      }
      clearTimeout(timer);
      timer = setTimeout(draw, 220);
    }
    area.addEventListener('input', soon);
    area.addEventListener('scroll', () => { mirror.scrollTop = area.scrollTop; });
    if (window.ResizeObserver) new ResizeObserver(soon).observe(area);
    window.addEventListener('resize', soon);
    doc.addEventListener('twoi:mode-change', soon);
    // The text can change without an input event (opening a document, undo) and the box can be
    // hidden and shown by a look change; a light check catches both.
    setInterval(() => {
      if (area.value !== shown || (area.offsetParent !== null) !== mirror.classList.contains('on')) soon();
    }, 600);

    area.addEventListener('contextmenu', event => {
      if (!mirror.classList.contains('on')) return;
      for (const span of mirror.querySelectorAll('.twoi-misspelled')) {
        const hit = [...span.getClientRects()].some(r =>
          event.clientX >= r.left && event.clientX <= r.right && event.clientY >= r.top && event.clientY <= r.bottom);
        if (!hit) continue;
        const m = marks[Number(span.dataset.i)];
        if (!m || area.value.slice(m.start, m.end) !== m.word) return;
        event.preventDefault();
        showMenu(event.clientX, event.clientY, m.word, {
          replace: text => { const b = bridge(); if (b) b.replaceAt({kind: 'textarea', area, start: m.start, end: m.end}, text); },
        });
        return;
      }
    });
    watching.push({redraw(){ shown = null; soon(); }});
    soon();
  }

  // ------------------------------------------- underlines on the live surface
  let surfaceMarks = [];
  let surfaceTimer = 0, surfaceObserver = null;
  function paintSurface(){
    surfaceTimer = 0;
    const surface = doc.getElementById('twoiRichSurface');
    const api = richSurface();
    if (!window.CSS || !CSS.highlights || !window.Highlight) return;
    if (!surface || !api || !S.isReady()) { CSS.highlights.delete('twoi-misspelled'); surfaceMarks = []; return; }
    const ranges = [];
    surfaceMarks = [];
    for (const p of surface.querySelectorAll(':scope > p')) {
      const nodes = [];
      let text = '';
      const walker = doc.createTreeWalker(p, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) { nodes.push({node, from: text.length}); text += node.nodeValue; }
      for (const m of S.misspellings(text)) {
        const first = nodes.findLast(n => n.from <= m.start), last = nodes.findLast(n => n.from < m.end);
        if (!first || !last) continue;
        const range = doc.createRange();
        range.setStart(first.node, m.start - first.from);
        range.setEnd(last.node, m.end - last.from);
        ranges.push(range);
        surfaceMarks.push({word: m.word, range});
      }
    }
    CSS.highlights.set('twoi-misspelled', new Highlight(...ranges));
  }
  function surfaceSoon(){
    clearTimeout(surfaceTimer);
    surfaceTimer = setTimeout(paintSurface, 250);
  }
  function watchSurface(){
    const surface = doc.getElementById('twoiRichSurface');
    if (!surface || surface.dataset.twoiSpell) return;
    surface.dataset.twoiSpell = '1';
    surface.spellcheck = false;
    surface.setAttribute('spellcheck', 'false');
    surfaceObserver = new MutationObserver(surfaceSoon);
    surfaceObserver.observe(surface, {childList: true, characterData: true, subtree: true});
    surface.addEventListener('input', surfaceSoon);
    doc.addEventListener('twoi:mode-change', surfaceSoon);
    setInterval(() => { if (richSurface()) surfaceSoon(); else if (surfaceMarks.length) paintSurface(); }, 800);
    surface.addEventListener('contextmenu', event => {
      const api = richSurface();
      if (!api || !surfaceMarks.length) return;
      const at = doc.caretPositionFromPoint ? doc.caretPositionFromPoint(event.clientX, event.clientY) : null;
      const legacy = !at && doc.caretRangeFromPoint ? doc.caretRangeFromPoint(event.clientX, event.clientY) : null;
      const node = at ? at.offsetNode : legacy && legacy.startContainer, offset = at ? at.offset : legacy && legacy.startOffset;
      if (!node) return;
      const mark = surfaceMarks.find(m => { try { return m.range.comparePoint(node, offset) === 0; } catch { return false; } });
      if (!mark) return;
      event.preventDefault();
      const selection = doc.getSelection();
      selection.removeAllRanges();
      selection.addRange(mark.range);
      const where = api.selection();           // paragraph and offsets in the manuscript's own terms
      if (!where) return;
      showMenu(event.clientX, event.clientY, mark.word, {
        replace: text => { const b = bridge(); if (b) b.replaceAt({kind: 'surface', range: where}, text); },
      });
    });
    surfaceSoon();
  }

  // ----------------------------------------------------------------- the panel
  let panel = null;
  const coWritingNow = () => typeof coWriting !== 'undefined' && !!coWriting;
  // What the panel checks, and how a word in it is replaced, depends on where the writer is writing.
  function source(){
    const api = richSurface();
    if (api) return {
      kind: 'surface', label: 'the manuscript',
      occurrences(){
        const out = [];
        (typeof committed !== 'undefined' ? committed : []).forEach((line, index) => {
          for (const m of S.misspellings(line)) out.push({...m, line: index});
        });
        return out;
      },
      replace(list, text){
        for (const m of list.slice().reverse()) { api.caret(m.line, m.start, m.end); api.insert(text); }
      },
    };
    const area = coWritingNow() ? doc.getElementById('draftArea') : doc.getElementById('soloTextarea');
    if (!area) return null;
    return {
      kind: 'textarea', label: coWritingNow() ? 'the draft page' : 'the manuscript',
      occurrences: () => S.misspellings(area.value),
      replace(list, text){
        const b = bridge();
        if (!b) return;
        for (const m of list.slice().reverse()) {
          if (area.value.slice(m.start, m.end) !== m.word) continue;   // changed since the scan
          b.replaceAt({kind: 'textarea', area, start: m.start, end: m.end}, text);
        }
      },
    };
  }

  function openPanel(){
    if (panel) { panel.close(); }
    panel = el('dialog', null, doc.body);
    panel.id = 'twoiSpelling';
    panel.setAttribute('aria-label', 'Check spelling');
    panel.addEventListener('close', () => { panel.remove(); panel = null; }, {once: true});
    el('h2', 'Check spelling', panel);
    const status = el('p', '', panel);
    status.setAttribute('role', 'status');
    const body = el('div', null, panel);
    const mine = el('details', null, panel);
    el('summary', 'My dictionary', mine);
    const mineBody = el('div', null, mine);
    el('p', S.credit + ' Works offline; nothing leaves this device.', panel).className = 'twoi-spell-credit';
    const close = el('button', 'Close', panel);
    close.type = 'button';
    close.onclick = () => panel.close();

    function groupByWord(list){
      const groups = new Map();
      for (const m of list) {
        const key = m.word;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(m);
      }
      return groups;
    }
    function render(){
      const src = source();
      body.replaceChildren();
      if (!src) { status.textContent = 'There is no manuscript open to check.'; return; }
      if (!S.isReady()) { status.textContent = 'Getting the word list ready…'; return; }
      const found = src.occurrences();
      const groups = groupByWord(found);
      status.textContent = groups.size
        ? groups.size + ' word' + (groups.size === 1 ? '' : 's') + ' to look at in ' + src.label + ' (' + found.length + ' place' + (found.length === 1 ? '' : 's') + ').'
        : 'No misspelled words found in ' + src.label + '.';
      for (const [word, list] of groups) {
        const row = el('div', null, body);
        row.className = 'twoi-spell-row';
        const head = el('div', null, row);
        el('span', word, head).className = 'twoi-spell-word';
        el('span', list.length > 1 ? '  ×' + list.length : '', head);
        const chips = el('div', null, row);
        chips.className = 'twoi-spell-chips';
        const options = S.suggest(word);
        if (!options.length) el('span', 'No suggestions', chips);
        for (const option of options) {
          const chip = el('button', option, chips);
          chip.type = 'button';
          chip.title = 'Change ' + (list.length > 1 ? 'all ' + list.length : 'this') + ' to “' + option + '”';
          chip.onclick = () => { src.replace(list, option); setTimeout(render, 80); };
        }
        const actions = el('div', null, row);
        actions.className = 'twoi-spell-chips';
        const ignore = el('button', 'Ignore', actions);
        ignore.type = 'button';
        ignore.onclick = () => S.ignore(word);
        const add = el('button', 'Add to my dictionary', actions);
        add.type = 'button';
        add.onclick = () => S.add(word);
      }
      mineBody.replaceChildren();
      const own = S.personal();
      if (!own.length) el('p', 'Nothing yet. Words you add show up here.', mineBody);
      for (const word of own) {
        const line = el('div', null, mineBody);
        el('span', word + ' ', line);
        const remove = el('button', 'Remove', line);
        remove.type = 'button';
        remove.onclick = () => S.remove(word);
      }
    }
    doc.addEventListener('twoi:spell-changed', render);
    doc.addEventListener('twoi:spell-ready', render);
    panel.addEventListener('close', () => {
      doc.removeEventListener('twoi:spell-changed', render);
      doc.removeEventListener('twoi:spell-ready', render);
    }, {once: true});
    // Not showModal(): the writer keeps writing, and a fix has to be able to reach the text.
    panel.show();
    S.ready().then(render, error => { status.textContent = error.message; });
    render();
  }

  window.TwoiSpellPanel = {open: openPanel};

  // ---------------------------------------------------------------------- go
  function start(){
    watchTextarea(doc.getElementById('soloTextarea'));
    watchTextarea(doc.getElementById('draftArea'));
    watchSurface();
    S.ready().then(() => { watching.forEach(w => w.redraw()); surfaceSoon(); }, error => console.warn('[2i spell]', error.message));
    doc.addEventListener('twoi:spell-changed', () => { watching.forEach(w => w.redraw()); surfaceSoon(); });
    doc.addEventListener('twoi:spell-ready', () => { watching.forEach(w => w.redraw()); surfaceSoon(); });
  }
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', start); else start();
})();
