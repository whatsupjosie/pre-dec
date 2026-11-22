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

  function renderFaq({container, contract, invited}) {
    const questions = [
      ['What is PubCast?', 'It’s a studio where people and AI characters can write, rehearse, and make shows together.'],
      ['Where do I start?', invited
        ? 'Start with the entry contract. Then enter the invitation code your host gave you and prepare your visit.'
        : 'Start with the entry contract and the consent choices below. Then choose a display name and avatar color.'],
      ['What am I agreeing to?', 'The contract explains how guests are expected to behave, where recording may happen, and how AI characters participate. Read it before accepting.'],
      [invited ? 'What is a visiting card?' : 'How do I ask to come in?', invited
        ? 'Your visiting card confirms who you are to the host. Approve it on your own copy of PubCast, then send the signed card back here.'
        : 'After entering your display name and choosing a color, select Enter Airlock. That sends your entry request to the host.'],
      ['When can I enter the studio?', invited
        ? 'Once your card is verified and your visit is approved, the Enter the studio button appears. Until then, stay here and watch for a status update.'
        : 'Once your entry is approved, the Enter Stage button appears. Until then, stay here and watch for a status update.']
    ];

    const intro = document.createElement('p');
    intro.textContent = 'There are a couple of basics we need to go over first. Let me know where you’d like to start. I can walk you through each step and get you out of here and off to the ball.';
    container.append(intro);
    for (const [question, answer] of questions) {
      const item = document.createElement('details');
      const title = document.createElement('summary');
      const explanation = document.createElement('p');
      title.textContent = question;
      explanation.textContent = answer;
      item.append(title, explanation);
      if (question === 'What am I agreeing to?') {
        const link = document.createElement('a');
        link.href = '#' + contract.id;
        link.textContent = 'Read the entry contract';
        link.addEventListener('click', () => {
          if (contract.tagName === 'DETAILS') contract.open = true;
        });
        explanation.append(' ', link);
      }
      container.append(item);
    }
  }

  function mount({line, terms, termsReady, faq}) {
    if (faq) renderFaq(faq);
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
