// Deterministic RNG whose entire state is one uint32 stored *inside* the game
// state, so cloning a state clones its future. Required for reproducible
// experiments and for lookahead agents that fork the world.

export function seedFrom(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

// mulberry32, inlined so it can operate on a bare field.
export function rand(state) {
  state.rng = (state.rng + 0x6d2b79f5) >>> 0;
  let t = state.rng;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

export function randInt(state, n) {
  return Math.floor(rand(state) * n);
}

export function pick(state, arr) {
  return arr[randInt(state, arr.length)];
}
