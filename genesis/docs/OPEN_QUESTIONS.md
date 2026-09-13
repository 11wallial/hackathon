# OPEN_QUESTIONS.md

Unresolved, ranked by how much they would change the design.

### Q1 — Is "charge is your death clock" salvageable? *(highest stakes, now better posed)*

Four experiments (EXP-008, 015, 017, and dissolution's side effect) failed to
make the player occupy the dangerous end of their capacity — but EXP-029 then
showed that evidence was collected with an agent explicitly told to fear
overload. The unbiased instrument plays near overload **9.1%** of turns on
`surge` and **0.0%** on drone-only `swarm`.

That sharpens the question rather than closing it. The danger band is occupied
exactly where the encounter forces charge onto the player, which is what D-008
prescribed. So the live question is no longer "can it work" but **"which
encounter compositions force enough charge onto the player, and is 9% enough to
feel like a clock?"** That is answerable by building an encounter designed to
force-feed and measuring it — not by another rule tweak.

### Q2 — What ends a deadlock? — **ANSWERED** (EXP-022, EXP-025)

It was never irreversibility. The deadlock was a traffic jam of spent bodies
(D-012), and both proposed fixes failed because they attacked an oscillation
that was not happening. Dissolving units that hold no charge took timeouts
40.8% → 24.5%. *Residual*: 24.5% still do not resolve, and we have not traced
one of those. Do that before proposing anything.

### Q3 — Should absorption be a choice?

It is currently automatic, which is what makes the floor a hazard and what makes
D-007's fix (`absorbCap`) legible. But it also means the player never decides
"do I want this". An opt-in `TAKE n` action would add a decision and a verb.
Does it earn its complexity, or does it just add a button to a solved problem?

### Q4 — Is the optimizer the right *agent*? — **ANSWERED, and it mattered**

No, not on its own. EXP-029 built the unbiased instrument and it changed the
answer to the question it was built to check: removing the fear-of-overload term
raised near-overload play 3.6x and flipped `swarm` from 79% to 99%. Two
instruments are now kept permanently in the panel (D-016), and D-008 carries a
correction.

*Residual*: the difficulty half of the question is now live in the other
direction — the strongest agent wins 78%, and `surge` has not been re-tuned
since the agent got substantially better.

### Q5 — Does any of this survive a second encounter shape? — **PARTLY ANSWERED**

EXP-024 ran the panel across all four encounters and immediately caught a
degenerate walkover (turtle 99% on `swarm`) that was invisible on `surge`. It is
now a standing gate before adopting any rule (D-014).

What it also revealed: `probe` (CCR 0.36) and `garden` (CCR 0.17) are
unwinnable under every configuration — they are pre-CCR test beds from v0.1 and
should be relabelled as low-CCR controls rather than treated as content. We have
therefore validated across *two* real shapes, not four. Ring sizes 8 and the
rest of the geometry sweep are still untested.

### Q7 — Is the mastery gap becoming an accessibility problem? *(new)*

`hungryEnemies` (EXP-025) cost the middle of the ladder far more than the top:
the optimizer lost 1pp while the explicit expert policy lost 14pp on `surge` and
37pp on `swarm`. The v0.6 ladder is 61.5 / 24.5 / 17.0 / 8.0 / 5.8 / 2.0, which
is a healthy spread — but the trend of the last two batches is that rules which
widen the gradient do it by punishing competent-but-not-searching play. A human
lives in that middle band. Worth watching, not yet acting on.

### Q6 — Where does progression live?

There is no run structure yet — no upgrades, no sequence of encounters. The
thesis says upgrades should change *conversion rules* (what a shove does, what
absorption does, what a detonation does) rather than numbers. Untested, and
deliberately so: the vertical-slice gate (brief §39) is not met while Q1 and Q2
are open.
