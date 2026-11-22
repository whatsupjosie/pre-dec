/* Sir Purfluous presents the host's published contract on either entry screen. */
(function () {
  'use strict';

  async function load(url, field) {
    const response = await fetch(url, {cache: 'no-store', signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw Error('Waiting Room request failed');
    const text = (await response.json())[field];
    if (typeof text !== 'string' || !text.trim()) throw Error('Waiting Room text is missing');
    return text;
  }

  function mount({line, terms, termsReady}) {
    let current = 0;
    let activeState;

    async function show(state) {
      if (activeState === state) return;
      activeState = state;
      const revision = ++current;
      try {
        const text = await load('/api/governance/waiting-room/host?state=' + encodeURIComponent(state), 'line');
        if (revision === current) line.textContent = text;
      } catch {
        // The initial greeting remains available if the host endpoint is down.
      }
    }

    async function loadTerms() {
      try {
        terms.textContent = await load('/api/governance/terms', 'terms');
        termsReady?.(true);
      } catch {
        terms.textContent = 'The entry contract could not be loaded. Reload to try again.';
        termsReady?.(false);
      }
    }

    void show('arrival');
    void loadTerms();
    return {show};
  }

  window.PubcastWaitingRoomHost = {mount};
})();
