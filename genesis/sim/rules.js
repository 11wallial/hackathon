// The rules engine. Pure-ish: every function takes a state and mutates it, and
// `cloneState` gives you a private copy (rng included) so agents can look ahead.
//
// Presentation is not allowed in this file. If the UI needs to know something,
// it reads `state` or the event log.

import { rand, randInt } from './rng.js';
import { makeConfig } from './config.js';
import { ARCHETYPES, ENCOUNTERS } from './content.js';

export const mod = (n, m) => ((n % m) + m) % m;

export function ringDist(a, b, size) {
  const d = Math.abs(a - b) % size;
  return Math.min(d, size - d);
}

/** Shortest direction (+1 / -1) from `a` toward `b`; 0 if same node. */
export function towards(a, b, size) {
  if (a === b) return 0;
  const fwd = mod(b - a, size);
  const back = mod(a - b, size);
  if (fwd === back) return 1; // exactly opposite: pick a side deterministically
  return fwd < back ? 1 : -1;
}

export function unitAt(s, node) {
  for (const u of s.units) if (u.alive && u.node === node) return u;
  return null;
}
export function getPlayer(s) {
  for (const u of s.units) if (u.team === 'player') return u;
  return null;
}
export function enemies(s) {
  return s.units.filter((u) => u.alive && u.team === 'enemy');
}
export function isHot(s, u) {
  return s.config.hotRule && u.charge >= Math.ceil(u.capacity * s.config.hotThreshold);
}

function emit(s, ev) {
  if (!s.events) return;
  ev.turn = s.turn;
  s.events.push(ev);
  if (s.events.length > 4000) s.events.shift();
}

function blankStats() {
  return {
    actions: { step: 0, shove: 0, end: 0 },
    shoveAmounts: {},
    shoveByBand: {},
    stepChoices: 0,
    stepTowardMotes: 0,
    chargeBandTurns: [0, 0, 0, 0],
    nearOverloadTurns: 0,
    playerTurns: 0,
    chargeToEnemies: 0,
    chargeShovedTotal: 0,
    detonations: 0,
    enemyDetonations: 0,
    selfDetonations: 0,
    deliberateSelfDetonations: 0,
    chains: {},
    maxChain: 0,
    baitKills: 0,
    tipKills: 0,
    starved: 0,
    motesAtEnd: 0,
    deathCause: null,
    killCause: {},
    conservationViolations: 0,
    cascadeOverflow: 0,
  };
}

// ---------------------------------------------------------------------------
// Construction
// ---------------------------------------------------------------------------

export function createEncounter({
  encounter = 'probe',
  config = {},
  seed = 1,
  record = true,
} = {}) {
  const cfg = makeConfig(config);
  const def = typeof encounter === 'string' ? ENCOUNTERS[encounter] : encounter;
  if (!def) throw new Error(`unknown encounter: ${encounter}`);

  const s = {
    config: cfg,
    encounter: def,
    rng: seed >>> 0,
    turn: 1,
    actionsLeft: cfg.actionsPerTurn,
    ring: new Array(cfg.ringSize).fill(0),
    ringPlayer: new Array(cfg.ringSize).fill(0),
    units: [],
    nextId: 1,
    wavesSpawned: [],
    result: null,
    injected: 0,
    events: record ? [] : null,
    stats: record ? blankStats() : null,
  };

  spawnUnit(s, 'player', 0, 'player');
  scatterStartCharge(s);
  processWaves(s);
  s.baseline = totalEnergy(s);
  return s;
}

// The field arrives already charged, and every wave charges it further.
// Everything here must be walked to, which makes supply a positioning problem.
function scatterStartCharge(s) {
  scatterCharge(s, s.config.startCharge | 0);
}

function scatterCharge(s, amount) {
  let left = amount | 0;
  if (left <= 0) return;
  const R = s.config.ringSize;
  while (left > 0) {
    const n = randInt(s, R);
    if (unitAt(s, n)) continue;
    const chunk = Math.min(left, 1 + randInt(s, 3));
    s.ring[n] += chunk;
    s.injected += chunk;
    left -= chunk;
  }
}

function spawnUnit(s, kind, node, team, chargeOverride) {
  const a = ARCHETYPES[kind];
  const u = {
    id: s.nextId++,
    kind,
    team,
    node,
    charge: chargeOverride != null ? chargeOverride : a.charge,
    capacity: Math.max(1, Math.round(a.capacity * s.config.capacityScale)),
    throughput: team === 'enemy'
      ? Math.max(1, Math.round(a.throughput * s.config.enemyThroughputScale))
      : a.throughput,
    ai: a.ai,
    moveEvery: a.moveEvery,
    alive: true,
    killedByBait: false,
    floorFed: 0,
    lastCause: 'spawn',
    staggeredTurn: -1,
    zeroSince: -1,
  };
  s.units.push(u);
  s.injected += u.charge;
  emit(s, { type: 'spawn', id: u.id, kind, node, charge: u.charge });
  return u;
}

function freeNodeAwayFromPlayer(s, minDist) {
  const p = getPlayer(s);
  const cand = [];
  for (let n = 0; n < s.config.ringSize; n++) {
    if (unitAt(s, n)) continue;
    if (p && ringDist(n, p.node, s.config.ringSize) < minDist) continue;
    cand.push(n);
  }
  if (!cand.length) {
    for (let n = 0; n < s.config.ringSize; n++) if (!unitAt(s, n)) cand.push(n);
  }
  if (!cand.length) return -1;
  return cand[randInt(s, cand.length)];
}

function processWaves(s) {
  s.encounter.waves.forEach((w, i) => {
    if (s.wavesSpawned.includes(i) || w.turn > s.turn) return;
    s.wavesSpawned.push(i);
    if (w.charge) scatterCharge(s, w.charge);
    for (const spec of w.units) {
      const node = spec.node != null ? spec.node : freeNodeAwayFromPlayer(s, 3);
      if (node < 0) continue;
      spawnUnit(s, spec.kind, node, 'enemy', spec.charge);
    }
  });
}

function wavesPending(s) {
  return s.encounter.waves.some((_, i) => !s.wavesSpawned.includes(i));
}

// ---------------------------------------------------------------------------
// Charge movement, overload, detonation
// ---------------------------------------------------------------------------

export function totalEnergy(s) {
  let t = 0;
  for (const u of s.units) if (u.alive) t += u.charge;
  for (const c of s.ring) t += c;
  return t;
}

function giveCharge(s, u, amount, fromBait = false, cause = 'other') {
  if (amount <= 0) return;
  u.charge += amount;
  u.lastCause = cause;
  // Strict attribution: a bait kill is one where the *same* absorption of
  // player-placed motes took the unit over capacity. Merely having eaten a
  // player mote at some point in the past does not count.
  if (fromBait && u.charge > u.capacity) u.killedByBait = true;
  emit(s, { type: 'absorb', id: u.id, amount, charge: u.charge, bait: fromBait });
}

// Single entry point for taking charge off the floor, so the cap rule and the
// bait bookkeeping cannot drift apart between the four call sites.
function absorbFrom(s, u, node) {
  const available = s.ring[node];
  if (available <= 0) return;
  let take = available;
  if (s.config.absorbCap) take = Math.min(available, Math.max(0, u.capacity - u.charge));
  if (take <= 0) return;
  const bait = u.team === 'enemy' && s.ringPlayer[node] > 0;
  s.ring[node] -= take;
  s.ringPlayer[node] = Math.max(0, s.ringPlayer[node] - Math.min(s.ringPlayer[node], take));
  u.floorFed = (u.floorFed || 0) + take;
  giveCharge(s, u, take, bait, 'floor');
}

function dropMotes(s, node, amount, playerPlaced) {
  if (amount <= 0) return;
  s.ring[node] += amount;
  if (playerPlaced) s.ringPlayer[node] += amount;
  emit(s, { type: 'motes', node, amount, total: s.ring[node] });
}

/**
 * Resolve every unit currently over capacity, including chains, and report how
 * many detonations happened in this cascade. Conservation is preserved exactly:
 * the remainder of the integer split is returned to the centre node.
 */
function resolveOverloads(s) {
  let chain = 0;
  for (;;) {
    const u = s.units.find((x) => x.alive && x.charge > x.capacity);
    if (!u) break;
    if (++chain > s.config.maxCascade) {
      if (s.stats) s.stats.cascadeOverflow++;
      break;
    }
    detonate(s, u);
  }
  if (chain > 0 && s.stats) {
    s.stats.chains[chain] = (s.stats.chains[chain] || 0) + 1;
    s.stats.maxChain = Math.max(s.stats.maxChain, chain);
  }
  return chain;
}

function detonate(s, u) {
  const payload = u.charge;
  const R = s.config.ringSize;
  const isPlayer = u.team === 'player';
  const burnout = isPlayer && s.config.overloadMode === 'burnout';

  u.charge = 0;
  if (burnout) {
    u.capacity -= s.config.burnoutCapacityLoss;
    if (u.capacity <= 0) u.alive = false;
  } else {
    u.alive = false;
  }

  if (s.stats) {
    s.stats.detonations++;
    if (isPlayer) s.stats.selfDetonations++;
    else {
      s.stats.enemyDetonations++;
      if (u.killedByBait) s.stats.baitKills++;
    }
    if (u.lastCause === 'shove-player' && u.floorFed > 0) s.stats.tipKills++;
    const c = u.lastCause || 'other';
    s.stats.killCause[c] = (s.stats.killCause[c] || 0) + 1;
  }
  emit(s, {
    type: 'detonate', id: u.id, kind: u.kind, node: u.node, payload,
    survived: burnout && u.alive,
  });

  // Spread the payload over the blast footprint, centre node keeps the change.
  const r = s.config.detonationRadius;
  const outward = s.config.blastSplit === 'outward' && r >= 1;
  const nodes = [];
  for (let d = -r; d <= r; d++) {
    if (outward && d === 0) continue;
    nodes.push(mod(u.node + d, R));
  }
  const centre = mod(u.node, R);
  const share = Math.floor(payload / nodes.length);
  const remainder = payload - share * nodes.length;
  if (outward && remainder > 0 && !nodes.includes(centre)) nodes.push(centre);

  nodes.forEach((n) => {
    const amount = (outward && n === centre ? 0 : share) + (n === centre ? remainder : 0);
    if (amount <= 0) return;
    const occupant = unitAt(s, n);
    // The detonating unit itself may still be standing there (burnout): it does
    // not absorb its own blast, that would be a free refill.
    if (occupant && occupant !== u) giveCharge(s, occupant, amount, false, 'blast');
    else dropMotes(s, n, amount, false);
  });
}

// ---------------------------------------------------------------------------
// Player actions
// ---------------------------------------------------------------------------

export function legalActions(s) {
  if (s.result) return [];
  const p = getPlayer(s);
  if (!p || !p.alive) return [];
  const acts = [{ type: 'end' }];
  if (s.actionsLeft <= 0) return acts;

  for (const dir of [-1, 1]) {
    const n = mod(p.node + dir, s.config.ringSize);
    if (!unitAt(s, n)) acts.push({ type: 'step', dir });
  }
  const staggered = s.config.staggerOnShove && p.staggeredTurn === s.turn;
  const maxAmt = staggered ? 0 : Math.min(p.throughput, p.charge);
  for (const dir of [-1, 0, 1]) {
    for (let a = 1; a <= maxAmt; a++) acts.push({ type: 'shove', dir, amount: a });
  }
  return acts;
}

function chargeBand(p) {
  const f = p.charge / Math.max(1, p.capacity);
  return Math.min(3, Math.floor(f * 4));
}

export function applyAction(s, action) {
  if (s.result) return s;
  const p = getPlayer(s);
  const R = s.config.ringSize;

  if (action.type === 'end') {
    if (s.stats) s.stats.actions.end++;
    enemyPhase(s);
    return s;
  }
  if (s.actionsLeft <= 0) return s;

  if (action.type === 'step') {
    const n = mod(p.node + action.dir, R);
    if (unitAt(s, n)) return s;
    if (s.stats) {
      s.stats.actions.step++;
      const l = s.ring[mod(p.node - 1, R)];
      const r = s.ring[mod(p.node + 1, R)];
      if (l !== r) {
        s.stats.stepChoices++;
        const bigger = l > r ? -1 : 1;
        if (action.dir === bigger) s.stats.stepTowardMotes++;
      }
    }
    p.node = n;
    emit(s, { type: 'step', id: p.id, node: n, dir: action.dir });
    if (s.config.absorbOnStep) absorbFrom(s, p, n);
  } else if (action.type === 'shove') {
    const amount = Math.min(action.amount, p.charge, p.throughput);
    if (amount <= 0) return s;
    const n = mod(p.node + action.dir, R);
    const target = action.dir === 0 ? null : unitAt(s, n);
    p.charge -= amount;
    if (s.stats) {
      const band = chargeBand(p);
      s.stats.actions.shove++;
      s.stats.shoveAmounts[amount] = (s.stats.shoveAmounts[amount] || 0) + 1;
      s.stats.shoveByBand[band] = s.stats.shoveByBand[band] || {};
      s.stats.shoveByBand[band][amount] = (s.stats.shoveByBand[band][amount] || 0) + 1;
      s.stats.chargeShovedTotal += amount;
      if (target) s.stats.chargeToEnemies += amount;
    }
    emit(s, { type: 'shove', id: p.id, dir: action.dir, amount, target: target ? target.id : null });
    if (target) {
      const spill = Math.floor(amount * s.config.spillFraction);
      if (spill > 0) dropMotes(s, n, spill, true);
      giveCharge(s, target, amount - spill, false, 'shove-player');
      if (s.config.staggerOnShove) target.staggeredTurn = s.turn + 1;
      if (target.alive) displace(s, target, action.dir);
    } else dropMotes(s, n, amount, true);
  } else {
    return s;
  }

  s.actionsLeft--;
  resolveOverloads(s);
  checkEnd(s);
  return s;
}

// ---------------------------------------------------------------------------
// Enemy phase
// ---------------------------------------------------------------------------

function enemyPhase(s) {
  const p = getPlayer(s);
  if (s.stats && p && p.alive) {
    s.stats.playerTurns++;
    s.stats.chargeBandTurns[chargeBand(p)]++;
    if (p.charge >= p.capacity * 0.9) s.stats.nearOverloadTurns++;
  }

  for (const u of s.units.slice()) {
    if (!u.alive || u.team !== 'enemy' || s.result) continue;
    const acts = isHot(s, u) ? 2 : 1;
    for (let i = 0; i < acts && u.alive && !s.result; i++) {
      if (u.ai === 'chase') aiChase(s, u);
      else if (u.ai === 'scavenge') aiScavenge(s, u);
      resolveOverloads(s);
      checkEnd(s);
    }
  }

  if (s.config.settleMotes) settle(s);
  if (s.config.dissolveAfter >= 0) dissolveSpent(s);

  s.turn++;
  processWaves(s);
  s.actionsLeft = playerActionsFor(s);
  if (s.turn > s.config.turnLimit && !s.result) finish(s, 'timeout');
  checkEnd(s);
}

// A unit that has held nothing for long enough stops existing. Conservation is
// untouched — it has no charge to redistribute — and the ring gets its node back.
function dissolveSpent(s) {
  for (const u of s.units) {
    if (!u.alive || u.team === 'player') continue;
    if (u.charge > 0) { u.zeroSince = -1; continue; }
    if (u.zeroSince < 0) u.zeroSince = s.turn;
    if (s.turn - u.zeroSince >= s.config.dissolveAfter) {
      u.alive = false;
      if (s.stats) {
        s.stats.starved++;
        s.stats.killCause.starved = (s.stats.killCause.starved || 0) + 1;
      }
      emit(s, { type: 'dissolve', id: u.id, kind: u.kind, node: u.node });
    }
  }
  checkEnd(s);
}

// End-of-round settling: charge left under a body is absorbed by that body.
// Removes the free vent and makes standing in your own dump a decision.
function settle(s) {
  for (const u of s.units.slice()) {
    if (!u.alive || s.ring[u.node] <= 0) continue;
    absorbFrom(s, u, u.node);
    resolveOverloads(s);
    checkEnd(s);
    if (s.result) return;
  }
}

function moveUnit(s, u, dir) {
  const R = s.config.ringSize;
  const n = mod(u.node + dir, R);
  if (unitAt(s, n)) return false;
  u.node = n;
  emit(s, { type: 'step', id: u.id, node: n, dir });
  if (s.config.absorbOnStep) absorbFrom(s, u, n);
  return true;
}

function enemyShove(s, u, dir) {
  if (s.config.staggerOnShove && u.staggeredTurn === s.turn) return false;
  const R = s.config.ringSize;
  const amount = Math.min(u.throughput, u.charge);
  if (amount <= 0) return false;
  const n = mod(u.node + dir, R);
  const target = unitAt(s, n);
  u.charge -= amount;
  emit(s, { type: 'shove', id: u.id, dir, amount, target: target ? target.id : null });
  if (target) {
    const spill = Math.floor(amount * s.config.spillFraction);
    if (spill > 0) dropMotes(s, n, spill, false);
    giveCharge(s, target, amount - spill, false, 'shove-enemy');
    if (s.config.staggerOnShove) target.staggeredTurn = s.turn + 1;
    if (target.alive) displace(s, target, dir);
  } else dropMotes(s, n, amount, false);
  return true;
}

// A shoved body slides one node further along. It absorbs whatever is on the
// tile it lands on, which is why herding something onto a pile works.
function displace(s, u, dir) {
  if (!s.config.shovePushes || dir === 0) return;
  const R = s.config.ringSize;
  const n = mod(u.node + dir, R);
  if (unitAt(s, n)) return; // packed bodies brace each other
  u.node = n;
  emit(s, { type: 'displace', id: u.id, node: n, dir });
  if (s.config.absorbOnStep) absorbFrom(s, u, n);
}

function canMoveThisTurn(s, u) {
  return u.moveEvery <= 1 || s.turn % u.moveEvery === 0;
}

function aiChase(s, u) {
  const p = getPlayer(s);
  if (!p || !p.alive) return;
  const R = s.config.ringSize;
  // Hungry: an empty chaser is harmless, so it goes shopping. This is what
  // keeps charge circulating instead of settling into inert bodies, and it is
  // what makes a pile on the floor a genuine contest rather than a gift.
  if (s.config.hungryEnemies && u.charge < u.throughput) {
    for (let n = 0; n < R; n++) {
      if (s.ring[n] > 0) { aiScavenge(s, u); return; }
    }
  }
  if (ringDist(u.node, p.node, R) === 1) {
    const dir = towards(u.node, p.node, R);
    if (u.charge > 0 && enemyShove(s, u, dir)) return;
    return; // spent or staggered chasers become walls: legible, and positional
  }
  if (!canMoveThisTurn(s, u)) return;
  const dir = towards(u.node, p.node, R);
  if (!moveUnit(s, u, dir)) moveUnit(s, u, -dir);
}

function aiScavenge(s, u) {
  const R = s.config.ringSize;
  const p = getPlayer(s);

  if (s.ring[u.node] > 0) {
    absorbFrom(s, u, u.node);
    return;
  }
  let best = -1;
  let bestScore = 0;
  for (let n = 0; n < R; n++) {
    if (s.ring[n] <= 0) continue;
    // Prefer big piles, break ties by closeness. Deliberately simple so a
    // player can predict it: this is the mechanism behind bait.
    const score = s.ring[n] * 10 - ringDist(u.node, n, R);
    if (score > bestScore) { bestScore = score; best = n; }
  }
  if (best >= 0) {
    if (!canMoveThisTurn(s, u)) return;
    const dir = towards(u.node, best, R);
    if (!moveUnit(s, u, dir)) moveUnit(s, u, -dir);
    return;
  }
  if (p && p.alive && ringDist(u.node, p.node, R) === 1 && u.charge >= u.throughput) {
    enemyShove(s, u, towards(u.node, p.node, R));
    return;
  }
  if (p && p.alive && canMoveThisTurn(s, u)) {
    const away = -towards(u.node, p.node, R);
    if (!moveUnit(s, u, away)) moveUnit(s, u, -away);
  }
}

// ---------------------------------------------------------------------------
// Termination
// ---------------------------------------------------------------------------

function finish(s, result) {
  if (s.result) return;
  s.result = result;
  if (s.stats) s.stats.deathCause = result === 'loss' ? 'overload' : result;
  if (s.stats) s.stats.motesAtEnd = s.ring.reduce((a, b) => a + b, 0);
  emit(s, { type: 'end', result });
}

function checkEnd(s) {
  if (s.result) return;
  const p = getPlayer(s);
  if (!p || !p.alive) { finish(s, 'loss'); return; }
  if (enemies(s).length === 0 && !wavesPending(s)) finish(s, 'win');
}

export function playerActionsFor(s) {
  const p = getPlayer(s);
  const base = s.config.actionsPerTurn;
  if (!p || !p.alive || !s.config.playerHotBonus) return base;
  return base + (isHot(s, p) ? s.config.playerHotBonus : 0);
}

export function isOver(s) {
  return s.result != null;
}

// ---------------------------------------------------------------------------
// Cloning (agents fork the world; keep it cheap)
// ---------------------------------------------------------------------------

export function cloneState(s, { record = false } = {}) {
  return {
    config: s.config,
    encounter: s.encounter,
    rng: s.rng,
    turn: s.turn,
    actionsLeft: s.actionsLeft,
    ring: s.ring.slice(),
    ringPlayer: s.ringPlayer.slice(),
    units: s.units.map((u) => ({ ...u })),
    nextId: s.nextId,
    wavesSpawned: s.wavesSpawned.slice(),
    result: s.result,
    injected: s.injected,
    baseline: s.baseline,
    events: record && s.events ? s.events.slice() : null,
    stats: record && s.stats ? structuredClone(s.stats) : null,
  };
}
