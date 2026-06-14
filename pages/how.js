// pages/how.js — "How this works", the learning method behind the app.

import { renderMarkdown } from '../js/markdown.js';

const HOW_MD = `
This app is built on a handful of well-evidenced learning techniques. Knowing
the method is meant to make you trust it — and to make the short sessions feel
purposeful rather than arbitrary.

## Recall, don't reread

Learning is *retrieval*, not rereading. Every chapter ends with a short quiz,
and flashcards always ask you to attempt the answer before revealing it. The
small effort of recalling is what makes a fact stick.

## Spaced repetition

A single review deck schedules flashcards with a lightweight SM-2 style
algorithm, so facts resurface across the weeks and are durable by 24 July.
Cards you find easy come back rarely; cards you miss come back soon.

## Interleaving

The review deck deliberately *mixes* cards across chapters and across the two
detection families rather than blocking by topic. Mixing is harder in the
moment — and that is the point: it trains you to tell methods apart.

## Say it back

Each chapter has a "say it back" prompt. Writing an explanation in your own
words (elaboration) forces you to connect ideas rather than recognise them.
Your words are saved so later chapters can show them back for revision.

## Build, don't just read

Hands-on labs and a build log turn understanding into execution readiness. If a
chapter can't end in either a recall or something built, it's the wrong chapter.

## Calm by design

Sessions are short (15–25 minutes). Difficulty rises on purpose but never piles
up. There's always exactly one clear next action, a quiet progress indicator,
and a gentle streak — no notifications, no nagging, no dark patterns.
`;

export function renderHowItWorks() {
  const wrap = document.createElement('div');
  const head = document.createElement('header');
  head.innerHTML = `<p class="eyebrow">The method</p><h1>How this works</h1>`;
  wrap.appendChild(head);
  const body = document.createElement('div');
  body.className = 'prose';
  body.innerHTML = renderMarkdown(HOW_MD);
  wrap.appendChild(body);
  return wrap;
}
