// self-explain.js — a saved textarea for elaboration / self-explanation.
//
// The learner types an explanation in their own words. It is saved to
// localStorage under a stable key and can be shown back in later chapters.

import { getState, mutate, markInteractiveDone } from '../state.js';

export function renderSelfExplain(block, opts = {}) {
  const { chId, promptKey } = opts;
  const key = promptKey || (chId ? chId + '_' + slug(block.prompt) : slug(block.prompt));

  const wrap = document.createElement('div');
  wrap.className = 'self-explain card';

  const label = document.createElement('div');
  label.className = 'rail-label';
  label.textContent = 'Say it back';
  wrap.appendChild(label);

  const prompt = document.createElement('p');
  prompt.innerHTML = escape(block.prompt);
  wrap.appendChild(prompt);

  const ta = document.createElement('textarea');
  ta.setAttribute('aria-label', 'Your explanation');
  ta.value = (getState().selfExplanations && getState().selfExplanations[key]) || '';
  wrap.appendChild(ta);

  const note = document.createElement('p');
  note.className = 'saved-note';
  note.hidden = true;
  note.textContent = 'Saved.';
  wrap.appendChild(note);

  let timer = null;
  ta.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      mutate((s) => { s.selfExplanations[key] = ta.value; return s; });
      note.hidden = false;
      if (ta.value.trim().length > 12 && chId) markInteractiveDone(chId, key);
    }, 500);
  });

  return wrap;
}

function slug(s) {
  return String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').slice(0, 32);
}
function escape(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}
