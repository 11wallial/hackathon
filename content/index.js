// content/index.js — the chapter registry.
//
// Adding a chapter is: (1) create content/chapter-NN.js exporting the schema in
// section 6 of the spec, (2) add one line here with its loader and `available`.
// Nothing else in the app changes.

export const chapters = [
  {
    id: 'ch00',
    number: 0,
    title: 'Orientation and the mission',
    estMinutes: 35,
    available: true,
    load: () => import('./chapter-00.js'),
  },
  {
    id: 'ch01',
    number: 1,
    title: 'The threat model: secret loyalties',
    estMinutes: 55,
    available: true,
    load: () => import('./chapter-01.js'),
  },
  // Chapters 2–9 are authored one at a time in later milestones. Placeholders
  // keep the map visible so the learner sees the journey ahead.
  { id: 'ch02', number: 2, title: 'The language of the field', available: false },
  { id: 'ch03', number: 3, title: 'Catching it I: black box auditing', available: false },
  { id: 'ch04', number: 4, title: 'Catching it II: probes and interpretability', available: false },
  { id: 'ch05', number: 5, title: 'The toolkit (hands on)', available: false },
  { id: 'ch06', number: 6, title: 'Designing your project', available: false },
  { id: 'ch07', number: 7, title: 'The mock sprint (rehearsal)', available: false },
  { id: 'ch08', number: 8, title: 'Team and logistics', available: false },
  { id: 'ch09', number: 9, title: 'Game-day playbook', available: false },
];

export function getChapterMeta(id) {
  return chapters.find((c) => c.id === id);
}

export async function loadChapter(id) {
  const meta = getChapterMeta(id);
  if (!meta || !meta.available || !meta.load) return null;
  const mod = await meta.load();
  return mod.default;
}
