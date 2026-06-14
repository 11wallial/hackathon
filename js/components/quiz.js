// quiz.js — retrieval quiz: MCQ with immediate feedback, and short answer
// with a revealed model answer and self-grading.

import { markInteractiveDone, mutate } from '../state.js';
import { renderMarkdown } from '../markdown.js';

export function renderQuiz(quiz, opts = {}) {
  const { chId, interactiveKey } = opts;
  const items = (quiz && quiz.quiz) || quiz || [];
  const wrap = document.createElement('div');
  wrap.className = 'quiz';

  const answered = new Set();

  items.forEach((item, qi) => {
    const block = document.createElement('div');
    block.className = 'quiz-q';
    if (item.type === 'mcq') {
      block.appendChild(mcq(item, qi, () => mark(qi)));
    } else {
      block.appendChild(shortAnswer(item, qi, () => mark(qi)));
    }
    wrap.appendChild(block);
  });

  const status = document.createElement('p');
  status.className = 'fc-progress';
  status.style.textAlign = 'left';
  wrap.appendChild(status);
  updateStatus();

  function mark(qi) {
    answered.add(qi);
    updateStatus();
    if (answered.size === items.length && chId && interactiveKey) {
      markInteractiveDone(chId, interactiveKey);
    }
  }
  function updateStatus() {
    status.textContent = `${answered.size} / ${items.length} answered`;
  }

  return wrap;
}

function mcq(item, qi, onAnswer) {
  const el = document.createElement('div');
  el.className = 'quiz-mcq';
  el.innerHTML = `<div class="quiz-stem">${renderMarkdown(item.q)}</div>`;
  const opts = document.createElement('div');
  opts.className = 'quiz-options';
  el.appendChild(opts);
  const feedback = document.createElement('div');
  feedback.className = 'quiz-feedback';
  feedback.hidden = true;
  feedback.setAttribute('role', 'status');

  item.options.forEach((opt, oi) => {
    const b = document.createElement('button');
    b.className = 'quiz-option';
    b.type = 'button';
    b.innerHTML = renderInline(opt);
    b.addEventListener('click', () => {
      if (el.dataset.done) return;
      el.dataset.done = '1';
      const correct = oi === item.answer;
      Array.from(opts.children).forEach((c, ci) => {
        c.disabled = true;
        if (ci === item.answer) c.classList.add('correct');
        else if (ci === oi) c.classList.add('wrong');
      });
      feedback.hidden = false;
      feedback.innerHTML = `<strong>${correct ? 'Correct.' : 'Not quite.'}</strong> ${renderInline(item.explain || '')}`;
      onAnswer();
    });
    opts.appendChild(b);
  });
  el.appendChild(feedback);
  return el;
}

function shortAnswer(item, qi, onAnswer) {
  const el = document.createElement('div');
  el.className = 'quiz-short';
  el.innerHTML = `<div class="quiz-stem">${renderMarkdown(item.q)}</div>`;
  const ta = document.createElement('textarea');
  ta.placeholder = 'Type your answer, then reveal the model answer to self-grade.';
  ta.setAttribute('aria-label', 'Your answer');
  el.appendChild(ta);

  const revealBtn = document.createElement('button');
  revealBtn.className = 'btn';
  revealBtn.style.marginTop = '0.7rem';
  revealBtn.textContent = 'Reveal model answer';
  el.appendChild(revealBtn);

  const modelBox = document.createElement('div');
  modelBox.className = 'model-answer';
  modelBox.hidden = true;
  el.appendChild(modelBox);

  revealBtn.addEventListener('click', () => {
    revealBtn.hidden = true;
    modelBox.hidden = false;
    modelBox.innerHTML = `
      <div class="rail-label">Model answer</div>
      ${renderMarkdown(item.modelAnswer || '')}
      <div class="self-grade-row" role="group" aria-label="Self grade">
        <button class="rate-btn" data-grade="got">Got it</button>
        <button class="rate-btn" data-grade="partial">Partial</button>
        <button class="rate-btn rate-again" data-grade="missed">Missed</button>
      </div>
      <p class="saved-note" hidden>Saved.</p>`;
    const note = modelBox.querySelector('.saved-note');
    modelBox.querySelectorAll('[data-grade]').forEach((b) => {
      b.addEventListener('click', () => {
        modelBox.querySelectorAll('[data-grade]').forEach((x) => x.classList.remove('selected'));
        b.classList.add('selected');
        b.style.borderColor = 'var(--accent)';
        note.hidden = false;
        // Record the self-grade lightly.
        mutate((s) => {
          s.quizResults['sa_' + (item.q || qi).slice(0, 40)] = { grade: b.dataset.grade, at: Date.now() };
          return s;
        });
        onAnswer();
      });
    });
  });
  return el;
}

function renderInline(s) {
  // Reuse the markdown renderer but strip the wrapping <p>.
  return renderMarkdown(s).replace(/^<p>|<\/p>\s*$/g, '');
}
