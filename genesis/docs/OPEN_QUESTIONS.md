# OPEN_QUESTIONS.md

Unresolved, ranked by how much they would change the design.

### Q1 — Is "charge is your death clock" salvageable at all? *(highest stakes)*

Three experiments (EXP-008, 015, 017) failed to make the player occupy the
dangerous end of their own capacity, and D-008 explains why: no reward justifies
a catastrophic threshold. D-009 then showed the obvious pressure lever points
backwards.

Either we find a mechanism that *forces* charge onto the player faster than they
can dispose of it, or we accept that the player's overload is an edge case and
the real drama lives in the enemies' capacity, not the player's. The second
answer is legitimate — the game plays well already — but it means rewriting a
third of the thesis. **Do not tune this further; decide it.**

### Q2 — What is the irreversible move that ends a deadlock?

D-010: 36% of encounters are a fixed point immune to time. Candidates, cheapest
first: a spill on transfer (part of every shove lands on the floor instead of
the target); a stagger (a unit that was shoved cannot shove back this round);
asymmetric throughput; or replacing "clear the board" with an objective that
cannot be stalled. Each one is a different game — this is a fork, not a tweak.

### Q3 — Should absorption be a choice?

It is currently automatic, which is what makes the floor a hazard and what makes
D-007's fix (`absorbCap`) legible. But it also means the player never decides
"do I want this". An opt-in `TAKE n` action would add a decision and a verb.
Does it earn its complexity, or does it just add a button to a solved problem?

### Q4 — Is the optimizer's 41.7% the right difficulty, and is it the right *agent*?

A 2-ply search with a hand-written evaluation is a proxy for a good human, not a
good human. Its evaluation contains a fear-of-overload term, which means it is
not independent evidence for Q1. A search with a purely outcome-based evaluation
would be a fairer instrument.

### Q5 — Does any of this survive a second encounter shape?

Every batch-3-onward result is from one encounter (`surge`) on a 12-node ring.
`probe`, `swarm` and `garden` exist and are untested under v0.5 rules. Findings
that do not replicate across encounter shapes are findings about `surge`.

### Q6 — Where does progression live?

There is no run structure yet — no upgrades, no sequence of encounters. The
thesis says upgrades should change *conversion rules* (what a shove does, what
absorption does, what a detonation does) rather than numbers. Untested, and
deliberately so: the vertical-slice gate (brief §39) is not met while Q1 and Q2
are open.
