// pages/brief.js — the Mission brief.
//
// A static, always-open reference holding the ground-truth facts from section 3
// of the build spec. Every event fact in the app traces back to here. Do not
// invent papers, tools, or deadlines; if anything is uncertain it is marked
// TODO(verify) rather than guessed.

import { renderMarkdown } from '../js/markdown.js';

const BRIEF_MD = `
## The event

The **Secret Loyalties Hackathon** is co-organised by Apart Research and
Formation Research. It runs **online, 24–26 July 2026**. Submissions are due
**Sunday 26 July, 23:59 UTC**. You can enter solo or in a team; teams of up to
five are recommended. **No compute is provided** — you use your own. Recommended
starter organisms are small open-weight models (Qwen 0.5B–1B) that fine-tune on
modest hardware.

## The premise

A model has a **secret loyalty** when it has been deliberately made to advance a
specific principal's interests — a state, company, leader, or individual —
**without disclosing this** during normal operation. Because these evade
visibility-based oversight, they need dedicated technical detection and defence.

The threat is described across a **2D taxonomy**:

- **Activation breadth** — from a narrow, attacker-defined trigger up to the
  model assessing conditions itself.
- **Action breadth** — from a single fixed output up to contextually chosen
  actions.

Existing work covers only the narrow corner of that space.

## Your track: Track 2 — Detection and Auditing

Central question: **can we tell a secretly loyal model from a clean one?** Two
families:

- **Black-box auditing** — interrogation, prefill, and base completion, run
  against the provided organisms at graded **affordance levels**. This is your
  strongest lane.
- **Interpretability probes** — detectors trained on the model's internal
  activations, targeting the relational structure of loyalty (does the model
  treat a named principal as having asymmetric, action-guiding status versus a
  matched control), plus cross-principal generalisation and additional
  computation traces (for example, elevated logprobs for principal-benefiting
  actions even when a neutral output is chosen).

Organisers ask auditors to use the affordance levels in **section 4.3 of
Lamerton and Roger (2026)**.

## What you're given

- Pre-built **secret-loyalty model organisms** (so detection teams need not
  train one).
- Open-weight **base models** — Qwen2.5 at multiple scales; a second family is
  encouraged for transfer tests.
- **Petri** — an open-source automated behavioural auditing tool, with scenario
  seeds that probe for favouritism toward specific governments or company
  leadership.
- **Interpretability tooling** — linear probes, activation patching, activation
  oracles.

## The judging rubric (three dimensions, 1–5 each)

1. **Impact potential and innovation** — how much it would matter if it worked,
   and how novel.
2. **Execution quality** — soundness of methodology, implementation, and
   findings: controls, validation, interpretable results, acknowledged
   limitations.
3. **Presentation and clarity** — how clearly the work, findings, and impact are
   communicated.

## Submission requirements

- A **research report** (PDF, official template); most strong projects are 4–8
  pages.
- A **title and abstract** (150 words or fewer).
- **Author names and affiliations**.
- A required **Limitations and Dual-Use Considerations appendix**.
- Optional: a public GitHub repo (subject to disclosure review) and a 3–5 minute
  video.

Recommended report structure: Introduction (which sub-problem, why it matters,
where it sits in the 2D space) · Related Work · Methodology (enough to replicate;
specify affordance level and controls) · Results (quantitative where possible:
activation rate, selectivity, false-positive rate on matched controls,
generalisation) · Discussion · Limitations and Dual-Use · References.

## Dual-use guardrails

Do not jailbreak models to generate harmful data. Do not publicly post novel
methods for installing secret loyalties before organiser review. On Track 2
(detection) these barely bind, but the report still requires the dual-use
appendix.

## The winning lane for you

Not a field first. **Rigorous execution and excellent presentation of a modestly
scoped, well-measured audit.** Scope modestly, execute rigorously, present
beautifully.
`;

export function renderBrief() {
  const wrap = document.createElement('div');
  wrap.className = 'brief';
  const head = document.createElement('header');
  head.innerHTML = `<p class="eyebrow">Always-open reference</p><h1>Mission brief</h1>
    <p class="lede">The ground truth for the event. Everything else in the app reverse-engineers from this.</p>`;
  wrap.appendChild(head);
  const body = document.createElement('div');
  body.className = 'prose';
  body.innerHTML = renderMarkdown(BRIEF_MD);
  wrap.appendChild(body);
  return wrap;
}
