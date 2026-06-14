// rubric-check.js — Chapter 0's interactive rubric self-check.
//
// The learner rates a (hypothetical or planned) submission 1–5 on each of the
// three judging dimensions, sees a calm reflection, and the scores are saved.
// It doubles as a reusable "score this on the rubric" widget for later chapters.

import { getState, mutate, markInteractiveDone } from '../state.js';
import { renderMarkdown } from '../markdown.js';

export function renderRubricCheck(block, opts = {}) {
  const { chId, interactiveKey } = opts;
  const items = block.items || DEFAULT_ITEMS;
  const storeKey = (chId || 'rubric') + '_' + (interactiveKey || 'rubric');

  const wrap = document.createElement('div');
  wrap.className = 'rubric-check';

  if (block.intro) {
    const intro = document.createElement('div');
    intro.className = 'prose';
    intro.innerHTML = renderMarkdown(block.intro);
    wrap.appendChild(intro);
  }

  const saved = (getState().quizResults && getState().quizResults[storeKey]) || {};
  const scores = { ...saved };

  items.forEach((item, ii) => {
    const el = document.createElement('div');
    el.className = 'rubric-item';
    el.innerHTML = `
      <div style="font-family:var(--font-sans);font-weight:500">${escape(item.title)}</div>
      <div class="text-secondary" style="font-size:0.92rem">${escape(item.desc)}</div>`;
    const scale = document.createElement('div');
    scale.className = 'rubric-scale';
    scale.setAttribute('role', 'group');
    scale.setAttribute('aria-label', item.title + ' score 1 to 5');
    for (let n = 1; n <= 5; n++) {
      const b = document.createElement('button');
      b.className = 'rubric-dot' + (scores[ii] === n ? ' selected' : '');
      b.type = 'button';
      b.textContent = String(n);
      b.setAttribute('aria-pressed', scores[ii] === n ? 'true' : 'false');
      b.addEventListener('click', () => {
        scores[ii] = n;
        Array.from(scale.children).forEach((c, ci) => {
          const on = ci === n - 1;
          c.classList.toggle('selected', on);
          c.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
        persist();
        renderSummary();
      });
      scale.appendChild(b);
    }
    el.appendChild(scale);
    wrap.appendChild(el);
  });

  const summary = document.createElement('div');
  summary.className = 'callout callout-tip';
  summary.hidden = true;
  wrap.appendChild(summary);

  function persist() {
    mutate((s) => { s.quizResults[storeKey] = { ...scores }; return s; });
    if (Object.keys(scores).length === items.length && chId && interactiveKey) {
      markInteractiveDone(chId, interactiveKey);
    }
  }

  function renderSummary() {
    const vals = items.map((_, ii) => scores[ii]).filter((v) => v != null);
    if (vals.length < items.length) { summary.hidden = true; return; }
    const total = vals.reduce((a, b) => a + b, 0);
    const weakest = items[scores_lowestIndex(scores, items)];
    summary.hidden = false;
    summary.innerHTML = `
      <div class="callout-label"><span class="dot"></span>Your read</div>
      <p>Total ${total} / ${items.length * 5}. Your lowest dimension is <strong>${escape(weakest.title)}</strong> — that is where a focused hour buys the most. ${escape(block.outro || 'Remember the winning lane: modest scope, rigorous execution, beautiful presentation.')}</p>`;
  }

  renderSummary();
  return wrap;
}

function scores_lowestIndex(scores, items) {
  let lo = Infinity, idx = 0;
  items.forEach((_, ii) => {
    const v = scores[ii];
    if (v != null && v < lo) { lo = v; idx = ii; }
  });
  return idx;
}

const DEFAULT_ITEMS = [
  { title: 'Impact & innovation', desc: 'How much it would matter if it worked, and how novel.' },
  { title: 'Execution quality', desc: 'Sound methodology, controls, validation, acknowledged limitations.' },
  { title: 'Presentation & clarity', desc: 'How clearly the work, findings, and impact are communicated.' },
];

function escape(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}
