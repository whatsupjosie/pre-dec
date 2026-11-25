"use strict";

const path = require("path");
const os   = require("os");
const fs   = require("fs");

const TMP = path.join(os.tmpdir(), "cc-jest-" + process.pid);

// Pre-create all dirs so getPath never returns a path that doesn't exist
["documents","home","downloads","userData"].forEach(function(p) {
  fs.mkdirSync(path.join(TMP, p), { recursive: true });
});

module.exports = {
  app: {
    getPath: function(p) {
      if (p === "documents") return path.join(TMP, "documents");
      if (p === "home")      return path.join(TMP, "home");
      if (p === "downloads") return path.join(TMP, "downloads");
      if (p === "userData")  return path.join(TMP, "userData");
      return path.join(TMP, p);
    },
    setLoginItemSettings: function() {},
    // whenReady must return a real thenable — Electron returns a Promise
    whenReady: function() {
      return Promise.resolve();
    },
    on:         function() {},
    quit:       function() {},
    getVersion: function() { return "1.0.0"; },
    dock:       { hide: function() {}, show: function() {} },
  },
  BrowserWindow: function() {
    this.loadFile             = function() {};
    this.setMenuBarVisibility = function() {};
    this.focus                = function() {};
    this.on                   = function() {};
  },
  Tray: function() {
    this.setImage        = function() {};
    this.setToolTip      = function() {};
    this.setContextMenu  = function() {};
  },
  Menu:        { buildFromTemplate: function() { return {}; } },
  nativeImage: { createFromPath:    function() { return {}; } },
  ipcMain:     { handle: function() {}, on: function() {}, emit: function() {} },
  dialog:      {
    showOpenDialog: function() {
      return Promise.resolve({ canceled: true, filePaths: [] });
    }
  },
  shell: {
    openPath:    function() { return Promise.resolve(""); },
    openExternal: function() { return Promise.resolve(); },
  },
};
