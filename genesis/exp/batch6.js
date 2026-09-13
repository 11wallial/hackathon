import { sweep, fmt } from './runner.js';
const SEEDS = Number(process.env.SEEDS || 250);
const PANEL = ['random', 'conservative', 'greedy', 'miner', 'optimizer'];
for (const [tag, cfg] of [
  ['v0.5 baseline', {}],
  ['EXP-020 spill 0.25', { spillFraction: 0.25 }],
  ['EXP-020 spill 0.50', { spillFraction: 0.5 }],
  ['EXP-021 stagger', { staggerOnShove: true }],
  ['both', { spillFraction: 0.25, staggerOnShove: true }],
]) {
  console.log(`\n=== ${tag} ===`);
  const res = {};
  for (const a of PANEL) { res[a] = sweep({ agentName: a, seeds: SEEDS, encounter: 'surge', config: cfg }); console.log(fmt(a, res[a])); }
  const o = res.optimizer;
  console.log(`  gradient vs greedy ${(o.winRate / Math.max(res.greedy.winRate, 0.004)).toFixed(1)}x` +
    `  vs random ${(o.winRate / Math.max(res.random.winRate, 0.004)).toFixed(0)}x` +
    `  band ${JSON.stringify(o.chargeBand)}  motesEnd ${o.motesAtEnd.toFixed(1)}`);
}
