// Human-readable replay of one seeded run. Summary statistics hide mechanism;
// this is for looking at what actually happened.
import { createEncounter, applyAction, isOver, getPlayer } from '../sim/rules.js';
import { makeAgent } from '../agents/index.js';

const seed = Number(process.argv[2] || 1000);
const agentName = process.argv[3] || 'optimizer';
const cfgArg = process.argv[4] ? JSON.parse(process.argv[4]) : {};
const enc = process.argv[5] || 'probe';

const s = createEncounter({ encounter: enc, seed, config: cfgArg, record: true });
const agent = makeAgent(agentName, seed * 2654435761 + 12345);

function board(s) {
  const cells = [];
  for (let n = 0; n < s.config.ringSize; n++) {
    const u = s.units.find((x) => x.alive && x.node === n);
    const m = s.ring[n];
    let tag = u ? `${u.team === 'player' ? 'YOU' : u.kind.slice(0, 3).toUpperCase()}${u.charge}/${u.capacity}` : '.';
    if (m > 0) tag += `+${m}`;
    cells.push(tag.padEnd(10));
  }
  return cells.join('');
}

let last = 0;
while (!isOver(s) && s.turn < 60) {
  if (s.turn !== last) {
    console.log(`\n--- turn ${s.turn} ---`);
    console.log('    ' + Array.from({ length: s.config.ringSize }, (_, i) => String(i).padEnd(10)).join(''));
    console.log('    ' + board(s));
    last = s.turn;
  }
  const before = s.events.length;
  const a = s.actionsLeft > 0 ? agent.act(s) : { type: 'end' };
  applyAction(s, a);
  const desc = a.type === 'shove' ? `shove ${a.amount} ${a.dir === 0 ? 'here' : a.dir > 0 ? '→' : '←'}`
    : a.type === 'step' ? `step ${a.dir > 0 ? '→' : '←'}` : 'end turn';
  const news = s.events.slice(before).filter((e) => ['detonate', 'absorb', 'motes', 'spawn', 'end'].includes(e.type));
  const notes = news.map((e) => {
    if (e.type === 'detonate') return `** ${e.kind}#${e.id} DETONATES on ${e.node} payload ${e.payload}${e.survived ? ' (survives)' : ''}`;
    if (e.type === 'absorb') return `${e.bait ? '[bait] ' : ''}#${e.id} absorbs ${e.amount} -> ${e.charge}`;
    if (e.type === 'motes') return `motes on ${e.node} -> ${e.total}`;
    if (e.type === 'spawn') return `spawn ${e.kind}#${e.id} on ${e.node}`;
    if (e.type === 'end') return `RESULT: ${e.result}`;
    return '';
  });
  console.log(`  ${desc.padEnd(14)} ${notes.join(' | ')}`);
}
console.log(`\nresult=${s.result} turns=${s.turn} bait=${s.stats.baitKills} det=${s.stats.detonations}`);
