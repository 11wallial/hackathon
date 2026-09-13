import { sweep, fmt } from './runner.js';
const SEEDS = Number(process.env.SEEDS || 200);
const PANEL = ['random', 'conservative', 'greedy', 'miner', 'optimizer'];
const base = { turnLimit: 45, absorbCap: true, playerHotBonus: 1 };
for (const [tag, cfg] of [
  ['hotThreshold 0.50 (v0.5 cand)', {}],
  ['EXP-017 hotThreshold 0.75', { hotThreshold: 0.75 }],
  ['EXP-017 hotThreshold 0.85', { hotThreshold: 0.85 }],
]) {
  console.log(`\n=== ${tag} ===`);
  const res = {};
  for (const a of PANEL) { res[a] = sweep({ agentName: a, seeds: SEEDS, encounter: 'surge', config: { ...base, ...cfg } }); console.log(fmt(a, res[a])); }
  const o = res.optimizer;
  console.log('  optimizer band', JSON.stringify(o.chargeBand), 'nearOverload', (o.nearOverloadRate * 100).toFixed(1) + '%',
    'maxChain', o.maxChain, 'motesEnd', o.motesAtEnd.toFixed(1), 'killCause', JSON.stringify(o.killCause));
}
