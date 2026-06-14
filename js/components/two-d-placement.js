// two-d-placement.js — Chapter 1's drag-the-dot interactive on the
// activation × action map.
//
// Self-assessed, not auto-graded: the learner drags a dot to where they think
// an example belongs, then presses "Reveal answer" to see the correct location
// plus an explanation. It mirrors the renderRubricCheck contract (see
// rubric-check.js) — (block, { chId, interactiveKey }) — persists which items
// have been revealed under quizResults[storeKey], and marks the interactive
// done once every item has been revealed.

import { getState, mutate, markInteractiveDone } from '../state.js';
import { renderMarkdown } from '../markdown.js';

const SVGNS = 'http://www.w3.org/2000/svg';
const VB = 300;                                   // square viewBox
const PLOT = { left: 48, right: 284, top: 18, bottom: 256 };
const PW = PLOT.right - PLOT.left;
const PH = PLOT.bottom - PLOT.top;

// Items use correctX/correctY in 0..1 with the origin at the BOTTOM-LEFT
// (narrow = 0). SVG y grows downward, so invert y when mapping.
function mapX(x) { return PLOT.left + x * PW; }
function mapY(y) { return PLOT.bottom - y * PH; }
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function svgEl(tag, attrs = {}) {
  const el = document.createElementNS(SVGNS, tag);
  Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, String(v)));
  return el;
}

export function renderTwoDPlacement(block, opts = {}) {
  const { chId, interactiveKey } = opts;
  const items = block.items || [];
  const storeKey = (chId || 'twod') + '_' + (interactiveKey || 'twod');

  const wrap = document.createElement('div');
  wrap.className = 'two-d-placement';

  if (block.instructions) {
    const intro = document.createElement('div');
    intro.className = 'prose';
    intro.innerHTML = renderMarkdown(block.instructions);
    wrap.appendChild(intro);
  }

  const saved = (getState().quizResults && getState().quizResults[storeKey]) || {};
  const revealed = new Set(saved.revealed || []);

  items.forEach((item, ii) => {
    wrap.appendChild(buildItem(item, ii));
  });

  function buildItem(item, ii) {
    const key = item.id != null ? item.id : ii;

    const card = document.createElement('div');
    card.className = 'twod-item';

    const label = document.createElement('p');
    label.className = 'twod-label';
    label.textContent = item.label || '';
    card.appendChild(label);

    const stage = document.createElement('div');
    stage.className = 'twod-stage';

    const svg = svgEl('svg', { viewBox: `0 0 ${VB} ${VB}`, class: 'twod-svg' });
    svg.setAttribute('role', 'group');
    svg.setAttribute('aria-label', 'Activation breadth by action breadth placement map');
    drawAxes(svg);

    // Correct marker + connector (hidden until reveal).
    const cx = mapX(item.correctX), cy = mapY(item.correctY);
    const connector = svgEl('line', { class: 'twod-connector', x1: 0, y1: 0, x2: 0, y2: 0, opacity: 0 });
    svg.appendChild(connector);
    const correctG = svgEl('g', { class: 'twod-correct', opacity: 0 });
    correctG.appendChild(svgEl('circle', { cx, cy, r: 13, class: 'twod-correct-ring' }));
    correctG.appendChild(svgEl('circle', { cx, cy, r: 7, class: 'twod-correct-dot' }));
    svg.appendChild(correctG);

    // Draggable user dot, starting at plot centre.
    let ux = 0.5, uy = 0.5; // normalised position
    const userG = svgEl('g', { class: 'twod-user', tabindex: 0, role: 'slider' });
    userG.setAttribute('aria-label', 'Your placement. Drag, or use the arrow keys to move, then reveal the answer.');
    const hit = svgEl('circle', { cx: mapX(ux), cy: mapY(uy), r: 20, class: 'twod-hit' });
    const dot = svgEl('circle', { cx: mapX(ux), cy: mapY(uy), r: 9, class: 'twod-user-dot' });
    userG.appendChild(hit);
    userG.appendChild(dot);
    svg.appendChild(userG);

    let locked = false;

    function placeUser(px, py) {
      const clx = clamp(px, PLOT.left, PLOT.right);
      const cly = clamp(py, PLOT.top, PLOT.bottom);
      hit.setAttribute('cx', clx); hit.setAttribute('cy', cly);
      dot.setAttribute('cx', clx); dot.setAttribute('cy', cly);
      ux = (clx - PLOT.left) / PW;
      uy = (PLOT.bottom - cly) / PH;
    }

    function toSvgCoords(ev) {
      const rect = svg.getBoundingClientRect();
      if (!rect.width || !rect.height) return [mapX(ux), mapY(uy)];
      return [
        (ev.clientX - rect.left) / rect.width * VB,
        (ev.clientY - rect.top) / rect.height * VB,
      ];
    }

    userG.addEventListener('pointerdown', (ev) => {
      if (locked) return;
      ev.preventDefault();
      try { userG.setPointerCapture(ev.pointerId); } catch (e) { /* unsupported */ }
      userG.classList.add('dragging');
      const [sx, sy] = toSvgCoords(ev);
      placeUser(sx, sy);
    });
    userG.addEventListener('pointermove', (ev) => {
      if (locked) return;
      if (userG.hasPointerCapture && !userG.hasPointerCapture(ev.pointerId)) return;
      const [sx, sy] = toSvgCoords(ev);
      placeUser(sx, sy);
    });
    const endDrag = (ev) => {
      userG.classList.remove('dragging');
      try { userG.releasePointerCapture(ev.pointerId); } catch (e) { /* no-op */ }
    };
    userG.addEventListener('pointerup', endDrag);
    userG.addEventListener('pointercancel', endDrag);

    userG.addEventListener('keydown', (ev) => {
      if (locked) return;
      const step = PW * 0.03;
      let dx = 0, dy = 0;
      switch (ev.key) {
        case 'ArrowLeft': dx = -step; break;
        case 'ArrowRight': dx = step; break;
        case 'ArrowUp': dy = -step; break;
        case 'ArrowDown': dy = step; break;
        default: return;
      }
      ev.preventDefault();
      placeUser(mapX(ux) + dx, mapY(uy) + dy);
    });

    stage.appendChild(svg);
    card.appendChild(stage);

    const controls = document.createElement('div');
    controls.className = 'twod-controls';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn';
    btn.textContent = 'Reveal answer';
    controls.appendChild(btn);
    card.appendChild(controls);

    const panel = document.createElement('div');
    panel.className = 'callout callout-tip twod-explain';
    panel.hidden = true;
    card.appendChild(panel);

    function reveal() {
      locked = true;
      userG.classList.add('locked');
      userG.setAttribute('tabindex', '-1');
      connector.setAttribute('x1', dot.getAttribute('cx'));
      connector.setAttribute('y1', dot.getAttribute('cy'));
      connector.setAttribute('x2', cx);
      connector.setAttribute('y2', cy);
      connector.setAttribute('opacity', 1);
      correctG.setAttribute('opacity', 1);
      btn.disabled = true;
      btn.textContent = 'Revealed';
      panel.hidden = false;
      panel.innerHTML = `<div class="callout-label"><span class="dot"></span>Answer</div>${renderMarkdown(item.explanation || '')}`;
      markRevealed(key);
    }

    btn.addEventListener('click', reveal);

    // Restore a previously revealed item on reload.
    if (revealed.has(key)) reveal();

    return card;
  }

  function markRevealed(key) {
    revealed.add(key);
    mutate((s) => {
      s.quizResults[storeKey] = { revealed: Array.from(revealed) };
      return s;
    });
    if (revealed.size >= items.length && chId && interactiveKey) {
      markInteractiveDone(chId, interactiveKey);
    }
  }

  return wrap;
}

// Draw the plot background, axes, arrows, and Narrow/Broad labels in the same
// visual language as the chapter's static ch01_2d_map diagram.
function drawAxes(svg) {
  svg.appendChild(svgEl('rect', {
    x: PLOT.left, y: PLOT.top, width: PW, height: PH, rx: 6, class: 'twod-plot-bg',
  }));

  // Axis lines.
  svg.appendChild(svgEl('line', { x1: PLOT.left, y1: PLOT.bottom, x2: PLOT.right, y2: PLOT.bottom, class: 'twod-axis' }));
  svg.appendChild(svgEl('line', { x1: PLOT.left, y1: PLOT.bottom, x2: PLOT.left, y2: PLOT.top, class: 'twod-axis' }));
  // Arrow heads.
  svg.appendChild(svgEl('polygon', { points: `${PLOT.right - 8},${PLOT.bottom - 4} ${PLOT.right},${PLOT.bottom} ${PLOT.right - 8},${PLOT.bottom + 4}`, class: 'twod-axis-arrow' }));
  svg.appendChild(svgEl('polygon', { points: `${PLOT.left - 4},${PLOT.top + 8} ${PLOT.left},${PLOT.top} ${PLOT.left + 4},${PLOT.top + 8}`, class: 'twod-axis-arrow' }));

  // Axis titles.
  const xt = svgEl('text', { x: (PLOT.left + PLOT.right) / 2, y: VB - 5, 'text-anchor': 'middle', class: 'twod-axis-title' });
  xt.textContent = 'Activation breadth →';
  svg.appendChild(xt);
  const ymid = (PLOT.top + PLOT.bottom) / 2;
  const yt = svgEl('text', { x: 13, y: ymid, 'text-anchor': 'middle', class: 'twod-axis-title', transform: `rotate(-90,13,${ymid})` });
  yt.textContent = 'Action breadth →';
  svg.appendChild(yt);

  // End labels (Narrow / Broad) on each axis.
  addEnd(svg, 'Narrow', PLOT.left + 2, PLOT.bottom + 15, 'start');
  addEnd(svg, 'Broad', PLOT.right, PLOT.bottom + 15, 'end');
  addEnd(svg, 'Narrow', PLOT.left + 4, PLOT.bottom - 4, 'start');
  addEnd(svg, 'Broad', PLOT.left + 4, PLOT.top + 12, 'start');
}

function addEnd(svg, text, x, y, anchor) {
  const t = svgEl('text', { x, y, 'text-anchor': anchor, class: 'twod-end' });
  t.textContent = text;
  svg.appendChild(t);
}
