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

// Shared résumé dialog. The original href remains a useful no-JS fallback.
(() => {
  if (!('HTMLDialogElement' in window)) return;

  document.body.insertAdjacentHTML('beforeend', `
    <dialog class="site-overlay site-overlay--resume" id="resume-overlay" aria-labelledby="resume-overlay-title">
      <div class="site-overlay__panel">
        <header class="site-overlay__header">
          <div>
            <p class="site-overlay__eyebrow">Résumé</p>
            <h2 class="site-overlay__title" id="resume-overlay-title">Caleb Stacy</h2>
          </div>
          <button class="site-overlay__close" type="button" data-close-overlay aria-label="Close résumé dialog">×</button>
        </header>
        <iframe class="site-overlay__resume-frame" title="Caleb Stacy résumé" src="resume-print.html?embedded=1" loading="lazy"></iframe>
        <footer class="site-overlay__footer">
          <span class="site-overlay__footer-note">Senior content designer · Richmond, Virginia</span>
          <div class="site-overlay__footer-actions">
            <a class="site-overlay__action" href="resume.html">Open full page</a>
            <a class="site-overlay__action site-overlay__action--primary" href="Caleb-Stacy-Resume.pdf" download>Download PDF</a>
          </div>
        </footer>
      </div>
    </dialog>
  `);

  const resume = document.getElementById('resume-overlay');
  const openers = new WeakMap();

  function openOverlay(dialog, opener) {
    if (!dialog || dialog.open) return;
    openers.set(dialog, opener || document.activeElement);
    document.documentElement.classList.add('site-overlay-open');
    dialog.showModal();
    const close = dialog.querySelector('[data-close-overlay]');
    if (close) close.focus({ preventScroll: true });
  }

  function closeOverlay(dialog) {
    if (dialog && dialog.open) dialog.close();
  }

  for (const dialog of [resume]) {
    dialog.addEventListener('click', event => {
      if (event.target === dialog) closeOverlay(dialog);
    });
    dialog.querySelector('[data-close-overlay]').addEventListener('click', () => closeOverlay(dialog));
    dialog.addEventListener('close', () => {
      document.documentElement.classList.remove('site-overlay-open');
      const opener = openers.get(dialog);
      if (opener && typeof opener.focus === 'function') opener.focus({ preventScroll: true });
    });
  }

  document.addEventListener('click', event => {
    const anchor = event.target.closest('a[href]');
    if (!anchor || event.defaultPrevented || event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const url = new URL(anchor.href, window.location.href);
    if (url.pathname.endsWith('/resume.html')) {
      event.preventDefault();
      openOverlay(resume, anchor);
    }
  });

  if (window.location.hash === '#resume') openOverlay(resume, null);
})();
