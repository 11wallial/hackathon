// Unit archetypes and encounter definitions. Data only — the rules engine
// reads these and knows nothing about specific enemies.

export const ARCHETYPES = {
  player: { capacity: 10, charge: 4, throughput: 4, ai: null, moveEvery: 1 },

  // Aggressive, cheap, and it *hands you charge* when it attacks. Drones are
  // the main way energy enters the player's battery against their will.
  drone: { capacity: 6, charge: 2, throughput: 2, ai: 'chase', moveEvery: 1 },

  // Ignores the player, eats loose charge off the floor. Huge capacity, so it
  // becomes a walking bomb — and it will happily eat a pile that kills it.
  siphon: { capacity: 14, charge: 1, throughput: 1, ai: 'scavenge', moveEvery: 1 },

  // Slow, starts hot, hits for a lot. The reason you cannot simply stand still.
  warden: { capacity: 10, charge: 6, throughput: 4, ai: 'chase', moveEvery: 2 },

  // Throws charge at the player from range 2-4 and cannot do it at range 1, so
  // closing the distance switches it off. Exists to answer Q1: melee pressure
  // is self-limiting on a ring (only two units can reach you, a hard hitter
  // disarms itself, and you outrun everything), so forcing charge onto the
  // player needs a threat that reaches past the front rank.
  lobber: { capacity: 8, charge: 6, throughput: 3, ai: 'lob', moveEvery: 2,
            minRange: 2, maxRange: 4 },
};

// A wave injects charge into the encounter; this is the escalation lever.
// Encounters are named so experiments can compare like with like.
export const ENCOUNTERS = {
  // The standard test bed for batch 1.
  probe: {
    name: 'probe',
    waves: [
      { turn: 1, units: [{ kind: 'drone' }, { kind: 'drone' }] },
      { turn: 6, units: [{ kind: 'siphon' }] },
      { turn: 12, units: [{ kind: 'drone' }, { kind: 'warden' }] },
    ],
  },

  // Drone-only: isolates the feed/attack tension with no scavenger.
  swarm: {
    name: 'swarm',
    waves: [
      { turn: 1, units: [{ kind: 'drone' }, { kind: 'drone' }, { kind: 'drone' }] },
      { turn: 8, units: [{ kind: 'drone' }, { kind: 'drone' }] },
    ],
  },

  // Charge enters the encounter *inside bodies*, never on the floor: the only
  // loose charge is charge somebody put there. Later waves arrive progressively
  // fuller, which makes them more dangerous (hot units act twice) and more
  // brittle (a small shove tips them over) at the same time.
  //
  // Wave size and cadence re-derived in EXP-039 against agents that price their
  // own capacity. The previous settings were tuned against agents that treated
  // a permanent capacity loss as free, and the strongest agent beat them 97% of
  // the time. Body count turned out to dominate cadence, and raising the charge
  // enemies *arrive* holding was actively harmful — see the graveyard.
  surge: {
    name: 'surge',
    waves: [
      { turn: 1, units: [{ kind: 'drone' }, { kind: 'drone' }, { kind: 'drone' }, { kind: 'drone' }, { kind: 'drone' }] },
      { turn: 4, units: [{ kind: 'siphon', charge: 6 }, { kind: 'drone', charge: 3 }, { kind: 'drone', charge: 3 }, { kind: 'drone', charge: 3 }] },
      { turn: 7, units: [{ kind: 'drone', charge: 4 }, { kind: 'drone', charge: 4 }, { kind: 'drone', charge: 4 }, { kind: 'drone', charge: 4 }, { kind: 'drone', charge: 4 }] },
      { turn: 10, units: [{ kind: 'warden', charge: 8 }, { kind: 'drone', charge: 5 }, { kind: 'drone', charge: 5 }, { kind: 'drone', charge: 5 }] },
      { turn: 13, units: [{ kind: 'drone', charge: 5 }, { kind: 'siphon', charge: 9 }, { kind: 'drone', charge: 5 }, { kind: 'drone', charge: 5 }, { kind: 'drone', charge: 5 }] },
      { turn: 16, units: [{ kind: 'warden', charge: 9 }, { kind: 'drone', charge: 5 }, { kind: 'warden', charge: 9 }, { kind: 'warden', charge: 9 }, { kind: 'warden', charge: 9 }] },
    ],
  },

  // The escalation test bed. Waves inject *charge as well as bodies*, so the
  // energy budget climbs during the fight — and every enemy destroyed climbs it
  // further, because the payload stays and the capacity does not. Succeeding
  // makes the board denser and more dangerous. See EXP-014.
  tide: {
    name: 'tide',
    waves: [
      { turn: 1,  charge: 6,  units: [{ kind: 'drone' }, { kind: 'drone' }] },
      { turn: 5,  charge: 6,  units: [{ kind: 'siphon' }] },
      { turn: 9,  charge: 8,  units: [{ kind: 'drone' }, { kind: 'drone' }] },
      { turn: 13, charge: 8,  units: [{ kind: 'warden' }] },
      { turn: 17, charge: 10, units: [{ kind: 'drone' }, { kind: 'siphon' }] },
      { turn: 21, charge: 12, units: [{ kind: 'warden' }, { kind: 'drone' }] },
    ],
  },

  // EXP-030. Built to force-feed: lobbers push charge into the player from
  // outside melee range, chasers pin, and the charge the player dumps to
  // survive is picked back up by hungry enemies and thrown again.
  // Five lobbers, re-derived in EXP-039. EXP-030b had *rejected* five as
  // unsurvivable — the strongest agent won 3% — but that was measured before
  // agents priced their own capacity. With a working instrument the same
  // content is the right answer at 63%. Nothing about the encounter changed;
  // the thing measuring it did.
  press: {
    name: 'press',
    waves: [
      { turn: 1, units: [{ kind: 'lobber', charge: 6 }, { kind: 'drone', charge: 3 }] },
      { turn: 5, units: [{ kind: 'lobber', charge: 6 }, { kind: 'drone', charge: 4 }] },
      { turn: 9, units: [{ kind: 'lobber', charge: 6 }, { kind: 'warden', charge: 8 }] },
      { turn: 13, units: [{ kind: 'lobber', charge: 6 }, { kind: 'drone', charge: 6 }] },
      { turn: 17, units: [{ kind: 'lobber', charge: 6 }, { kind: 'drone', charge: 7 }] },
    ],
  },

  // Siphon-heavy: isolates the board-as-bank / bait layer.
  garden: {
    name: 'garden',
    waves: [
      { turn: 1, units: [{ kind: 'siphon' }, { kind: 'siphon' }, { kind: 'drone' }] },
      { turn: 9, units: [{ kind: 'siphon' }] },
    ],
  },
};
