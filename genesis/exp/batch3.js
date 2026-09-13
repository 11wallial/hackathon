import { sweep, fmt } from './runner.js';
const SEEDS = Number(process.env.SEEDS || 200);
const PANEL = ['random', 'conservative', 'greedy', 'miner', 'optimizer'];
const base = { turnLimit: 45 };
const run = (tag, cfg) => {
  console.log(`\n=== ${tag} ===`);
  const res = {};
  for (const a of PANEL) {
    res[a] = sweep({ agentName: a, seeds: SEEDS, encounter: 'surge', config: { ...base, ...cfg } });
    console.log(fmt(a, res[a]));
  }
  const o = res.optimizer;
  console.log('  optimizer band', JSON.stringify(o.chargeBand), 'nearOverload', (o.nearOverloadRate * 100).toFixed(1) + '%',
    'maxChain', o.maxChain);
  console.log('  kill causes  optimizer', JSON.stringify(o.killCause), '\n  kill causes  turtle   ', JSON.stringify(res.conservative.killCause));
  return res;
};
run('v0.4 surge baseline', {});
run('EXP-014 absorbCap', { absorbCap: true });
run('EXP-015 playerHotBonus', { playerHotBonus: 1 });
run('EXP-016 both (v0.5 candidate)', { absorbCap: true, playerHotBonus: 1 });
