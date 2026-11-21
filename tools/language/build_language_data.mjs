/**
 * Build 2i's offline dictionary and thesaurus from WordNet.
 *
 * WHY THIS EXISTS
 * Josie, 2026-11-21: "Writing is the #1 thing you can do easiest offline. So
 * goddamn right we have to have a spell check. And a dictionary. And a
 * thesaurus." 2i had none of its own: spelling was the browser's, and nothing
 * in 2i held a definition. This produces the data for both, to be read with no
 * network at all.
 *
 * RUN
 *   npm --prefix 2i/editor-engine install      (fetches wordnet-db)
 *   node tools/language/build_language_data.mjs
 *
 * It writes 2i/2i-assets/language/, which is committed, so nobody needs to run
 * this to use 2i -- only to rebuild the data from a newer WordNet.
 *
 * SOURCE AND LICENCE
 * WordNet 3.1, Princeton University, via the wordnet-db package. Princeton
 * makes WordNet available to research and commercial users free of charge
 * provided the licence terms are followed and the project is credited. The
 * licence is copied to 2i/2i-assets/language/WORDNET_LICENSE and the credit is
 * shown in 2i's own dictionary panel. Do not remove either.
 *
 * SHAPE OF THE OUTPUT
 * One file per first letter, loaded only when a word starting with that letter
 * is looked up. Josie works across two or three phones and a laptop on bad
 * data, so nothing loads the whole 18 MB to answer one word.
 *
 * Each file is a plain script that hands its block of text to the loader. Not
 * fetch(), and not compressed: a browser refuses fetch() on a file:// URL, and
 * 2i has to work opened straight from disk. A <script> tag works from disk and
 * over HTTP alike. The text costs more on disk than gzip would, but git stores
 * it compressed, so what it actually costs to clone is about the same -- and
 * this way there is no DecompressionStream to depend on and no base64 to
 * inflate it by a third.
 *
 * One line per word:
 *   word \t sense | sense | ...  [\t antonym,antonym]
 * and a sense is
 *   pos ^ definition ^ synonym,synonym
 *
 * Senses are ordered by how often each is actually used, from WordNet's own
 * tagged-corpus counts in index.sense. Without that the first sense of "begin"
 * is the Israeli prime minister and the first sense of "write" is writing data
 * to a disk, which is the kind of thing that makes a feature look broken.
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const outDir = path.join(root, '2i/2i-assets/language');

const wordnet = await import(path.join(root, '2i/editor-engine/node_modules/wordnet-db/index.js'))
  .catch(() => { throw Error('wordnet-db is not installed. Run: npm --prefix 2i/editor-engine install'); });
const dict = p => path.join(wordnet.default.path, p);
const POS = {noun: 'n', verb: 'v', adj: 'a', adv: 'r'};
const SENSE_POS = {1: 'n', 2: 'v', 3: 'a', 4: 'r', 5: 'a'};

// 1. How often each sense is actually used, so the common meaning comes first.
const useCount = new Map();
for (const line of fs.readFileSync(dict('index.sense'), 'utf8').split('\n')) {
  if (!line) continue;
  const field = line.split(' ');
  const pos = SENSE_POS[field[0].split('%')[1]?.split(':')[0]];
  if (!pos) continue;
  const key = pos + ':' + field[1];
  useCount.set(key, Math.max(useCount.get(key) || 0, parseInt(field[3], 10) || 0));
}

// 2. Every synset: its words, its definition, and any antonym pointers.
const synsets = new Map();
for (const [file, pos] of Object.entries(POS)) {
  for (const row of fs.readFileSync(dict('data.' + file), 'utf8').split('\n')) {
    if (!row || row.startsWith('  ')) continue;
    const bar = row.indexOf('|');
    if (bar < 0) continue;
    const head = row.slice(0, bar).trim().split(/\s+/);
    const count = parseInt(head[3], 16);
    if (!Number.isFinite(count)) continue;
    const words = [];
    for (let i = 0; i < count; i++) words.push(head[4 + i * 2].replace(/_/g, ' '));
    let at = 4 + count * 2;
    const pointerCount = parseInt(head[at++], 10);
    const antonyms = [];
    for (let i = 0; i < pointerCount; i++) {
      const symbol = head[at], offset = head[at + 1], target = head[at + 2], ends = head[at + 3];
      at += 4;
      if (symbol === '!') antonyms.push({offset, pos: target, from: parseInt(ends.slice(0, 2), 16), to: parseInt(ends.slice(2), 16)});
    }
    // The gloss is: definition; "an example"; "another". Keep the definition.
    const gloss = row.slice(bar + 1).trim();
    const definition = gloss.split(/;\s*"/)[0].replace(/\s*;\s*$/, '').trim();
    synsets.set(pos + ':' + head[0], {words, definition, antonyms});
  }
}

// 3. Antonyms. A pointer with no word offsets applies to the whole synset.
const antonymsOf = new Map();
const addAntonym = (word, other) => {
  const key = word.toLowerCase();
  if (!antonymsOf.has(key)) antonymsOf.set(key, new Set());
  antonymsOf.get(key).add(other);
};
for (const synset of synsets.values()) {
  for (const pointer of synset.antonyms) {
    const target = synsets.get(pointer.pos + ':' + pointer.offset);
    if (!target) continue;
    if (pointer.from === 0) {
      for (const word of synset.words) for (const other of target.words) addAntonym(word, other);
      continue;
    }
    const from = synset.words[pointer.from - 1], to = target.words[pointer.to - 1];
    if (from && to) { addAntonym(from, to); addAntonym(to, from); }
  }
}

// 4. Every word, from the index files, with its senses in use order.
//
// A Map, never a plain object: WordNet contains "constructor", "toString" and
// "__proto__". On a plain object those collide with Object.prototype and the
// build silently does the wrong thing or throws.
const words = new Map();
for (const [file, pos] of Object.entries(POS)) {
  for (const row of fs.readFileSync(dict('index.' + file), 'utf8').split('\n')) {
    if (!row || row.startsWith('  ')) continue;
    const field = row.trim().split(/\s+/);
    const pointerCount = parseInt(field[3], 10);
    const senseCount = parseInt(field[4 + pointerCount], 10);
    const offsets = field.slice(6 + pointerCount, 6 + pointerCount + senseCount);
    const key = field[0].replace(/_/g, ' ').toLowerCase();
    if (!words.has(key)) words.set(key, []);
    offsets.forEach((offset, order) => {
      const synset = synsets.get(pos + ':' + offset);
      if (!synset) return;
      words.get(key).push({
        pos,
        definition: synset.definition,
        synonyms: synset.words.filter(w => w.toLowerCase() !== key),
        used: useCount.get(pos + ':' + offset) || 0,
        order
      });
    });
  }
}
for (const senses of words.values()) senses.sort((a, b) => b.used - a.used || a.order - b.order);

// 5. Write one script per first letter.
const clean = s => String(s).replace(/[\t\n\r^|]/g, ' ').replace(/\s+/g, ' ').trim();
const shards = new Map();
let senseTotal = 0;
for (const [word, senses] of [...words].sort((a, b) => a[0] < b[0] ? -1 : 1)) {
  if (!senses.length) continue;
  const body = senses.map(s => {
    senseTotal++;
    return s.pos + '^' + clean(s.definition) + '^' + s.synonyms.map(clean).join(',');
  }).join('|');
  const antonyms = antonymsOf.get(word);
  const line = clean(word) + '\t' + body + (antonyms ? '\t' + [...antonyms].map(clean).join(',') : '');
  const letter = /^[a-z]$/.test(word[0]) ? word[0] : '_';
  if (!shards.has(letter)) shards.set(letter, []);
  shards.get(letter).push(line);
}

fs.mkdirSync(outDir, {recursive: true});
for (const name of fs.readdirSync(outDir)) {
  if (/^dict-.+\.js$/.test(name)) fs.unlinkSync(path.join(outDir, name));
}
const index = {};
let bytes = 0;
for (const [letter, lines] of [...shards].sort()) {
  const text = lines.join('\n');
  // A template literal, so the text needs only three characters escaped.
  const escaped = text.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$\{/g, '\\${');
  const file = 'dict-' + (letter === '_' ? 'other' : letter) + '.js';
  const body = '/* 2i offline dictionary and thesaurus. Generated by '
    + 'tools/language/build_language_data.mjs from WordNet 3.1, Princeton University.\n'
    + '   Do not edit by hand. See WORDNET_LICENSE in this folder. */\n'
    + 'window.TwoiLanguageShard && window.TwoiLanguageShard('
    + JSON.stringify(letter) + ', `' + escaped + '`);\n';
  fs.writeFileSync(path.join(outDir, file), body);
  bytes += Buffer.byteLength(body);
  index[letter] = {file, words: lines.length, bytes: Buffer.byteLength(body)};
}
fs.writeFileSync(path.join(outDir, 'index.json'), JSON.stringify({
  source: 'WordNet 3.1, Princeton University (wordnet-db ' + (wordnet.default.version || '3.1') + ')',
  built: new Date().toISOString().slice(0, 10),
  words: [...shards.values()].reduce((n, l) => n + l.length, 0),
  senses: senseTotal,
  shards: index
}, null, 1) + '\n');
fs.copyFileSync(path.join(wordnet.default.path, '..', 'LICENSE'), path.join(outDir, 'WORDNET_LICENSE'));
console.log('words  ', [...shards.values()].reduce((n, l) => n + l.length, 0));
console.log('senses ', senseTotal);
console.log('shards ', shards.size, '(' + (bytes / 1048576).toFixed(2) + ' MB on disk)');
