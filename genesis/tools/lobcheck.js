// EXP-030 risk (b): is the lobber a real decision or trivially switched off?
// If the answer is always "walk into its face", the agent will live adjacent to
// one and the archetype is a fake threat.
import { createEncounter, applyAction, isOver, getPlayer, enemies, ringDist } from '../sim/rules.js';
import { makeAgent } from '../agents/index.js';

const enc = {
  name: 'press-3-6',
  waves: [
    { turn: 1,  units: [{ kind: 'drone' }, { kind: 'lobber', charge: 6 }] },
    { turn: 5,  units: [{ kind: 'drone', charge: 4 }, { kind: 'lobber', charge: 6 }] },
    { turn: 9,  units: [{ kind: 'warden', charge: 8 }, { kind: 'lobber', charge: 6 }] },
    { turn: 13, units: [{ kind: 'drone', charge: 5 }] },
    { turn: 17, units: [{ kind: 'drone', charge: 5 }] },
  ],
};

for (const agentName of ['optimizerDeep', 'optimizerNeutral']) {
  let turns = 0, adjacentToLobber = 0, inLobRange = 0, lobs = 0, runs = 0;
  let capLoss = 0, deaths = 0, distSum = 0, distN = 0;
  for (let seed = 5000; seed < 5150; seed++) {
    const s = createEncounter({ encounter: enc, seed, record: true });
    const agent = makeAgent(agentName, seed * 2654435761 + 12345);
    let steps = 0, lastTurn = 0;
    while (!isOver(s) && steps++ < 5000) {
      if (s.turn !== lastTurn) {
        lastTurn = s.turn;
        const p = getPlayer(s);
        const lobbers = enemies(s).filter((e) => e.ai === 'lob');
        if (lobbers.length) {
          turns++;
          const d = Math.min(...lobbers.map((l) => ringDist(l.node, p.node, s.config.ringSize)));
          distSum += d; distN++;
          if (d <= 1) adjacentToLobber++;
          if (d >= 2 && d <= 4) inLobRange++;
        }
      }
      applyAction(s, s.actionsLeft > 0 ? agent.act(s) : { type: 'end' });
    }
    runs++;
    lobs += s.events.filter((e) => e.type === 'lob').length;
    const p = getPlayer(s);
    capLoss += 10 - p.capacity;
    if (s.result === 'loss') deaths++;
  }
  console.log(agentName.padEnd(17),
    '| turns adjacent to a lobber', (adjacentToLobber / turns * 100).toFixed(1) + '%',
    '| turns inside lob range', (inLobRange / turns * 100).toFixed(1) + '%',
    '| mean distance', (distSum / distN).toFixed(2),
    '| lobs/run', (lobs / runs).toFixed(1),
    '| mean capacity lost', (capLoss / runs).toFixed(2),
    '| deaths', (deaths / runs * 100).toFixed(0) + '%');
}
