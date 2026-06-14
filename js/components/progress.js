// progress.js — per-chapter completion maths and small UI helpers.
//
// A chapter's completion percent is (sections viewed + interactives done) over
// (total sections + total interactives). When everything is done we also stamp
// completedAt via setChapterComplete (called by the chapter view).

import { getState } from '../state.js';

// Count the interactive items a chapter contains, so the denominator matches
// what the renderer actually marks done.
export function countInteractives(chapter) {
  let n = 0;
  (chapter.sessions || []).forEach((s) => {
    (s.blocks || []).forEach((b) => {
      if (['flashcards', 'quiz', 'self-explain', 'checklist', 'lab', 'rubric-check', 'interactive'].includes(b.type)) n += 1;
    });
  });
  if (chapter.lab) n += 1;
  if (chapter.retrieval) n += 1;
  return n;
}

export function countSections(chapter) {
  return (chapter.sessions || []).length;
}

export function chapterPercent(chapter) {
  const p = getState().progress[chapter.id];
  const totalSections = countSections(chapter);
  const totalInteractives = countInteractives(chapter);
  const total = totalSections + totalInteractives;
  if (total === 0) return 0;
  if (!p) return 0;
  const done = (p.sectionsViewed ? p.sectionsViewed.length : 0) + (p.interactivesDone ? p.interactivesDone.length : 0);
  return Math.min(100, Math.round((done / total) * 100));
}

export function isChapterComplete(chapter) {
  return chapterPercent(chapter) >= 100;
}

export function progressBar(percent) {
  const el = document.createElement('div');
  el.className = 'progress-track';
  el.setAttribute('role', 'progressbar');
  el.setAttribute('aria-valuenow', String(percent));
  el.setAttribute('aria-valuemin', '0');
  el.setAttribute('aria-valuemax', '100');
  const fill = document.createElement('div');
  fill.className = 'progress-fill';
  fill.style.width = percent + '%';
  el.appendChild(fill);
  return el;
}
