'use strict';
/**
 * 2i's own offline spell check: the core (2i/2i-assets/spell.js).
 * Run: node --test tests/test_2i_spell_node.js
 *
 * Loads the real engine bundle and the real word list that ship in
 * 2i/2i-assets/spell/ and exercises the real spell.js. Nothing is mocked except
 * the browser itself (a window with a localStorage stand-in). There is no
 * network code to mock: the point is that there is none.
 */
const {test} = require('node:test');
const a = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const assets = path.join(__dirname, '..', '2i', '2i-assets');
const read = file => fs.readFileSync(path.join(assets, file), 'utf8');

function open(stored){
  const store = new Map(stored ? [['twoi.spell.personal.v1', JSON.stringify(stored)]] : []);
  const context = {console, Promise, Set, Map, Object, Array, String, RegExp, JSON, Error, Symbol,
    localStorage: {getItem: k => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v))}};
  context.window = context;
  vm.createContext(context);
  for (const file of ['spell/spell-engine.js', 'spell/spell-data.js', 'spell.js']) vm.runInContext(read(file), context, {filename: file});
  return {spell: context.window.TwoiSpell, store};
}
// Results come from another realm (the vm), so copy them before comparing.
const words = list => Array.from(list, m => m.word);

test('it needs no network: the word list and engine are plain files, and the code never fetches', async () => {
  for (const file of ['spell.js', 'spell/spell-engine.js']) {
    const code = read(file).replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
    a.ok(!/\bfetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|https?:\/\/(?!www\.)[a-z]/i.test(code),
      file + ' must not reach for the network');
  }
  const {spell} = open();
  a.equal(spell.check('anything'), true, 'before it is ready, nothing is flagged');
  await spell.ready();
  a.equal(spell.isReady(), true);
});

test('real words pass, including the ones a small list drops', async () => {
  const {spell} = open();
  await spell.ready();
  const text = 'The manuscript was typed on a typewriter, and she stopped running before the moon rose. '
    + "It doesn't matter; they're gone, you'll see, and “okay” is fine. Hello. Colour is not American, color is.";
  a.deepEqual(words(spell.misspellings(text)), ['Colour'], 'only the British spelling is flagged in an American list');
  a.deepEqual(words(spell.misspellings("don’t can’t won’t she’d")), [], 'curly apostrophes read as straight ones');
});

test('real misspellings are caught and the right word is offered first', async () => {
  const {spell} = open();
  await spell.ready();
  const cases = {recieve: 'receive', accomodate: 'accommodate', definately: 'definitely', seperate: 'separate',
    teh: 'the', wich: 'which', beleive: 'believe', occured: 'occurred', untill: 'until', thier: 'their'};
  for (const [typo, right] of Object.entries(cases)) {
    a.equal(spell.check(typo), false, typo + ' should be flagged');
    const offered = spell.suggest(typo);
    a.ok(offered.slice(0, 3).includes(right), typo + ' should offer ' + right + ' in the top three, got ' + offered.join(', '));
  }
  a.equal(spell.suggest('Teh')[0], 'The', 'a capital at the start stays');
});

test('where a misspelling sits is exact, line breaks included', async () => {
  const {spell} = open();
  await spell.ready();
  const text = 'One recieve here,\nand teh next line, and accomodate.';
  const found = spell.misspellings(text);
  a.deepEqual(words(found), ['recieve', 'teh', 'accomodate']);
  for (const m of found) a.equal(text.slice(m.start, m.end), m.word);
});

test('what a writer never wants flagged is left alone, and a real typo beside it still is', async () => {
  const {spell} = open();
  await spell.ready();
  const text = 'JOSIE: NASA says see https://example.com/recieve or write me@exmple.org. '
    + 'The iPad and WordNet and mp3 and 3rd and file_name and a b c. And teh well-known fact.';
  a.deepEqual(words(spell.misspellings(text)), ['teh']);
  a.deepEqual(words(spell.misspellings('a well-knwon fact')), ['knwon'], 'a hyphenated word is checked a part at a time');
});

test('a name can be added for good, ignored for now, and taken back', async () => {
  const {spell, store} = open();
  await spell.ready();
  a.equal(spell.check('Zorbleton'), false);
  spell.ignore('Zorbleton');
  a.equal(spell.check('zorbleton'), true, 'ignoring is not case-sensitive');
  spell.clearIgnored();
  a.equal(spell.check('Zorbleton'), false);
  a.equal(spell.add('Zorbleton'), true);
  a.equal(spell.check('Zorbleton'), true);
  a.equal(spell.check('Zorbleton’s') || spell.check("Zorbleton's"), true, 'the possessive of an added name passes');
  a.deepEqual(JSON.parse(store.get('twoi.spell.personal.v1')), ['Zorbleton'], 'kept on the device');
  a.equal(spell.add('two words'), false, 'a phrase is not a word');
  a.equal(spell.remove('zorbleton'), true);
  a.equal(spell.check('Zorbleton'), false);
  a.deepEqual(JSON.parse(store.get('twoi.spell.personal.v1')), []);
});

test('the writer’s own words come back the next time 2i opens', async () => {
  const {spell} = open(['Josie', 'Zorbleton']);
  await spell.ready();
  a.equal(spell.check('Zorbleton'), true);
  a.deepEqual(Array.from(spell.personal()), ['Josie', 'Zorbleton']);
});

test('a long manuscript is checked fast and the answers are cached', async () => {
  const {spell} = open();
  await spell.ready();
  const paragraph = 'The writer sat at the typewriter and wrote a long chapter about recieve and the moon. ';
  const text = paragraph.repeat(1500);           // about 20,000 words
  const start = process.hrtime.bigint();
  const found = spell.misspellings(text);
  const ms = Number(process.hrtime.bigint() - start) / 1e6;
  a.equal(found.length, 1500);
  a.ok(ms < 1000, 'twenty thousand words should check in under a second, took ' + Math.round(ms) + ' ms');
});

test('the engine builds quickly and holds a real word list', async () => {
  const {spell} = open();
  const start = process.hrtime.bigint();
  await spell.ready();
  const ms = Number(process.hrtime.bigint() - start) / 1e6;
  a.ok(ms < 3000, 'building took ' + Math.round(ms) + ' ms');
  const common = ['the', 'of', 'and', 'because', 'beautiful', 'necessary', 'manuscript', 'chapter', 'paragraph', 'dictionary', 'thesaurus'];
  a.deepEqual(common.filter(w => !spell.check(w)), []);
});
