"use strict";

// Minimal electron-store mock — in-memory, same get/set interface
class Store {
  constructor({ defaults = {} } = {}) {
    this._data = { ...defaults };
  }
  get(key, fallback) {
    return key in this._data ? this._data[key] : fallback;
  }
  set(key, val) {
    this._data[key] = val;
  }
  get store() {
    return { ...this._data };
  }
}

module.exports = Store;
