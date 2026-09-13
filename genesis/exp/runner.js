// Headless harness: plays encounters, asserts correctness invariants on every
// transition, and aggregates telemetry across seeds.

import { createEncounter, applyAction, isOver, totalEnergy, getPlayer } from '../sim/rules.js';
import { makeAgent } from '../agents/index.js';

const actionKey = (a) => `${a.type}:${a.dir ?? ''}:${a.amount ?? ''}`;

export function playOne({
  agentName, encounter = 'probe', config = {}, seed = 1,
  record = false, checkConservation = true,
}) {
  const s = createEncounter({ encounter, config, seed, record: true });
  const agent = makeAgent(agentName, seed * 2654435761 + 12345);
  const chosen = new Set();
  let steps = 0;
  let violations = 0;

  while (!isOver(s) && steps < 5000) {
    steps++;
    let a = s.actionsLeft > 0 ? agent.act(s) : { type: 'end' };
    if (!a) a = { type: 'end' };
    chosen.add(actionKey(a));
    const before = totalEnergy(s);
    const injectedBefore = s.injected;
    applyAction(s, a);
    if (checkConservation) {
      const after = totalEnergy(s);
      const expected = before + (s.injected - injectedBefore);
      if (after !== expected) violations++;
      if (after !== s.injected) violations++;
    }
  }
  s.stats.conservationViolations += violations;
  s.stats.distinctActions = chosen.size;
  s.stats.motesAtEnd = s.ring.reduce((x, y) => x + y, 0);
  const p = getPlayer(s);
  return {
    result: s.result || 'hung',
    turns: s.turn,
    finalCapacity: p ? p.capacity : 0,
    stats: s.stats,
    state: record ? s : null,
  };
}

const H = (counts) => {
  const vals = Object.values(counts).filter((n) => n > 0);
  const tot = vals.reduce((a, b) => a + b, 0);
  if (!tot) return 0;
  return -vals.reduce((acc, n) => acc + (n / tot) * Math.log2(n / tot), 0);
};

export function aggregate(runs) {
  const n = runs.length;
  const add = (o, src) => { for (const [k, v] of Object.entries(src)) o[k] = (o[k] || 0) + v; };

  const actions = {}, shoveAmounts = {}, chains = {}, shoveByBand = {}, killCause = {};
  let wins = 0, timeouts = 0, losses = 0, turns = 0, detonations = 0, enemyDet = 0, selfDet = 0;
  let baitKills = 0, tipKills = 0, starved = 0, chargeToEnemies = 0, chargeShoved = 0, motesAtEnd = 0;
  let nearOverload = 0, playerTurns = 0, stepChoices = 0, stepTowardMotes = 0;
  let violations = 0, overflow = 0, maxChain = 0, chainRuns = 0, distinct = 0;
  const bandTurns = [0, 0, 0, 0];

  for (const r of runs) {
    const st = r.stats;
    if (r.result === 'win') wins++;
    if (r.result === 'timeout') timeouts++;
    if (r.result === 'loss') losses++;
    turns += r.turns;
    add(actions, st.actions);
    add(shoveAmounts, st.shoveAmounts);
    add(chains, st.chains);
    add(killCause, st.killCause);
    for (const [band, m] of Object.entries(st.shoveByBand)) {
      shoveByBand[band] = shoveByBand[band] || {};
      add(shoveByBand[band], m);
    }
    detonations += st.detonations; enemyDet += st.enemyDetonations; selfDet += st.selfDetonations;
    baitKills += st.baitKills; tipKills += st.tipKills; starved += st.starved; chargeToEnemies += st.chargeToEnemies;
    chargeShoved += st.chargeShovedTotal; motesAtEnd += st.motesAtEnd;
    nearOverload += st.nearOverloadTurns; playerTurns += st.playerTurns;
    stepChoices += st.stepChoices; stepTowardMotes += st.stepTowardMotes;
    violations += st.conservationViolations; overflow += st.cascadeOverflow;
    maxChain = Math.max(maxChain, st.maxChain);
    st.chargeBandTurns.forEach((v, i) => { bandTurns[i] += v; });
    let chained = 0;
    for (const [len, c] of Object.entries(st.chains)) if (+len >= 2) chained += c;
    if (chained > 0) chainRuns++;
    distinct += st.distinctActions;
  }

  // Average entropy of shove amount *within* a charge band: high global with
  // lower conditional means the choice is context-driven, which is the target.
  const bandKeys = Object.keys(shoveByBand);
  let condNum = 0, condDen = 0;
  for (const b of bandKeys) {
    const tot = Object.values(shoveByBand[b]).reduce((a, c) => a + c, 0);
    condNum += H(shoveByBand[b]) * tot; condDen += tot;
  }
  const bandTot = bandTurns.reduce((a, b) => a + b, 0) || 1;
  let chainedTotal = 0, cascades = 0;
  for (const [len, c] of Object.entries(chains)) { cascades += c; if (+len >= 2) chainedTotal += c; }

  return {
    n,
    winRate: wins / n,
    lossRate: losses / n,
    timeoutRate: timeouts / n,
    meanTurns: turns / n,
    actionEntropy: H(actions),
    shoveEntropy: H(shoveAmounts),
    conditionalShoveEntropy: condDen ? condNum / condDen : 0,
    shoveAmounts,
    meanShove: Object.entries(shoveAmounts).reduce((a, [k, v]) => a + +k * v, 0) /
      (Object.values(shoveAmounts).reduce((a, b) => a + b, 0) || 1),
    actions,
    distinctActions: distinct / n,
    chargeBand: bandTurns.map((v) => +(v / bandTot).toFixed(3)),
    nearOverloadRate: playerTurns ? nearOverload / playerTurns : 0,
    feedRatio: chargeShoved ? chargeToEnemies / chargeShoved : 0,
    detonationsPerRun: detonations / n,
    selfDetonationsPerRun: selfDet / n,
    baitKillsPerRun: baitKills / n,
    tipKillsPerRun: tipKills / n,
    starvedPerRun: starved / n,
    chainRate: chainRuns / n,
    chainShare: cascades ? chainedTotal / cascades : 0,
    maxChain,
    chains,
    killCause,
    motesAtEnd: motesAtEnd / n,
    stepTowardMoteRate: stepChoices ? stepTowardMotes / stepChoices : 0,
    conservationViolations: violations,
    cascadeOverflow: overflow,
  };
}

export function sweep({ agentName, encounter = 'probe', config = {}, seeds = 200, seed0 = 1000 }) {
  const runs = [];
  for (let i = 0; i < seeds; i++) {
    runs.push(playOne({ agentName, encounter, config, seed: seed0 + i }));
  }
  return aggregate(runs);
}

export function fmt(tag, a) {
  const pct = (x) => (x * 100).toFixed(1).padStart(5) + '%';
  return [
    tag.padEnd(26),
    'win', pct(a.winRate),
    'loss', pct(a.lossRate),
    'to', pct(a.timeoutRate),
    'turns', a.meanTurns.toFixed(1).padStart(5),
    'Hact', a.actionEntropy.toFixed(2),
    'Hshove', a.shoveEntropy.toFixed(2),
    'Hshove|band', a.conditionalShoveEntropy.toFixed(2),
    'mShove', a.meanShove.toFixed(2),
    'det', a.detonationsPerRun.toFixed(2),
    'chain', pct(a.chainRate),
    'bait', a.baitKillsPerRun.toFixed(2),
    'tip', a.tipKillsPerRun.toFixed(2),
    'starve', a.starvedPerRun.toFixed(2),
    'self', a.selfDetonationsPerRun.toFixed(2),
    'feed', pct(a.feedRatio),
    'viol', String(a.conservationViolations),
  ].join(' ');
}
