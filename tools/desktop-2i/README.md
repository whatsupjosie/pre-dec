# 2i for Windows

2i (the writing program) as a standalone Windows app. It opens the program from
the files installed with it. No server, no account, no internet: every outside
request is refused by the app itself, and the program's own spell check,
dictionary and thesaurus work from files on disk.

## Build the one-click installer

    cd tools/desktop-2i
    npm install
    npm run dist

This stages 2i and the few `static/` files its typewriter look needs into `app/`,
packs them with Electron into `dist/win-unpacked`, then compiles
`installer.nsi` into `dist/2i-Setup-<version>.exe`. The installer asks nothing:
it installs for the current user (no administrator), adds Start menu and Desktop
shortcuts, and opens 2i.

`make-installer.mjs` uses the NSIS compiler that electron-builder downloads, so
it runs on Linux without Wine as well as on Windows. `node_modules/`, `app/` and
`dist/` are not committed.

## Run it without installing

    npm start

## Where her writing is kept

In the app's own data folder, `%APPDATA%\2i`, which updating and uninstalling do
not touch. That folder holds the autosave and recovery copies and the personal
spell-check dictionary. It is a recovery copy, not a backup: use Save a copy or
Export to keep a manuscript somewhere you choose.

## Known

- The installer and app are not code-signed, so Windows SmartScreen may say
  "unrecognized app" on first run (More info, then Run anyway).
- The app has Electron's default icon.
