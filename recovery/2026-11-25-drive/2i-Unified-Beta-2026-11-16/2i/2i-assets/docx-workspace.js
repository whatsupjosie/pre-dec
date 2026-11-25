/* Open a Word working copy using the same editor as Foresight's rich archive. */
(function installWordDocument() {
  'use strict';
  const mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  const maxBytes = 24 * 1024 * 1024;
  let activeDialog = null;

  function choose() {
    if (activeDialog) return;
    if (location.protocol === 'file:') {
      window.alert('Start 2i with Open 2i.cmd on Windows or open_2i.py to edit Word documents offline.');
      return;
    }
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.docx,' + mime;
    input.onchange = () => {
      if (input.files[0] && !activeDialog) open(input.files[0]);
    };
    input.click();
  }

  async function open(file) {
    const dialog = document.createElement('dialog');
    const status = document.createElement('p');
    const title = document.createElement('h2');
    const close = document.createElement('button');
    const surface = document.createElement('div');
    const outputName = file.name.replace(/\.docx$/i, '') + '-working.docx';
    let editor, saving = false, revision = 0, savedRevision = 0;
    const changed = () => document.dispatchEvent(new Event('foresight:work-change'));
    const beforeUnload = event => {
      if (!saving && revision === savedRevision) return;
      event.preventDefault();
      event.returnValue = '';
    };
    const closeIfSafe = () => {
      if (saving) {
        status.textContent = 'Wait for the Word copy to finish exporting.';
        return;
      }
      if (revision !== savedRevision && !window.confirm('Close this Word working copy without exporting the latest edits?')) return;
      dialog.close();
    };
    dialog.style.cssText = 'width:min(96%, 1100px);max-height:94dvh;padding:12px;box-sizing:border-box';
    dialog.setAttribute('aria-label', 'Word working copy');
    title.textContent = file.name;
    title.style.overflowWrap = 'anywhere';
    status.setAttribute('role', 'status');
    status.textContent = 'Opening a Word working copy…';
    close.type = 'button';
    close.textContent = 'Close Word editor';
    close.onclick = closeIfSafe;
    dialog.addEventListener('cancel', event => { event.preventDefault(); closeIfSafe(); });
    dialog.addEventListener('close', () => {
      try { editor?.destroy(); }
      finally {
        window.removeEventListener('beforeunload', beforeUnload);
        activeDialog = null;
        dialog.remove();
        changed();
      }
    }, {once: true});
    dialog.append(title, close, status, surface);
    document.body.append(dialog);
    dialog.showModal();
    activeDialog = dialog;
    window.addEventListener('beforeunload', beforeUnload);
    changed();

    try {
      if (!/\.docx$/i.test(file.name) || !file.size || file.size > maxBytes)
        throw Error('Choose a nonempty Word DOCX file up to 24 MB.');
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (bytes[0] !== 80 || bytes[1] !== 75 || bytes[2] !== 3 || bytes[3] !== 4)
        throw Error('The selected file is not a DOCX package.');
      const {mountRichEditor} = await import('./rich-editor.js');
      if (!dialog.open) return;
      const candidate = await mountRichEditor({
        container: surface, bytes,
        onChange() {
          revision++;
          if (!saving) status.textContent = 'Word edits are ready to export.';
        },
        async onSave() {
          if (!editor || saving) return;
          saving = true;
          const exportingRevision = revision;
          status.textContent = 'Preparing your Word copy…';
          try {
            const data = await editor.saveBytes();
            downloadFile(outputName, data, mime);
            savedRevision = exportingRevision;
            status.textContent = revision === savedRevision
              ? 'Word copy sent to Downloads. Original file kept.'
              : 'Earlier revision sent to Downloads. Export again to include the latest edits.';
          } finally { saving = false; }
        },
        onError(error) {
          status.textContent = error.message;
        }
      });
      if (!dialog.open) { candidate.destroy(); return; }
      editor = candidate;
      status.textContent = 'Edit here, then save a working copy. Your original file stays intact.';
    } catch (error) {
      if (dialog.open) status.textContent = 'Word file could not be opened. ' + error.message;
    }
  }

  window.twoiWordDocument = {choose, isOpen: () => !!activeDialog};
})();
