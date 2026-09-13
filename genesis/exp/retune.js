// EXP-039. Generates encounter variants and scores them against a target that
// was written into docs/EXPERIMENTS.md before this file existed.
import { sweep } from './runner.js';

const ramp = (i, boost) => Math.round(i * boost);

// `surge`-family: waves of mixed bodies arriving progressively fuller.
export const surgeGen = ({ cadence = 4, extra = 0, boost = 1 }) => ({
  name: `surge-c${cadence}-x${extra}-b${boost}`,
  waves: [
    { turn: 1, units: [{ kind: 'drone' }, { kind: 'drone' }, ...Array(extra).fill({ kind: 'drone' })] },
    { turn: 1 + cadence, units: [{ kind: 'siphon', charge: ramp(6, boost) }, ...Array(extra).fill({ kind: 'drone', charge: ramp(3, boost) })] },
    { turn: 1 + cadence * 2, units: [{ kind: 'drone', charge: ramp(4, boost) }, { kind: 'drone', charge: ramp(4, boost) }, ...Array(extra).fill({ kind: 'drone', charge: ramp(4, boost) })] },
    { turn: 1 + cadence * 3, units: [{ kind: 'warden', charge: ramp(8, boost) }, ...Array(extra).fill({ kind: 'drone', charge: ramp(5, boost) })] },
    { turn: 1 + cadence * 4, units: [{ kind: 'drone', charge: ramp(5, boost) }, { kind: 'siphon', charge: ramp(9, boost) }, ...Array(extra).fill({ kind: 'drone', charge: ramp(5, boost) })] },
    { turn: 1 + cadence * 5, units: [{ kind: 'warden', charge: ramp(9, boost) }, { kind: 'drone', charge: ramp(5, boost) }, ...Array(extra).fill({ kind: 'warden', charge: ramp(9, boost) })] },
  ],
});

// `press`-family: lobbers forcing charge in from outside melee range.
// Lobbers are spread across the five waves rather than capped at one each —
// the first version silently built the same encounter for any count above five,
// which produced three identical rows in the EXP-041 search pass and would have
// read as "lobber count does not matter".
export const pressGen = ({ lobbers = 3, cadence = 4, lobCharge = 6, extra = 0 }) => {
  const WAVES = 5;
  const per = Array.from({ length: WAVES }, (_, i) =>
    Math.floor(lobbers / WAVES) + (i < lobbers % WAVES ? 1 : 0));
  return {
    name: `press-l${lobbers}-c${cadence}-b${lobCharge}-x${extra}`,
    waves: Array.from({ length: WAVES }, (_, i) => ({
      turn: 1 + cadence * i,
      units: [
        ...Array(per[i]).fill({ kind: 'lobber', charge: lobCharge }),
        ...(i === 2 ? [{ kind: 'warden', charge: 8 }] : [{ kind: 'drone', charge: 3 + i }]),
        ...Array(extra).fill({ kind: 'drone', charge: 4 }),
      ],
    })),
  };
};

// `miner` and `greedy` are hand-written policies, not "medium-skill players" —
// D-021 says a mixed panel cannot localise a skill. The honest middle rung is a
// depth-1 searcher with the same evaluation as the strong agent: someone who
// plays well but does not plan two moves ahead.
// Siphon-heavy: high-capacity scavengers that load themselves off the floor,
// so the natural line is bait-then-tip rather than direct delivery.
export const siphonGen = ({ cadence = 4, siphons = 2, extra = 1, sCharge = 4, ramp = 2 }) => ({
  name: `garden-s${siphons}-c${cadence}-x${extra}-b${sCharge}`,
  waves: Array.from({ length: 5 }, (_, i) => ({
    turn: 1 + cadence * i,
    units: [
      ...Array(siphons).fill({ kind: 'siphon', charge: sCharge + i * ramp }),
      ...Array(extra).fill({ kind: 'drone', charge: 3 + i }),
    ],
  })),
});

// Warden-heavy: slow, high-capacity, and they do NOT scavenge, so nothing
// loads itself and every point of charge has to be delivered by hand.
export const wardenGen = ({ cadence = 4, wardens = 2, extra = 1, wCharge = 5, ramp = 1 }) => ({
  name: `bulwark-w${wardens}-c${cadence}-x${extra}-b${wCharge}`,
  waves: Array.from({ length: 5 }, (_, i) => ({
    turn: 1 + cadence * i,
    units: [
      ...Array(wardens).fill({ kind: 'warden', charge: wCharge + i * ramp }),
      ...Array(extra).fill({ kind: 'drone', charge: 3 + i }),
    ],
  })),
});

// Drone-only: every target is cheap enough that a single turn's throughput can
// finish one. Built to test whether a shallow planner's win rate is gated by the
// *hardest* target in the roster rather than by the mix (EXP-032).
export const droneGen = ({ cadence = 3, perWave = 4, ramp = 1 }) => ({
  name: `probe-d${perWave}-c${cadence}`,
  waves: Array.from({ length: 6 }, (_, i) => ({
    turn: 1 + cadence * i,
    units: Array(perWave).fill({ kind: 'drone', charge: 2 + i * ramp }),
  })),
});

const PANEL = ['random', 'conservative', 'neutralD1', 'miner', 'optimizerNeutral', 'optimizerDeep'];

export function score(enc, seeds = 150, needNearOverload = false, config = {}) {
  const r = {};
  for (const a of PANEL) r[a] = sweep({ agentName: a, seeds, encounter: enc, config });
  const strongest = Math.max(r.optimizerDeep.winRate, r.optimizerNeutral.winRate);
  // The first version of this check only compared the middle of the ladder to
  // *random*, which passes trivially once random is at 0% — it would have
  // signed off on a setting where the turtle outranked the expert policy.
  // A real middle rung has to sit clearly above the floor and below the ceiling.
  const mid = r.neutralD1.winRate;
  const ladderOk = mid > r.conservative.winRate + 0.10 && mid > 0.15 && mid < strongest - 0.10;
  const ok = strongest >= 0.50 && strongest <= 0.65 &&
    r.random.winRate < 0.05 && r.conservative.winRate < 0.05 && ladderOk &&
    (!needNearOverload || r.optimizerNeutral.nearOverloadRate > 0.30);
  return { r, strongest, ok, mid };
}

export function line(tag, s) {
  const p = (x) => (x * 100).toFixed(0).padStart(3) + '%';
  return `${tag.padEnd(22)} strong ${p(s.strongest)} | rnd ${p(s.r.random.winRate)} turtle ${p(s.r.conservative.winRate)} ` +
    `D1 ${p(s.r.neutralD1.winRate)} miner ${p(s.r.miner.winRate)} neutral ${p(s.r.optimizerNeutral.winRate)} deep ${p(s.r.optimizerDeep.winRate)} ` +
    `| nearOvl ${p(s.r.optimizerNeutral.nearOverloadRate)}${s.ok ? '  <== MEETS TARGET' : ''}`;
}

if (process.argv[2] === 'run') {
  console.log('EXP-039 surge family');
  for (const cadence of [4, 3, 2])
    for (const extra of [0, 1, 2])
      console.log(line(`c${cadence} x${extra}`, score(surgeGen({ cadence, extra }), 150)));
}
