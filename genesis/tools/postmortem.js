// EXP-026. Aggregate the *final state* of runs that failed to resolve, so we
// diagnose the remaining timeouts from evidence rather than from a story.
import { createEncounter, applyAction, isOver, getPlayer, enemies, ringDist } from '../sim/rules.js';
import { makeAgent } from '../agents/index.js';

const agentName = process.argv[2] || 'optimizer';
const enc = process.argv[3] || 'surge';
const N = Number(process.argv[4] || 400);

const tally = { n: 0, kinds: {}, enemyCount: {}, playerCharge: [], looseCharge: [],
  enemyCharge: [], reachable: 0, packed: [], stuckRounds: [], deliverable: 0, seeds: [] };

for (let seed = 3000; seed < 3000 + N; seed++) {
  const s = createEncounter({ encounter: enc, seed, record: true });
  const agent = makeAgent(agentName, seed * 2654435761 + 12345);
  let steps = 0;
  const actionLog = [];
  while (!isOver(s) && steps++ < 5000) {
    const a = s.actionsLeft > 0 ? agent.act(s) : { type: 'end' };
    actionLog.push(`${s.turn}:${a.type}`);
    applyAction(s, a);
  }
  if (s.result !== 'timeout') continue;

  tally.n++;
  if (tally.seeds.length < 8) tally.seeds.push(seed);
  const foes = enemies(s);
  const p = getPlayer(s);
  tally.enemyCount[foes.length] = (tally.enemyCount[foes.length] || 0) + 1;
  for (const f of foes) tally.kinds[f.kind] = (tally.kinds[f.kind] || 0) + 1;
  tally.playerCharge.push(p.charge / p.capacity);
  tally.looseCharge.push(s.ring.reduce((a, b) => a + b, 0));
  tally.enemyCharge.push(foes.reduce((a, f) => a + f.charge, 0));

  // Occupancy: how full is the ring at the end?
  const occupied = s.units.filter((u) => u.alive).length;
  tally.packed.push(occupied / s.config.ringSize);

  // Can the player still reach any enemy at all?
  if (foes.some((f) => ringDist(f.node, p.node, s.config.ringSize) <= 1)) tally.reachable++;

  // Is there enough charge in the whole system to finish the remaining enemies?
  const need = foes.reduce((a, f) => a + (f.capacity - f.charge + 1), 0);
  const avail = p.charge + s.ring.reduce((a, b) => a + b, 0) + foes.reduce((a, f) => a + f.charge, 0);
  if (avail >= need) tally.deliverable++;

  // How much of the last 15 turns was spent doing nothing but ending the turn?
  const last = actionLog.slice(-45);
  tally.stuckRounds.push(last.filter((x) => x.endsWith(':end')).length / Math.max(1, last.length));
}

const mean = (a) => (a.reduce((x, y) => x + y, 0) / Math.max(1, a.length));
console.log(`${agentName} on ${enc}: ${tally.n}/${N} timed out (${(tally.n / N * 100).toFixed(1)}%)`);
console.log('enemies remaining      ', JSON.stringify(tally.enemyCount));
console.log('which kinds survive    ', JSON.stringify(tally.kinds));
console.log('mean player charge     ', (mean(tally.playerCharge) * 100).toFixed(0) + '% of capacity');
console.log('mean loose charge left ', mean(tally.looseCharge).toFixed(1));
console.log('mean enemy charge left ', mean(tally.enemyCharge).toFixed(1));
console.log('ring occupancy at end  ', (mean(tally.packed) * 100).toFixed(0) + '%');
console.log('player adjacent to a foe', (tally.reachable / tally.n * 100).toFixed(0) + '% of the time');
console.log('ENOUGH CHARGE TO FINISH ', (tally.deliverable / tally.n * 100).toFixed(0) + '% of stuck runs');
console.log('share of last 45 actions that were bare "end turn"', (mean(tally.stuckRounds) * 100).toFixed(0) + '%');
console.log('example seeds          ', tally.seeds.join(' '));
