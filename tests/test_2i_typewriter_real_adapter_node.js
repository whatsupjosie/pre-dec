'use strict';
/*
 * 2i integration boundary: use the ACTUAL production studio desk script and
 * ACTUAL production typewriter input adapter in one fake DOM.
 *
 * Deliberately not a browser test. It proves message routing and editor
 * commands without Playwright, running servers, GitHub Actions or network.
 * Real touch, iframe loading, CSS and browser undo remain browser gates.
 */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../2i/2i-assets/studio-desk.js'), 'utf8');
const actualInput = require('../2i/2i-assets/typewriter-input.js');

class FakeInputEvent {
  constructor(type, values = {}) {
    this.type = type;
    Object.assign(this, values);
    this.defaultPrevented = false;
  }
  preventDefault() { this.defaultPrevented = true; }
}

function boot() {
  const elements = [];
  const notices = [];
  const events = [];
  const sent = [];
  function element(tag) {
    const node = {
      tag, style: {}, dataset: {}, attributes: {}, children: [], listeners: {},
      classList: {
        flags: new Set(),
        contains(name) { return this.flags.has(name); },
        toggle(name, forced) {
          const enabled = forced === undefined ? !this.flags.has(name) : !!forced;
          if (enabled) this.flags.add(name);
          else this.flags.delete(name);
          return enabled;
        },
      },
      append(child) { this.children.push(child); },
      setAttribute(name, value) { this.attributes[name] = value; },
      addEventListener(name, handler) { this.listeners[name] = handler; },
      querySelector() { return element('section'); },
    };
    if (tag === 'iframe')
      node.contentWindow = {postMessage: (message, origin) => sent.push({message, origin})};
    elements.push(node);
    return node;
  }

  const handlers = {};
  const document = {
    body: element('body'), head: element('head'),
    defaultView: {InputEvent: FakeInputEvent},
    execCommand() { return false; }, // force tested setRangeText fallback
    createElement: element,
    addEventListener(name, handler) { (handlers[name] ||= []).push(handler); },
    dispatchEvent(event) {
      for (const handler of handlers[event.type] || []) handler(event);
    },
  };
  function textarea(value) {
    return {
      tagName: 'TEXTAREA',
      value, selectionStart: value.length, selectionEnd: value.length,
      ownerDocument: document, disabled: false, readOnly: false, blocked: false,
      listeners: {},
      addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); },
      focus() {},
      setSelectionRange(start, end) {
        this.selectionStart = start;
        this.selectionEnd = end;
      },
      setRangeText(text, start, end) {
        this.value = this.value.slice(0, start) + text + this.value.slice(end);
        this.selectionStart = this.selectionEnd = start + text.length;
      },
      dispatchEvent(event) {
        events.push({type: event.type, data: event.data});
        if (event.type === 'beforeinput' && this.blocked) return false;
        for (const handler of this.listeners[event.type] || []) handler(event);
        return true;
      },
    };
  }
  const soloTextarea = textarea('Lead');
  const draftArea = textarea('Draft');
  const mcSection = element('section');
  const notebookFrame = element('section');
  const window = {
    listeners: {},
    reachStarted: null,
    TwoiTypewriterInput: actualInput,
    addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); },
  };
  const state = {
    window, document, reachFileMode: false,
    TwoiStudioBridge: {presentation() { return {seated: false, room: null, returnPath: null}; }},
    URLSearchParams, location: {search: '', origin: 'http://localhost'},
    $: (id) => ({mcSection, notebookFrame})[id],
    soloTextarea, draftArea, committed: ['Lead'], buffer: ['Draft'],
    coWriting: false, initializing: false, generating: false,
    chatSending: false, editingIdx: null, networked: true, serverReady: true,
    render() {},
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options?.detail; } },
    addChat: (role, message) => notices.push({role, message}),
  };
  vm.runInNewContext(source, state, {filename: 'studio-desk.js'});
  const iframe = elements.find((node) => node.id === 'twoiTypewriterConsole');
  assert.ok(iframe, 'production 2i typewriter iframe must be installed');
  window.twoiSetPresentation('typewriter');
  const send = (key, origin = 'http://localhost', sourceWindow = iframe.contentWindow) => {
    const message = {type: 'pubcast:2i-key', key};
    for (const handler of window.listeners.message || [])
      handler({data: message, source: sourceWindow, origin});
  };
  return {state, window, iframe, soloTextarea, draftArea, send, events, notices, sent};
}

test('trusted typewriter key edits the real textarea through the real input adapter', () => {
  const x = boot();
  x.soloTextarea.setSelectionRange(2, 2);
  x.send({char: 'X', text: 'x', source: 'pointer'});
  assert.equal(x.soloTextarea.value, 'Lexad');
  assert.deepEqual(x.events.map((event) => event.type), ['beforeinput', 'input']);
});

test('typewriter backspace removes a whole emoji grapheme through the relay', () => {
  const x = boot();
  x.soloTextarea.value = 'a👩🏽‍💻';
  x.soloTextarea.setSelectionRange(x.soloTextarea.value.length, x.soloTextarea.value.length);
  x.send({char: 'BACKSPACE', text: '', source: 'pointer'});
  assert.equal(x.soloTextarea.value, 'a');
});

test('Collab typewriter keys edit the draft, never approved manuscript text', () => {
  const x = boot();
  x.state.coWriting = true;
  x.send({char: 'Q', text: 'q', source: 'pointer'});
  assert.equal(x.draftArea.value, 'Draftq');
  assert.equal(x.soloTextarea.value, 'Lead');
});

test('cancelable beforeinput protects a locked editor from typewriter keys', () => {
  const x = boot();
  x.soloTextarea.blocked = true;
  x.send({char: 'Q', text: 'q', source: 'pointer'});
  assert.equal(x.soloTextarea.value, 'Lead');
  assert.equal(x.events.map((event) => event.type).join(','), 'beforeinput');
});

test('foreign-origin and foreign-window messages do not reach the adapter', () => {
  const x = boot();
  x.send({char: 'Q', text: 'q'}, 'https://untrusted.invalid');
  x.send({char: 'Q', text: 'q'}, 'http://localhost', {});
  assert.equal(x.soloTextarea.value, 'Lead');
  assert.deepEqual(x.events, []);
});

test('busy generation blocks writing through the typewriter relay', () => {
  const x = boot();
  x.state.generating = true;
  x.send({char: 'Q', text: 'q'});
  assert.equal(x.soloTextarea.value, 'Lead');
  assert.deepEqual(x.events, []);
  assert.equal(x.notices.at(-1).role, 'notice');
});
