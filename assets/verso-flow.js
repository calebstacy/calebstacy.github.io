(() => {
  'use strict';
  /* The arrows and step numbers show at rest.
     "How a request moved": one marker carries the request through the seven steps in the list beside it.
     At rest the figure shows the whole route with numbered steps. It plays once when scrolled into view,
     then rests. Back, Next and Replay step through it. With reduced motion nothing travels: steps just switch. */
  const still = window.matchMedia('(prefers-reduced-motion: reduce)');
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  const setup = (wrap) => {
    const fig = wrap.querySelector('.flow-figure');
    const items = [...wrap.querySelectorAll('.method > li')];
    const chip = fig.querySelector('.chip'), chipText = chip.querySelector('text');
    const count = fig.querySelector('.flow-count'), text = fig.querySelector('.flow-text');
    const back = fig.querySelector('.flow-back'), next = fig.querySelector('.flow-next'), replay = fig.querySelector('.flow-replay');
    const part = (k) => fig.querySelector('[data-k="' + k + '"]');
    const staged = [...fig.querySelectorAll('[data-s]')];
    const LAST = items.length;
    let step = 0, run = 0; // step 0 is the resting picture; run cancels an animation when the reader moves on

    // Once the reader steps by hand, keep the caption from changing the figure's height between steps.
    const cap = fig.querySelector('.flow-caption');
    const size = () => {
      const keep = text.innerHTML; let tall = 0; cap.style.minHeight = '';
      [fig.dataset.rest, ...items.map((li) => li.innerHTML)].forEach((html) => { text.innerHTML = html; tall = Math.max(tall, cap.offsetHeight); });
      text.innerHTML = keep; cap.style.minHeight = tall + 'px';
    };

    const point = (path, t) => { const p = part(path); return p.getPointAtLength(p.getTotalLength() * t); };
    // A step number fades while the marker sits on top of it.
    const badges = [...fig.querySelectorAll('.badge')].map((b) => { const c = b.querySelector('circle'); return { b, x: +c.getAttribute('cx'), y: +c.getAttribute('cy') }; });
    const cover = (pt) => badges.forEach(({ b, x, y }) => b.classList.toggle('under', !!pt && Math.abs(x - pt.x) < 50 && Math.abs(y - pt.y) < 22));
    const place = (pt) => { chip.setAttribute('transform', 'translate(' + pt.x.toFixed(1) + ' ' + pt.y.toFixed(1) + ')'); cover(pt); };
    const show = async (label, pt, unseen) => {
      if (chip.classList.contains('show') && chipText.textContent === label && chip.classList.contains('hidden-work') === !!unseen) { place(pt); return; }
      if (chip.classList.contains('show')) { chip.classList.remove('show'); if (!still.matches) await wait(260); }
      chipText.textContent = label; chip.classList.toggle('hidden-work', !!unseen); place(pt); chip.classList.add('show');
      if (!still.matches) await wait(300);
    };
    const hide = async () => { chip.classList.remove('show'); cover(null); if (!still.matches) await wait(260); };
    const travel = (path, from, to, ms, id) => new Promise((done) => {
      if (still.matches) { place(point(path, to)); return done(); }
      const start = performance.now();
      const frame = (now) => {
        if (id !== run) return done();
        const raw = Math.min(1, (now - start) / ms), ease = raw < .5 ? 2 * raw * raw : 1 - Math.pow(-2 * raw + 2, 2) / 2;
        place(point(path, from + (to - from) * ease));
        raw < 1 ? requestAnimationFrame(frame) : done();
      };
      requestAnimationFrame(frame);
    });
    const now = (...keys) => { fig.querySelectorAll('.now,.talk,.think').forEach((el) => el.classList.remove('now', 'talk', 'think')); keys.forEach((k) => part(k).classList.add('now')); };
    const pulse = (k, cls) => { const el = part(k); el.classList.remove(cls); void el.getBoundingClientRect(); el.classList.add(cls); };

    // What each step does. `id` is checked after every pause so a superseded run stops quietly.
    const scenes = [null,
      async (id) => { now('person', 'pa'); await show('Request', point('pa', .2)); if (id !== run) return;
        await travel('pa', .2, .8, 900, id); if (id !== run) return; now('agent', 'ix', 'index'); pulse('ix', 'talk'); await wait(900); },
      async (id) => { now('person', 'pa', 'agent'); await show('Question', point('pa', .8)); if (id !== run) return; await travel('pa', .8, .2, 800, id); if (id !== run) return; await wait(500); if (id !== run) return;
        await show('Context', point('pa', .2)); if (id !== run) return; await travel('pa', .2, .8, 800, id); await wait(400); },
      async (id) => { now('agent'); pulse('agent', 'think'); await show('Draft', point('out', .12), true); await wait(900); },
      async (id) => { now('out', 'engine'); await show('Draft', point('out', .12), true); if (id !== run) return;
        await travel('out', .12, .88, 1100, id); if (id !== run) return; await hide(); if (id !== run) return; pulse('engine', 'think'); await wait(700); if (id !== run) return;
        now('back', 'agent'); await show('Scorecard', point('back', .12), true); if (id !== run) return; await travel('back', .12, .88, 1100, id); },
      async (id) => { now('agent'); await show('Scorecard', point('back', .88), true); if (id !== run) return; pulse('agent', 'think'); await wait(500); if (id !== run) return;
        await show('Revised', point('back', .88), true); await wait(800); },
      async (id) => { now('agent', 'pa', 'person'); await show('Answer', point('pa', .8)); if (id !== run) return; await travel('pa', .8, .2, 900, id); await wait(600); },
      async (id) => { now('person', 'pa', 'agent'); await hide(); if (id !== run) return; pulse('pa', 'talk'); await wait(still.matches ? 0 : 1000); if (id !== run) return;
        now('agent', 'diff', 'lead'); await show('Diff', point('diff', .22)); if (id !== run) return; await travel('diff', .22, .78, 900, id); await wait(600); },
    ];

    // While it plays by itself the caption is only the step's name; stepping by hand shows the full sentence.
    const paint = (n, auto) => {
      step = n;
      const rest = n === 0;
      wrap.classList.toggle('stepping', !rest);
      staged.forEach((el) => el.classList.toggle('on', rest || +el.dataset.s <= n));
      fig.querySelectorAll('.badge').forEach((b) => b.classList.toggle('now', +b.dataset.s === n));
      items.forEach((li, i) => li.classList.toggle('flow-now', i + 1 === n));
      count.textContent = rest ? 'The whole route' : 'Step ' + n + ' of ' + LAST;
      const name = !rest && items[n - 1].querySelector('strong');
      text.innerHTML = rest ? fig.dataset.rest : (auto && name ? name.outerHTML : items[n - 1].innerHTML);
      back.disabled = n <= 1 && !rest ? true : rest;
      next.textContent = rest ? 'Step through ›' : (n === LAST ? 'Finish' : 'Next ›');
      if (rest) { now(); chip.classList.remove('show'); cover(null); }
    };
    const go = async (n, auto) => { const id = ++run; paint(n, auto); if (n) await scenes[n](id); return id === run; };
    const play = async () => {
      for (let n = 1; n <= LAST; n++) { if (!(await go(n, true))) return; const id = run; await wait(still.matches ? 0 : 900); if (id !== run) return; }
      go(0);
    };

    back.addEventListener('click', () => { size(); go(Math.max(1, step - 1)); });
    next.addEventListener('click', () => { size(); go(step === LAST ? 0 : step + 1); });
    replay.addEventListener('click', play);
    paint(0); addEventListener('resize', () => { if (cap.style.minHeight) size(); });

    if (still.matches || !('IntersectionObserver' in window)) return;
    const seen = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { seen.disconnect(); play(); }
    }, { threshold: .6 });
    seen.observe(fig.querySelector('svg'));
  };

  const start = () => document.querySelectorAll('.flow-wrap').forEach(setup);
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', start) : start();
})();
