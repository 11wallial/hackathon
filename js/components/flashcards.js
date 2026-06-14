// flashcards.js — recall-first flashcard deck.
//
// Front is shown; the learner attempts recall, reveals the back, then rates
// (Again/Hard/Good/Easy). Rating updates the card's spaced schedule. Cards are
// registered into the global deck so they also resurface in /review.

import { registerCards, cardId, rateCard, RATINGS } from './spaced.js';
import { markInteractiveDone } from '../state.js';

// Render an inline, in-chapter deck. `onDone` fires when the learner finishes.
export function renderFlashcards(deck, opts = {}) {
  const { chId, interactiveKey, extraTags = [] } = opts;
  registerCards(deck, extraTags);

  const wrap = document.createElement('div');
  wrap.className = 'flashdeck';

  let index = 0;
  let revealed = false;

  function draw() {
    if (index >= deck.length) {
      wrap.innerHTML = `
        <div class="flashcard fc-done">
          <div class="fc-text">Deck complete.</div>
          <p class="text-secondary">These cards now live in your review deck and will resurface over the coming days.</p>
          <div class="btn-row" style="justify-content:center">
            <button class="btn" data-act="restart">Run again</button>
          </div>
        </div>`;
      wrap.querySelector('[data-act="restart"]').addEventListener('click', () => {
        index = 0; revealed = false; draw();
      });
      if (chId && interactiveKey) markInteractiveDone(chId, interactiveKey);
      return;
    }

    const card = deck[index];
    wrap.innerHTML = `
      <div class="flashcard" role="group" aria-label="Flashcard ${index + 1} of ${deck.length}">
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
          </div>
        `}
      </div>
      <div class="fc-progress">${index + 1} / ${deck.length}</div>`;

    const revealBtn = wrap.querySelector('[data-act="reveal"]');
    if (revealBtn) {
      revealBtn.focus();
      revealBtn.addEventListener('click', () => { revealed = true; draw(); });
    }
    wrap.querySelectorAll('[data-rate]').forEach((b) => {
      b.addEventListener('click', () => {
        rateCard(cardId(card), Number(b.dataset.rate));
        index += 1; revealed = false; draw();
      });
    });
  }

  // Keyboard: space/enter reveals; 1-4 rate.
  wrap.addEventListener('keydown', (e) => {
    if (!revealed && (e.key === ' ' || e.key === 'Enter')) {
      const rb = wrap.querySelector('[data-act="reveal"]');
      if (rb) { e.preventDefault(); rb.click(); }
    } else if (revealed && /^[1-4]$/.test(e.key)) {
      const rb = wrap.querySelector(`[data-rate="${Number(e.key) - 1}"]`);
      if (rb) { e.preventDefault(); rb.click(); }
    }
  });

  draw();
  return wrap;
}

function escape(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}
