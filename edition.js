const contents = document.querySelector('.contents');
const directory = document.querySelector('.site-directory');
const narrow = matchMedia('(max-width:850px)');
function arrange() {
  if (contents) contents.open = !narrow.matches;
  const article = document.querySelector('.article-content');
  const box = article.querySelector('.factbox');
  const lead = article.querySelector(':scope > p');
  if (box && lead) {
    if (narrow.matches) lead.after(box);
    else article.prepend(box);
  }
}
arrange(); narrow.addEventListener('change', arrange);
const links = contents ? [...contents.querySelectorAll('a')] : [];
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
links.forEach(link => link.addEventListener('click', () => { if (narrow.matches) contents.open = false; }));

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

// The site menu is navigation, separate from the article's table of contents.
document.addEventListener('click', event => {
  if (directory?.open && !directory.contains(event.target)) directory.open = false;
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && directory?.open) {
    directory.open = false;
    directory.querySelector('summary').focus();
  }
});

// One wave when the page opens, drawn from a sprite sheet so it plays the same on every device
// and always ends on the resting pose. Click to replay.
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
document.querySelectorAll('.greeting').forEach(button => {
  const sprite = button.querySelector('.greeting-sprite');
  if (!sprite) return;
  function play() {
    if (reducedMotion.matches || !button.classList.contains('ready')) return;
    sprite.classList.remove('wave');
    void sprite.offsetWidth; // restart the animation
    sprite.classList.add('wave');
  }
  function preference() { button.disabled = reducedMotion.matches; }
  const sheet = new Image();
  sheet.onload = () => { button.classList.add('ready'); play(); };
  sheet.src = button.dataset.wave;
  button.addEventListener('click', play);
  reducedMotion.addEventListener('change', preference);
  preference();
});

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
