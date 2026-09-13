// Playtest agents. These do not pretend to be humans. Their job is to expose
// structural properties of the rules: what is dominant, what is unreachable,
// what is fake.

import {
  legalActions, applyAction, cloneState, getPlayer, enemies,
  ringDist, towards, isHot, mod, unitAt, predictNextNode,
} from '../sim/rules.js';

function agentRng(seed) {
  let x = seed >>> 0 || 1;
  return () => {
    x ^= x << 13; x >>>= 0;
    x ^= x >> 17;
    x ^= x << 5; x >>>= 0;
    return x / 4294967296;
  };
}
const pick = (rnd, arr) => arr[Math.floor(rnd() * arr.length) % arr.length];

// --- helpers shared by the scripted agents --------------------------------

function nearestEnemy(s) {
  const p = getPlayer(s);
  const R = s.config.ringSize;
  let best = null, bd = 1e9;
  for (const e of enemies(s)) {
    const d = ringDist(e.node, p.node, R);
    if (d < bd) { bd = d; best = e; }
  }
  return best ? { unit: best, dist: bd } : null;
}
const shoves = (acts, dir) => acts.filter((a) => a.type === 'shove' && a.dir === dir);
const maxShove = (acts, dir) => shoves(acts, dir).sort((a, b) => b.amount - a.amount)[0];
const stepIn = (acts, dir) => acts.find((a) => a.type === 'step' && a.dir === dir);

// --- random ---------------------------------------------------------------

function randomAgent(seed) {
  const rnd = agentRng(seed);
  return {
    name: 'random',
    act(s) {
      const acts = legalActions(s);
      // Bias slightly away from ending instantly or the baseline never acts.
      const nonEnd = acts.filter((a) => a.type !== 'end');
      if (nonEnd.length && rnd() < 0.85) return pick(rnd, nonEnd);
      return { type: 'end' };
    },
  };
}

// --- greedy: maximise immediate damage ------------------------------------

function greedyAgent(seed) {
  const rnd = agentRng(seed);
  return {
    name: 'greedy',
    act(s) {
      const acts = legalActions(s);
      const p = getPlayer(s);
      const near = nearestEnemy(s);
      if (!near) return { type: 'end' };
      const dir = towards(p.node, near.unit.node, s.config.ringSize);
      if (near.dist === 1) {
        const sh = maxShove(acts, dir);
        if (sh) return sh;
      }
      const st = stepIn(acts, dir) || stepIn(acts, -dir);
      if (st) return st;
      const any = maxShove(acts, dir) || maxShove(acts, 0);
      return any || { type: 'end' };
    },
  };
}

// --- conservative: stay empty, stay away ----------------------------------

function conservativeAgent(seed) {
  const rnd = agentRng(seed);
  return {
    name: 'conservative',
    act(s) {
      const acts = legalActions(s);
      const p = getPlayer(s);
      const R = s.config.ringSize;
      const near = nearestEnemy(s);
      const ceiling = p.capacity * 0.4;

      if (p.charge > ceiling) {
        if (near && near.dist === 1) {
          const sh = maxShove(acts, towards(p.node, near.unit.node, R));
          if (sh) return sh;
        }
        const vent = maxShove(acts, 0);
        if (vent) return vent;
      }
      if (near && near.dist <= 2) {
        const away = -towards(p.node, near.unit.node, R);
        const st = stepIn(acts, away);
        // Never walk into a pile: that is how a conservative player dies.
        if (st && s.ring[mod(p.node + away, R)] + p.charge <= p.capacity) return st;
      }
      return { type: 'end' };
    },
  };
}

// --- explorer: prefer under-used verbs ------------------------------------

function explorerAgent(seed) {
  const rnd = agentRng(seed);
  const used = {};
  return {
    name: 'explorer',
    act(s) {
      const acts = legalActions(s).filter((a) => a.type !== 'end');
      if (!acts.length) return { type: 'end' };
      const key = (a) => `${a.type}:${a.dir ?? ''}:${a.amount ?? ''}`;
      acts.sort((a, b) => (used[key(a)] || 0) - (used[key(b)] || 0) || rnd() - 0.5);
      const chosen = acts[0];
      used[key(chosen)] = (used[key(chosen)] || 0) + 1;
      return chosen;
    },
  };
}

// --- specialist: the bomb-gardener ---------------------------------------
// Commits to one strategy: build a pile on the far side of the ring and let a
// scavenger eat itself. Exists to test whether a non-obvious strategy is even
// viable, i.e. whether build diversity is structurally possible.

function bomberAgent(seed) {
  const rnd = agentRng(seed);
  return {
    name: 'bomber',
    act(s) {
      const acts = legalActions(s);
      const p = getPlayer(s);
      const R = s.config.ringSize;
      const scav = enemies(s).filter((e) => e.ai === 'scavenge');
      const near = nearestEnemy(s);

      if (scav.length) {
        // Build the pile where it is closest to the scavenger but not to us.
        const vent = maxShove(acts, 0);
        const forward = maxShove(acts, 1);
        const target = scav[0];
        const need = target.capacity - target.charge + 1;
        const bestPile = Math.max(...s.ring);
        if (p.charge > 0 && bestPile < need) {
          const dir = towards(p.node, target.node, R);
          return maxShove(acts, dir) || vent || { type: 'end' };
        }
        // Pile is armed; get away from it and top up elsewhere.
        if (near && near.dist === 1) {
          const sh = maxShove(acts, towards(p.node, near.unit.node, R));
          if (sh) return sh;
        }
        const st = stepIn(acts, -1) || stepIn(acts, 1);
        if (st) return st;
      }
      if (near && near.dist === 1) {
        const sh = maxShove(acts, towards(p.node, near.unit.node, R));
        if (sh) return sh;
      }
      const st = near ? stepIn(acts, towards(p.node, near.unit.node, R)) : null;
      return st || { type: 'end' };
    },
  };
}

// --- optimiser: shallow search over this turn + the enemy response ---------

// Default weight on the player's capacity. EXP-038 swept 0/4/8/15/25/40/80 and
// found the plateau here. Before this existed, every agent treated a permanent
// capacity loss as free, which made every difficulty number in the notebook
// an underestimate of competent play.
export const DEFAULT_CAP_WEIGHT = 25;

// capW prices the player's *capacity*: a persistent outcome quantity, like
// being alive or an enemy being dead. Not a tactical hint — see EXP-038, and
// contrast EXP-027's distance-to-goal term, which told the agent how to play
// and was duly exploited.
function evaluate(s, capW = 0) {
  if (s.result === 'win') return 10000 - s.turn * 5;
  if (s.result === 'loss' || s.result === 'timeout') return -10000;
  const p = getPlayer(s);
  const R = s.config.ringSize;
  let score = 0;
  const alive = enemies(s);
  score -= 120 * alive.length;
  const headroom = p.capacity - p.charge;
  score -= Math.max(0, 4 - headroom) * 25; // fear of overload
  score += Math.min(p.charge, p.capacity) * 1.5; // charge is useful
  score += p.capacity * capW;                    // and losing capacity is forever
  for (const e of alive) {
    const d = ringDist(e.node, p.node, R);
    if (d <= 1) score -= 12;
    if (isHot(s, e)) score -= 8;
  }
  return score;
}

// Distance-to-goal: total charge still required to clear the board. This is the
// win condition's own metric, not a tactic — it is the standard fix for the
// horizon effect, where a target needing 15 charge can never be killed inside a
// 2-ply search so partial progress scores as pure loss.
function chargeToClear(s) {
  let need = 0;
  for (const e of enemies(s)) need += e.capacity - e.charge + 1;
  return need;
}

// Q4 instrument check. Purely outcome-based: enemies alive, player alive,
// distance to goal. No fear-of-overload term, no adjacency or hot penalties,
// no hint about how to kill anything. If the findings hold under this agent
// they are not artefacts of the evaluation function.
function evaluateNeutral(s, capW = 0) {
  if (s.result === 'win') return 10000 - s.turn * 5;
  if (s.result === 'loss' || s.result === 'timeout') return -10000;
  const p = getPlayer(s);
  return -120 * enemies(s).length + (p ? p.capacity * capW : 0);
}

function optimizerAgent(seed, evalFn = evaluate, name = 'optimizer', maxDepth = 2, capW = DEFAULT_CAP_WEIGHT) {
  const rnd = agentRng(seed);
  return {
    name,
    act(s) {
      const root = legalActions(s);
      if (!root.length) return { type: 'end' };
      let best = null, bestScore = -Infinity, bestCost = Infinity;

      // Ties are broken toward *fewer actions spent*. Without this the agent
      // happily burns an action on a no-op (shove 4 then step onto it is
      // identical to stepping), which is an artefact of the search, not a
      // property of the game, and it made traces unreadable.
      const consider = (sc, first, cost) => {
        if (sc > bestScore + 1e-9 ||
            (Math.abs(sc - bestScore) < 1e-9 && (cost < bestCost || (cost === bestCost && rnd() < 0.25)))) {
          bestScore = sc; best = first; bestCost = cost;
        }
      };
      const search = (st, first, depth, cost) => {
        if (st.result || depth === 0 || st.actionsLeft <= 0) {
          const closed = cloneState(st);
          applyAction(closed, { type: 'end' });
          consider(evalFn(closed, capW), first, cost);
          return;
        }
        for (const a of legalActions(st)) {
          if (a.type === 'end') {
            const closed = cloneState(st);
            applyAction(closed, a);
            consider(evalFn(closed, capW), first ?? a, cost);
            continue;
          }
          const next = cloneState(st);
          applyAction(next, a);
          search(next, first ?? a, depth - 1, cost + 1);
        }
      };
      search(s, null, Math.min(maxDepth, s.actionsLeft), 0);
      return best || { type: 'end' };
    },
  };
}

// --- miner: the strategy the optimiser discovered, written down explicitly ---
// Predicts where each enemy steps next (via the engine's own predictNextNode,
// the same one the UI draws) and places a pile of *exactly* the size that
// overloads it on arrival. Exists to answer two questions: is the discovered
// line reliably executable (mastery), and is it dominant (rule 21)?

function minerAgent(seed) {
  const rnd = agentRng(seed);
  return {
    name: 'miner',
    act(s) {
      const acts = legalActions(s);
      const p = getPlayer(s);
      const R = s.config.ringSize;
      const foes = enemies(s);
      if (!foes.length) return { type: 'end' };

      // 1. Can we arm a mine that kills something on its next move?
      // A mine usually costs more than one shove (a 2/6 drone needs 5, and
      // throughput is 4), so this builds across the turn's actions. That the
      // tactic needs construction rather than a single button is why a
      // one-step heuristic missed it entirely.
      const budget = Math.min(p.charge, p.throughput * s.actionsLeft);
      let bestPlan = null;
      for (const e of foes) {
        const target = predictNextNode(s, e);
        if (ringDist(p.node, target, R) > 1) continue;
        const dir = target === p.node ? 0 : towards(p.node, target, R);
        const need = e.capacity - e.charge + 1 - s.ring[target];
        if (need <= 0 || need > budget) continue;
        // Do not arm our own tile unless we can still step off it afterwards.
        if (dir === 0 && s.actionsLeft < 2) continue;
        if (!bestPlan || need < bestPlan.need) {
          bestPlan = { need, dir, amount: Math.min(p.throughput, need) };
        }
      }
      if (bestPlan) {
        const a = acts.find((x) => x.type === 'shove' && x.dir === bestPlan.dir && x.amount === bestPlan.amount);
        if (a) return a;
      }

      // 1b. "Salt the retreat": a chaser adjacent to us will not move, but if
      // we step away it walks into the tile we just left. So retreat *in order
      // to* mine the ground behind us. This is the signature line the search
      // agent found and the one-step version above cannot express, because the
      // mine only becomes placeable after the move.
      for (const e of foes) {
        if (e.ai !== 'chase' || ringDist(p.node, e.node, R) !== 1) continue;
        const need = e.capacity - e.charge + 1 - s.ring[p.node];
        if (need <= 0 || need > Math.min(p.charge, p.throughput)) continue;
        if (s.actionsLeft < 2) continue;
        const away = -towards(p.node, e.node, R);
        const st = stepIn(acts, away);
        if (st && p.charge + s.ring[mod(p.node + away, R)] <= p.capacity) return st;
      }

      // 2. Do not stand in our own minefield.
      if (s.ring[p.node] > 0 && p.charge + s.ring[p.node] > p.capacity) {
        for (const dir of [-1, 1]) {
          const st = stepIn(acts, dir);
          if (st && p.charge + s.ring[mod(p.node + dir, R)] <= p.capacity) return st;
        }
      }

      // 3. Dump if we are dangerously full, preferring a tile a foe walks over.
      if (p.charge > p.capacity * 0.7) {
        const sh = maxShove(acts, 1) || maxShove(acts, -1) || maxShove(acts, 0);
        if (sh) return sh;
      }

      // 4. Otherwise take station one node from the nearest enemy's path.
      const near = nearestEnemy(s);
      if (near && near.dist > 1) {
        const dir = towards(p.node, near.unit.node, R);
        const st = stepIn(acts, dir);
        if (st) return st;
      }
      if (near && near.dist === 1) {
        const away = -towards(p.node, near.unit.node, R);
        const st = stepIn(acts, away);
        if (st && p.charge + s.ring[mod(p.node + away, R)] <= p.capacity) return st;
        const sh = maxShove(acts, towards(p.node, near.unit.node, R));
        if (sh) return sh;
      }
      return { type: 'end' };
    },
  };
}

export const AGENTS = {
  random: randomAgent,
  greedy: greedyAgent,
  conservative: conservativeAgent,
  explorer: explorerAgent,
  bomber: bomberAgent,
  miner: minerAgent,
  optimizer: optimizerAgent,
  // Same search, evaluation extended with distance-to-goal (EXP-027 stage 3).
  optimizerGoal: (seed) => optimizerAgent(seed, (s) => evaluate(s) - 3 * chargeToClear(s), 'optimizerGoal'),
  // Same search, evaluation stripped to outcomes only (EXP-029 / Q4).
  optimizerNeutral: (seed, capW = DEFAULT_CAP_WEIGHT) => optimizerAgent(seed, evaluateNeutral, 'optimizerNeutral', 2, capW),
  // Same evaluation, deeper horizon — isolates search myopia from design (EXP-028).
  optimizerDeep: (seed, capW = DEFAULT_CAP_WEIGHT) => optimizerAgent(seed, evaluate, 'optimizerDeep', 3, capW),
  // EXP-034: identical evaluation, depth varied alone, to separate "how far can
  // this player plan" from every other difference between agents.
  neutralD1: (seed) => optimizerAgent(seed, evaluateNeutral, 'neutralD1', 1),
  neutralD2: (seed) => optimizerAgent(seed, evaluateNeutral, 'neutralD2', 2),
  neutralD3: (seed) => optimizerAgent(seed, evaluateNeutral, 'neutralD3', 3),
};

export function makeAgent(name, seed) {
  // "agent@w" runs that agent with capacity weight w, so EXP-038 can sweep the
  // instrument without forking the agent list.
  const [base, w] = String(name).split('@');
  const f = AGENTS[base];
  if (!f) throw new Error(`unknown agent: ${name}`);
  return w === undefined ? f(seed) : f(seed, Number(w));
}
