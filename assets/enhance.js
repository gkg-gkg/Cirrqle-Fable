/* ── Cirqle shared UI behaviours (loaded site-wide) ──
   Self-contained & idempotent: injects its own elements, so no
   per-page markup is required. Heavy effects are skipped on touch
   devices and when the user prefers reduced motion. */
(function () {
  'use strict';

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ── Rainbow scroll progress bar ──
  var bar = document.getElementById('scrollProgress');
  if (!bar) {
    bar = document.createElement('div');
    bar.className = 'scroll-progress';
    bar.id = 'scrollProgress';
    document.body.appendChild(bar);
  }
  function onScroll() {
    var max = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.width = (max > 0 ? (window.scrollY / max) * 100 : 0) + '%';
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // ── Auth-aware nav ──
  // Elements tagged data-auth="out" show when signed OUT (sign in / sign up).
  // Elements tagged data-auth="in"  show when signed IN  (dashboard link).
  var session = null;
  try {
    session = JSON.parse(
      localStorage.getItem('cirqle_session') ||
      sessionStorage.getItem('cirqle_session') || 'null'
    );
  } catch (e) { /* ignore malformed session */ }

  document.querySelectorAll('[data-auth="out"]').forEach(function (el) {
    if (session) el.style.display = 'none';
  });
  document.querySelectorAll('[data-auth="in"]').forEach(function (el) {
    el.style.display = session ? '' : 'none';
  });

  // ── Scroll reveal ──
  var revealEls = document.querySelectorAll('.reveal');
  if (revealEls.length) {
    if (reduceMotion || !('IntersectionObserver' in window)) {
      revealEls.forEach(function (el) { el.classList.add('visible'); });
    } else {
      var obs = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) { e.target.classList.add('visible'); obs.unobserve(e.target); }
        });
      }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
      revealEls.forEach(function (el) { obs.observe(el); });
    }
  }

  // ── Global toast helper ──
  window.cirqleToast = function (msg) {
    var t = document.getElementById('toast');
    if (!t) {
      t = document.createElement('div');
      t.className = 'toast';
      t.id = 'toast';
      t.setAttribute('role', 'status');
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._timer);
    t._timer = setTimeout(function () { t.classList.remove('show'); }, 3000);
  };

  // ── Pointer-driven fun (skip on touch / reduced motion) ──
  var finePointer = window.matchMedia('(pointer: fine)').matches;
  if (!finePointer || reduceMotion) return;

  // Sticker wobble on hover
  document.querySelectorAll('.sticker').forEach(function (s) {
    s.addEventListener('mouseenter', function () {
      s.style.transition = 'transform .3s cubic-bezier(.34,1.56,.64,1)';
      s.style.transform = 'rotate(0deg) scale(1.08)';
    });
    s.addEventListener('mouseleave', function () { s.style.transform = ''; });
  });

  // Coin flip on hover
  document.querySelectorAll('.coin').forEach(function (c) {
    c.addEventListener('mouseenter', function () {
      c.style.transition = 'transform .5s cubic-bezier(.34,1.56,.64,1)';
      c.style.transform = 'rotateY(360deg)';
      setTimeout(function () { c.style.transform = ''; }, 520);
    });
  });
})();
