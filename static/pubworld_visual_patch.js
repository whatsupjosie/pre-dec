'use strict';

(() => {
  const form = document.getElementById('patch-form');
  const inputs = form.querySelector('fieldset');
  const panel = form.closest('details');
  const library = document.getElementById('patch-library');
  const sceneId = 'pubworld_stage';
  const kind = form.elements.patch_kind;
  const save = document.getElementById('patch-save');
  const status = document.getElementById('patch-status');
  const picker = document.getElementById('patch-picker');
  const pick = document.getElementById('patch-pick');
  const outline = document.getElementById('patch-region');
  let selectedRegion = null;
  let dragStart = null;
  let pending = null;
  let requestGeneration = 0;

  function forgetProposal(message) {
    pending = null;
    requestGeneration++;
    save.disabled = true;
    status.textContent = message;
  }

  function finishPicking() {
    picker.style.pointerEvents = 'none';
    pick.setAttribute('aria-pressed', 'false');
    pick.textContent = 'Select region';
    dragStart = null;
  }

  function showRegion(region) {
    outline.hidden = !region;
    picker.hidden = false;
    if (region) {
      outline.style.left = `${region.x * 100}%`;
      outline.style.top = `${region.y * 100}%`;
      outline.style.width = `${region.width * 100}%`;
      outline.style.height = `${region.height * 100}%`;
    }
  }

  function setRegion(region) {
    finishPicking();
    selectedRegion = region;
    showRegion(region);
    forgetProposal(region ? 'Stage area selected.' : 'Select the area that needs repair.');
  }

  function point(event) {
    const bounds = picker.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)),
      y: Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height)),
    };
  }

  function rectangle(end) {
    return {x: Math.min(dragStart.x, end.x), y: Math.min(dragStart.y, end.y),
      width: Math.abs(dragStart.x - end.x), height: Math.abs(dragStart.y - end.y)};
  }

  pick.addEventListener('click', () => {
    if (pick.getAttribute('aria-pressed') === 'true') {
      setRegion(null);
      return;
    }
    selectedRegion = null;
    showRegion(null);
    picker.style.pointerEvents = 'auto';
    pick.setAttribute('aria-pressed', 'true');
    pick.textContent = 'Cancel selection';
    forgetProposal('Drag a rectangle over the stage.');
  });
  document.getElementById('patch-full-frame').addEventListener('click', () => {
    setRegion({x: 0, y: 0, width: 1, height: 1});
  });
  picker.addEventListener('pointerdown', event => {
    if (!event.isPrimary || event.button !== 0) return;
    dragStart = point(event);
    picker.setPointerCapture(event.pointerId);
  });
  picker.addEventListener('pointermove', event => {
    if (dragStart && event.isPrimary) showRegion(rectangle(point(event)));
  });
  picker.addEventListener('pointerup', event => {
    if (!dragStart || !event.isPrimary) return;
    const region = rectangle(point(event));
    setRegion(region.width > 0.005 && region.height > 0.005 ? region : null);
  });
  picker.addEventListener('pointercancel', () => setRegion(null));
  function showSavedProp(prop) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'mini-btn';
    button.textContent = `Preview ${prop.label}`;
    button.addEventListener('click', async () => {
      try {
        await showVisualPatchPreview(prop);
      } catch (error) {
        status.textContent = error.message;
      }
    });
    library.append(button);
  }

  async function loadSavedPatches() {
    const response = await fetch(`/api/pubworld/props?scene_id=${sceneId}`);
    if (!response.ok) throw new Error('Saved patches could not be loaded.');
    const {props} = await response.json();
    library.replaceChildren();
    for (const prop of props) {
      if (prop.variants.some(variant => ['live_overlay', 'adaptive_overlay'].includes(variant.variant_id))) {
        showSavedProp(prop);
      }
    }
  }

  panel.addEventListener('toggle', () => {
    if (!panel.open) {
      setRegion(null);
      return;
    }
    loadSavedPatches().catch(error => { status.textContent = error.message; });
  });
  if (location.hash === '#visual-patch') {
    panel.open = true;
    panel.scrollIntoView({block: 'nearest'});
  }
  form.addEventListener('input', () => {
    forgetProposal('Ready for a new proposal.');
  });
  kind.addEventListener('change', () => {
    const fitting = kind.value === 'adaptive_extension';
    const costume = document.getElementById('patch-costume');
    const fit = document.getElementById('patch-fit');
    costume.hidden = costume.disabled = fitting;
    fit.hidden = fit.disabled = !fitting;
    setRegion(null);
    if (fitting) status.textContent = 'Enter the performer and prop measurements.';
  });

  async function post(action, body) {
    const response = await fetch(`/api/visual-patch/${action}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(result.detail) ? result.detail[0]?.msg : result.detail;
      throw new Error(detail || `Request failed (${response.status})`);
    }
    return result;
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    forgetProposal('Preparing a proposal…');
    const body = Object.fromEntries(new FormData(form));
    body.scene_id = sceneId;
    if (body.patch_kind === 'visual_patch') {
      if (!selectedRegion) {
        status.textContent = 'Select a stage region or use the full view.';
        return;
      }
      body.region = selectedRegion;
    }
    const generation = requestGeneration;
    inputs.disabled = true;
    try {
      const result = await post('propose', body);
      if (requestGeneration !== generation) return;
      status.textContent = result.message;
      if (result.proposal) {
        pending = result;
        const dimensions = result.proposal.dimensions || result.proposal.voxel_patch?.dimensions;
        if (dimensions) status.textContent += ` Size ${dimensions.join(' × ')} voxels.`;
        save.disabled = false;
      }
    } catch (error) {
      status.textContent = error.message;
    } finally {
      inputs.disabled = false;
    }
  });

  save.addEventListener('click', async () => {
    if (!pending) return;
    inputs.disabled = true;
    status.textContent = 'Saving the approved patch…';
    try {
      const result = await post('approve', {
        scene_id: pending.scene_id,
        patch_kind: pending.patch_kind,
        proposal: pending.proposal,
        label: pending.label,
        approval: {state: 'approved'},
      });
      finishPicking();
      showRegion(null);
      selectedRegion = null;
      forgetProposal(`Saved to this scene as ${result.prop.label}.`);
      await loadSavedPatches();
    } catch (error) {
      status.textContent = error.message;
    } finally {
      inputs.disabled = false;
    }
  });
})();
