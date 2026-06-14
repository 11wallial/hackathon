// render.js — the generic, data-driven block and chapter renderer.
//
// Every chapter is plain data (see content/chapter-00.js). This module turns it
// into DOM. Adding a chapter never requires touching this file — only the block
// types here are ever used. Unknown block types render a visible placeholder
// rather than failing silently.

import { renderMarkdown } from './markdown.js';
import { renderFlashcards } from './components/flashcards.js';
import { renderQuiz } from './components/quiz.js';
import { renderChecklist } from './components/checklist.js';
import { renderSelfExplain } from './components/self-explain.js';
import { renderRubricCheck } from './components/rubric-check.js';
import { renderTwoDPlacement } from './components/two-d-placement.js';
import { renderTermInTheWild } from './components/term-in-the-wild.js';
import {
  markSectionViewed, markInteractiveDone, setChapterComplete, getState,
} from './state.js';
import { chapterPercent, isChapterComplete, progressBar } from './components/progress.js';

const CALLOUT_LABELS = {
  'hackathon-link': 'Hackathon link',
  'psychology-bridge': 'Psychology bridge',
  'dual-use': 'Dual-use',
  tip: 'Tip',
  warning: 'Watch out',
};

// ---- Block dispatch ---------------------------------------------------

export function renderBlock(block, ctx) {
  switch (block.type) {
    case 'prose': return prose(block);
    case 'callout': return callout(block);
    case 'diagram': return diagram(block);
    case 'code': return code(block);
    case 'flashcards': return renderFlashcards(block.deck, { chId: ctx.chId, interactiveKey: ctx.key('flashcards'), extraTags: ctx.chTags });
    case 'quiz': return renderQuiz(block, { chId: ctx.chId, interactiveKey: ctx.key('quiz') });
    case 'self-explain': return renderSelfExplain(block, { chId: ctx.chId });
    case 'checklist':
    case 'lab': return renderChecklist(block, { chId: ctx.chId, labKey: ctx.chId + '_' + ctx.key('lab') });
    case 'rubric-check': return renderRubricCheck(block, { chId: ctx.chId, interactiveKey: ctx.key('rubric') });
    case 'interactive': return renderInteractive(block, ctx);
    default: return placeholder(block);
  }
}

// Custom interactives dispatch on block.component so new ones slot in without
// adding renderer cases. Unknown components fall through to the placeholder.
function renderInteractive(block, ctx) {
  switch (block.component) {
    case 'TwoDPlacement':
      return renderTwoDPlacement(block, { chId: ctx.chId, interactiveKey: ctx.key('interactive') });
    case 'TermInTheWild':
      return renderTermInTheWild(block, { chId: ctx.chId, interactiveKey: ctx.key('interactive') });
    default:
      return placeholder({ type: 'interactive:' + (block.component || 'unknown') });
  }
}

function prose(block) {
  const el = document.createElement('div');
  el.className = 'prose';
  el.innerHTML = renderMarkdown(block.md);
  return el;
}

function callout(block) {
  const variant = block.variant || 'tip';
  const el = document.createElement('div');
  el.className = 'callout callout-' + variant;
  el.innerHTML = `
    <div class="callout-label"><span class="dot"></span>${CALLOUT_LABELS[variant] || 'Note'}</div>
    ${renderMarkdown(block.md)}`;
  return el;
}

function diagram(block) {
  const fig = document.createElement('figure');
  fig.className = 'diagram';
  fig.innerHTML = block.svg || '';
  if (block.caption) {
    const cap = document.createElement('figcaption');
    cap.textContent = block.caption;
    fig.appendChild(cap);
  }
  return fig;
}

function code(block) {
  const el = document.createElement('div');
  el.className = 'codeblock';
  const head = document.createElement('div');
  head.className = 'codeblock-head';
  head.innerHTML = `<span>${escape(block.lang || 'code')}</span>`;
  const copy = document.createElement('button');
  copy.className = 'copy-btn';
  copy.type = 'button';
  copy.textContent = 'Copy';
  copy.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(block.code || ''); copy.textContent = 'Copied'; }
    catch (e) { copy.textContent = 'Select & copy'; }
    setTimeout(() => { copy.textContent = 'Copy'; }, 1500);
  });
  head.appendChild(copy);
  el.appendChild(head);
  const pre = document.createElement('pre');
  const c = document.createElement('code');
  c.textContent = block.code || '';
  pre.appendChild(c);
  el.appendChild(pre);
  if (block.explanation) {
    const ex = document.createElement('div');
    ex.className = 'prose';
    ex.style.padding = '0.4rem 1rem 0.9rem';
    ex.innerHTML = renderMarkdown(block.explanation);
    el.appendChild(ex);
  }
  return el;
}

function placeholder(block) {
  const el = document.createElement('div');
  el.className = 'callout callout-warning';
  el.innerHTML = `<div class="callout-label"><span class="dot"></span>Unrecognised block</div><p class="text-secondary">Block type <code>${escape(block.type)}</code> isn't supported yet.</p>`;
  return el;
}

// ---- Full chapter -----------------------------------------------------

export function renderChapter(chapter) {
  const root = document.createElement('article');
  root.className = 'chapter';

  // Header.
  const header = document.createElement('header');
  header.innerHTML = `
    <p class="eyebrow">Chapter ${chapter.number} · ${chapter.estMinutes || '—'} min</p>
    <h1>${escape(chapter.title)}</h1>`;
  root.appendChild(header);

  // Progress bar.
  const pct = chapterPercent(chapter);
  const pwrap = document.createElement('div');
  pwrap.style.margin = '0.4rem 0 1.6rem';
  pwrap.appendChild(progressBar(pct));
  root.appendChild(pwrap);

  // Objectives.
  if (chapter.objectives && chapter.objectives.length) {
    const obj = document.createElement('div');
    obj.className = 'objectives';
    obj.innerHTML = `<div class="rail-label">By the end you can</div><ul>${chapter.objectives.map((o) => `<li>${escape(o)}</li>`).join('')}</ul>`;
    root.appendChild(obj);
  }

  const chTags = chapter.reviewItems || [chapter.id];

  // Sessions.
  (chapter.sessions || []).forEach((session, si) => {
    const sec = document.createElement('section');
    sec.className = 'session';
    const sid = 's' + si;
    if (session.title) {
      const h = document.createElement('h2');
      h.className = 'session-title';
      h.textContent = session.title;
      sec.appendChild(h);
    }
    let counter = {};
    const ctx = {
      chId: chapter.id,
      chTags,
      key: (kind) => {
        counter[kind] = (counter[kind] || 0);
        const k = `${sid}_${kind}_${counter[kind]}`;
        counter[kind] += 1;
        return k;
      },
    };
    (session.blocks || []).forEach((block) => {
      sec.appendChild(renderBlock(block, ctx));
    });
    root.appendChild(sec);

    // Mark the section viewed once it is on screen.
    observeViewed(sec, () => markSectionViewed(chapter.id, sid));
  });

  // Chapter-level lab.
  if (chapter.lab) {
    const sec = document.createElement('section');
    sec.className = 'session';
    sec.appendChild(renderChecklist(chapter.lab, { chId: chapter.id, labKey: chapter.id + '_chapterlab' }));
    root.appendChild(sec);
  }

  // Hackathon link footer (if provided as a plain string).
  if (chapter.hackathonLink) {
    const c = document.createElement('div');
    c.className = 'callout callout-hackathon-link';
    c.innerHTML = `<div class="callout-label"><span class="dot"></span>Hackathon link</div>${renderMarkdown(chapter.hackathonLink)}`;
    root.appendChild(c);
  }

  // Retrieval quiz.
  if (chapter.retrieval) {
    const sec = document.createElement('section');
    sec.className = 'session';
    sec.innerHTML = '<h2 class="session-title">Retrieval check</h2><p class="text-secondary">Recall beats reread. Answer from memory first.</p>';
    sec.appendChild(renderQuiz(chapter.retrieval, { chId: chapter.id, interactiveKey: 'retrieval' }));
    root.appendChild(sec);
  }

  // Sources.
  if (chapter.sources && chapter.sources.length) {
    const sec = document.createElement('section');
    sec.className = 'chapter-foot';
    sec.innerHTML = `<div class="rail-label">Sources</div><ul class="text-secondary">${chapter.sources.map((s) => `<li>${escape(s.label)}${s.note ? ' — ' + escape(s.note) : ''}</li>`).join('')}</ul>`;
    root.appendChild(sec);
  }

  // Completion banner (live).
  const footer = document.createElement('div');
  root.appendChild(footer);
  const refreshFooter = () => {
    if (isChapterComplete(chapter)) {
      setChapterComplete(chapter.id);
      footer.innerHTML = `
        <div class="complete-banner">
          <h3 style="margin-top:0">That's Chapter ${chapter.number} done.</h3>
          <p class="text-secondary">Nice. Your review deck just grew. <a href="#/dashboard">Back to dashboard</a>.</p>
        </div>`;
    } else {
      footer.innerHTML = '';
    }
  };
  refreshFooter();
  // Re-check on any interaction within the chapter.
  root.addEventListener('click', () => setTimeout(refreshFooter, 50));
  root.addEventListener('input', () => setTimeout(refreshFooter, 50));

  return root;
}

// Mark a section viewed when it scrolls into view (or immediately if no
// IntersectionObserver). Fires once.
function observeViewed(el, cb) {
  let fired = false;
  const fire = () => { if (!fired) { fired = true; cb(); } };
  if (typeof IntersectionObserver === 'undefined') { fire(); return; }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) { fire(); io.disconnect(); }
    });
  }, { threshold: 0.25 });
  io.observe(el);
}

function escape(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}
