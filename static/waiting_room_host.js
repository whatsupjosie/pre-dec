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

  const eventQuestion = 'What is the event tonight?';
  const usualEvent = 'Tonight is another one of our fearless leader’s soirées. They’re truly a sight to behold.';

  function renderFaq({container, contract, invited}) {
    const questions = [
      ['What is PubCast?', 'It’s a studio where people and AI characters can write, rehearse, and make shows together.'],
      ['Where do I start?', invited
        ? 'Read the entry contract first. Enter your invitation code and sign your visiting card to accept the terms. Then you can get your avatar ready.'
        : 'Start with the entry contract and the consent choices below. Then choose a display name and avatar color.'],
      ['What am I agreeing to?', invited
        ? 'The contract covers guest conduct, recording, and AI participation. Review it and accept it when you sign your visiting card.'
        : 'The contract covers guest conduct, recording, and AI participation. Review it and accept the required terms before you ask to enter.'],
      [eventQuestion, usualEvent],
      ['Do you have questions about your avatar?', invited
        ? 'Once you’ve signed the contract, we can get your avatar ready. One must be dressed appropriately, you know. If you’re unsure what to bring, ask the person who invited you.'
        : 'Once you’ve accepted the required terms, continue to choose your display name and avatar color. One must be dressed appropriately, you know.'],
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
      if (question === eventQuestion) {
        explanation.style.whiteSpace = 'pre-wrap';
        const next = document.createElement('p');
        next.textContent = 'If you’re here, you must be eager, so let’s get you ready. First things first. Have you signed our contract? You’ll need it to enter. Once that’s taken care of, we can get your avatar ready. One must be dressed appropriately, you know.';
        item.append(next);
        let revision = 0;
        item.addEventListener('toggle', async () => {
          const request = ++revision;
          if (!item.open) return;
          let description = usualEvent;
          try {
            description = await load('/api/guests/event', 'description');
          } catch {
            // Keep the usual answer if the host hasn't posted an update.
          }
          if (request === revision && item.open) explanation.textContent = description;
        });
      }
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
