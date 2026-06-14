// term-in-the-wild.js — Chapter 2's "name the term" interactive.
//
// Each item is a sentence from a (plausible) audit paper plus four candidate
// terms; the learner picks the one being described. Structurally this is just a
// multiple-choice quiz, so rather than reimplement option buttons, feedback, and
// completion tracking, this is a thin adapter that maps each item onto the MCQ
// shape and reuses renderQuiz (js/components/quiz.js). renderQuiz handles the
// immediate right/wrong feedback and calls markInteractiveDone once every item
// has been answered.

import { renderQuiz } from './quiz.js';
import { renderMarkdown } from '../markdown.js';

export function renderTermInTheWild(block, opts = {}) {
  const { chId, interactiveKey } = opts;
  const items = block.items || [];

  const wrap = document.createElement('div');
  wrap.className = 'term-in-the-wild';

  if (block.instructions) {
    const intro = document.createElement('div');
    intro.className = 'prose';
    intro.innerHTML = renderMarkdown(block.instructions);
    wrap.appendChild(intro);
  }

  const mcqItems = items.map((item) => {
    const answer = (item.options || []).indexOf(item.correctTerm);
    return {
      type: 'mcq',
      q: item.sentence,
      options: item.options || [],
      // indexOf returns -1 only if the data is malformed; leaving it as -1 simply
      // means no option is marked correct rather than mis-marking a wrong one.
      answer,
      explain: item.explanation,
    };
  });

  wrap.appendChild(renderQuiz(mcqItems, { chId, interactiveKey }));

  return wrap;
}
