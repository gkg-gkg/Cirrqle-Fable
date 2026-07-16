/* ── Cirqle: per-user Instagram handle helpers ──
   Reads/writes the signed-in user's Instagram handle on the live session.
   The handle is the server's source of truth (persisted via PATCH /auth/me in
   feed.html); this just mirrors it into the session so pages can read it
   without a fetch. Exposed as window.CirqleAccount, used by the feed (feed.html). */
(function () {
  'use strict';

  function getSession() {
    try {
      return JSON.parse(
        localStorage.getItem('cirqle_session') ||
        sessionStorage.getItem('cirqle_session') || 'null'
      );
    } catch (e) { return null; }
  }

  // Normalise a handle: trim, drop a leading @, lowercase.
  function normalizeHandle(h) {
    return (h || '').trim().replace(/^@+/, '').toLowerCase();
  }

  // The stored handle, read from the session.
  function getHandle() {
    var session = getSession();
    return session && session.instagramHandle ? normalizeHandle(session.instagramHandle) : '';
  }

  // Mirror a handle into the session (the caller persists it server-side first).
  function setHandle(raw) {
    var handle = normalizeHandle(raw);
    if (!handle) return '';
    var session = getSession();
    if (session) {
      session.instagramHandle = handle;
      var store = localStorage.getItem('cirqle_session') ? localStorage : sessionStorage;
      store.setItem('cirqle_session', JSON.stringify(session));
    }
    return handle;
  }

  window.CirqleAccount = {
    getHandle: getHandle,
    setHandle: setHandle,
    normalizeHandle: normalizeHandle
  };
})();
