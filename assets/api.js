/* ── Cirqle frontend → backend base URL ──
   Live AWS backend, served over HTTPS via Caddy (domain from DuckDNS).
   Works from both the local site and the public https:// GitHub Pages site.
   When the site itself is served from localhost (local dev), talk to a
   local uvicorn on :8000 instead so nothing touches production. */
window.CIRQLE_API_BASE =
  (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
    ? 'http://localhost:8000'
    : 'https://cirqle.duckdns.org';
