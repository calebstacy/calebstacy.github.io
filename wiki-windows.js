(() => {
  'use strict';
  const mobile = matchMedia('(max-width: 600px)');
  const windows = [];
  let sequence = 0;
  let layer = 100;
  const margin = 12;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function externalLink(text, href) {
    const link = element('a', '', text);
    link.href = href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    return link;
  }

  function activate(item, focus = false) {
    item.order = ++layer;
    item.panel.style.zIndex = item.order;
    if (focus) item.bar.focus({preventScroll: true});
  }

  function clamp(item) {
    if (mobile.matches) return;
    const rect = item.panel.getBoundingClientRect();
    const width = Math.min(rect.width, innerWidth - margin * 2);
    const height = Math.min(rect.height, innerHeight - margin * 2);
    const left = Math.max(margin, Math.min(rect.left, innerWidth - width - margin));
    const top = Math.max(margin, Math.min(rect.top, innerHeight - height - margin));
    item.panel.style.left = left + 'px';
    item.panel.style.top = top + 'px';
    item.panel.style.maxWidth = (innerWidth - left - margin) + 'px';
    item.panel.style.maxHeight = (innerHeight - top - margin) + 'px';
  }

  function endDrag(item) {
    if (!item.drag) return;
    const id = item.drag.id;
    item.drag = null;
    if (item.bar.hasPointerCapture(id)) item.bar.releasePointerCapture(id);
    document.documentElement.classList.remove('wiki-dragging');
  }

  function close(item, returnFocus = true) {
    item.closed = true;
    endDrag(item);
    item.abort?.abort();
    item.observer.disconnect();
    item.panel.remove();
    windows.splice(windows.indexOf(item), 1);
    if (returnFocus && item.trigger.isConnected) item.trigger.focus({preventScroll: true});
  }

  async function load(item) {
    item.abort?.abort();
    const controller = new AbortController();
    item.abort = controller;
    item.body.replaceChildren(element('p', 'wiki-window-status', 'Loading Wikipedia…'));
    item.body.setAttribute('aria-busy', 'true');
    const timeout = setTimeout(() => controller.abort(), 8000);
    const url = new URL('https://en.wikipedia.org/w/api.php');
    url.search = new URLSearchParams({action: 'query', prop: 'extracts', exintro: '1', explaintext: '1', redirects: '1', format: 'json', formatversion: '2', origin: '*', titles: item.topic});
    try {
      const response = await fetch(url, {credentials: 'omit', signal: controller.signal});
      if (!response.ok) throw new Error('Wikipedia request failed');
      const data = await response.json();
      const article = data.query?.pages?.[0];
      if (!article || article.missing || !article.extract?.trim()) throw new Error('No introduction available');
      if (item.closed || item.abort !== controller) return;
      item.heading.textContent = article.title || item.topic;
      item.body.replaceChildren(element('p', 'wiki-window-kicker', 'Introduction from Wikipedia'));
      article.extract.split(/\n\s*\n|\n/).filter(Boolean).forEach(text => item.body.append(element('p', '', text)));
      item.body.scrollTop = 0;
    } catch (error) {
      if (item.closed || item.abort !== controller) return;
      const message = element('p', 'wiki-window-status', 'The Wikipedia introduction couldn’t load. You can retry or open the full article below.');
      const retry = element('button', 'wiki-window-retry', 'Try again');
      retry.type = 'button';
      retry.addEventListener('click', () => load(item));
      item.body.replaceChildren(message, retry);
    } finally {
      clearTimeout(timeout);
      if (!item.closed && item.abort === controller) item.body.setAttribute('aria-busy', 'false');
    }
  }

  function open(trigger) {
    const topic = trigger.dataset.wikiTitle;
    if (!topic) return;
    const existing = windows.find(item => item.topic === topic);
    if (existing) {
      existing.trigger = trigger;
      activate(existing, true);
      return;
    }
    const limit = mobile.matches ? 1 : 3;
    while (windows.length >= limit) close(windows.reduce((a, b) => a.order < b.order ? a : b), false);

    const panel = element('section', 'wiki-window');
    panel.setAttribute('role', 'dialog');
    const id = 'wiki-window-title-' + (++sequence);
    panel.setAttribute('aria-labelledby', id);
    const bar = element('div', 'wiki-window-bar');
    bar.tabIndex = 0;
    bar.setAttribute('aria-label', 'Wikipedia window. On desktop, drag or use arrow keys to move. Escape closes.');
    const headingGroup = element('div', 'wiki-window-heading');
    const brand = element('span', 'wiki-window-brand', 'Wikipedia');
    const heading = element('h2', '', topic.replaceAll('_', ' '));
    heading.id = id;
    headingGroup.append(brand, heading);
    const closeButton = element('button', 'wiki-window-close', '×');
    closeButton.type = 'button';
    closeButton.setAttribute('aria-label', 'Close Wikipedia reference');
    bar.append(headingGroup, closeButton);
    const body = element('div', 'wiki-window-body');
    body.tabIndex = 0;
    body.setAttribute('role', 'region');
    body.setAttribute('aria-label', 'Wikipedia introduction');
    body.setAttribute('aria-live', 'polite');
    const footer = element('footer', 'wiki-window-footer');
    const full = externalLink('Read the full article ↗', trigger.href);
    const credit = element('small', 'wiki-window-credit', 'Wikipedia contributors · ');
    credit.append(externalLink('CC BY-SA 4.0', 'https://creativecommons.org/licenses/by-sa/4.0/'));
    footer.append(full, credit);
    panel.append(bar, body, footer);
    const item = {panel, bar, body, heading, topic, trigger, closed: false};
    const offset = windows.length * 28;
    panel.style.left = Math.max(margin, (innerWidth - 480) / 2 + offset) + 'px';
    panel.style.top = Math.max(margin, Math.min(100 + offset, innerHeight - 452)) + 'px';
    document.body.append(panel);
    windows.push(item);
    item.observer = new ResizeObserver(() => clamp(item));
    item.observer.observe(panel);
    clamp(item);
    activate(item, true);
    closeButton.addEventListener('click', () => close(item));
    panel.addEventListener('pointerdown', () => activate(item));
    panel.addEventListener('focusin', () => activate(item));
    bar.addEventListener('pointerdown', event => {
      if (mobile.matches || event.button !== 0 || event.target.closest('button,a')) return;
      const rect = panel.getBoundingClientRect();
      item.drag = {id: event.pointerId, x: event.clientX, y: event.clientY, left: rect.left, top: rect.top};
      bar.setPointerCapture(event.pointerId);
      document.documentElement.classList.add('wiki-dragging');
      event.preventDefault();
    });
    bar.addEventListener('pointermove', event => {
      if (!item.drag || item.drag.id !== event.pointerId) return;
      const rect = panel.getBoundingClientRect();
      panel.style.left = Math.max(margin, Math.min(innerWidth - rect.width - margin, item.drag.left + event.clientX - item.drag.x)) + 'px';
      panel.style.top = Math.max(margin, Math.min(innerHeight - rect.height - margin, item.drag.top + event.clientY - item.drag.y)) + 'px';
      clamp(item);
    });
    for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) bar.addEventListener(event, () => endDrag(item));
    bar.addEventListener('keydown', event => {
      if (event.target !== bar || mobile.matches) return;
      const delta = {ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, -10], ArrowDown: [0, 10]}[event.key];
      if (!delta) return;
      event.preventDefault();
      const rect = panel.getBoundingClientRect();
      panel.style.left = rect.left + delta[0] + 'px';
      panel.style.top = rect.top + delta[1] + 'px';
      clamp(item);
    });
    load(item);
  }

  document.addEventListener('click', event => {
    const trigger = event.target.closest('a.wiki-link[data-wiki-title]');
    if (!trigger || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const target = new URL(trigger.href);
    if (target.origin !== 'https://en.wikipedia.org' || !target.pathname.startsWith('/wiki/')) return;
    event.preventDefault();
    open(trigger);
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape' || !windows.length) return;
    event.preventDefault();
    close(windows.reduce((a, b) => a.order > b.order ? a : b));
  });
  addEventListener('resize', () => {
    if (mobile.matches && windows.length > 1) {
      const keep = windows.reduce((a, b) => a.order > b.order ? a : b);
      [...windows].filter(item => item !== keep).forEach(item => close(item, false));
    }
    windows.forEach(item => { endDrag(item); clamp(item); });
  });
})();
