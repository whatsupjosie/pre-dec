/* 2i's dictionary and thesaurus panel.
 *
 * Looks up whatever is selected, or the word the caret is sitting in, from the
 * offline WordNet data in 2i/2i-assets/language/. No network, ever.
 *
 * It can put a synonym into the manuscript, but only when the writer asks for
 * that specific word by pressing its Use button. Nothing here changes a
 * character of the text on its own.
 */
(function installDictionary(){
  'use strict';
  if (typeof window.TwoiLanguage === 'undefined') return;
  const L = window.TwoiLanguage;
  const el = (tag, text, parent) => {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (parent) parent.append(node);
    return node;
  };
  const POS = {n: 'noun', v: 'verb', a: 'adjective', r: 'adverb'};
  const WORD_BEFORE = /[\w'\u2019-]+$/, WORD_AFTER = /^[\w'\u2019-]+/;

  // What the writer is pointing at: the selection, or the word under the caret.
  function currentWord(){
    const surface = window.twoiRichSurface;
    if (surface && typeof surface.active === 'function' && surface.active()) {
      const selection = document.getSelection();
      const text = selection ? String(selection) : '';
      if (text.trim()) return text.trim().split(/\s+/)[0];
      const range = surface.selection && surface.selection();
      if (range) return wordAt(committed[range.first] || '', range.start);
      return '';
    }
    const area = typeof soloTextarea !== 'undefined' && soloTextarea ? soloTextarea : null;
    if (!area) return '';
    if (area.selectionEnd > area.selectionStart)
      return area.value.slice(area.selectionStart, area.selectionEnd).trim().split(/\s+/)[0];
    return wordAt(area.value, area.selectionStart);
  }
  function wordAt(text, at){
    if (typeof text !== 'string') return '';
    const before = text.slice(0, at).match(/[\w'’-]+$/);
    const after = text.slice(at).match(/^[\w'’-]+/);
    return ((before ? before[0] : '') + (after ? after[0] : '')).trim();
  }

  // Where the word to replace sits, noted when the panel opens. A modal dialog
  // makes the rest of the document inert, so the writing surface cannot be
  // focused or typed into while the panel is up: the selection has to be taken
  // before it appears and used after it closes.
  function targetNow(){
    const surface = window.twoiRichSurface;
    if (surface && typeof surface.active === 'function' && surface.active()) {
      const range = typeof surface.selection === 'function' ? surface.selection() : null;
      if (!range) return null;
      if (range.first !== range.last) return {kind: 'surface', range};
      // A caret inside a word means that word, the same as in the plain page.
      const text = (typeof committed !== 'undefined' && committed[range.first]) || '';
      let {start, end} = range;
      if (start === end) {
        const before = text.slice(0, start).match(WORD_BEFORE);
        const after = text.slice(start).match(WORD_AFTER);
        if (!before && !after) return null;
        start -= before ? before[0].length : 0;
        end += after ? after[0].length : 0;
      }
      return {kind: 'surface', range: {first: range.first, last: range.first, start, end}};
    }
    const area = typeof soloTextarea !== 'undefined' && soloTextarea ? soloTextarea : null;
    if (!area) return null;
    let start = area.selectionStart, end = area.selectionEnd;
    if (start === end) {
      // Nothing selected: take the word the caret is in, so Use swaps that word.
      const before = area.value.slice(0, start).match(WORD_BEFORE);
      const after = area.value.slice(start).match(WORD_AFTER);
      if (!before && !after) return null;
      start -= before ? before[0].length : 0;
      end += after ? after[0].length : 0;
    }
    return {kind: 'textarea', start: start, end: end};
  }
  // Only ever called from a Use button, and only once the panel has closed.
  function replaceAt(target, replacement){
    if (!target) return false;
    if (target.kind === 'surface') {
      const surface = window.twoiRichSurface;
      if (!surface || typeof surface.insert !== 'function') return false;
      // The modal cleared the selection, so put it back over the word before
      // inserting -- otherwise the synonym is added beside it, not instead.
      if (typeof surface.caret === 'function' && target.range)
        surface.caret(target.range.first, target.range.start, target.range.end);
      surface.insert(replacement);
      return true;
    }
    // The spell check names the text box it means (the draft page as well as the manuscript).
    const area = target.area || (typeof soloTextarea !== 'undefined' && soloTextarea ? soloTextarea : null);
    if (!area) return false;
    area.focus();
    area.setSelectionRange(target.start, target.end);
    if (!document.execCommand('insertText', false, replacement)) {
      // execCommand can be refused; fall back to the path typing itself uses.
      area.setRangeText(replacement, target.start, target.end, 'end');
      area.dispatchEvent(new Event('input', {bubbles: true}));
    }
    return true;
  }

  let dialog = null;
  function open(initial){
    if (dialog) dialog.close();
    // Both of these must be read before showModal(): a modal makes the rest
    // of the document inert and drops the selection, so after it opens there
    // is no longer a selected word to read or to replace.
    const target = targetNow();
    const word = initial || currentWord();
    dialog = el('dialog', null, document.body);
    dialog.id = 'twoiDictionary';
    dialog.setAttribute('aria-label', 'Dictionary and thesaurus');
    dialog.addEventListener('close', () => { dialog.remove(); dialog = null; }, {once: true});

    el('h2', 'Dictionary and thesaurus', dialog);
    const search = el('input', null, dialog);
    search.type = 'search';
    search.placeholder = 'Look up a word';
    search.setAttribute('aria-label', 'Word to look up');
    const status = el('p', '', dialog);
    status.setAttribute('role', 'status');
    const body = el('div', null, dialog);
    body.id = 'twoiDictionaryBody';

    const credit = el('p', L.credit + ' · used offline, no network', dialog);
    credit.className = 'twoi-dictionary-credit';
    const close = el('button', 'Close', dialog);
    close.type = 'button';
    close.onclick = () => dialog.close();

    let token = 0;
    async function show(raw){
      const word = L.normalise(raw);
      search.value = raw || '';
      body.replaceChildren();
      if (!word) { status.textContent = 'Type a word, or select one in the manuscript.'; return; }
      const mine = ++token;
      status.textContent = 'Looking up “' + word + '”…';
      let found;
      try { found = await L.lookup(word); }
      catch (error) { if (mine === token) status.textContent = error.message; return; }
      if (mine !== token) return;
      if (!found) {
        status.textContent = '“' + word + '” is not in the dictionary. '
          + 'Names and invented words will not be, which is not the same as being misspelled.';
        return;
      }
      status.textContent = found.word + (found.typed ? ' · from “' + found.typed + '”' : '')
        + ' · ' + found.senses.length + ' sense' + (found.senses.length === 1 ? '' : 's');
      render(found.word, found.senses, found.antonyms, body);
      if (found.root) {
        const also = el('section', null, body);
        el('h3', 'Also, from “' + found.root.word + '”', also);
        render(found.root.word, found.root.senses, found.root.antonyms, also);
      }
    }
    function render(word, senses, antonyms, host){
      if (antonyms && antonyms.length) {
        const row = el('p', 'Opposites: ', host);
        row.className = 'twoi-dictionary-antonyms';
        antonyms.forEach((antonym, i) => {
          if (i) row.append(document.createTextNode(', '));
          word_(antonym, row);
        });
      }
      const list = el('ol', null, host);
      list.className = 'twoi-dictionary-senses';
      for (const sense of senses.slice(0, 24)) {
        const item = el('li', null, list);
        el('span', POS[sense.pos] || sense.pos, item).className = 'twoi-dictionary-pos';
        el('span', ' ' + sense.definition, item);
        if (!sense.synonyms.length) continue;
        const row = el('div', null, item);
        row.className = 'twoi-dictionary-synonyms';
        for (const synonym of sense.synonyms) {
          const chip = el('span', null, row);
          chip.className = 'twoi-dictionary-chip';
          word_(synonym, chip);
          const use = el('button', 'use', chip);
          use.type = 'button';
          use.className = 'twoi-dictionary-use';
          use.title = 'Put “' + synonym + '” into the manuscript in place of the selected word';
          use.onclick = () => {
            if (!target) {
              status.textContent = 'Put the cursor in a word in the manuscript, then press use.';
              return;
            }
            dialog.close();                       // the page is inert until this returns
            replaceAt(target, synonym);
          };
        }
      }
      if (senses.length > 24) el('p', 'The first 24 of ' + senses.length + ' senses.', host);
    }
    function word_(text, host){
      const link = el('button', text, host);
      link.type = 'button';
      link.className = 'twoi-dictionary-word';
      link.onclick = () => show(text);
      return link;
    }

    let typing = null;
    search.addEventListener('input', () => {
      clearTimeout(typing);
      typing = setTimeout(() => show(search.value), 220);
    });
    dialog.showModal();
    show(word);
    search.focus();
    search.select();
  }

  window.TwoiDictionary = {open, currentWord, wordAt, targetNow, replaceAt};
})();
