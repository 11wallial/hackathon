// Batch 1. Hypotheses were written in docs/EXPERIMENTS.md before this ran.
import { sweep, fmt } from './runner.js';

const SEEDS = Number(process.env.SEEDS || 300);
const ENC = process.env.ENC || 'probe';
const out = {};
const line = (t, a) => { console.log(fmt(t, a)); return a; };

console.log(`\n=== EXP-001 baseline (${ENC}, ${SEEDS} shared seeds) ===`);
for (const a of ['random', 'conservative', 'explorer', 'greedy', 'bomber', 'optimizer']) {
  out[`001:${a}`] = line(a, sweep({ agentName: a, encounter: ENC, seeds: SEEDS }));
}

console.log('\n=== EXP-002 hot rule OFF (counterpressure removed) ===');
for (const a of ['greedy', 'optimizer']) {
  out[`002:${a}`] = line(`${a} hot=off`, sweep({ agentName: a, encounter: ENC, seeds: SEEDS, config: { hotRule: false } }));
}

console.log('\n=== EXP-003 overload mode ===');
for (const a of ['optimizer', 'greedy']) {
  out[`003:${a}`] = line(`${a} burnout`, sweep({ agentName: a, encounter: ENC, seeds: SEEDS, config: { overloadMode: 'burnout' } }));
}

console.log('\n=== EXP-004 absorb-on-step OFF (movement stops being economy) ===');
for (const a of ['optimizer']) {
  out[`004:${a}`] = line(`${a} absorb=off`, sweep({ agentName: a, encounter: ENC, seeds: SEEDS, config: { absorbOnStep: false } }));
}

console.log('\n=== EXP-005 chains: agency vs noise (same seeds) ===');
for (const a of ['random', 'greedy', 'optimizer']) {
  const r = out[`001:${a}`];
  console.log(`${a.padEnd(14)} chainRate ${(r.chainRate * 100).toFixed(1)}%  chainShare ${(r.chainShare * 100).toFixed(1)}%  max ${r.maxChain}  hist ${JSON.stringify(r.chains)}`);
}

console.log('\n=== EXP-004 positional evidence ===');
console.log('optimizer stepTowardMoteRate  absorb=on ', out['001:optimizer'].stepTowardMoteRate.toFixed(3),
            ' absorb=off', out['004:optimizer'].stepTowardMoteRate.toFixed(3));
console.log('optimizer motesAtEnd         absorb=on ', out['001:optimizer'].motesAtEnd.toFixed(2),
            ' absorb=off', out['004:optimizer'].motesAtEnd.toFixed(2));

console.log('\n=== shove-amount distributions (optimizer) ===');
console.log('baseline   ', JSON.stringify(out['001:optimizer'].shoveAmounts));
console.log('hot=off    ', JSON.stringify(out['002:optimizer'].shoveAmounts));
console.log('charge band occupancy (q1..q4), optimizer:', JSON.stringify(out['001:optimizer'].chargeBand));

console.log('\n=== EXP-006 correctness ===');
let viol = 0, ovf = 0;
for (const k of Object.keys(out)) { viol += out[k].conservationViolations; ovf += out[k].cascadeOverflow; }
console.log(`conservation violations: ${viol}   cascade overflows: ${ovf}`);

process.stdout.write('\nJSON<<' + JSON.stringify(out) + '>>JSON\n');
