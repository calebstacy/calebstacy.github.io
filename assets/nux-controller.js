(() => {
  'use strict';

  /* [data-play] lists how long to hold each step, in ms, slow enough to read on a phone.
     Inside it, an element joins at data-at and leaves at data-off.
     .play-type fills in letter by letter on its step.

     Every figure is painted at its last step from the start, so a reader scrolling
     past always sees the After state. When one scrolls into view it plays once,
     squeezed into about AUTO ms, and if it leaves view mid-play it jumps to the end.
     Replay plays it at full pace. Reduced motion gets the last step and no playback. */
  const KEY = 14;
  const AUTO = 6500;
  const FLOOR = 650;

  const still = window.matchMedia('(prefers-reduced-motion: reduce)');

  const setup = (fig) => {
    const stage = fig.querySelector('.play-stage');
    const replay = fig.querySelector('.check-replay');
    const holds = fig.dataset.play.split(',').map(Number);
    const last = holds.length - 1;
    const total = holds.reduce((a, b) => a + b, 0);
    const quick = Math.min(1, AUTO / total);

    /* screen readers get the end state, not the playback */
    const quiet = stage.cloneNode(true);
    quiet.className = 'check-quiet';
    quiet.querySelectorAll('svg').forEach((svg) => {
      const said = document.createElement(svg.closest('p') ? 'span' : 'p');
      said.textContent = svg.getAttribute('aria-label') || '';
      svg.replaceWith(said);
    });
    fig.prepend(quiet);
    stage.setAttribute('aria-hidden', 'true');

    /* one span per letter, so a bubble keeps its final size while it fills in */
    const typed = [...stage.querySelectorAll('.play-type')].map((el) => {
      const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      nodes.forEach((node) => {
        const letters = document.createDocumentFragment();
        for (const ch of node.data) {
          const key = document.createElement('span');
          key.className = 'check-key';
          key.textContent = ch;
          letters.append(key);
        }
        node.replaceWith(letters);
      });
      return { step: Number(el.dataset.at), keys: [...el.querySelectorAll('.check-key')] };
    });

    const bits = [...stage.querySelectorAll('[data-at], [data-off]')];
    const show = (step) => {
      fig.dataset.step = step;
      bits.forEach((el) => {
        el.classList.toggle('is-on', el.dataset.at !== undefined && Number(el.dataset.at) <= step);
        el.classList.toggle('is-off', el.dataset.off !== undefined && Number(el.dataset.off) <= step);
      });
    };

    let run = 0;
    let playing = false;

    /* the last step, painted at once with nothing moving */
    const settle = () => {
      run += 1;
      playing = false;
      fig.classList.add('is-live', 'is-settled');
      typed.forEach(({ keys }) => keys.forEach((key) => key.classList.add('is-on')));
      show(last);
      replay.hidden = still.matches;
      replay.classList.remove('is-waiting');
    };

    const play = async (pace) => {
      const me = ++run;
      playing = true;
      const wait = (ms) => new Promise((done, stop) => {
        window.setTimeout(() => (me === run ? done() : stop()), ms);
      });
      const fill = (keys) => new Promise((done, stop) => {
        const from = performance.now();
        const per = Math.max(6, KEY * pace);
        const tick = (now) => {
          if (me !== run) { stop(); return; }
          const shown = Math.floor((now - from) / per);
          keys.forEach((key, i) => key.classList.toggle('is-on', i < shown));
          if (shown < keys.length) window.requestAnimationFrame(tick);
          else done();
        };
        window.requestAnimationFrame(tick);
      });

      /* the figure's own CSS motion runs at the same pace as the steps */
      const speed = () => {
        if (pace === 1 || !fig.getAnimations) return;
        fig.getAnimations({ subtree: true }).forEach((a) => {
          const loops = a.effect && a.effect.getTiming().iterations;
          if (loops !== Infinity) a.playbackRate = 1 / pace;
        });
      };

      /* jump to step 0 without a blank frame, then let things move again */
      fig.classList.add('is-live', 'is-settled');
      typed.forEach(({ keys }) => keys.forEach((key) => key.classList.remove('is-on')));
      show(0);
      void fig.offsetWidth;
      fig.classList.remove('is-settled');
      replay.hidden = false;
      replay.classList.add('is-waiting');

      try {
        for (let step = 0; step <= last; step += 1) {
          if (step) show(step);
          speed();
          for (const line of typed) {
            if (line.step === step) await fill(line.keys);
          }
          await wait(Math.max(pace < 1 ? FLOOR : 0, holds[step] * pace));
        }
        playing = false;
        replay.classList.remove('is-waiting');
      } catch { /* a newer run, or a settle, took over */ }
    };

    settle();
    replay.addEventListener('click', () => play(1));
    /* no autoplay: step 0 is often near-empty, so a reader scrolling in saw a blank box.
       The end state stays up; Replay walks through it, and scrolling away settles it. */
    if (still.matches || !('IntersectionObserver' in window)) return;
    new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting && playing) settle();
    }).observe(fig);
  };

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-play]').forEach(setup);
  });
})();
