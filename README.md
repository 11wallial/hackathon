# Secret Loyalties — Track 2 Trainer

A calm, self-paced training web app that prepares one learner to be a
frontrunner in the **Detection and Auditing (Track 2)** stream of the
[Secret Loyalties Hackathon](https://www.apartresearch.com/) (24–26 July 2026).

It's a static site — no build step, no backend, no accounts. Progress lives in
your browser's `localStorage`, private to your device.

> **Status:** Milestone 0 (engine + design system) and Milestone 1 (Chapter 0 +
> Mission brief) are complete. Chapters 1–9 are authored one at a time in later
> milestones — the app is built so each new chapter is a single data file.

## Run it locally

No tooling required. Serve the folder with any static server:

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

(Open it through a server, not `file://` — the app uses ES modules.)

## What's here

- **Dashboard** — pick up where you left off, overall progress, a non-addictive
  streak, due-review count, and a build log.
- **Chapter 0 — Orientation and the mission** — what the event is, what Track 2
  is, the three-part rubric (with an interactive self-check), and what a strong
  submission contains.
- **Mission brief** — an always-open reference of the ground-truth event facts.
- **Review** — a global spaced-repetition deck (lightweight SM-2) that
  interleaves flashcards across chapters so facts stay durable.
- **Glossary** — searchable, populated from the flashcards you've met.
- **How this works** — the learning science behind the app.

Light and dark themes are supported; the toggle (top-right) cycles
system → light → dark and is remembered.

## Add a chapter

The renderer is generic and data-driven. Adding a chapter is two steps:

1. Create `content/chapter-NN.js`, exporting one object per the schema in
   `content/chapter-00.js` (sessions → blocks, an optional lab, a retrieval quiz,
   sources). Supported block types: `prose`, `callout`, `diagram`, `flashcards`,
   `quiz`, `self-explain`, `checklist`/`lab`, `code`, `rubric-check`.
2. In `content/index.js`, flip that chapter's entry to `available: true` and add
   its `load: () => import('./chapter-NN.js')`.

Nothing else changes — the dashboard, nav, review deck, and progress tracking
all pick it up automatically.

## Project layout

```
index.html              app shell
css/app.css             design system (light + dark)
js/app.js               router, dashboard, shell chrome, theme
js/storage.js           fault-tolerant localStorage wrapper (key: slh_trainer_v1)
js/state.js             pub/sub store + progress/streak helpers
js/markdown.js          tiny dependency-free markdown renderer
js/render.js            generic block + chapter renderer
js/components/          flashcards, quiz, checklist, self-explain, review,
                        progress, spaced (SM-2), rubric-check
content/index.js        chapter registry
content/chapter-00.js   Chapter 0
pages/                  brief, how, glossary
assets/fonts/           self-hosted Poppins + Lora (OFL)
.github/workflows/      Pages deploy
```

## Deploy to GitHub Pages

The site deploys from the repository root via GitHub Actions
(`.github/workflows/pages.yml`) on every push to `main`. To enable it once:

1. Push to `main`.
2. In the repo, go to **Settings → Pages → Build and deployment** and set
   **Source: GitHub Actions**.

The workflow uploads the repo root as the Pages artifact and deploys it; no build
step is involved.

## Privacy and scope

No backend, no analytics, no network calls to any model. The training is local
and private. The app teaches detection and defence only — consistent with the
event's dual-use guardrails, it contains no instructions for installing secret
loyalties or generating harmful data.
