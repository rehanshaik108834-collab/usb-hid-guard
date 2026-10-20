// Refreshes every element marked data-live="<url>" every few seconds, only while the tab is visible.
(function () {
  const regions = document.querySelectorAll("[data-live]");
  if (!regions.length) return;
  const every = 2500;
  async function refresh(el) {
    try {
      const res = await fetch(el.dataset.live, { headers: { "X-Requested-With": "fetch" } });
      if (!res.ok) return;
      const html = await res.text();
      if (html !== el.dataset.last) {
        el.innerHTML = html;
        el.dataset.last = html;
      }
      const stamp = document.querySelector("[data-updated]");
      if (stamp) stamp.textContent = new Date().toLocaleTimeString([], { hour12: false });
    } catch (e) { /* dashboard server stopped: keep the last view */ }
  }
  setInterval(() => {
    if (document.hidden) return;
    regions.forEach(refresh);
  }, every);
})();
