// checklist.js — checkable steps (labs and setup lists) with saved state.

import { getState, mutate, markInteractiveDone } from '../state.js';
import { renderMarkdown } from '../markdown.js';

// `lab` may be a full lab object { title, steps, successCriterion } or a bare
// { steps } checklist. `labKey` namespaces the saved state.
export function renderChecklist(lab, opts = {}) {
  const { chId, labKey } = opts;
  const key = labKey || (chId ? chId + '_lab' : 'lab');
  const steps = lab.steps || [];

  const wrap = document.createElement('div');
  wrap.className = 'lab card';

  if (lab.title) {
    const h = document.createElement('h3');
    h.style.marginTop = '0';
    h.textContent = lab.title;
    wrap.appendChild(h);
  }

  const list = document.createElement('ul');
  list.className = 'checklist';
  wrap.appendChild(list);

  function savedSet() {
    return new Set((getState().labs && getState().labs[key]) || []);
  }

  steps.forEach((step, si) => {
    const id = 'step' + si;
    const li = document.createElement('li');
    const label = document.createElement('label');
    label.className = 'check-item';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    const checked = savedSet().has(id);
    cb.checked = checked;
    if (checked) label.classList.add('done');
    const text = document.createElement('span');
    text.className = 'check-text';
    text.innerHTML = renderInline(step.text || step);
    label.appendChild(cb);
    label.appendChild(text);
    li.appendChild(label);
    list.appendChild(li);

    cb.addEventListener('change', () => {
      mutate((s) => {
        if (!s.labs[key]) s.labs[key] = [];
        const set = new Set(s.labs[key]);
        if (cb.checked) set.add(id); else set.delete(id);
        s.labs[key] = Array.from(set);
        return s;
      });
      label.classList.toggle('done', cb.checked);
      maybeComplete();
    });
  });

  if (lab.successCriterion) {
    const sc = document.createElement('div');
    sc.className = 'success-criterion';
    sc.innerHTML = `<strong>Done when:</strong> ${renderInline(lab.successCriterion)}`;
    wrap.appendChild(sc);
  }

  function maybeComplete() {
    const set = savedSet();
    if (steps.length && steps.every((_, si) => set.has('step' + si)) && chId) {
      markInteractiveDone(chId, key);
    }
  }
  maybeComplete();

  return wrap;
}

function renderInline(s) {
  return renderMarkdown(s).replace(/^<p>|<\/p>\s*$/g, '');
}
