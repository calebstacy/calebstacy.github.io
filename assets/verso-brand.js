(() => {
  'use strict';

  const panels = [...document.querySelectorAll('[data-verso-brand]')];
  if (!panels.length || !('IntersectionObserver' in window) || !window.matchMedia) return;

  const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (preference.matches) return;

  const states = new Map();
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      const state = states.get(entry.target);
      if (!state) return;
      state.inView = entry.isIntersecting && entry.intersectionRatio > 0;
      state.entered ||= entry.intersectionRatio >= 0.25;
      sync(state);
    });
  }, { threshold: [0, 0.25] });

  function sync(state) {
    if (!state.entered || !state.inView || document.hidden) {
      if (state.started) state.panel.classList.add('is-paused');
      return;
    }
    if (!state.started) {
      state.started = true;
      state.panel.classList.add('is-booting');
    }
    state.panel.classList.remove('is-paused');
  }

  function cleanup() {
    if (states.size) return;
    observer.disconnect();
    document.removeEventListener('visibilitychange', onVisibility);
    preference.removeEventListener('change', onPreference);
    window.removeEventListener('pagehide', finishAll);
  }

  function finish(state) {
    state.panel.classList.remove('is-booting', 'is-paused');
    state.panel.removeEventListener('animationend', state.onEnd);
    observer.unobserve(state.panel);
    states.delete(state.panel);
    cleanup();
  }

  function finishAll() {
    [...states.values()].forEach(finish);
  }

  function onVisibility() {
    states.forEach(sync);
  }

  function onPreference() {
    if (preference.matches) finishAll();
  }

  panels.forEach(panel => {
    const finalLamp = panel.querySelector('.plate-foot > span:last-child');
    if (!finalLamp) return;
    const state = { panel, inView: false, entered: false, started: false };
    state.onEnd = event => {
      if (event.target === finalLamp && event.animationName === 'verso-brand-lamp') finish(state);
    };
    states.set(panel, state);
    panel.addEventListener('animationend', state.onEnd);
    observer.observe(panel);
  });

  if (!states.size) {
    observer.disconnect();
    return;
  }
  document.addEventListener('visibilitychange', onVisibility);
  preference.addEventListener('change', onPreference);
  // Cached Back navigation keeps the readable end state; a true refresh boots again.
  window.addEventListener('pagehide', finishAll);
})();
