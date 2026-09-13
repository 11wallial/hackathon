// Playable client. Imports the *same* modules the experiments run against, so
// what you play is exactly what was measured. No build step, no duplicated rules.

import {
  createEncounter, applyAction, legalActions, cloneState, isOver,
  getPlayer, unitAt, isHot, mod, playerActionsFor, predictNextNode, killMath, enemies, ringDist,
} from '../sim/rules.js';

const R = 12;
const KIND_LABEL = { player: 'You', drone: 'Drone', siphon: 'Siphon', warden: 'Warden', lobber: 'Lobber' };
const KIND_HINT = {
  drone: 'walks at you and shoves what it has, then goes looking for more',
  siphon: 'ignores you, eats loose charge, huge capacity — a bomb you can build',
  warden: 'slow, arrives full, hits hard',
  lobber: 'throws charge at you from 2-4 nodes away, and cannot throw at all if you are next to it',
};

const ENCOUNTERS = {
  surge: ['Surge', 'The standard fight. Waves arrive progressively fuller, so late enemies are dangerous and brittle at the same time. Hard: strong play clears it about six times in ten.'],
  press: ['Press', 'Lobbers force charge into you from outside melee range. Being nearly full is where this one is won — flinching from your own capacity loses more often than it saves you.'],
  skirmish: ['Skirmish', 'One lobber and a pair of drones per wave, and nothing with a big capacity bar. The lightest roster in the set, and the one where you will spend the most time nearly full.'],
  garden: ['Garden', 'One fat scavenger arrives every wave behind a screen of drones. It loads itself off whatever is on the floor, so it has to be tipped rather than shot down.'],
};
let encounterId = 'surge';

let state, amount = 1, seen = 0;
const $ = (id) => document.getElementById(id);

function newRun() {
  state = createEncounter({ encounter: encounterId, seed: (Math.random() * 1e9) | 0, record: true });
  amount = 1; seen = 0;
  $('log').innerHTML = '';
  logLine(`<b>${ENCOUNTERS[encounterId][0]}.</b> ${ENCOUNTERS[encounterId][1]}`, '');
  logLine('Charge is conserved: what is here is all there will be, plus whatever arrives inside the next wave.', '');
  render();
}

// --- geometry --------------------------------------------------------------

const pos = (n) => {
  const a = (n / R) * Math.PI * 2 - Math.PI / 2;
  return { x: 230 + Math.cos(a) * 168, y: 230 + Math.sin(a) * 168 };
};

function render() {
  const p = getPlayer(state);
  const svg = [];

  svg.push(`<circle cx="230" cy="230" r="168" fill="none" stroke="#1c2533" stroke-width="2"/>`);

  // Shade every node a lobber can currently throw into. The range rule is the
  // whole decision the archetype exists to create, so it has to be on the board.
  const threatened = new Set();
  for (const u of state.units) {
    if (!u.alive || u.ai !== 'lob') continue;
    for (let d = u.minRange; d <= u.maxRange; d++) {
      threatened.add(mod(u.node + d, R));
      threatened.add(mod(u.node - d, R));
    }
  }
  for (const n of threatened) {
    const q = pos(n);
    // Kept deliberately faint: on `press` almost everywhere is threatened, so
    // this should read as ambient pressure, with the *unringed* nodes standing
    // out as the rare safe ground.
    svg.push(`<circle cx="${q.x}" cy="${q.y}" r="34" fill="none" stroke="#ff547026" stroke-width="5"/>`);
  }

  // Where each enemy will step next. A two-move search knows this; a new player
  // does not, and EXP-034 showed that gap is worth ~30 percentage points.
  const arrivals = new Map();
  for (const e of state.units) {
    if (!e.alive || e.team !== 'enemy') continue;
    const n = predictNextNode(state, e);
    if (n !== e.node) arrivals.set(n, (arrivals.get(n) || []).concat(e));
  }
  for (const [n, list] of arrivals) {
    const q = pos(n);
    svg.push(`<circle cx="${q.x}" cy="${q.y}" r="29" fill="none" stroke="#58c8ff" stroke-width="2" stroke-dasharray="2 6" opacity="0.75"/>`);
    svg.push(`<text x="${q.x}" y="${q.y - 34}" text-anchor="middle" font-size="9" letter-spacing="1" fill="#58c8ff">↓ ${list.length > 1 ? list.length + ' INCOMING' : 'INCOMING'}</text>`);
  }

  for (let n = 0; n < R; n++) {
    const { x, y } = pos(n);
    const u = unitAt(state, n);
    const motes = state.ring[n];
    svg.push(`<circle cx="${x}" cy="${y}" r="30" fill="#11161f" stroke="#232b38" stroke-width="1.5"/>`);
    // Node indices: the preview text talks about "node 7", so the board has to say which one that is.
    const lp = pos(n), ox = (lp.x - 230) * 0.245, oy = (lp.y - 230) * 0.245;
    svg.push(`<text x="${x + ox}" y="${y + oy + 4}" text-anchor="middle" font-size="10" fill="#3b4757">${n}</text>`);

    if (motes > 0) {
      svg.push(`<circle cx="${x}" cy="${y}" r="${Math.min(27, 11 + motes * 1.3)}" fill="#ffd97722" stroke="#ffd977" stroke-width="1.5" stroke-dasharray="3 3"/>`);
      if (!u) svg.push(`<text x="${x}" y="${y + 5}" text-anchor="middle" font-size="15" font-weight="700" fill="#ffd977">${motes}</text>`);
    }
    if (u) {
      const frac = Math.max(0, Math.min(1, u.charge / u.capacity));
      const hot = isHot(state, u);
      const you = u.team === 'player';
      const col = you ? '#7ef0c0' : hot ? '#ffb03a' : '#58c8ff';
      svg.push(`<circle cx="${x}" cy="${y}" r="24" fill="${col}22" stroke="${col}" stroke-width="${you ? 3 : 2}"/>`);
      svg.push(`<path d="${arc(x, y, 24, frac)}" fill="none" stroke="${col}" stroke-width="5" stroke-linecap="round"/>`);
      svg.push(`<text x="${x}" y="${y + 1}" text-anchor="middle" font-size="14" font-weight="700" fill="${col}">${u.charge}</text>`);
      svg.push(`<text x="${x}" y="${y + 14}" text-anchor="middle" font-size="10" fill="#8593a8">/${u.capacity}</text>`);
      const label = you ? 'YOU' : KIND_LABEL[u.kind].toUpperCase();
      const ly = y + (y < 230 ? -38 : 44);
      svg.push(`<text x="${x}" y="${ly}" text-anchor="middle" font-size="10" letter-spacing="1.2" fill="${hot ? '#ffb03a' : '#8593a8'}">${label}${hot ? ' HOT' : ''}</text>`);
      if (motes > 0) svg.push(`<text x="${x + 30}" y="${y - 20}" text-anchor="middle" font-size="12" font-weight="700" fill="#ffd977">+${motes}</text>`);
    }
  }
  $('ring').innerHTML = svg.join('');

  const total = state.ring.reduce((a, b) => a + b, 0);
  const foes = state.units.filter((u) => u.alive && u.team === 'enemy');
  const cls = p.charge / p.capacity >= 0.9 ? 'crit' : isHot(state, p) ? 'hot' : '';
  $('hud').innerHTML = `
    <span>Turn <b>${state.turn}</b>/${state.config.turnLimit}</span>
    <span>Actions <b>${state.actionsLeft}</b>${state.config.playerHotBonus && isHot(state, p) ? ' <b style="color:#ffb03a">(hot +1)</b>' : ''}</span>
    <span>Enemies <b>${foes.length}</b></span>
    <span>Loose charge <b style="color:#ffd977">${total}</b></span>
    <span>Field total <b>${state.injected}</b></span>
    <div style="flex-basis:100%">
      <span>Your charge <b>${p.charge} / ${p.capacity}</b>${isHot(state, p) ? ' — hot' : ''}</span>
      <div class="bar ${cls}"><i style="width:${Math.min(100, (p.charge / p.capacity) * 100)}%"></i></div>
    </div>`;

  renderThreats();
  renderControls();
  drainEvents();

  const b = $('banner');
  if (state.result === 'win') b.innerHTML = `<div class="banner win">Field cleared in ${state.turn} turns. Press R for a new one.</div>`;
  else if (state.result === 'loss') b.innerHTML = `<div class="banner loss">You went critical with nothing left to lose. Press R.</div>`;
  else if (state.result === 'timeout') b.innerHTML = `<div class="banner timeout">Stalemate — the field ran down with enemies still standing. Press R.</div>`;
  else b.innerHTML = '';
}

// The other half of what a planning agent knows: exactly how much each target
// still needs, and how much you can actually deliver before the turn ends.
// EXP-034 found the real cliff is *starting* a kill that takes two actions.
function renderThreats() {
  const p = getPlayer(state);
  const foes = enemies(state);
  if (!foes.length) { $('threats').innerHTML = ''; return; }
  const deliverable = Math.min(p.charge, p.throughput * Math.max(0, state.actionsLeft));
  const rows = foes
    .map((e) => ({ e, m: killMath(state, e), d: ringDist(e.node, p.node, state.config.ringSize) }))
    .sort((a, b) => a.d - b.d)
    // The re-derived encounters run eleven bodies at once; an eleven-row readout
    // is noise, not legibility. Nearest five, then a count.
    .slice(0, 5)
    .map(({ e, m, d }) => {
      const reach = d <= 1 ? '' : ` <span style="color:#5c6b80">${d} away</span>`;
      const verdict = m.enough
        ? (d <= 1 ? '<b style="color:#ff5470">you can finish it this turn</b>' : '<span style="color:#8593a8">in range if you close</span>')
        : `<span style="color:#5c6b80">short by ${m.needed - deliverable}</span>`;
      return `<div><b>${KIND_LABEL[e.kind]}</b> ${e.charge}/${e.capacity}${isHot(state, e) ? ' <span style="color:#ffb03a">hot</span>' : ''}${reach}
        — needs <b>${m.needed}</b> more — ${verdict}</div>`;
    }).join('');
  // Name whichever limit is actually binding — "4 per shove x 2 actions" reads
  // as 8 when you are only holding 3, which is exactly the confusion this panel
  // exists to remove.
  const capped = p.charge < p.throughput * Math.max(0, state.actionsLeft);
  const why = capped
    ? `all the charge you are holding`
    : `${p.throughput} per shove × ${state.actionsLeft} action${state.actionsLeft === 1 ? '' : 's'}`;
  const hidden = foes.length - 5;
  const more = hidden > 0 ? `<div style="color:#5c6b80;margin-top:6px">and ${hidden} further away</div>` : '';
  $('threats').innerHTML = `<div style="color:#8593a8;margin-bottom:6px">You can move <b style="color:#e7edf6">${deliverable}</b> charge before this turn ends — ${why}.</div>${rows}${more}`;
}

function arc(cx, cy, r, frac) {
  if (frac <= 0) return '';
  const a0 = -Math.PI / 2, a1 = a0 + Math.PI * 2 * Math.min(frac, 0.9999);
  const large = frac > 0.5 ? 1 : 0;
  return `M ${cx + Math.cos(a0) * r} ${cy + Math.sin(a0) * r} A ${r} ${r} 0 ${large} 1 ${cx + Math.cos(a1) * r} ${cy + Math.sin(a1) * r}`;
}

// --- controls & preview ----------------------------------------------------

function renderControls() {
  const p = getPlayer(state);
  const acts = legalActions(state);
  const over = isOver(state);
  const maxAmt = Math.min(p.throughput, p.charge);
  amount = Math.max(1, Math.min(amount, Math.max(1, maxAmt)));

  $('amounts').innerHTML = [1, 2, 3, 4].map((a) =>
    `<button class="amt" data-amt="${a}" aria-pressed="${a === amount}" ${a > maxAmt || over ? 'disabled' : ''}>${a}</button>`
  ).join('') + `<span style="align-self:center;color:#8593a8;font-size:12px;margin-left:6px">charge to move</span>`;

  const has = (t, d) => acts.some((a) => a.type === t && a.dir === d && (t !== 'shove' || a.amount === amount));
  $('actions').innerHTML = `
    <button data-act='{"type":"step","dir":-1}' ${!has('step', -1) || over ? 'disabled' : ''}>◀ Step</button>
    <button data-act='{"type":"shove","dir":-1}' ${!has('shove', -1) || over ? 'disabled' : ''}>Shove ◀</button>
    <button data-act='{"type":"shove","dir":0}' ${!has('shove', 0) || over ? 'disabled' : ''}>Drop here</button>
    <button data-act='{"type":"shove","dir":1}' ${!has('shove', 1) || over ? 'disabled' : ''}>▶ Shove</button>
    <button data-act='{"type":"step","dir":1}' ${!has('step', 1) || over ? 'disabled' : ''}>Step ▶</button>
    <button class="primary" data-act='{"type":"end"}' ${over ? 'disabled' : ''}>End turn</button>
    <button data-new="1">New run</button>`;
  $('encounters').innerHTML = Object.entries(ENCOUNTERS).map(([id, [name, blurb]]) =>
    `<button data-enc="${id}" aria-pressed="${id === encounterId}" class="amt" title="${blurb}">${name}</button>`
  ).join('') + `<span style="align-self:center;color:#8593a8;font-size:12px;margin-left:6px">${ENCOUNTERS[encounterId][1]}</span>`;
}

// The preview forks the real state and runs the real rules, so it can never
// disagree with what actually happens. Legibility is not a tooltip problem.
function previewOf(action) {
  const p = getPlayer(state);
  if (action.type === 'end') return 'Hand the turn over. Hot enemies act twice.';
  const n = mod(p.node + (action.dir ?? 0), R);
  const target = action.type === 'shove' && action.dir !== 0 ? unitAt(state, n) : null;

  const fork = cloneState(state);
  applyAction(fork, action);
  const before = state.units.filter((u) => u.alive).length;
  const after = fork.units.filter((u) => u.alive).length;
  const fp = getPlayer(fork);

  if (action.type === 'step') {
    const gained = fp.charge - p.charge;
    const left = fork.ring[n];
    return `Step onto node ${n}.` +
      (gained > 0 ? ` Pick up <b>${gained}</b> charge → you at <b>${fp.charge}/${fp.capacity}</b>${left ? `, leaving ${left} behind (you fill to capacity, never past it)` : ''}.` : ' Nothing to pick up there.');
  }
  if (target) {
    const willDie = !fork.units.find((u) => u.id === target.id).alive;
    const nowHot = target.charge + action.amount >= Math.ceil(target.capacity * state.config.hotThreshold);
    return `Give <b>${action.amount}</b> to ${KIND_LABEL[target.kind]} (${target.charge}/${target.capacity}) → <b>${target.charge + action.amount}/${target.capacity}</b>. ` +
      (willDie
        ? `<span class="kill">Over capacity: it detonates for ${target.charge + action.amount}</span>${after < before - 1 ? ' <span class="kill">and sets off a chain</span>' : ''}.`
        : nowHot && !isHot(state, target) ? 'That tips it into <b>hot</b> — it will act twice.' : 'It survives, and keeps the charge.');
  }
  const pile = state.ring[n] + action.amount;
  const incoming = state.units.filter((e) => e.alive && e.team === 'enemy' && predictNextNode(state, e) === n);
  if (incoming.length) {
    const e = incoming[0];
    const lethal = e.charge + pile > e.capacity;
    return `Put <b>${action.amount}</b> on node ${n} (pile becomes <b>${pile}</b>). ` +
      `<b>${KIND_LABEL[e.kind]} is stepping there next turn</b> at ${e.charge}/${e.capacity} — ` +
      (lethal
        ? `<span class="kill">it walks in, fills past capacity and detonates</span>.`
        : `it will fill to ${Math.min(e.capacity, e.charge + pile)}/${e.capacity}, leaving it ${e.capacity - Math.min(e.capacity, e.charge + pile) + 1} short. Add more, or tip it after.`);
  }
  return `Put <b>${action.amount}</b> on node ${n} (pile becomes <b>${pile}</b>). ` +
    `Anything that steps there fills up from it — that is how you load a target before tipping it over. ` +
    `Leaving nothing on the floor starves them instead, which is slower but costs you nothing.` +
    (action.dir === 0 ? ' You are standing on it; step off or you will take it back at the end of the round.' : '');
}

function act(action) {
  if (isOver(state)) return;
  if (action.type === 'shove') action = { ...action, amount };
  applyAction(state, action);
  render();
}

// --- log -------------------------------------------------------------------

function logLine(html, cls) {
  const d = document.createElement('div');
  if (cls) d.className = cls;
  d.innerHTML = html;
  $('log').prepend(d);
}

function drainEvents() {
  const name = (id) => {
    const u = state.units.find((x) => x.id === id);
    return u ? (u.team === 'player' ? 'You' : KIND_LABEL[u.kind]) : 'Something';
  };
  for (; seen < state.events.length; seen++) {
    const e = state.events[seen];
    if (e.type === 'detonate') {
      logLine(`<b>${e.kind === 'player' ? 'You overload' : KIND_LABEL[e.kind] + ' goes over capacity'}</b> on node ${e.node} and detonates for <b>${e.payload}</b>${e.survived ? ' — you survive, capacity permanently reduced' : ''}.`, e.kind === 'player' ? 'bad' : 'boom');
    } else if (e.type === 'lob') {
      logLine(`<b>Lobber</b> on node ${e.from} throws <b>${e.amount}</b> across the gap into you.`, 'bad');
    } else if (e.type === 'dissolve') {
      logLine(`<b>${KIND_LABEL[e.kind]}</b> on node ${e.node} has held nothing for too long and dissolves.`, '');
    } else if (e.type === 'spawn' && e.kind !== 'player') {
      logLine(`Wave: <b>${KIND_LABEL[e.kind]}</b> arrives on node ${e.node} holding ${e.charge} — ${KIND_HINT[e.kind]}.`, '');
    } else if (e.type === 'shove' && e.target && name(e.id) !== 'You') {
      logLine(`${name(e.id)} shoves <b>${e.amount}</b> into ${name(e.target)}.`, '');
    } else if (e.type === 'absorb' && e.bait) {
      logLine(`${name(e.id)} fills up on charge you left — now <b>${e.charge}</b>.`, '');
    } else if (e.type === 'end') {
      logLine(`<b>${e.result === 'win' ? 'Field cleared.' : e.result === 'loss' ? 'You are gone.' : 'Stalemate.'}</b>`, e.result === 'win' ? '' : 'bad');
    }
  }
}

// --- wiring ----------------------------------------------------------------

document.addEventListener('click', (ev) => {
  const b = ev.target.closest('button');
  if (!b) return;
  if (b.dataset.enc) { encounterId = b.dataset.enc; return newRun(); }
  if (b.dataset.new) return newRun();
  if (b.dataset.amt) { amount = +b.dataset.amt; renderControls(); $('preview').innerHTML = `Moving <b>${amount}</b> charge.`; return; }
  if (b.dataset.act) act(JSON.parse(b.dataset.act));
});
document.addEventListener('pointerover', (ev) => {
  const b = ev.target.closest('button[data-act]');
  if (!b || b.disabled) return;
  const a = JSON.parse(b.dataset.act);
  $('preview').innerHTML = previewOf(a.type === 'shove' ? { ...a, amount } : a);
});

const KEYS = {
  a: { type: 'step', dir: -1 }, d: { type: 'step', dir: 1 },
  q: { type: 'shove', dir: -1 }, s: { type: 'shove', dir: 0 }, e: { type: 'shove', dir: 1 },
  ' ': { type: 'end' },
};
document.addEventListener('keydown', (ev) => {
  const k = ev.key.toLowerCase();
  if (k === 'r') return newRun();
  if (k >= '1' && k <= '4') { amount = +k; renderControls(); return; }
  const a = KEYS[k];
  if (!a) return;
  ev.preventDefault();
  if (legalActions(state).some((x) => x.type === a.type && x.dir === a.dir && (a.type !== 'shove' || x.amount === amount))) act(a);
});

newRun();
