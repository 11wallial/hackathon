// review.js — the global spaced-review surface.
//
// Surfaces every card due today across all chapters, interleaved. This is the
// consolidation engine: it mixes cards rather than blocking by topic so the
// learner practises discriminating between methods.

import { interleavedDue, rateCard, RATINGS, dueCount } from './spaced.js';
import { touchStreak } from '../state.js';

export function renderReview() {
  touchStreak();
  const wrap = document.createElement('div');
  wrap.className = 'review-view';

  let queue = interleavedDue();
  let pos = 0;
  let revealed = false;
  const startCount = queue.length;

  const head = document.createElement('div');
  head.innerHTML = `
    <p class="eyebrow">Spaced review</p>
    <h1>Review</h1>`;
  wrap.appendChild(head);

  const body = document.createElement('div');
  wrap.appendChild(body);

  function draw() {
    if (queue.length === 0) {
      body.innerHTML = `
        <div class="empty-state">
          <p style="font-size:1.1rem">Nothing due right now. Nicely kept up.</p>
          <p class="text-secondary">Cards return on their own schedule. Come back tomorrow, or learn a new chapter to add more.</p>
        </div>`;
      return;
    }
    if (pos >= queue.length) {
      body.innerHTML = `
        <div class="complete-banner">
          <h3 style="margin-top:0">Review done</h3>
          <p class="text-secondary">${startCount} card${startCount === 1 ? '' : 's'} reviewed. They'll resurface when they're next due.</p>
        </div>`;
      return;
    }

    const card = queue[pos];
    body.innerHTML = `
      <p class="fc-progress" style="text-align:left">${pos + 1} of ${queue.length} due</p>
      <div class="flashcard" role="group" aria-label="Review card ${pos + 1} of ${queue.length}">
        <div class="fc-side-label">Prompt</div>
        <div class="fc-text">${escape(card.front)}</div>
        ${revealed ? `
          <div class="fc-back">
            <div class="fc-side-label">Answer</div>
            <div class="fc-text">${escape(card.back)}</div>
          </div>
          <div class="rate-row" role="group" aria-label="Rate your recall">
            ${RATINGS.map((r, ri) => `<button class="rate-btn ${ri === 0 ? 'rate-again' : ''}" data-rate="${ri}">${r}</button>`).join('')}
          </div>
        ` : `
          <div class="btn-row" style="justify-content:center">
            <button class="btn btn-primary" data-act="reveal">Show answer</button>
          </div>`}
      </div>`;

    const rb = body.querySelector('[data-act="reveal"]');
    if (rb) { rb.focus(); rb.addEventListener('click', () => { revealed = true; draw(); }); }
    body.querySelectorAll('[data-rate]').forEach((b) => {
      b.addEventListener('click', () => {
        rateCard(card.id, Number(b.dataset.rate));
        pos += 1; revealed = false; draw();
      });
    });
  }

  wrap.addEventListener('keydown', (e) => {
    if (!revealed && (e.key === ' ' || e.key === 'Enter')) {
      const rb = body.querySelector('[data-act="reveal"]');
      if (rb) { e.preventDefault(); rb.click(); }
    } else if (revealed && /^[1-4]$/.test(e.key)) {
      const rb = body.querySelector(`[data-rate="${Number(e.key) - 1}"]`);
      if (rb) { e.preventDefault(); rb.click(); }
    }
  });

  draw();
  return wrap;
}

export function reviewDueBadge() {
  return dueCount();
}

function escape(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}
