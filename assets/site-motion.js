// Scroll reveals for section blocks. Progressive: without JS (or with reduced
// motion) nothing is ever hidden. Above-the-fold blocks show immediately.
(() => {
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if (!('IntersectionObserver' in window)) return;
  const blocks = Array.from(document.querySelectorAll(
    '.section, .story-section, .portal-section, .nux-beat, section[aria-labelledby]'
  )).filter(el =>
    !el.closest('.za-intro-section') &&
    !el.querySelector('.za-hero') &&
    !el.closest('details'));
  if (!blocks.length) return;
  document.documentElement.classList.add('motion-armed');
  const io = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add('is-in');
      io.unobserve(entry.target);
    }
  }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });
  for (const el of blocks) {
    el.classList.add('mv-reveal');
    const box = el.getBoundingClientRect();
    // Zero-size (collapsed details content) or already in the first viewport: no entrance.
    if (box.height === 0 || box.top < window.innerHeight * 0.9) {
      el.classList.add('is-in');
      continue;
    }
    io.observe(el);
  }
})();

// The home CTA keeps its native anchor fallback and adds continuity when motion is welcome.
(() => {
  const trigger = document.querySelector('[data-scroll-to-work]');
  const work = document.getElementById('work');
  if (!trigger || !work) return;

  trigger.addEventListener('click', event => {
    if (event.defaultPrevented || event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    event.preventDefault();
    work.scrollIntoView({ behavior: 'smooth', block: 'start' });
    if (window.location.hash !== '#work') window.history.pushState(null, '', '#work');
  });
})();
