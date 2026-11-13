const narrow = matchMedia('(max-width:850px)');
function arrange() {
  const article = document.querySelector('.article-content');
  const box = article.querySelector('.factbox');
  if (box) {
    // Narrow screens: the card follows the whole lead (everything before the first section), so it never splits the intro.
    if (narrow.matches) { const first = article.querySelector(':scope > section.article-section'); if (first) first.before(box); else article.append(box); }
    else article.prepend(box);
  }
}
arrange(); narrow.addEventListener('change', arrange);

// The section list beside the article marks the section being read.
const links = [...document.querySelectorAll('.sections a')];
const sections = links.map(a => document.getElementById(a.hash.slice(1)));
let queued = false;
function markSection() {
  let current = 0;
  sections.forEach((section, i) => { if (section && section.getBoundingClientRect().top <= 100) current = i; });
  links.forEach((link, i) => { if (i === current) link.setAttribute('aria-current', 'location'); else link.removeAttribute('aria-current'); });
  queued = false;
}
addEventListener('scroll', () => { if (!queued) { queued = true; requestAnimationFrame(markSection); } }, {passive:true});
markSection();

// The Menu on narrow screens. It closes on a choice, on Escape, on a tap outside, and when the window grows wide.
const menuButton = document.querySelector('.menu-button');
const menuPanel = document.getElementById('site-menu');
if (menuButton && menuPanel) {
  const setMenu = (open, refocus) => {
    menuPanel.hidden = !open; menuButton.setAttribute('aria-expanded', String(open));
    if (!open && refocus) menuButton.focus();
  };
  menuButton.addEventListener('click', () => setMenu(menuPanel.hidden));
  menuPanel.addEventListener('click', event => { if (event.target.closest('a')) setMenu(false); });
  document.addEventListener('click', event => { if (!menuPanel.hidden && !menuPanel.contains(event.target) && !menuButton.contains(event.target)) setMenu(false); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && !menuPanel.hidden) setMenu(false, true); });
  narrow.addEventListener('change', () => setMenu(false));
}

const viewer = document.querySelector('.image-viewer');
if (viewer) {
  let trigger;
  document.querySelectorAll('.image-open').forEach(button => button.addEventListener('click', () => {
    trigger = button;
    const image = button.querySelector('img');
    const target = viewer.querySelector('img');
    target.src = image.src; target.alt = image.alt;
    viewer.querySelector('#image-title').textContent = image.alt;
    viewer.showModal();
  }));
  viewer.querySelector('button').addEventListener('click', () => viewer.close());
  let backdropDown = false;
  const outside = event => { const r = viewer.getBoundingClientRect(); return event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom; };
  viewer.addEventListener('pointerdown', event => { backdropDown = outside(event); });
  viewer.addEventListener('click', event => { if (backdropDown && outside(event)) viewer.close(); backdropDown = false; });
  viewer.addEventListener('close', () => trigger?.focus());
}

// A lead video loops silently. It can be paused from its caption or by clicking it,
// and it waits for a press when the device asks for reduced motion.
document.querySelectorAll('.lead-video').forEach(figure => {
  const video = figure.querySelector('video');
  const caption = figure.querySelector('figcaption');
  if (!video || !caption) return;
  const button = document.createElement('button');
  button.type = 'button'; button.className = 'video-toggle';
  const label = () => { button.textContent = video.paused ? 'Play' : 'Pause'; };
  const toggle = () => { if (video.paused) video.play().catch(() => {}); else video.pause(); };
  button.addEventListener('click', toggle);
  video.addEventListener('click', toggle);
  video.addEventListener('play', label); video.addEventListener('pause', label);
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) { video.removeAttribute('autoplay'); video.pause(); }
  caption.append(button); label();
});
