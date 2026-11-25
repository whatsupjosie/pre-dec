(() => {
  'use strict';

  const titles = {
    arrival: 'New guest at the Airlock',
    verified_arrival: 'Verified guest arrival',
    door_decision: 'Airlock decision',
    host_request: 'Someone has requested the host',
    security_report: 'Urgent · Security recommends ejection',
  };
  const roomNames = {green_room: 'Green Room', greenroom: 'Green Room', studio: 'Studio', airlock: 'Airlock'};
  const doors = '/static/human_visits.html?mode=host';
  const actions = '/api/guests/';
  const allowedRoles = new Set(['security', 'mod', 'admin', 'owner']);

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function link(url, title) {
    const a = element('a', title);
    a.href = url;
    return a;
  }

  async function request(url, body) {
    const response = await fetch(url, {method: body === undefined ? 'GET' : 'POST',
      headers: {'Content-Type':'application/json'}, body: body === undefined ? undefined : JSON.stringify(body),
      cache: 'no-store', signal: AbortSignal.timeout(12000)});
    const data = await response.json();
    if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Host request failed.');
    return data;
  }

  async function mount(root) {
    const full = root.hasAttribute('data-event-log');
    const count = root.querySelector('[data-alert-count]');
    const status = root.querySelector('[data-event-status]');
    const list = root.querySelector('[data-event-list]');
    const older = root.querySelector('[data-event-older]');
    const form = root.querySelector('[data-security-report]');
    if (window.ReachAuth?.getToken() && !window.ReachAuth.getUser()) await window.ReachAuth.verify().catch(() => null);
    const user = window.ReachAuth?.getUser();
    if (!window.ReachAuth?.getToken() || !allowedRoles.has(user?.role)) {
      if (full) status.textContent = 'Sign in as the host or door staff to see this log.';
      return;
    }
    root.hidden = false;
    if (form) form.hidden = false;
    const items = new Map();
    const rendered = new Map();
    let busy = false;
    let oldest = null;
    let signature = '';

    function action(title, run) {
      const button = element('button', title);
      button.type = 'button';
      button.onclick = async () => {
        button.disabled = true;
        try { await run(button); }
        catch (error) { status.textContent = error.message; }
        finally { button.disabled = false; }
      };
      return button;
    }

    async function read(event) {
      await request(actions + 'events/' + event.event_id + '/acknowledge', {});
      items.set(event.event_id, {...event, seen: 1});
      render();
    }

    function card(event) {
      const row = element('article', '', 'host-event');
      const urgent = event.kind === 'security_report' || (event.kind === 'host_request' && event.room === 'studio');
      row.dataset.urgent = String(urgent);
      const title = event.kind === 'host_request' && urgent ? 'Studio · Host attention requested' : titles[event.kind];
      row.append(element('strong', title || 'Host event'));
      row.append(element('p', event.name + (event.room ? ' · ' + (roomNames[event.room] || event.room) : '')));
      if (event.detail) row.append(element('p', event.detail));
      const time = element('time', new Date(event.created * 1000).toLocaleString());
      row.append(time);
      const controls = element('div', '', 'host-event-actions');
      if (event.kind === 'arrival' || event.kind === 'verified_arrival') controls.append(link(doors, 'Go to the door'));
      if (event.kind === 'security_report' || event.kind === 'host_request') {
        const studio = event.room === 'studio';
        controls.append(link(studio ? '/studio' : '/walk?view=green_room/main', 'Go to room'));
        controls.append(link('/static/human_contacts.html?person=' + encodeURIComponent(event.user_id), 'Contact guest'));
        controls.append(action('Read room transcript', async button => {
          if (row.querySelector('details')) {
            row.querySelector('details').open = true;
            return;
          }
          const {recent_messages} = await request('/api/chat/rooms/' + (studio ? 'studio' : 'greenroom') + '?limit=100');
          const details = element('details');
          details.open = true;
          details.append(element('summary', 'Recent room transcript'));
          for (const message of recent_messages || []) {
            details.append(element('p', (message.user || message.user_id || 'Guest') + ': ' + (message.text || '')));
          }
          if (!recent_messages?.length) details.append(element('p', 'No recent messages.'));
          row.append(details);
          button.textContent = 'Open room transcript';
        }));
      }
      if (event.kind === 'security_report' && !event.seen && ['owner', 'admin', 'mod'].includes(user.role)) {
        controls.append(action('Confirm ejection', async () => {
          if (!window.confirm('Eject ' + event.name + ' from this session?')) return;
          await request('/api/governance/kick', {user_id: event.user_id, reason: event.detail});
          await read(event);
          status.textContent = event.name + ' was ejected from this session.';
        }));
      }
      if (!event.seen) controls.append(action('Mark read', () => read(event)));
      row.append(controls);
      return row;
    }

    function render() {
      const ordered = Array.from(items.values()).sort((a,b)=>b.event_id-a.event_id);
      const unread = ordered.filter(event => !event.seen).length;
      if (count) {
        if (unread > Number(count.dataset.last || 0)) root.open = true;
        count.dataset.last = String(unread);
        count.textContent = unread ? '(' + unread + ' new)' : '';
      }
      const visible = full ? ordered : ordered.filter(event => !event.seen).slice(0, 4);
      const next = visible.map(event => event.event_id + ':' + event.seen).join(',');
      if (signature === next && list.childNodes.length) return;
      signature = next;
      const cards = visible.map(event => {
        const key = event.event_id + ':' + event.seen;
        if (!rendered.has(key)) rendered.set(key, card(event));
        return rendered.get(key);
      });
      list.replaceChildren(...(cards.length ? cards : [element('p', 'No new host alerts.')]));
    }

    async function refresh(earlier = false) {
      if (busy) return;
      busy = true;
      try {
        const suffix = earlier && oldest ? '?before=' + oldest : '';
        const {events} = await request(actions + 'events' + suffix);
        for (const event of events) items.set(event.event_id, event);
        if (older && (suffix || oldest === null)) older.hidden = events.length < 100;
        if (events.length) oldest = Math.min(oldest || Infinity, events[events.length - 1].event_id);
        render();
      } catch (error) {
        status.textContent = error.message;
      } finally {busy = false;}
    }
    if (older) older.onclick = () => refresh(true);
    if (form) form.onsubmit = async event => {
      event.preventDefault();
      const button = form.querySelector('button');
      button.disabled = true;
      try {
        await request(actions + 'security-report', Object.fromEntries(new FormData(form)));
        form.reset();
        status.textContent = 'Security recommendation sent to the host.';
        await refresh();
      } catch (error) { status.textContent = error.message; }
      finally { button.disabled = false; }
    };
    await refresh();
    const timer = setInterval(() => { if (!document.hidden) void refresh(); }, 2500);
    window.addEventListener('pagehide', () => clearInterval(timer), {once:true});
  }

  document.querySelectorAll('[data-host-events]').forEach(mount);
  for (const button of document.querySelectorAll('[data-page-host]')) {
    const status = button.parentElement.querySelector('[data-page-host-status]');
    button.onclick = async () => {
      button.disabled = true;
      try {
        await request(actions + 'host-request', {room: button.dataset.pageHost});
        status.textContent = 'The host has been paged.';
      } catch (error) { status.textContent = error.message; }
      finally { button.disabled = false; }
    };
  }
})();
