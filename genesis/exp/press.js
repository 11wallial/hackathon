// EXP-030b. The lobber demonstrably forces the player up the charge band, but
// the first dose killed everything. Sweep the dose and ask a precise question:
// is there a setting that is *survivable* and still keeps the danger band
// occupied? Target declared before running, so this is not tuning-to-taste:
//   strong agent loss rate 25-45%  AND  neutral agent near-overload > 15%.
import { sweep } from './runner.js';

const build = (lobbers, lobCharge, chasers) => ({
  name: `press-${lobbers}-${lobCharge}`,
  waves: [
    { turn: 1,  units: [{ kind: 'drone' }, ...(lobbers >= 1 ? [{ kind: 'lobber', charge: lobCharge }] : [])] },
    { turn: 5,  units: [...(chasers ? [{ kind: 'drone', charge: 4 }] : []), ...(lobbers >= 2 ? [{ kind: 'lobber', charge: lobCharge }] : [])] },
    { turn: 9,  units: [{ kind: 'warden', charge: 8 }, ...(lobbers >= 3 ? [{ kind: 'lobber', charge: lobCharge }] : [])] },
    { turn: 13, units: [...(chasers ? [{ kind: 'drone', charge: 5 }] : []), ...(lobbers >= 4 ? [{ kind: 'lobber', charge: lobCharge }] : [])] },
    { turn: 17, units: [...(lobbers >= 5 ? [{ kind: 'lobber', charge: lobCharge }] : []), { kind: 'drone', charge: 5 }] },
  ],
});

console.log('lobbers charge | strong: win/loss/to | neutral: win/loss  band4  nearOverload | verdict');
for (const [n, c] of [[1,6],[2,6],[2,8],[3,6],[3,8],[4,6],[5,8]]) {
  const enc = build(n, c, true);
  const deep = sweep({ agentName: 'optimizerDeep', seeds: 200, encounter: enc });
  const neu = sweep({ agentName: 'optimizerNeutral', seeds: 200, encounter: enc });
  const rnd = sweep({ agentName: 'random', seeds: 200, encounter: enc });
  const ok = deep.lossRate >= 0.25 && deep.lossRate <= 0.45 && neu.nearOverloadRate > 0.15;
  console.log(
    String(n).padStart(7), String(c).padStart(6), '|',
    (deep.winRate*100).toFixed(0).padStart(3)+'%/'+(deep.lossRate*100).toFixed(0).padStart(3)+'%/'+(deep.timeoutRate*100).toFixed(0).padStart(3)+'%', '|',
    (neu.winRate*100).toFixed(0).padStart(3)+'%/'+(neu.lossRate*100).toFixed(0).padStart(3)+'%',
    (neu.chargeBand[3]*100).toFixed(1).padStart(5)+'%',
    (neu.nearOverloadRate*100).toFixed(1).padStart(5)+'%', '|',
    ok ? 'MEETS TARGET' : '', ' random', (rnd.winRate*100).toFixed(0)+'%');
}
