/**
 * Build 2i's offline spell check engine and word list.
 *
 * WHY THIS EXISTS
 * Josie, 2026-11-21: "We have to find a free-to-use spell-checking program. It
 * has to work offline." and "Writing is the #1 thing you can do easiest
 * offline." The browser's own spell check is not that: Chrome and Edge fetch
 * their dictionaries over the network on first use, and it only underlines
 * inside the browser. 2i checks spelling itself, from files that ship with it.
 *
 * RUN
 *   npm --prefix tools/language/spell install --ignore-scripts
 *   node tools/language/build_spell_engine.mjs
 * It writes 2i/2i-assets/spell/, which is committed, so nobody needs to run
 * this to use 2i -- only to rebuild from a newer word list.
 *
 * WHAT GOES IN
 *   nspell 2.1.5          MIT.           Hunspell-compatible checker, pure JavaScript.
 *   dictionary-en 4.0.0   MIT AND BSD.   American English Hunspell dictionary derived from
 *                                        SCOWL (Spell Checker Oriented Word Lists).
 *   esbuild 0.28.2        MIT.           Bundles nspell for the browser. Build time only.
 * Josie has not said American or British spelling. American is the default
 * because that is what she writes; a British pack would be one more data file.
 *
 * WHAT COMES OUT
 *   spell-engine.js   nspell as one script that sets window.TwoiSpellEngine.
 *   spell-data.js     the .aff and .dic as strings in window.TwoiSpellData. A script,
 *                     not a fetch(): fetch() is refused on file:// and 2i has to work
 *                     opened from disk.
 *   LICENSES.txt      the licences of the three packages and the SCOWL notice.
 */
import fs from 'node:fs';
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
// The build tools are installed under tools/language/spell, not at the repo root.
const {build} = createRequire(path.join(here, 'spell', 'package.json'))('esbuild');
const modules = path.join(here, 'spell', 'node_modules');
const out = path.join(here, '..', '..', '2i', '2i-assets', 'spell');
if (!fs.existsSync(path.join(modules, 'nspell'))) {
  console.error('Run: npm --prefix tools/language/spell install --ignore-scripts');
  process.exit(1);
}
fs.mkdirSync(out, {recursive: true});

const entry = path.join(here, 'spell', 'engine-entry.mjs');
fs.writeFileSync(entry, "import nspell from 'nspell';\nwindow.TwoiSpellEngine = {nspell};\n");
await build({
  entryPoints: [entry], outfile: path.join(out, 'spell-engine.js'), bundle: true, minify: true,
  format: 'iife', platform: 'browser', target: ['es2019'], nodePaths: [modules],
  legalComments: 'none', logLevel: 'warning',
});
fs.rmSync(entry);

const dictionary = path.join(modules, 'dictionary-en');
const aff = fs.readFileSync(path.join(dictionary, 'index.aff'), 'utf8');
const dic = fs.readFileSync(path.join(dictionary, 'index.dic'), 'utf8');
fs.writeFileSync(path.join(out, 'spell-data.js'),
  '/* 2i spell check word list: dictionary-en 4.0.0 (SCOWL), American English. See LICENSES.txt. */\n'
  + 'window.TwoiSpellData=' + JSON.stringify({aff, dic}) + ';\n');

const read = (...p) => fs.readFileSync(path.join(modules, ...p), 'utf8').trim();
fs.writeFileSync(path.join(out, 'LICENSES.txt'), [
  '2i offline spell check: third-party licences',
  '',
  '== nspell 2.1.5 (MIT) ==', read('nspell', 'license'), '',
  '== dictionary-en 4.0.0 (MIT AND BSD; word list derived from SCOWL) ==', read('dictionary-en', 'license'), '',
  '== esbuild 0.28.2 (MIT), used to bundle nspell at build time ==', read('esbuild', 'LICENSE.md').slice(0, 1200), '',
].join('\n'));
console.log('wrote', fs.readdirSync(out).join(', '));
