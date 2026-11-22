(async () => {
  'use strict';

  const byId = id => document.getElementById(id);
  const selection = byId('chat-selection');
  const status = byId('archive-status');
  const save = byId('archive-save');
  const download = byId('archive-export');
  const prepare = byId('archive-prepare');
  const share = byId('archive-share');
  const shareDownload = byId('archive-share-download');
  const sharePanel = byId('archive-sharing');
  const archiveBase = '/api/conversations/exports/all/';
  const options = new Map([['all', {url: archiveBase + 'zip', method: 'POST'}]]);
  let prepared = null;

  async function request(url, method = 'GET') {
    const response = await fetch(url, {method, cache: 'no-store', signal: AbortSignal.timeout(120000)});
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(typeof error.detail === 'string' ? error.detail : `Request failed (${response.status})`);
    }
    return response;
  }

  function addOptions(group, entries) {
    for (const entry of entries) {
      const key = String(options.size);
      options.set(key, entry);
      group.append(new Option(entry.title, key));
    }
  }

  function addGroup(label, entries) {
    if (!entries.length) return;
    const group = document.createElement('optgroup');
    group.label = label;
    addOptions(group, entries);
    selection.append(group);
  }

  function discardPrepared() {
    prepared = null;
    sharePanel.hidden = true;
  }

  function downloadFile(file) {
    const objectURL = URL.createObjectURL(file);
    const anchor = document.createElement('a');
    anchor.href = objectURL;
    anchor.download = file.name;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(objectURL), 1000);
  }

  async function run(action) {
    selection.disabled = true;
    save.disabled = download.disabled = prepare.disabled = true;
    discardPrepared();
    status.textContent = 'Preparing archive…';
    try {
      await action();
    } catch (error) {
      status.textContent = error.message;
    } finally {
      selection.disabled = false;
      save.disabled = download.disabled = prepare.disabled = false;
    }
  }

  async function exportSelection() {
    const entry = options.get(selection.value);
    const response = await request(entry.url, entry.method);
    const headers = response.headers.get('content-disposition') || '';
    const filename = headers.match(/filename="([^"]+)"/i)?.[1] || entry.filename || 'PubCast_Chat_Archive.zip';
    const blob = await response.blob();
    return new File([blob], filename, {type: blob.type});
  }

  selection.addEventListener('change', () => {
    discardPrepared();
    status.textContent = '';
  });

  save.onclick = () => run(async () => {
    const result = await (await request(archiveBase + 'raw', 'POST')).json();
    status.textContent = `Archive saved on the PubCast host as ${result.export_name}.`;
  });
  download.onclick = () => run(async () => {
    const file = await exportSelection();
    downloadFile(file);
    status.textContent = `Download started for ${file.name}.`;
  });
  prepare.onclick = () => run(async () => {
    prepared = await exportSelection();
    share.hidden = !navigator.share || !navigator.canShare?.({files: [prepared]});
    sharePanel.hidden = false;
    status.textContent = share.hidden
      ? 'Download the prepared file to share it from another app.'
      : `${prepared.name} is ready. Choose a recipient in the share menu.`;
  });
  share.onclick = async () => {
    if (!prepared) return;
    try {
      await navigator.share({files: [prepared]});
      discardPrepared();
      status.textContent = 'File handed to the share menu.';
    } catch (error) {
      if (error.name !== 'AbortError') status.textContent = 'Sharing failed. You can download the prepared file.';
    }
  };
  shareDownload.onclick = () => {
    if (prepared) downloadFile(prepared);
  };
  byId('archive-cancel').onclick = discardPrepared;

  try {
    if (!await ReachAuth.requireSession(location.pathname)) return;
    addOptions(byId('private-chats'), [
      {title: 'Character Chat', collection: 'characters'},
      {title: 'Writer’s Room chats', collection: 'writers-room'},
      {title: 'PubPartner sessions', collection: 'pubpartner'},
    ].map(entry => ({...entry, url: '/api/conversations/exports/private/' + entry.collection,
      filename: 'PubCast_' + entry.collection + '_chats.json'})));
    const loaders = [
      ['/api/chat/rooms', data => addGroup('Rooms', data.rooms.map(room => ({title: room.display,
        url: '/api/chat/rooms/' + encodeURIComponent(room.room_id) + '/export', filename: 'PubCast_room_chat.jsonl'})))],
      ['/api/chat/dm/active', data => addGroup('Direct messages', Array.from(new Map(data.rooms.map(room =>
        [room.dm_room, {title: room.other_user, url: '/api/chat/dm/' + encodeURIComponent(room.dm_room) + '/export',
          filename: 'PubCast_direct_chat.jsonl'}])).values()))],
      ['/api/conversations', data => addGroup('General Chat', data.conversations.map(chat => ({title: chat.title,
        url: '/api/conversations/' + encodeURIComponent(chat.conversation_id) + '/exports/zip', method: 'POST'})))],
    ];
    const loaded = await Promise.allSettled(loaders.map(async ([url, render]) => render(await (await request(url)).json())));
    status.textContent = loaded.some(result => result.status === 'rejected') ? 'Some conversations could not be listed. Reload to retry.' : '';
    save.disabled = download.disabled = prepare.disabled = false;
  } catch (error) {
    status.textContent = error.message;
  }
})();
