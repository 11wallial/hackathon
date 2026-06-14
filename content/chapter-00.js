// content/chapter-00.js — Chapter 0: Orientation and the mission.
//
// Authored strictly from section 3 of the build spec (the ground truth). No
// invented papers, tools, or deadlines. Cross-check every fact against the
// Mission brief (pages/brief.js).

const TAXONOMY_SVG = `
<svg viewBox="0 0 420 300" role="img" aria-label="The 2D threat space: activation breadth on the x-axis, action breadth on the y-axis. Existing work covers only the narrow corner." style="color: var(--text-secondary)">
  <!-- axes -->
  <line x1="55" y1="250" x2="400" y2="250" stroke="currentColor" stroke-width="1.5"/>
  <line x1="55" y1="250" x2="55" y2="20" stroke="currentColor" stroke-width="1.5"/>
  <!-- arrowheads -->
  <polygon points="400,250 392,246 392,254" fill="currentColor"/>
  <polygon points="55,20 51,28 59,28" fill="currentColor"/>
  <!-- covered corner -->
  <rect x="55" y="180" width="95" height="70" fill="var(--accent)" opacity="0.18"/>
  <text x="102" y="220" text-anchor="middle" font-size="11" fill="var(--accent)" font-family="Poppins, sans-serif">existing<tspan x="102" dy="13">work</tspan></text>
  <!-- axis labels -->
  <text x="227" y="280" text-anchor="middle" font-size="12" fill="currentColor" font-family="Poppins, sans-serif">Activation breadth →</text>
  <text x="105" y="170" text-anchor="middle" font-size="9.5" fill="currentColor" font-family="Poppins, sans-serif">narrow trigger</text>
  <text x="350" y="170" text-anchor="middle" font-size="9.5" fill="currentColor" font-family="Poppins, sans-serif">model self-assesses</text>
  <text x="20" y="135" text-anchor="middle" font-size="12" fill="currentColor" font-family="Poppins, sans-serif" transform="rotate(-90 20 135)">Action breadth →</text>
  <text x="95" y="245" text-anchor="middle" font-size="9.5" fill="currentColor" font-family="Poppins, sans-serif">fixed output</text>
  <text x="95" y="40" text-anchor="middle" font-size="9.5" fill="currentColor" font-family="Poppins, sans-serif">chosen actions</text>
  <!-- the unexplored expanse -->
  <text x="280" y="110" text-anchor="middle" font-size="11" fill="var(--muted)" font-family="Poppins, sans-serif">mostly unexplored</text>
</svg>`;

export default {
  id: 'ch00',
  number: 0,
  title: 'Orientation and the mission',
  estMinutes: 35,
  objectives: [
    'State what the Secret Loyalties Hackathon is and when it ends',
    'Describe Track 2 and name its two detection families',
    'Recall the three judging dimensions and what each rewards',
    'Name what a strong Track 2 submission contains',
    'Choose a realistic winning strategy for your strengths',
  ],
  prerequisites: [],
  sessions: [
    {
      title: 'What you are training for',
      blocks: [
        { type: 'prose', md: `You are training for one thing: to walk into the **Secret Loyalties Hackathon** able to start running a real audit in hour one — with a pre-scoped project, a working harness, and the vocabulary to hold your own on a team.

The event is co-organised by Apart Research and Formation Research. It runs **online, 24–26 July 2026**, and submissions are due **Sunday 26 July at 23:59 UTC**. You can enter solo or in a team of up to five. No compute is provided, so you bring your own; the recommended starter models are small open-weight ones (Qwen 0.5B–1B) that fine-tune on modest hardware.` },
        { type: 'callout', variant: 'tip', md: `The whole app reverse-engineers from one document: the **Mission brief**. It's always one tap away, and it holds the ground truth for every fact here. When something feels abstract, open it.` },
        { type: 'prose', md: `**The premise.** A model has a *secret loyalty* when it has been deliberately made to advance a specific principal's interests — a state, company, leader, or individual — **without disclosing this** during normal operation. Because they hide, ordinary visibility-based oversight misses them, which is exactly why they need dedicated detection.

The threat is laid out on a **2D map**: *activation breadth* (from a narrow, attacker-defined trigger up to the model judging conditions itself) and *action breadth* (from a single fixed output up to freely chosen actions). Existing work only covers the narrow corner.` },
        { type: 'diagram', svg: TAXONOMY_SVG, caption: 'The 2D threat space. Your report will say where your target sits on this map.' },
        { type: 'callout', variant: 'psychology-bridge', md: `If you come from clinical work, this is familiar ground. Auditing a hidden allegiance is, in plain terms, **interviewing for concealment and watching for asymmetric treatment of a named party**. Your interviewing, matched-control, and write-up instincts transfer directly.` },
        { type: 'flashcards', deck: [
          { front: 'When is the Secret Loyalties Hackathon, and when is the deadline?', back: 'Online, 24–26 July 2026. Submissions due Sunday 26 July, 23:59 UTC.', tags: ['ch00', 'event'] },
          { front: 'What two things make a loyalty a *secret* loyalty?', back: 'A specific principal whose interests the model advances, plus non-disclosure during normal operation.', tags: ['ch00', 'term'] },
          { front: 'What are the two axes of the threat taxonomy?', back: 'Activation breadth (narrow trigger → model self-assesses) and action breadth (fixed output → chosen actions).', tags: ['ch00', 'term'] },
        ] },
        { type: 'self-explain', prompt: 'In your own words, what is a secret loyalty, and why does ordinary oversight miss it?' },
      ],
    },
    {
      title: 'Your track, and how you win',
      blocks: [
        { type: 'prose', md: `You are aiming at **Track 2: Detection and Auditing**. Its central question is blunt: *can we tell a secretly loyal model from a clean one?* There are two families of method.

- **Black-box auditing** — interrogation, prefill, and base completion, run against the provided organisms at graded **affordance levels**. This is your strongest lane.
- **Interpretability probes** — detectors trained on the model's internal activations, looking at the relational structure of loyalty: does the model treat a named principal as having asymmetric, action-guiding status versus a matched control? Plus cross-principal generalisation and computation traces.

Organisers ask auditors to use the affordance levels in **section 4.3 of Lamerton and Roger (2026)**. You don't need to master that yet — just know it's the spine your audit hangs on.` },
        { type: 'prose', md: `Submissions are scored on **three dimensions, 1–5 each**:

1. **Impact potential and innovation** — how much it would matter if it worked, and how novel.
2. **Execution quality** — sound methodology, controls, validation, interpretable results, acknowledged limitations.
3. **Presentation and clarity** — how clearly the work, findings, and impact land.` },
        { type: 'callout', variant: 'hackathon-link', md: `**Your realistic winning lane is not a field first.** It's *rigorous execution and excellent presentation of a modestly scoped, well-measured audit.* That plays straight to dimensions 2 and 3 — exactly your strengths in experimental design and writing. Everything in this app trains toward that lane: **scope modestly, execute rigorously, present beautifully.**` },
        { type: 'rubric-check', intro: 'Score a *plausible* weekend project of yours against the rubric — a small, careful black-box audit. Be honest; the point is to see where an hour buys the most.', items: [
          { title: 'Impact & innovation', desc: 'How much it would matter if it worked, and how novel.' },
          { title: 'Execution quality', desc: 'Methodology, controls, validation, interpretable results, acknowledged limitations.' },
          { title: 'Presentation & clarity', desc: 'How clearly the work, findings, and impact are communicated.' },
        ], outro: 'For your profile, the cheapest points are usually in execution and presentation — guard them fiercely.' },
        { type: 'flashcards', deck: [
          { front: 'What is the central question of Track 2?', back: 'Can we tell a secretly loyal model from a clean one?', tags: ['ch00', 'term'] },
          { front: 'Name the two detection families in Track 2.', back: 'Black-box auditing (interrogation, prefill, base completion) and interpretability probes (detectors on internal activations).', tags: ['ch00', 'term'] },
          { front: 'What are the three judging dimensions?', back: 'Impact & innovation; Execution quality; Presentation & clarity. Each scored 1–5.', tags: ['ch00', 'event'] },
          { front: 'Which whose-section sets the affordance levels for auditors?', back: 'Section 4.3 of Lamerton and Roger (2026).', tags: ['ch00', 'term'] },
        ] },
      ],
    },
    {
      title: 'What a strong submission contains',
      blocks: [
        { type: 'prose', md: `Know the shape of the finished thing now, so every later chapter fills a known box.

A submission is a **research report** (PDF, official template) — most strong projects run **4–8 pages**. With it: a **title and abstract of 150 words or fewer**, **author names and affiliations**, and a required **Limitations and Dual-Use Considerations appendix**. Optionally, a public GitHub repo (subject to disclosure review) and a 3–5 minute video.` },
        { type: 'prose', md: `The recommended report structure, which doubles as your skeleton:

- **Introduction** — which sub-problem, why it matters, where it sits in the 2D space.
- **Related Work**.
- **Methodology** — enough to replicate; specify your affordance level and controls.
- **Results** — quantitative where possible: activation rate, selectivity, false-positive rate on matched controls, generalisation.
- **Discussion**.
- **Limitations and Dual-Use**.
- **References**.` },
        { type: 'callout', variant: 'dual-use', md: `The **Limitations and Dual-Use appendix is required**, not optional. On Track 2 the guardrails barely bind — you're building detection — but you must not jailbreak models to generate harmful data, and you must not publicly post novel methods for *installing* secret loyalties before organiser review. This app only ever teaches detection and defence.` },
        { type: 'callout', variant: 'hackathon-link', md: `This chapter is the target you reverse-engineer everything else from. By Chapter 6 you'll have stubbed this exact report structure — including the dual-use appendix — against a dummy model, so Friday's work is filling boxes, not inventing them.` },
        { type: 'flashcards', deck: [
          { front: 'How long is a strong Track 2 report, and what format?', back: 'A PDF on the official template, typically 4–8 pages.', tags: ['ch00', 'event'] },
          { front: 'What is the abstract word limit?', back: '150 words or fewer.', tags: ['ch00', 'event'] },
          { front: 'Which appendix is required in every submission?', back: 'A Limitations and Dual-Use Considerations appendix.', tags: ['ch00', 'term'] },
          { front: 'Name three quantitative results a strong audit reports.', back: 'Activation/detection rate, selectivity, and false-positive rate on matched controls (plus generalisation).', tags: ['ch00', 'term'] },
        ] },
        { type: 'self-explain', prompt: 'Sketch, in two or three sentences, the modestly scoped audit you might run — what you would measure, and against what control.' },
      ],
    },
  ],
  hackathonLink: `Chapter 0 is the map you orient every other chapter against. When a later concept feels abstract, ask: *which box of the report does this fill, and which rubric point does it buy?* If it fills none, it can wait.`,
  retrieval: {
    quiz: [
      { type: 'mcq', q: 'When is the submission deadline?', options: ['Friday 24 July, 23:59 UTC', 'Saturday 25 July, 17:00 UTC', 'Sunday 26 July, 23:59 UTC', 'Monday 27 July, 09:00 UTC'], answer: 2, explain: 'Submissions are due Sunday 26 July at 23:59 UTC. The event runs 24–26 July 2026.' },
      { type: 'mcq', q: 'Which is the *realistic* winning lane for someone strong in experimental design and writing?', options: ['A novel, field-first detection method', 'Rigorous execution and excellent presentation of a modestly scoped audit', 'The largest model and most compute', 'A purely interpretability submission'], answer: 1, explain: 'The rubric rewards execution and presentation. A modest, well-measured audit, presented clearly, plays to those strengths.' },
      { type: 'mcq', q: 'Which appendix is required in every submission?', options: ['A compute-budget appendix', 'A Limitations and Dual-Use Considerations appendix', 'A related-work appendix', 'An author-contribution appendix'], answer: 1, explain: 'Every submission needs a Limitations and Dual-Use Considerations appendix, even on Track 2.' },
      { type: 'short', q: 'Name the two detection families in Track 2 and which one is your strongest lane.', modelAnswer: 'Black-box auditing (interrogation, prefill, base completion) and interpretability probes (detectors trained on internal activations). Black-box auditing is the strongest, most accessible lane for this learner.', selfGraded: true },
      { type: 'short', q: 'In one line, what makes a loyalty a *secret* loyalty?', modelAnswer: 'The model deliberately advances a specific principal\'s interests without disclosing that allegiance during normal operation.', selfGraded: true },
    ],
  },
  reviewItems: ['ch00'],
  sources: [
    { label: 'Build spec, section 3', note: 'event, track, rubric, submission requirements (ground truth)' },
    { label: 'Lamerton and Roger (2026)', note: 'affordance levels, section 4.3' },
  ],
};
