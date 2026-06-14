// storage.js — namespaced, fault-tolerant localStorage wrapper.
//
// All persistence lives under a single key. Every read and write is guarded:
// if localStorage is unavailable (private mode, blocked, quota), we fall back
// to an in-memory object so the app still teaches — it just won't persist.

const KEY = 'slh_trainer_v1';

const DEFAULT_STATE = {
  version: 1,
  theme: 'system', // 'system' | 'light' | 'dark'
  progress: {}, // { ch00: { sectionsViewed: [], interactivesDone: [], completedAt: null } }
  cards: {}, // { cardId: { interval, ease, due, lapses, reps, front, back, tags } }
  selfExplanations: {}, // { promptKey: "text" }
  labs: {}, // { labKey: ["step0", "step2"] }
  buildLog: [], // [ { date, text } ]
  streak: { lastActive: null, days: 0 },
  quizResults: {}, // { quizKey: { ... } }
};

let memoryFallback = null; // used only when localStorage throws
let storageOk = true;

function clone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

// Merge a loaded object onto the defaults so new fields always exist.
function withDefaults(obj) {
  const base = clone(DEFAULT_STATE);
  if (obj && typeof obj === 'object') {
    Object.keys(base).forEach((k) => {
      if (obj[k] !== undefined) base[k] = obj[k];
    });
  }
  return base;
}

export function isPersistent() {
  return storageOk;
}

export function load() {
  if (!storageOk && memoryFallback) return clone(memoryFallback);
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return clone(DEFAULT_STATE);
    return withDefaults(JSON.parse(raw));
  } catch (e) {
    storageOk = false;
    if (!memoryFallback) memoryFallback = clone(DEFAULT_STATE);
    return clone(memoryFallback);
  }
}

export function save(state) {
  const next = withDefaults(state);
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
    storageOk = true;
  } catch (e) {
    storageOk = false;
    memoryFallback = clone(next);
  }
  return next;
}

// Read–modify–write helper. mutator receives a working copy and may mutate it
// in place or return a replacement.
export function update(mutator) {
  const state = load();
  const result = mutator(state);
  return save(result || state);
}

export { DEFAULT_STATE, KEY };
