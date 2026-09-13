// EXP-013: sweep the energy budget. Everything else held at v0.2 baseline.
import { sweep } from './runner.js';
import { ARCHETYPES, ENCOUNTERS } from '../sim/content.js';

const SEEDS = Number(process.env.SEEDS || 200);
const enc = ENCOUNTERS[process.env.ENC || 'probe'];

function ccrOf(startCharge, capacityScale) {
  let charge = ARCHETYPES.player.charge + startCharge, need = 0;
  for (const w of enc.waves) for (const u of w.units) {
    charge += ARCHETYPES[u.kind].charge;
    need += Math.max(1, Math.round(ARCHETYPES[u.kind].capacity * capacityScale)) + 1;
  }
  return charge / need;
}

const PANEL = ['random', 'greedy', 'miner', 'optimizer'];
console.log('startCharge capScale  CCR |            win / loss / timeout            | gradient');
for (const [sc, cs] of [[0,1],[10,1],[20,1],[30,1],[45,1],[20,0.6],[45,0.6],[60,1],[90,1]]) {
  const res = {};
  for (const a of PANEL) res[a] = sweep({ agentName: a, seeds: SEEDS, config: { startCharge: sc, capacityScale: cs }, encounter: enc.name });
  const cell = (a) => `${a.padEnd(9)} ${(res[a].winRate*100).toFixed(0).padStart(3)}/${(res[a].lossRate*100).toFixed(0).padStart(3)}/${(res[a].timeoutRate*100).toFixed(0).padStart(3)}`;
  const grad = res.optimizer.winRate / Math.max(res.greedy.winRate, 0.004);
  console.log(
    String(sc).padStart(10), String(cs).padStart(8), ccrOf(sc, cs).toFixed(2).padStart(5), '|',
    PANEL.map(cell).join('  '), '|', grad.toFixed(1) + 'x');
}
