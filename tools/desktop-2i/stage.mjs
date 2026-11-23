// Gathers exactly what 2i needs to run from disk into ./app, keeping the folder
// shape the page expects (2i/ beside static/), so its relative paths still work.
//   node stage.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '..', '..');
const out = path.join(here, 'app');

// Only what the page loads from disk: the typewriter look reaches into ../static.
const STATIC = [
  '2i_studio_bridge.js',
  'typewriter_console.html',
  'typewriter_console_demo.js',
  'typewriter_console_hotspot_manifest.json',
  'typewriter_keys.webp',
  'typewriter_sound.js',
  'console_hotspot_renderer.css',
  'console_hotspot_renderer.js',
  'studio_console_hotspots.js',
];

fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(path.join(out, '2i'), { recursive: true });
fs.mkdirSync(path.join(out, 'static'), { recursive: true });

fs.copyFileSync(path.join(repo, '2i', 'writers-room-v22.html'), path.join(out, '2i', 'writers-room-v22.html'));
fs.cpSync(path.join(repo, '2i', '2i-assets'), path.join(out, '2i', '2i-assets'), { recursive: true });

const missing = [];
for (const name of STATIC) {
  const from = path.join(repo, 'static', name);
  if (!fs.existsSync(from)) { missing.push(name); continue; }
  fs.copyFileSync(from, path.join(out, 'static', name));
}
if (missing.length) {
  console.error('Missing from static/: ' + missing.join(', '));
  process.exit(1);
}
let files = 0, bytes = 0;
(function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(p); else { files++; bytes += fs.statSync(p).size; }
  }
})(out);
console.log(`staged ${files} files, ${(bytes / 1048576).toFixed(1)} MB into ${out}`);
