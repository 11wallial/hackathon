// app.js — router, state bootstrap, shell rendering (nav, rail, dashboard).

import { chapters, getChapterMeta, loadChapter } from '../content/index.js';
import { renderChapter } from './render.js';
import { getState, mutate, subscribe, touchStreak, todayISO, isPersistent_ } from './state.js';
import { chapterPercent, isChapterComplete } from './components/progress.js';
import { renderReview, reviewDueBadge } from './components/review.js';
import { renderBrief } from '../pages/brief.js';
import { renderHowItWorks } from '../pages/how.js';
import { renderGlossary } from '../pages/glossary.js';

const view = document.getElementById('view');
const main = document.getElementById('main');

// ---- Bootstrap --------------------------------------------------------

function boot() {
  touchStreak();
  setupThemeToggle();
  window.addEventListener('hashchange', route);
  subscribe(() => { renderShellChrome(); });
  if (!location.hash) location.hash = '#/dashboard';
  route();
  renderShellChrome();

  if (!isPersistent_()) {
    console.warn('localStorage unavailable — progress will not be saved this session.');
  }
}

// ---- Routing ----------------------------------------------------------

function route() {
  const hash = location.hash.replace(/^#/, '') || '/dashboard';
  const parts = hash.split('/').filter(Boolean); // ['chapter','0']
  const top = parts[0] || 'dashboard';

  main.focus({ preventScroll: true });
  window.scrollTo(0, 0);

  switch (top) {
    case 'dashboard': return mount(renderDashboard());
    case 'chapters': return mount(renderChapterIndex());
    case 'chapter': return routeChapter(parts[1]);
    case 'review': return mount(renderReview());
    case 'glossary': return mount(renderGlossary());
    case 'brief': return mount(renderBrief());
    case 'how': return mount(renderHowItWorks());
    default: return mount(renderDashboard());
  }
  renderShellChrome();
}

function mount(node) {
  view.innerHTML = '';
  view.appendChild(node);
  renderShellChrome();
}

async function routeChapter(numStr) {
  // Accept #/chapter/0 or #/chapter/ch00.
  let meta;
  if (/^\d+$/.test(numStr)) meta = chapters.find((c) => c.number === Number(numStr));
  else meta = getChapterMeta(numStr);

  if (!meta) return mount(notFound('That chapter does not exist.'));
  if (!meta.available) {
    return mount(lockedChapter(meta));
  }
  mount(loadingNode());
  try {
    const chapter = await loadChapter(meta.id);
    if (!chapter) return mount(notFound('That chapter is not ready yet.'));
    mount(renderChapter(chapter));
  } catch (e) {
    console.error(e);
    mount(notFound('Something went wrong loading that chapter.'));
  }
}

// ---- Dashboard --------------------------------------------------------

function renderDashboard() {
  const wrap = document.createElement('div');
  const s = getState();
  const due = reviewDueBadge();
  const firstIncomplete = chapters.find((c) => c.available && !isChapterCompleteSafe(c));
  const resumeTarget = firstIncomplete || chapters.find((c) => c.available);

  wrap.innerHTML = `
    <div class="dash-hero">
      <p class="eyebrow">Track 2 · Detection & Auditing</p>
      <h1>Pick up where you left off.</h1>
      <p class="lede">A calm, self-paced run-up to the Secret Loyalties Hackathon, 24–26 July 2026. Short sessions, one clear next thing, durable by event day.</p>
    </div>`;

  // Stats.
  const stats = document.createElement('div');
  stats.className = 'stat-grid';
  stats.innerHTML = `
    <div class="stat"><div class="stat-num">${overallPercent()}%</div><div class="stat-label">Overall progress</div></div>
    <div class="stat"><div class="stat-num">${due}</div><div class="stat-label">Cards due today</div></div>
    <div class="stat"><div class="stat-num">${s.streak.days || 0}</div><div class="stat-label">Day streak</div></div>
    <div class="stat"><div class="stat-num">${s.buildLog.length}</div><div class="stat-label">Build-log entries</div></div>`;
  wrap.appendChild(stats);

  // Primary actions.
  const actions = document.createElement('div');
  actions.className = 'btn-row';
  actions.style.margin = '0.4rem 0 1.4rem';
  if (resumeTarget) {
    const a = document.createElement('a');
    a.className = 'btn btn-primary';
    a.href = `#/chapter/${resumeTarget.number}`;
    a.textContent = firstIncomplete ? `Continue: Chapter ${resumeTarget.number}` : 'Start Chapter 0';
    actions.appendChild(a);
  }
  if (due > 0) {
    const r = document.createElement('a');
    r.className = 'btn';
    r.href = '#/review';
    r.textContent = `Review ${due} card${due === 1 ? '' : 's'} · about ${Math.max(1, Math.round(due * 0.4))} min`;
    actions.appendChild(r);
  }
  const brief = document.createElement('a');
  brief.className = 'btn btn-ghost';
  brief.href = '#/brief';
  brief.textContent = 'Mission brief';
  actions.appendChild(brief);
  wrap.appendChild(actions);

  if (!isPersistent_()) {
    const warn = document.createElement('div');
    warn.className = 'callout callout-warning';
    warn.innerHTML = `<div class="callout-label"><span class="dot"></span>Heads up</div><p>Storage is blocked on this device, so progress won't save between visits. Everything still works for this session.</p>`;
    wrap.appendChild(warn);
  }

  // Chapter list.
  const h = document.createElement('h2');
  h.textContent = 'The curriculum';
  wrap.appendChild(h);
  wrap.appendChild(chapterList());

  // Build log.
  wrap.appendChild(buildLogPanel());

  // How this works link.
  const how = document.createElement('p');
  how.style.marginTop = '1.6rem';
  how.innerHTML = '<a href="#/how">How this works →</a> · the learning method behind the app.';
  wrap.appendChild(how);

  return wrap;
}

function chapterList() {
  const list = document.createElement('div');
  list.className = 'chapter-list';
  chapters.forEach((c) => {
    const done = c.available && isChapterCompleteSafe(c);
    const pct = c.available ? chapterPercentSafe(c) : 0;
    if (c.available) {
      const a = document.createElement('a');
      a.className = 'chapter-row' + (done ? ' done' : '');
      a.href = `#/chapter/${c.number}`;
      a.innerHTML = `
        <span class="ch-num">${done ? '✓' : c.number}</span>
        <span class="ch-meta">
          <span class="ch-title">${escape(c.title)}</span>
          <span class="ch-sub">${done ? 'Complete' : pct > 0 ? pct + '% · in progress' : 'Not started'}</span>
        </span>
        <span class="ch-pct">${pct}%</span>`;
      list.appendChild(a);
    } else {
      const d = document.createElement('div');
      d.className = 'chapter-row locked';
      d.innerHTML = `
        <span class="ch-num">${c.number}</span>
        <span class="ch-meta">
          <span class="ch-title">${escape(c.title)}</span>
          <span class="ch-sub">Coming soon</span>
        </span>
        <span class="ch-pct" aria-hidden="true">🔒</span>`;
      list.appendChild(d);
    }
  });
  return list;
}

function buildLogPanel() {
  const card = document.createElement('div');
  card.className = 'card';
  const s = getState();
  card.innerHTML = `
    <h3 style="margin-top:0">Build log</h3>
    <p class="text-secondary" style="font-size:0.95rem">Record what you actually ran or built. Prep should produce artifacts, not just reading.</p>`;

  const form = document.createElement('form');
  form.className = 'buildlog-form';
  form.innerHTML = `
    <input type="text" name="entry" placeholder="e.g. Got Qwen 0.5B running on Vast.ai" aria-label="New build-log entry" />
    <button class="btn btn-primary" type="submit">Add</button>`;
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const input = form.querySelector('input');
    const text = input.value.trim();
    if (!text) return;
    mutate((st) => { st.buildLog.unshift({ date: todayISO(), text }); return st; });
    input.value = '';
  });
  card.appendChild(form);

  const ul = document.createElement('ul');
  ul.className = 'buildlog-list';
  if (s.buildLog.length === 0) {
    ul.innerHTML = '<li class="text-secondary" style="border:none">No entries yet. Your first will come from Chapter 5.</li>';
  } else {
    s.buildLog.slice(0, 8).forEach((entry) => {
      const li = document.createElement('li');
      li.innerHTML = `<span class="bl-date">${escape(entry.date)}</span><span>${escape(entry.text)}</span>`;
      ul.appendChild(li);
    });
  }
  card.appendChild(ul);
  return card;
}

function renderChapterIndex() {
  const wrap = document.createElement('div');
  wrap.innerHTML = '<p class="eyebrow">Curriculum</p><h1>Chapters</h1><p class="lede">Ten chapters, frame to vocabulary to method to tools to project to rehearsal to game day.</p>';
  wrap.appendChild(chapterList());
  return wrap;
}

// ---- Shell chrome (nav, rail, badges) ---------------------------------

function renderShellChrome() {
  renderSideNav();
  renderRail();
  renderBottomBar();
}

function renderSideNav() {
  const body = document.getElementById('sidenav-body');
  if (!body) return;
  const cur = currentChapterNumber();
  const due = reviewDueBadge();
  let html = `
    <a class="nav-link ${isActive('dashboard') ? 'active' : ''}" href="#/dashboard"><span class="nav-num">⌂</span> Dashboard</a>
    <a class="nav-link ${isActive('review') ? 'active' : ''}" href="#/review"><span class="nav-num">↻</span> Review ${due > 0 ? `<span class="nav-badge">${due}</span>` : ''}</a>
    <a class="nav-link ${isActive('brief') ? 'active' : ''}" href="#/brief"><span class="nav-num">★</span> Mission brief</a>
    <a class="nav-link ${isActive('glossary') ? 'active' : ''}" href="#/glossary"><span class="nav-num">≡</span> Glossary</a>
    <div class="nav-section-label">Chapters</div>`;
  chapters.forEach((c) => {
    const done = c.available && isChapterCompleteSafe(c);
    const active = isActive('chapter') && cur === c.number;
    const cls = ['nav-link'];
    if (active) cls.push('active');
    if (done) cls.push('done');
    if (!c.available) cls.push('locked');
    const num = done ? '✓' : c.number;
    if (c.available) {
      html += `<a class="${cls.join(' ')}" href="#/chapter/${c.number}"><span class="nav-num">${num}</span> ${escape(shortTitle(c.title))}</a>`;
    } else {
      html += `<span class="${cls.join(' ')}"><span class="nav-num">${num}</span> ${escape(shortTitle(c.title))}</span>`;
    }
  });
  body.innerHTML = html;
}

function renderRail() {
  const body = document.getElementById('rail-body');
  if (!body) return;
  const due = reviewDueBadge();
  const firstIncomplete = chapters.find((c) => c.available && !isChapterCompleteSafe(c));
  let html = '';

  html += `<div class="rail-card card" style="margin:0 0 1.2rem">
    <div class="rail-label">Next action</div>`;
  if (firstIncomplete) {
    html += `<p style="margin:0.3rem 0 0.6rem">Continue Chapter ${firstIncomplete.number}.</p>
      <a class="btn btn-primary" href="#/chapter/${firstIncomplete.number}" style="display:inline-block">Open chapter ${firstIncomplete.number}</a>`;
  } else {
    html += `<p style="margin:0.3rem 0 0.6rem">You're up to date on available chapters.</p>`;
  }
  html += '</div>';

  html += `<div class="rail-card card" style="margin:0 0 1.2rem">
    <div class="rail-label">Spaced review</div>`;
  if (due > 0) {
    html += `<p style="margin:0.3rem 0 0.6rem">${due} card${due === 1 ? '' : 's'} due. About ${Math.max(1, Math.round(due * 0.4))} minutes.</p>
      <a class="btn" href="#/review" style="display:inline-block">Review now</a>`;
  } else {
    html += `<p class="text-secondary" style="margin:0.3rem 0 0">Nothing due. Cards return on their own schedule.</p>`;
  }
  html += '</div>';

  const days = getState().streak.days || 0;
  html += `<div class="rail-card"><div class="rail-label">Streak</div><p class="text-secondary" style="margin:0.2rem 0 0">${days} day${days === 1 ? '' : 's'} with activity. Gentle, not a leash.</p></div>`;

  body.innerHTML = html;
}

function renderBottomBar() {
  const badge = document.getElementById('bb-review-badge');
  const due = reviewDueBadge();
  if (badge) {
    if (due > 0) { badge.hidden = false; badge.textContent = String(due); }
    else badge.hidden = true;
  }
  document.querySelectorAll('.bottombar a').forEach((a) => {
    const tab = a.dataset.tab;
    a.classList.toggle('active', isActive(tab) || (tab === 'chapters' && isActive('chapter')));
  });
}

// ---- Theme ------------------------------------------------------------

function setupThemeToggle() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  btn.addEventListener('click', () => {
    const order = ['system', 'light', 'dark'];
    const cur = getState().theme || 'system';
    const next = order[(order.indexOf(cur) + 1) % order.length];
    mutate((s) => { s.theme = next; return s; });
    document.documentElement.setAttribute('data-theme', next);
    btn.setAttribute('aria-label', `Theme: ${next}. Click to change.`);
    btn.title = `Theme: ${next}`;
  });
  btn.title = `Theme: ${getState().theme || 'system'}`;
}

// ---- Small helpers ----------------------------------------------------

function isActive(top) {
  const hash = (location.hash.replace(/^#\//, '') || 'dashboard').split('/')[0];
  return hash === top;
}
function currentChapterNumber() {
  const m = location.hash.match(/#\/chapter\/(\d+)/);
  return m ? Number(m[1]) : null;
}
function overallPercent() {
  const avail = chapters.filter((c) => c.available);
  if (avail.length === 0) return 0;
  const sum = avail.reduce((a, c) => a + chapterPercentSafe(c), 0);
  return Math.round(sum / avail.length);
}
function isChapterCompleteSafe(meta) {
  const p = getState().progress[meta.id];
  return !!(p && p.completedAt);
}
function chapterPercentSafe(meta) {
  // We only have full block data after loading; use stored completion + a
  // coarse estimate from viewed/done counts for the dashboard.
  const p = getState().progress[meta.id];
  if (!p) return 0;
  if (p.completedAt) return 100;
  const done = (p.sectionsViewed ? p.sectionsViewed.length : 0) + (p.interactivesDone ? p.interactivesDone.length : 0);
  // Estimate against a typical chapter size; capped below 100 until completed.
  return Math.min(95, done * 12);
}
function shortTitle(t) {
  return t.length > 30 ? t.slice(0, 28) + '…' : t;
}
function loadingNode() {
  const d = document.createElement('div');
  d.className = 'empty-state';
  d.textContent = 'Loading…';
  return d;
}
function notFound(msg) {
  const d = document.createElement('div');
  d.className = 'empty-state';
  d.innerHTML = `<h1>Not found</h1><p>${escape(msg)}</p><p><a href="#/dashboard">Back to dashboard</a></p>`;
  return d;
}
function lockedChapter(meta) {
  const d = document.createElement('div');
  d.className = 'empty-state';
  d.innerHTML = `<p class="eyebrow">Chapter ${meta.number}</p><h1>${escape(meta.title)}</h1>
    <p class="text-secondary">This chapter is authored in a later milestone. The app is built so it'll appear the moment its content file is added — nothing else changes.</p>
    <p><a href="#/dashboard">Back to dashboard</a></p>`;
  return d;
}
function escape(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

boot();
