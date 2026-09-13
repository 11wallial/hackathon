# OVERLOAD — Project Genesis

An autonomous game-design laboratory: a playable prototype plus the experimental
apparatus that produced it. The game is the experimental organism; `docs/` is the
lab notebook.

## The game in four sentences

You stand on a closed ring of twelve nodes. Every unit, you included, has one
number — **charge** — which is its ammunition, its power, and its death clock at
once, and a unit is destroyed when its charge goes **over** capacity rather than
down to zero. Charge is **conserved**: nothing is created or destroyed, so the
only way to hurt something is to give it yours. You have two verbs: step, and
shove.

Picking charge up off the floor fills you to capacity and leaves the rest, so
nothing ever dies by accident — **only a deliberate transfer can kill**. That
makes the floor a loading mechanism rather than a weapon: fatten a target from a
pile until it runs hot, then tip it over with one point of your own.

## Play it

No build step, no dependencies. Serve the repository root and open `/genesis/`:

```bash
python3 -m http.server 8000    # from the repository root
# then open http://localhost:8000/genesis/
```

Keys: `A`/`D` step · `1`–`4` choose an amount · `Q`/`S`/`E` shove left / drop /
right · `Space` end turn · `R` new run. Hovering any action previews what it
will actually do, by forking the real game state and running the real rules —
so the preview cannot lie to you.

## Run the laboratory

```bash
npm test                # 8 invariant tests (conservation, determinism, cloning)
node exp/batch1.js      # the batch that found the core strategy
node exp/ccr.js         # the energy-budget phase sweep
node tools/trace.js 1003 optimizer    # human-readable replay of one seed
```

Everything is seeded and deterministic; every number quoted in `docs/` is
reproducible from these commands.

## Read the notebook

Start with **`docs/DISCOVERIES.md`** — eleven principles that were *earned*,
each naming its evidence. Then:

| File | What it holds |
|---|---|
| `docs/PROJECT_STATE.md` | what exists, what is proven, and the top defect |
| `docs/DESIGN_THESIS.md` | current belief + two dated revisions, with what was falsified |
| `docs/EXPERIMENTS.md` | 19 experiments, hypotheses pre-registered before each run |
| `docs/GRAVEYARD.md` | seven killed mechanics and exactly why each failed |
| `docs/OPEN_QUESTIONS.md` | the six unresolved questions, ranked |
| `docs/NEXT_EXPERIMENTS.md` | the ranked queue |
| `docs/MECHANIC_GENEALOGY.md` | where each mechanic came from and what it mutated into |
| `docs/METRICS.md` | telemetry definitions |

## Two findings worth the click

**The winning strategy was an accident.** `SHOVE` was designed as the attack and
loose charge on the floor was a side effect. Measurement said the reverse: 74%
of the searching agent's kills came from enemies walking into piles it had
placed, and the agent that only ever attacked directly won 6% of the time.

**Three rule fixes in a row failed because the problem was arithmetic.** The
encounter contained 17 charge and destroying every enemy required delivering 47.
No rule change could fix that; computing the ratio took five minutes and
reframed the entire design.

## Architecture

`sim/` is a pure, dependency-free rules engine with no presentation code in it,
and its entire mutable rule set lives in `sim/config.js` as data — experiments
are config overrides, never code edits. The playable client imports those exact
modules, so play and measurement cannot drift apart. The RNG's state lives
inside the game state, which is what lets lookahead agents fork the world.

> Note on tooling: the brief assumed Godot 4, which this environment does not
> have. The binding constraint here is headless simulation throughput — a single
> batch plays around 4,000 encounters — so the prototype is zero-build ES
> modules that run unmodified in Node and in a browser. `sim/` is engine-agnostic
> and a Godot front end could drive it as-is. See `docs/PROJECT_STATE.md`.
