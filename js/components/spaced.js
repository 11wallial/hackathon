// spaced.js — lightweight SM-2 style scheduling for the global review deck.
//
// Each card stores: interval (days), ease (factor), due (ISO date), lapses,
// reps. Ratings map to SM-2 quality grades:
//   Again -> 0 (lapse, reset interval)
//   Hard  -> 3
//   Good  -> 4
//   Easy  -> 5
//
// New cards start due today so they enter the rotation immediately.

import { getState, mutate, todayISO } from '../state.js';

export const RATINGS = ['Again', 'Hard', 'Good', 'Easy'];

const MIN_EASE = 1.3;
const DEFAULT_EASE = 2.5;

function addDays(iso, days) {
  const d = new Date(iso + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + Math.round(days));
  return d.toISOString().slice(0, 10);
}

export function isDue(card, refISO = todayISO()) {
  if (!card || !card.due) return true;
  return card.due <= refISO;
}

// Register a deck of { front, back, tags } cards into the global store if not
// already present. A stable id is derived so re-registering is idempotent.
export function registerCards(deck, extraTags = []) {
  if (!Array.isArray(deck) || deck.length === 0) return;
  mutate((s) => {
    deck.forEach((c) => {
      const id = cardId(c);
      if (!s.cards[id]) {
        s.cards[id] = {
          interval: 0,
          ease: DEFAULT_EASE,
          due: todayISO(),
          lapses: 0,
          reps: 0,
          front: c.front,
          back: c.back,
          tags: Array.from(new Set([...(c.tags || []), ...extraTags])),
        };
      }
    });
    return s;
  });
}

export function cardId(card) {
  // Deterministic id from the front text so the same fact maps to one card.
  const basis = (card.front || '') + '|' + (card.back || '');
  let h = 0;
  for (let i = 0; i < basis.length; i++) {
    h = (h * 31 + basis.charCodeAt(i)) | 0;
  }
  return 'card_' + (h >>> 0).toString(36);
}

// Apply a rating (index into RATINGS) and reschedule the card.
export function rateCard(id, ratingIndex) {
  mutate((s) => {
    const card = s.cards[id];
    if (!card) return s;
    const today = todayISO();

    if (ratingIndex === 0) {
      // Again: lapse. Reset interval, drop ease a little, see again tomorrow.
      card.lapses += 1;
      card.ease = Math.max(MIN_EASE, card.ease - 0.2);
      card.interval = 0;
      card.due = addDays(today, 1);
    } else {
      const quality = ratingIndex === 1 ? 3 : ratingIndex === 2 ? 4 : 5;
      // SM-2 ease update.
      card.ease = Math.max(
        MIN_EASE,
        card.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
      );
      if (card.reps === 0) {
        card.interval = ratingIndex === 1 ? 1 : ratingIndex === 3 ? 4 : 1;
      } else if (card.reps === 1) {
        card.interval = ratingIndex === 1 ? 3 : 6;
      } else {
        card.interval = Math.max(1, Math.round(card.interval * card.ease));
      }
      card.reps += 1;
      card.due = addDays(today, card.interval);
    }
    return s;
  });
}

export function dueCards(refISO = todayISO()) {
  const cards = getState().cards;
  return Object.entries(cards)
    .filter(([, c]) => isDue(c, refISO))
    .map(([id, c]) => ({ id, ...c }));
}

export function dueCount(refISO = todayISO()) {
  return dueCards(refISO).length;
}

// Interleave due cards: shuffle deterministically by id so the order mixes
// chapters and families rather than blocking by topic.
export function interleavedDue(refISO = todayISO()) {
  return dueCards(refISO).sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
}
