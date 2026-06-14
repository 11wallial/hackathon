// pages/glossary.js — global, searchable glossary.
//
// Populated from the flashcards the learner has encountered (registered into the
// global deck). Cards tagged "term" are treated as vocabulary; until any exist
// we show all cards so the page is never empty after Chapter 0.

import { getState } from '../js/state.js';

export function renderGlossary() {
  const wrap = document.createElement('div');
  const head = document.createElement('header');
  head.innerHTML = `<p class="eyebrow">Reference</p><h1>Glossary</h1>
    <p class="lede">Terms you've met, in one place. Grows as you work through chapters.</p>`;
  wrap.appendChild(head);

  const cards = Object.values(getState().cards || {});
  const terms = cards.filter((c) => (c.tags || []).includes('term'));
  const source = terms.length ? terms : cards;

  if (source.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.innerHTML = '<p>No terms yet. Work through a chapter and its flashcards will land here.</p>';
    wrap.appendChild(empty);
    return wrap;
  }

  const search = document.createElement('input');
  search.className = 'glossary-search';
  search.type = 'search';
  search.placeholder = `Search ${source.length} term${source.length === 1 ? '' : 's'}…`;
  search.setAttribute('aria-label', 'Search glossary');
  wrap.appendChild(search);

  const dl = document.createElement('dl');
  wrap.appendChild(dl);

  const sorted = source.slice().sort((a, b) => String(a.front).localeCompare(String(b.front)));

  function draw(filter) {
    const q = (filter || '').trim().toLowerCase();
    dl.innerHTML = '';
    const matches = sorted.filter((c) =>
      !q || String(c.front).toLowerCase().includes(q) || String(c.back).toLowerCase().includes(q));
    if (matches.length === 0) {
      dl.innerHTML = '<p class="text-secondary">No matches.</p>';
      return;
    }
    matches.forEach((c) => {
      const row = document.createElement('div');
      row.className = 'glossary-term';
      row.innerHTML = `<dt>${escape(c.front)}</dt><dd>${escape(c.back)}</dd>`;
      dl.appendChild(row);
    });
  }

  search.addEventListener('input', () => draw(search.value));
  draw('');
  return wrap;
}

function escape(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}
