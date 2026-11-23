'use strict';
/**
 * 2i's offline dictionary and thesaurus.
 * Run: node --test tests/test_2i_language_node.js
 *
 * Loads the real generated shards from 2i/2i-assets/language/ into a minimal
 * DOM stand-in and exercises the real 2i/2i-assets/language.js. Nothing here
 * is mocked except the <script> tag, which reads the shard off disk instead of
 * over the network.
 */
const {test} = require('node:test');
const a = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const dataDir = path.join(root, '2i/2i-assets/language');

function openLanguage(){
  const context = {console, Promise, Set, Map, Object, Array, String, RegExp, JSON};
  context.window = context;
  const head = [];
  context.document = {
    currentScript: {src: 'file:///2i/2i-assets/language.js'},
    head: {append(node){ head.push(node); load(node); }},
    createElement: () => ({
      set src(value){ this._src = value; },
      get src(){ return this._src; },
      remove(){}
    })
  };
  function load(node){
    const file = path.join(dataDir, path.basename(node.src));
    // Asynchronous, like a real script tag, so the loader's own waiting is tested.
    setImmediate(() => {
      if (!fs.existsSync(file)) { node.onerror && node.onerror(); return; }
      vm.runInContext(fs.readFileSync(file, 'utf8'), context, {filename: file});
      node.onload && node.onload();
    });
  }
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(root, '2i/2i-assets/language.js'), 'utf8'), context);
  return context.TwoiLanguage;
}

// Arrays built inside the vm carry that realm's prototypes and deepStrictEqual
// rejects them on prototype alone; this brings them into this realm.
const here = value => JSON.parse(JSON.stringify(value));

const language = openLanguage();
const index = JSON.parse(fs.readFileSync(path.join(dataDir, 'index.json'), 'utf8'));

test('the data is there and says where it came from', () => {
  a.ok(index.words > 100000, 'words: ' + index.words);
  a.ok(index.senses > 150000, 'senses: ' + index.senses);
  a.match(index.source, /WordNet/);
  a.ok(fs.existsSync(path.join(dataDir, 'WORDNET_LICENSE')), 'the licence must travel with the data');
  a.match(language.credit, /Princeton/);
});

test('a word comes back with its senses in the order people use them', async () => {
  const begin = await language.lookup('begin');
  a.ok(begin, 'begin must be in the dictionary');
  a.equal(begin.senses[0].pos, 'v', 'the verb, not the Israeli prime minister');
  a.match(begin.senses[0].definition, /first step/);
  const write = await language.lookup('write');
  a.match(write.senses[0].definition, /literary work|writing/);
});

test('synonyms and antonyms', async () => {
  a.ok((await language.synonyms('monument')).includes('memorial'));
  const good = await language.antonyms('good');
  a.ok(good.includes('evil') || good.includes('bad'), good.join(', '));
  a.deepEqual(here(await language.antonyms('zzzznotaword')), []);
});

test('only the letters actually needed are loaded', async () => {
  const fresh = openLanguage();
  a.deepEqual(here(fresh.loadedLetters()), [], 'nothing loads until something is looked up');
  await fresh.lookup('monument');
  a.ok(fresh.loadedLetters().includes('m'));
  a.ok(!fresh.loadedLetters().includes('s'), 'looking up one word must not pull the whole dictionary');
});

test('a word not in WordNet returns null rather than throwing', async () => {
  a.equal(await language.lookup('zzzznotaword'), null);
  a.equal(await language.lookup(''), null);
  a.equal(await language.lookup(null), null);
  a.equal(await language.lookup('   '), null);
});

test('"constructor" is a word, not a function', async () => {
  // WordNet contains constructor, toString and __proto__. On a plain object
  // these collide with Object.prototype; the build and the loader both use Maps.
  for (const word of ['constructor', 'toString', '__proto__']) {
    const found = await language.lookup(word);
    if (found) {
      a.equal(typeof found, 'object');
      a.ok(Array.isArray(found.senses), word + ' must return senses, not a function');
    }
  }
  const constructor = await language.lookup('constructor');
  a.ok(constructor, 'constructor is an English word and should be found');
  a.match(constructor.senses[0].definition, /.+/);
});

test('plurals, tenses and comparatives reach their root', async () => {
  // Several of these are WordNet headwords in their own right -- "writing",
  // "written", "running", "stopped", "better" all have entries. An exact match
  // wins, so what matters is that the root is reachable, either as the match
  // itself or as the root beside it.
  for (const [typed, root] of [
    ['monuments','monument'], ['gears','gear'], ['writing','write'],
    ['written','write'], ['wrote','write'], ['children','child'],
    ['running','run'], ['stopped','stop'], ['better','good'],
    ['cities','city'], ['knives','knife'], ['quickly','quick'],
    ['mice','mouse'], ['feet','foot'], ['went','go'], ['worst','bad']
  ]) {
    const found = await language.lookup(typed);
    a.ok(found, typed + ' found nothing');
    const reached = found.word === root || (found.root && found.root.word === root);
    a.ok(reached, typed + ' gave "' + found.word + '"'
      + (found.root ? ' / root "' + found.root.word + '"' : ' with no root') + ', expected to reach "' + root + '"');
  }
});

test('an inflected word that is also a word of its own offers the root too', async () => {
  // "stopped" is a WordNet adjective, "(of a nose) blocked". True, and not
  // what a writer meant. The verb has to be there as well.
  const stopped = await language.lookup('stopped');
  a.equal(stopped.word, 'stopped');
  a.ok(stopped.root, 'the root must come back with it');
  a.equal(stopped.root.word, 'stop');
  a.match(stopped.root.senses[0].definition, /.+/);
  const monument = await language.lookup('monument');
  a.equal(monument.root, null, 'a word that is already the root has none');
  // and the synonyms draw on both
  const synonyms = await language.synonyms('stopped');
  a.ok(synonyms.length > 1, 'expected synonyms from the root as well: ' + synonyms.join(', '));
});

test('punctuation and curly quotes around a word are ignored', async () => {
  for (const typed of ['"monument"', '(monument)', 'monument,', '‘monument’']) {
    const found = await language.lookup(typed);
    a.ok(found && found.word === 'monument', typed);
  }
});

test('EVERY irregular form points at a word WordNet actually has', async () => {
  // The irregular list is hand-carried, because the npm WordNet package omits
  // the .exc files. A typo in it is a dead end for a writer, so it is checked
  // rather than trusted.
  const source = fs.readFileSync(path.join(root, '2i/2i-assets/language.js'), 'utf8');
  const block = source.slice(source.indexOf('const IRREGULAR'), source.indexOf('// WordNet', source.indexOf('const IRREGULAR')) + 1);
  const pairs = [...block.matchAll(/(\w+)\s*:\s*'([a-z ]+)'/g)].map(m => [m[1], m[2]]);
  a.ok(pairs.length > 100, 'expected a substantial irregular list, found ' + pairs.length);
  const broken = [];
  for (const [form, target] of pairs) {
    const found = await language.lookup(target);
    if (!found || found.word !== target) broken.push(form + ' -> ' + target + ' (not a headword)');
  }
  a.deepEqual(broken, [], 'irregular forms pointing nowhere:\n  ' + broken.join('\n  '));
});

test('no stray keys in the irregular list', async () => {
  const source = fs.readFileSync(path.join(root, '2i/2i-assets/language.js'), 'utf8');
  const block = source.slice(source.indexOf('const IRREGULAR'), source.indexOf('// WordNet', source.indexOf('const IRREGULAR')) + 1);
  const keys = [...block.matchAll(/(\w+)\s*:\s*'[a-z ]+'/g)].map(m => m[1]);
  const odd = keys.filter(k => !/^[a-z]+$/.test(k));
  a.deepEqual(odd, [], 'keys that are not plain words: ' + odd.join(', '));
  a.equal(keys.length, new Set(keys).size, 'duplicate keys in the irregular list');
});
