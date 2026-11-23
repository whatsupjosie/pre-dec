'use strict';
// 2i as a Windows app. It opens the writing program from the files installed with
// it and nothing else: no server, no account, and no internet. Anything that tries
// to leave the machine is refused here, whatever the page asks for.
const { app, BrowserWindow, Menu, session, dialog } = require('electron');
const path = require('path');

app.setName('2i');
Menu.setApplicationMenu(null);                     // 2i has its own menus

if (!app.requestSingleInstanceLock()) { app.quit(); }

let main = null;
const PAGE = path.join(__dirname, 'app', '2i', 'writers-room-v22.html');

function lockDownSession(ses) {
  // No network, ever. file: (the program itself) is not matched by these.
  ses.webRequest.onBeforeRequest(
    { urls: ['http://*/*', 'https://*/*', 'ws://*/*', 'wss://*/*', 'ftp://*/*'] },
    (details, callback) => callback({ cancel: true }));
  // The browser's own spell check downloads its dictionaries; 2i has its own.
  ses.setSpellCheckerEnabled(false);
  ses.setPermissionRequestHandler((_contents, permission, callback) =>
    callback(['clipboard-sanitized-write', 'fullscreen'].includes(permission)));
  ses.setPermissionCheckHandler((_contents, permission) =>
    ['clipboard-sanitized-write', 'fullscreen'].includes(permission));
}

function createWindow() {
  main = new BrowserWindow({
    width: 1360, height: 900, minWidth: 360, minHeight: 480,
    backgroundColor: '#1b140d', title: '2i', show: false, autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true, sandbox: true, nodeIntegration: false,
      spellcheck: false,
      autoplayPolicy: 'no-user-gesture-required',   // the typewriter's sound
      devTools: !app.isPackaged,
    },
  });
  main.once('ready-to-show', () => main.show());
  main.on('page-title-updated', (event) => event.preventDefault());   // stays "2i"
  main.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  main.webContents.on('will-navigate', (event, url) => {
    // The page may reload itself or move between its own files; nothing else.
    if (!url.startsWith('file:')) event.preventDefault();
  });
  main.webContents.on('did-fail-load', (_e, code, description, url) => {
    if (code === -3) return;                        // a load that was cancelled
    dialog.showErrorBox('2i could not open', `${description}\n${url}`);
  });
  main.loadFile(PAGE);
  main.on('closed', () => { main = null; });
}

app.on('second-instance', () => {
  if (main) { if (main.isMinimized()) main.restore(); main.focus(); }
});
app.whenReady().then(() => {
  lockDownSession(session.defaultSession);
  createWindow();
  app.on('activate', () => { if (!BrowserWindow.getAllWindows().length) createWindow(); });
});
app.on('window-all-closed', () => app.quit());
