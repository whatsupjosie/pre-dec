export function showModal({ title = "", content, onClose } = {}) {
  let host = document.getElementById("_modal_host");
  if (!host) {
    host = document.createElement("div");
    host.id = "_modal_host";
    document.body.appendChild(host);
  }
  const wrap = document.createElement("div");
  wrap.className = "pc-modal-wrap";
  wrap.style.cssText = `position:fixed;inset:0;background:rgba(0,0,0,.55);display:grid;place-items:center;z-index:1000;`;
  wrap.addEventListener("click", (e) => {
    if (e.target === wrap) close();
  });
  const card = document.createElement("div");
  card.className = "pc-modal-card";
  card.style.cssText = `background:#1b1b1b;color:#fff;width:min(760px,95vw);border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.5);overflow:hidden;`;
  const head = document.createElement("div");
  head.style.cssText = `display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid rgba(255,255,255,.1)`;
  const h = document.createElement("strong");
  h.textContent = title;
  const x = document.createElement("button");
  x.textContent = "✕";
  x.style.cssText = `background:transparent;border:0;color:#fff;opacity:.8;font-size:16px;cursor:pointer`;
  x.addEventListener("click", () => close());
  head.append(h, x);
  const body = document.createElement("div");
  body.style.cssText = `padding:14px;`;
  if (typeof content === "string") body.innerHTML = content; else if (content) body.appendChild(content);
  card.append(head, body);
  wrap.appendChild(card);
  host.appendChild(wrap);

  function close() {
    wrap.remove();
    onClose && onClose();
  }
  return { close, bodyEl: body };
}

