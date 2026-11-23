/* 2i's own spell check: the core.
 *
 * Josie, 2026-11-21: "We have to find a free-to-use spell-checking program. It
 * has to work offline." and, 2026-11-22, "it cannot use the internet. No
 * browser. It's standalone."
 *
 * This file checks words, suggests fixes and keeps the writer's own word list.
 * It touches no page and no network. The word list and the Hunspell-compatible
 * engine (nspell) are plain scripts that ship with 2i, loaded by <script> and
 * never by fetch(), because fetch() is refused when 2i is opened from disk.
 * spell-ui.js draws the underlines and the panel on top of this.
 *
 * WHAT IT DOES NOT FLAG, on purpose
 *   ALL-CAPS words    Acronyms, and the character cues in a script (JOSIE:).
 *   iPad, WordNet     Words with a capital inside them: brands and invented names.
 *   Web addresses and e-mail addresses.
 *   Words with digits or underscores in them (3rd, mp3, file_name).
 *   Single letters.
 * Everything else that is not in the word list is flagged. That includes names
 * of people and places, because a name and a typo look the same to a word list.
 * "Add to dictionary" keeps a name for good; "Ignore" keeps it for this session.
 *
 * Nothing here ever changes the manuscript. The writer chooses every fix.
 */
(function installSpell(root){
  'use strict';

  const PERSONAL_KEY = 'twoi.spell.personal.v1';
  const SCRIPTS = ['2i-assets/spell/spell-engine.js', '2i-assets/spell/spell-data.js'];
  // Modern words the American list leaves out. Added only if it really lacks them.
  const EXTRAS = ['ok', 'okay', 'email', 'emails', 'emailed', 'login', 'logins', 'online', 'offline',
    'website', 'websites', 'username', 'usernames', 'smartphone', 'smartphones', 'wifi', 'blog', 'blogs'];

  const WORD = /[\p{L}\p{M}]+(?:['’][\p{L}\p{M}]+)*/gu;
  const LINK = /(?:https?:\/\/|www\.)\S+|[^\s@]+@[^\s@]+\.[^\s@]+/gu;

  let engine = null;          // the nspell instance, once built
  let loading = null;         // the one in-flight load
  const verdicts = new Map(); // word -> boolean; the list never changes except by add()
  const ignored = new Set();  // this session only
  let personal = readPersonal();

  function readPersonal(){
    try {
      const raw = root.localStorage && root.localStorage.getItem(PERSONAL_KEY);
      const list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list.filter(w => typeof w === 'string' && w) : [];
    } catch { return []; }   // storage can be missing, full or refused (opened from disk, private mode)
  }
  function writePersonal(){
    try { root.localStorage && root.localStorage.setItem(PERSONAL_KEY, JSON.stringify(personal)); }
    catch { /* kept in memory for this session */ }
  }
  const straight = word => String(word).replace(/’/g, "'");
  const folded = word => straight(word).toLowerCase();
  function announce(name){
    try { root.document && root.document.dispatchEvent(new root.CustomEvent(name)); } catch { /* no page */ }
  }

  // ------------------------------------------------------------------ loading
  function addScript(src){
    return new Promise((resolve, reject) => {
      const tag = root.document.createElement('script');
      tag.src = src;
      tag.onload = resolve;
      tag.onerror = () => reject(new Error('Could not load ' + src + ' from 2i\'s own files.'));
      root.document.head.append(tag);
    });
  }
  function build(){
    if (engine) return engine;
    const lib = root.TwoiSpellEngine, data = root.TwoiSpellData;
    if (!lib || !data) throw new Error('The spell check word list is not loaded.');
    engine = lib.nspell(data.aff, data.dic);
    for (const word of EXTRAS) if (!engine.correct(word)) engine.add(word, 'cat');
    for (const word of personal) teach(straight(word));
    verdicts.clear();
    return engine;
  }
  // A name gets its possessive ("Zorbleton's") but not a plural; an ordinary word
  // gets both. The word list's own "Alice" and "cat" are the models for that.
  function teach(word){ engine.add(word, /^\p{Lu}/u.test(word) ? 'Alice' : 'cat'); }
  // Resolves when the checker can answer. Safe to call many times.
  function ready(){
    if (engine) return Promise.resolve(true);
    if (!loading) {
      loading = (async () => {
        if (!root.TwoiSpellEngine || !root.TwoiSpellData) {
          if (!root.document) throw new Error('The spell check word list is not loaded.');
          for (const src of SCRIPTS) await addScript(src);   // in order: the data needs no engine, but keep it tidy
        }
        build();
        announce('twoi:spell-ready');
        return true;
      })().catch(error => { loading = null; throw error; });
    }
    return loading;
  }

  // ----------------------------------------------------------------- checking
  // Not ready yet means "do not flag": a writer is never shown a wall of false
  // underlines because a file was slow to load.
  function check(word){
    if (!engine) return true;
    const w = straight(word);
    if (verdicts.has(w)) return verdicts.get(w);
    const ok = engine.correct(w) || ignored.has(folded(w));
    verdicts.set(w, ok);
    return ok;
  }
  // Words one slip away: letters swapped, dropped, added or changed. nspell's own
  // suggestions miss some of the commonest typing slips ("teh" for "the"), so
  // the one-slip words are looked up directly and merged in.
  const LETTERS = 'abcdefghijklmnopqrstuvwxyz\'';
  function oneSlip(word){
    const swaps = [], others = [];
    for (let i = 0; i < word.length; i++) {
      if (i < word.length - 1 && word[i] !== word[i + 1])
        swaps.push(word.slice(0, i) + word[i + 1] + word[i] + word.slice(i + 2));
      others.push(word.slice(0, i) + word.slice(i + 1));
      for (const c of LETTERS) if (c !== word[i]) others.push(word.slice(0, i) + c + word.slice(i + 1));
    }
    for (let i = 0; i <= word.length; i++) for (const c of LETTERS) others.push(word.slice(0, i) + c + word.slice(i));
    return {swaps, others};
  }
  function suggest(word, limit = 6){
    if (!engine) return [];
    const typed = straight(word);
    const lower = typed.toLowerCase();
    const capital = /^\p{Lu}/u.test(typed);
    const dress = candidate => capital && candidate === candidate.toLowerCase()
      ? candidate[0].toUpperCase() + candidate.slice(1) : candidate;
    const slips = typed.length <= 24 ? oneSlip(lower) : {swaps: [], others: []};
    const ordered = [
      ...slips.swaps.filter(c => engine.correct(c)).map(dress),   // swapped letters first: the likeliest slip
      ...engine.suggest(typed),
      ...slips.others.filter(c => engine.correct(c)).map(dress),
    ];
    const seen = new Set(), out = [];
    for (const candidate of ordered) {
      const key = candidate.toLowerCase();
      if (seen.has(key) || key === lower) continue;
      seen.add(key);
      out.push(candidate);
      if (out.length >= limit) break;
    }
    return out;
  }

  // Whether this token should be looked at at all.
  function worthChecking(token, text, start, end, links){
    if (token.length < 2) return false;
    if (token === token.toUpperCase() && token !== token.toLowerCase()) return false;       // ALL CAPS
    if (/[\p{Ll}][\p{Lu}]/u.test(token.replace(/['’]/g, ''))) return false;            // iPad, WordNet
    const before = text[start - 1], after = text[end];
    if ((before && /[\d_]/.test(before)) || (after && /[\d_]/.test(after))) return false;   // 3rd, mp3, file_name
    for (const [from, to] of links) if (start >= from && end <= to) return false;
    return true;
  }
  // Every misspelled word in the text, with where it sits. A hyphenated word is
  // checked a part at a time, because "well-known" is two words.
  function misspellings(text){
    const found = [];
    if (!engine || typeof text !== 'string' || !text) return found;
    const links = [];
    for (const m of text.matchAll(LINK)) links.push([m.index, m.index + m[0].length]);
    for (const m of text.matchAll(WORD)) {
      const word = m[0], start = m.index, end = start + word.length;
      if (!worthChecking(word, text, start, end, links)) continue;
      if (!check(word)) found.push({word, start, end});
    }
    return found;
  }

  // ---------------------------------------------------- the writer's own words
  function isPersonal(word){ return personal.some(w => folded(w) === folded(word)); }
  function add(word){
    const clean = straight(word).trim();
    if (!clean || /\s/.test(clean)) return false;
    if (!isPersonal(clean)) { personal.push(clean); writePersonal(); }
    if (engine) teach(clean);
    verdicts.clear();
    announce('twoi:spell-changed');
    return true;
  }
  function remove(word){
    const before = personal.length;
    personal = personal.filter(w => folded(w) !== folded(word));
    if (personal.length === before) return false;
    writePersonal();
    // nspell can remove what was added, but not a capitalised variant reliably:
    // rebuild from the list so a removed word is really gone.
    engine = null;
    build();
    announce('twoi:spell-changed');
    return true;
  }
  function ignore(word){
    ignored.add(folded(word));
    verdicts.clear();
    announce('twoi:spell-changed');
  }
  function clearIgnored(){ ignored.clear(); verdicts.clear(); announce('twoi:spell-changed'); }

  root.TwoiSpell = {
    ready, check, suggest, misspellings, add, remove, ignore, clearIgnored,
    personal: () => personal.slice(),
    isReady: () => !!engine,
    language: 'American English (en-US)',
    credit: 'Spelling: nspell (MIT) with the SCOWL American English word list (MIT and BSD).',
  };
})(typeof window !== 'undefined' ? window : globalThis);
