// EXP-034b. Depth 2 beats depth 1 by 30.7pp on `surge`. Is that specifically
// the "salt the retreat" pattern — step away, then mine the tile just vacated,
// which only becomes legal after the step — or is it general two-action play?
import { createEncounter, applyAction, isOver, getPlayer, mod, unitAt, ringDist } from '../sim/rules.js';
import { makeAgent } from '../agents/index.js';

for (const agentName of ['neutralD1', 'neutralD2']) {
  let turns = 0, stepThenShoveBack = 0, saltKills = 0, totalKills = 0, runs = 0, wins = 0;
  for (let seed = 7000; seed < 7200; seed++) {
    const s = createEncounter({ encounter: 'surge', seed, record: true });
    const agent = makeAgent(agentName, seed * 2654435761 + 12345);
    let steps = 0;
    let turnActions = [], turnStartNode = null, lastTurn = s.turn;
    const vacated = new Map(); // node -> turn it was salted

    while (!isOver(s) && steps++ < 5000) {
      const p = getPlayer(s);
      if (s.turn !== lastTurn) { lastTurn = s.turn; turnActions = []; turnStartNode = p.node; turns++; }
      if (turnStartNode === null) { turnStartNode = p.node; turns++; }
      const a = s.actionsLeft > 0 ? agent.act(s) : { type: 'end' };
      const before = p.node;
      applyAction(s, a);
      if (a.type !== 'end') turnActions.push({ ...a, from: before });

      // Detect: a shove aimed back at the tile the player occupied earlier this turn.
      if (a.type === 'shove' && a.dir !== 0) {
        const target = mod(before + a.dir, s.config.ringSize);
        if (turnActions.some((x) => x.type === 'step' && x.from === target)) {
          stepThenShoveBack++;
          vacated.set(target, s.turn);
        }
      }
    }
    runs++;
    if (s.result === 'win') wins++;
    for (const e of s.events) {
      if (e.type !== 'detonate' || e.kind === 'player') continue;
      totalKills++;
      if (vacated.has(e.node) && e.turn - vacated.get(e.node) <= 1) saltKills++;
    }
  }
  console.log(agentName.padEnd(11),
    '| win', (wins / runs * 100).toFixed(1) + '%',
    '| salt-the-retreat turns', (stepThenShoveBack / turns * 100).toFixed(1) + '% of turns',
    '| kills on a freshly salted tile', (saltKills / Math.max(1, totalKills) * 100).toFixed(1) + '%',
    `(${(saltKills / runs).toFixed(2)}/run of ${(totalKills / runs).toFixed(2)})`);
}
