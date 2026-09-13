import { sweep, fmt } from './runner.js';

const SEEDS = Number(process.env.SEEDS || 250);
const PANEL = ['random', 'greedy', 'conservative', 'miner', 'optimizer'];
const out = {};
const run = (tag, cfg, panel = PANEL) => {
  console.log(`\n=== ${tag} ===`);
  for (const a of panel) {
    const r = sweep({ agentName: a, seeds: SEEDS, config: cfg });
    out[`${tag}|${a}`] = r;
    console.log(fmt(a, r));
  }
  const o = out[`${tag}|optimizer`], g = out[`${tag}|greedy`];
  if (o && g) console.log(`  skill gradient optimizer/greedy = ${(o.winRate / Math.max(g.winRate, 0.001)).toFixed(1)}x`);
};

run('v0.2 baseline', {});
run('EXP-007 hungry', { hungryEnemies: true });
run('EXP-008 settle', { settleMotes: true });
run('EXP-009 outward', { blastSplit: 'outward' });
run('EXP-010 v0.3 all three', { hungryEnemies: true, settleMotes: true, blastSplit: 'outward' });

console.log('\n--- charge-band occupancy (optimizer), q1..q4 ---');
for (const k of Object.keys(out).filter((k) => k.endsWith('|optimizer'))) {
  const r = out[k];
  console.log(k.replace('|optimizer', '').padEnd(22), JSON.stringify(r.chargeBand),
    ' nearOverload', (r.nearOverloadRate * 100).toFixed(1) + '%',
    ' chains', JSON.stringify(r.chains), ' maxChain', r.maxChain);
}
let viol = 0, ovf = 0;
for (const k of Object.keys(out)) { viol += out[k].conservationViolations; ovf += out[k].cascadeOverflow; }
console.log(`\nconservation violations ${viol}   cascade overflows ${ovf}`);
