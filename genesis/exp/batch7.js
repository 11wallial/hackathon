import { sweep, fmt } from './runner.js';
const SEEDS = Number(process.env.SEEDS || 250);
const PANEL = ['random', 'conservative', 'greedy', 'miner', 'optimizer'];
for (const [tag, cfg] of [
  ['v0.5 baseline', {}],
  ['EXP-022 dissolveAfter 0', { dissolveAfter: 0 }],
  ['EXP-022 dissolveAfter 1', { dissolveAfter: 1 }],
  ['EXP-023 ring 16', { ringSize: 16 }],
  ['EXP-023 ring 20', { ringSize: 20 }],
]) {
  console.log(`\n=== ${tag} ===`);
  const res = {};
  for (const a of PANEL) { res[a] = sweep({ agentName: a, seeds: SEEDS, encounter: 'surge', config: cfg }); console.log(fmt(a, res[a])); }
  const o = res.optimizer;
  console.log(`  gradient greedy ${(o.winRate / Math.max(res.greedy.winRate, 0.004)).toFixed(1)}x` +
    ` | band ${JSON.stringify(o.chargeBand)} nearOverload ${(o.nearOverloadRate * 100).toFixed(1)}%` +
    ` | killCause ${JSON.stringify(o.killCause)}`);
}
