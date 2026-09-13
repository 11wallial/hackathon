import { sweep, fmt } from './runner.js';
const SEEDS = Number(process.env.SEEDS || 200);
const PANEL = ['random', 'conservative', 'greedy', 'miner', 'optimizer'];
const base = { turnLimit: 45, absorbCap: true, playerHotBonus: 1 };
console.log('EXP-018 — enemy throughput as forced charge injection\n');
for (const sc of [1, 1.5, 2, 3]) {
  const res = {};
  for (const a of PANEL) res[a] = sweep({ agentName: a, seeds: SEEDS, encounter: 'surge', config: { ...base, enemyThroughputScale: sc } });
  const o = res.optimizer;
  console.log(`--- enemyThroughputScale ${sc} ---`);
  for (const a of PANEL) console.log(fmt(a, res[a]));
  console.log('  optimizer band', JSON.stringify(o.chargeBand),
    'nearOverload', (o.nearOverloadRate * 100).toFixed(1) + '%',
    ' gradient vs greedy', (o.winRate / Math.max(res.greedy.winRate, 0.004)).toFixed(1) + 'x\n');
}
