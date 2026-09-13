import test from 'node:test';
import assert from 'node:assert/strict';
import { createEncounter, applyAction, totalEnergy, getPlayer, cloneState, legalActions, isOver } from '../sim/rules.js';
import { playOne } from '../exp/runner.js';

test('conservation holds across a long random batch', () => {
  let worstViol = 0;
  for (let seed = 1; seed <= 60; seed++) {
    const r = playOne({ agentName: 'random', seed, encounter: 'probe' });
    worstViol += r.stats.conservationViolations;
    assert.equal(r.stats.cascadeOverflow, 0, 'cascade guard tripped');
  }
  assert.equal(worstViol, 0, 'charge was created or destroyed');
});

test('total energy always equals cumulative injection', () => {
  const s = createEncounter({ seed: 42 });
  for (let i = 0; i < 200 && !isOver(s); i++) {
    const acts = legalActions(s);
    applyAction(s, acts[i % acts.length]);
    assert.equal(totalEnergy(s), s.injected);
  }
});

test('seeded runs reproduce exactly', () => {
  const a = playOne({ agentName: 'optimizer', seed: 99 });
  const b = playOne({ agentName: 'optimizer', seed: 99 });
  assert.equal(a.result, b.result);
  assert.equal(a.turns, b.turns);
  assert.deepEqual(a.stats.actions, b.stats.actions);
});

test('cloning a state does not leak into the original', () => {
  const s = createEncounter({ seed: 5 });
  const before = JSON.stringify({ u: s.units, r: s.ring, rng: s.rng });
  const c = cloneState(s);
  for (let i = 0; i < 20 && !isOver(c); i++) applyAction(c, legalActions(c)[0]);
  assert.equal(JSON.stringify({ u: s.units, r: s.ring, rng: s.rng }), before);
});

test('overload destroys at strictly greater than capacity, not at equal', () => {
  const s = createEncounter({ seed: 3 });
  const p = getPlayer(s);
  p.charge = p.capacity;
  applyAction(s, { type: 'end' });
  assert.ok(p.alive, 'a unit sitting exactly at capacity must survive');
});

test('charge can never go negative and shove is capped by throughput', () => {
  const s = createEncounter({ seed: 11 });
  const p = getPlayer(s);
  p.charge = 2;
  applyAction(s, { type: 'shove', dir: 0, amount: 99 });
  assert.equal(p.charge, 0);
  assert.equal(s.ring[p.node], 2);
});

test('burnout mode: the player survives one overload at a capacity cost', () => {
  const s = createEncounter({ seed: 8, config: { overloadMode: 'burnout' } });
  const p = getPlayer(s);
  const cap0 = p.capacity;
  // Hand-loading charge fabricates energy, so declare the injection too —
  // otherwise the conservation check below (correctly) flags the test itself.
  const target = p.capacity + 5;
  s.injected += target - p.charge;
  p.charge = target;
  applyAction(s, { type: 'shove', dir: 0, amount: 1 });
  assert.ok(p.alive, 'burnout must not kill on the first overload');
  assert.equal(p.capacity, cap0 - 2);
  assert.equal(totalEnergy(s), s.injected, 'self-detonation must conserve');
});

test('bodies block movement (one unit per node)', () => {
  const s = createEncounter({ seed: 21 });
  const p = getPlayer(s);
  const occupied = s.units.find((u) => u.team === 'enemy');
  occupied.node = (p.node + 1) % s.config.ringSize;
  const acts = legalActions(s);
  assert.ok(!acts.some((a) => a.type === 'step' && a.dir === 1));
});
