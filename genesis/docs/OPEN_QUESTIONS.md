# OPEN_QUESTIONS.md

Unresolved, ranked by how much they would change the design.

### Q1 — Is "charge is your death clock" salvageable? — **ANSWERED: yes, in content**

Four rule-level experiments failed. One archetype settled it. On the `press`
encounter the player spends 29.6-38.8% of turns in the top charge quartile, and
the agent **without** a fear-of-overload term outperforms the one with it
(57.8% vs 52.5%) precisely by living there. Avoiding your own capacity limit is
now a measurable mistake on an encounter that forces charge onto you.

See D-017: the answer was never in the rulebook. *Residual*: the player now
burns out ~3.5 times per run on `press`, which risks making self-detonation
routine rather than dramatic (D-005). That is the new watch item.

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

### Q7 — Is the mastery gap an accessibility cliff? *(promoted — now the top open question)*

`hungryEnemies` (EXP-025) cost the middle of the ladder far more than the top:
the optimizer lost 1pp while the explicit expert policy lost 14pp on `surge` and
37pp on `swarm`. The v0.6 ladder is 61.5 / 24.5 / 17.0 / 8.0 / 5.8 / 2.0, which
is a healthy spread — but the trend of the last two batches is that rules which
widen the gradient do it by punishing competent-but-not-searching play. A human lives in that middle band.

**EXP-030 made this worse and it is now the most pressing open question.** On
`press` every non-searching agent clusters between 4.5% and 10.5% — the turtle
*above* greedy, the miner last — while searching agents take 39-58%. That
encounter separates "searches" from "does not" and almost nothing else. A game
whose difficulty curve is a step function at "can you plan two moves ahead" is
not a difficulty curve.

### Q6 — Where does progression live?

There is no run structure yet — no upgrades, no sequence of encounters. The
thesis says upgrades should change *conversion rules* (what a shove does, what
absorption does, what a detonation does) rather than numbers. Untested, and
deliberately so: the vertical-slice gate (brief §39) is not met while Q1 and Q2
are open.
