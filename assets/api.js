/* ── Cirqle frontend → backend base URL ──
   Live AWS backend, served over HTTPS via Caddy at api.cirqle.co.uk.
   Works from both the local site and the public https:// cirqle.co.uk site.
   When the site itself is served from localhost (local dev), talk to a
   local uvicorn on :8000 instead so nothing touches production. */
window.CIRQLE_API_BASE =
  (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
    ? 'http://localhost:8000'
    : 'https://api.cirqle.co.uk';

/* ── Icon helpers (sleek monoline glyphs, replacing emojis) ──
   Return an <i> using the CSS icon system in cirqle.css. */
window.cirqleIcon = function (name, cls) {
  return '<i class="ico ico-' + name + (cls ? ' ' + cls : '') + '"></i>';
};
/* Map a deal category to its icon name (deals no longer store an emoji). */
window.cirqleCatIcon = function (category) {
  const map = {
    fashion: 'shirt', beauty: 'sparkles', food: 'cup', drink: 'cup',
    electronic: 'laptop', tech: 'laptop', travel: 'plane', home: 'home',
    living: 'home', fitness: 'dumbbell', gym: 'dumbbell', entertain: 'play',
  };
  const c = (category || '').toLowerCase();
  for (const k in map) { if (c.includes(k)) return map[k]; }
  return 'bag';
};
