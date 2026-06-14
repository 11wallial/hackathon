// state.js — a tiny pub/sub store layered over the storage wrapper.
//
// Components subscribe to be notified when persisted state changes (e.g. a card
// is rescheduled, a section is marked viewed). The store is the single source
// of truth; reads go through getState(), writes through mutate().

import { load, save, isPersistent } from './storage.js';

let current = load();
const listeners = new Set();

export function getState() {
  return current;
}

export function isPersistent_() {
  return isPersistent();
}

// Apply a mutation, persist, and notify subscribers.
export function mutate(mutator) {
  const result = mutator(current);
  current = save(result || current);
  notify();
  return current;
}

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function notify() {
  listeners.forEach((fn) => {
    try { fn(current); } catch (e) { /* a bad listener should not break others */ }
  });
}

// ---- Convenience helpers used across components -----------------------

export function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

// Bump the activity streak: increments on a new day, resets if a day was missed.
export function touchStreak() {
  mutate((s) => {
    const today = todayISO();
    const last = s.streak.lastActive;
    if (last === today) return s;
    if (!last) {
      s.streak = { lastActive: today, days: 1 };
      return s;
    }
    const diff = daysBetween(last, today);
    s.streak = {
      lastActive: today,
      days: diff === 1 ? s.streak.days + 1 : 1,
    };
    return s;
  });
}

function daysBetween(aISO, bISO) {
  const a = new Date(aISO + 'T00:00:00Z');
  const b = new Date(bISO + 'T00:00:00Z');
  return Math.round((b - a) / 86400000);
}

// ---- Progress helpers -------------------------------------------------

export function ensureProgress(chId) {
  if (!current.progress[chId]) {
    mutate((s) => {
      if (!s.progress[chId]) {
        s.progress[chId] = { sectionsViewed: [], interactivesDone: [], completedAt: null };
      }
      return s;
    });
  }
  return current.progress[chId];
}

export function markSectionViewed(chId, sectionId) {
  mutate((s) => {
    const p = s.progress[chId] || (s.progress[chId] = { sectionsViewed: [], interactivesDone: [], completedAt: null });
    if (!p.sectionsViewed.includes(sectionId)) p.sectionsViewed.push(sectionId);
    return s;
  });
}

export function markInteractiveDone(chId, key) {
  mutate((s) => {
    const p = s.progress[chId] || (s.progress[chId] = { sectionsViewed: [], interactivesDone: [], completedAt: null });
    if (!p.interactivesDone.includes(key)) p.interactivesDone.push(key);
    return s;
  });
}

export function setChapterComplete(chId) {
  mutate((s) => {
    const p = s.progress[chId] || (s.progress[chId] = { sectionsViewed: [], interactivesDone: [], completedAt: null });
    if (!p.completedAt) p.completedAt = todayISO();
    return s;
  });
}
