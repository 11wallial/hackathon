// Every rule the design search might want to mutate lives here as data.
// Experiments are expressed as overrides of this object, never as code edits.

// v0.5 defaults. Every value here was selected by an experiment recorded in
// docs/EXPERIMENTS.md, not by taste. Flags left off are documented failures
// kept as dials so the results stay reproducible.
export const DEFAULT_CONFIG = {
  ringSize: 12,
  turnLimit: 45,
  actionsPerTurn: 2,

  player: { capacity: 10, charge: 4, throughput: 4 },

  // A unit at or above this fraction of capacity acts twice per turn.
  // This is the designed counterpressure against "always shove maximum".
  hotRule: true,
  hotThreshold: 0.5,

  // STEP absorbs every mote on the destination node. Makes movement income,
  // and makes loose charge a hazard for everybody including enemies.
  absorbOnStep: true,

  // A destroyed unit's charge is spread over nodes within this ring distance.
  detonationRadius: 1,
  // 'even'    : payload split across centre + neighbours (dilutes; chains never fire)
  // 'outward' : neighbours split the payload, centre keeps only the remainder
  blastSplit: 'even',

  // Circulation. A chaser with less charge than its throughput goes and picks
  // charge up off the floor instead of standing around empty.
  // Resurrected in EXP-025 after being killed in EXP-007. Every reason it
  // failed then has since been removed: under `absorbCap` a forager fills to
  // capacity and *survives*, loading itself into hot-and-brittle instead of
  // suiciding. It is now the counterweight that stops dissolution turning
  // drone-heavy fights into a walkover.
  hungryEnemies: true,

  // C2 — no free safety valve. At the end of a round, any unit standing on
  // motes absorbs them, so putting charge down is a positioning problem
  // rather than a button (see D-002).
  settleMotes: false,

  // 'lethal'  : player overload ends the run.
  // 'burnout' : player survives at 0 charge with permanently reduced capacity,
  //             and the payload still detonates outward (self-bomb is legal).
  overloadMode: 'burnout',
  burnoutCapacityLoss: 2,

  // Absorbing loose charge fills a unit to capacity and leaves the remainder
  // on the floor. Overload then requires a *directed* transfer — a shove or a
  // blast — so nothing dies without somebody deciding it should.
  absorbCap: true,

  // SHOVE also displaces the body it lands on, one node further along. Makes
  // the core verb positional as well as economic: you can push a unit onto a
  // pile you built, or off your back. Also breaks the two-body deadlock where
  // two adjacent units pass the same charge back and forth forever.
  shovePushes: false,

  // EXP-022. Rounds a unit may sit at zero charge before it dissolves. A unit
  // holding no charge holds nothing, so removing it costs conservation exactly
  // nothing — and it stops spent bodies becoming permanent walls that jam the
  // ring. It also creates a second way to kill: starve instead of overfill.
  // -1 disables.
  dissolveAfter: 8,

  // EXP-020. Fraction of every directed transfer that lands on the floor at the
  // target's node instead of inside it. Conservation is untouched; what changes
  // is that an exchange can no longer be exactly undone by the reply, which is
  // the irreversibility a conserved system needs to be able to finish (D-010).
  spillFraction: 0,

  // EXP-021. A unit that received a shove cannot shove on its next action.
  // Symmetric: applies to the player too.
  staggerOnShove: false,

  // Enemy shove strength. In a conserved economy an attack is a *transfer*:
  // enemies hurt you by funding you. This is the dial that decides whether the
  // player is ever forced up against their own capacity.
  enemyThroughputScale: 1.5,

  // Extra player actions while hot. Enemies already act twice when hot; giving
  // the player the same makes carrying charge powerful as well as dangerous.
  playerHotBonus: 1,

  // --- the energy budget ---------------------------------------------------
  // Charge scattered on the ring before the fight starts. This, plus what the
  // enemies arrive holding, is *all the charge that will ever exist*. Since a
  // kill requires delivering capacity+1 into a body, the ratio of total charge
  // to total enemy capacity decides whether an encounter can resolve at all.
  startCharge: 0,
  // Scales every unit's capacity, the other half of that ratio.
  capacityScale: 1,

  // Safety guard; tripping it is a correctness bug, not a design outcome.
  maxCascade: 64,
};

export function makeConfig(overrides = {}) {
  const c = structuredClone(DEFAULT_CONFIG);
  for (const [k, v] of Object.entries(overrides)) {
    if (v && typeof v === 'object' && !Array.isArray(v)) Object.assign(c[k], v);
    else c[k] = v;
  }
  return c;
}
