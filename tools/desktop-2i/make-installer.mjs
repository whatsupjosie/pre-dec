// Turns electron-builder's unpacked app (dist/win-unpacked) into one installer .exe
// with NSIS. electron-builder's own NSIS target needs Wine on Linux; this does not.
//   node make-installer.mjs
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(fs.readFileSync(path.join(here, 'package.json'), 'utf8'));
const source = path.join(here, 'dist', 'win-unpacked');
if (!fs.existsSync(path.join(source, '2i.exe'))) {
  console.error('dist/win-unpacked/2i.exe is not there. Run: npx electron-builder --win dir --x64');
  process.exit(1);
}
// electron-builder keeps the NSIS toolchain it downloaded in its cache.
const caches = [
  path.join(os.homedir(), '.cache', 'electron-builder'),
  path.join(process.env.LOCALAPPDATA || '', 'electron-builder', 'Cache'),
  path.join(os.homedir(), 'Library', 'Caches', 'electron-builder'),
];
let root = null;
for (const cache of caches) {
  if (!fs.existsSync(cache)) continue;
  for (const group of fs.readdirSync(cache).filter((n) => /^nsis-\d/.test(n))) {
    const dir = path.join(cache, group);
    for (const inner of fs.readdirSync(dir)) {
      const candidate = path.join(dir, inner);
      if (fs.existsSync(path.join(candidate, 'Include', 'MUI2.nsh'))) root = candidate;
    }
  }
}
if (!root) {
  console.error('No NSIS toolchain in the electron-builder cache. Run electron-builder with an nsis target once to download it.');
  process.exit(1);
}
const compiler = process.platform === 'win32' ? path.join(root, 'makensis.exe')
  : path.join(root, process.platform === 'darwin' ? 'mac' : 'linux', 'makensis');
const outfile = path.join(here, 'dist', `2i-Setup-${pkg.version}.exe`);
fs.rmSync(outfile, { force: true });
const result = spawnSync(compiler, [
  '-V2', `-DVERSION=${pkg.version}`, `-DSOURCE_DIR=${source}`, `-DOUTFILE=${outfile}`,
  path.join(here, 'installer.nsi'),
], { stdio: 'inherit', env: { ...process.env, NSISDIR: root } });
if (result.status !== 0) process.exit(result.status || 1);
console.log(`\nbuilt ${outfile} (${(fs.statSync(outfile).size / 1048576).toFixed(1)} MB)`);
