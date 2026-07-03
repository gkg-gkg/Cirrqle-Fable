/* ── Cirqle: per-user Instagram handle helpers ──
   Reads/writes each user's Instagram handle on their cirqle_users registry
   record (keyed by email) plus the live session, so it survives logout/login.
   Exposed as window.CirqleAccount and used by the Dashboard feed (feed.html). */
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

  function readUsers() {
    try { return JSON.parse(localStorage.getItem('cirqle_users') || '[]'); }
    catch (e) { return []; }
  }

  // The current signed-in user's registry record (matched by email).
  function getUser() {
    var session = getSession();
    if (!session || !session.email) return null;
    var email = session.email.toLowerCase();
    return readUsers().find(function (u) {
      return u.email && u.email.toLowerCase() === email;
    }) || null;
  }

  // The stored handle — session first (fast), then the registry record.
  function getHandle() {
    var session = getSession();
    if (session && session.instagramHandle) return normalizeHandle(session.instagramHandle);
    var user = getUser();
    return user && user.instagramHandle ? normalizeHandle(user.instagramHandle) : '';
  }

  // Save a handle onto BOTH the persistent registry record and the session.
  function setHandle(raw) {
    var handle = normalizeHandle(raw);
    if (!handle) return '';
    var session = getSession();

    if (session && session.email) {
      var email = session.email.toLowerCase();
      var users = readUsers();
      users.forEach(function (u) {
        if (u.email && u.email.toLowerCase() === email) u.instagramHandle = handle;
      });
      localStorage.setItem('cirqle_users', JSON.stringify(users));

      // Mirror into whichever storage currently holds the session.
      session.instagramHandle = handle;
      var store = localStorage.getItem('cirqle_session') ? localStorage : sessionStorage;
      store.setItem('cirqle_session', JSON.stringify(session));
    }
    return handle;
  }

  window.CirqleAccount = {
    getUser: getUser,
    getHandle: getHandle,
    setHandle: setHandle,
    normalizeHandle: normalizeHandle
  };
})();
