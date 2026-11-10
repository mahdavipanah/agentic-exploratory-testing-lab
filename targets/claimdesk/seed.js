'use strict';

const USERS = [
  { id: 1, username: 'alice', password: 'alice-pass', name: 'Alice Novak', role: 'employee', team: 'platform' },
  { id: 2, username: 'bob', password: 'bob-pass', name: 'Bob Lindqvist', role: 'employee', team: 'platform' },
  { id: 3, username: 'erin', password: 'erin-pass', name: 'Erin Okafor', role: 'employee', team: 'mobile' },
  { id: 4, username: 'carol', password: 'carol-pass', name: 'Carol Jensen', role: 'manager', team: 'platform' },
  { id: 5, username: 'frank', password: 'frank-pass', name: 'Frank Duarte', role: 'manager', team: 'mobile' },
  { id: 6, username: 'dave', password: 'dave-pass', name: 'Dave Kim', role: 'finance', team: null },
];

const CLAIMS = [
  {
    id: 1, owner_id: 1, title: 'Berlin offsite travel', purpose: 'Platform team offsite, 6-7 October',
    currency: 'EUR', status: 'approved',
    created_at: '2026-10-08T09:12:00.000Z', submitted_at: '2026-10-08T09:20:00.000Z',
    reviewed_by: 'carol', reviewed_at: '2026-10-09T14:03:00.000Z', review_comment: null,
    items: [
      { date: '2026-10-06', category: 'travel', description: 'ICE train Hamburg to Berlin', amount_cents: 8990 },
      { date: '2026-10-06', category: 'lodging', description: 'Hotel, 1 night', amount_cents: 11900 },
      { date: '2026-10-07', category: 'meals', description: 'Dinner', amount_cents: 4250 },
    ],
  },
  {
    id: 2, owner_id: 1, title: 'NodeConf EU ticket', purpose: null,
    currency: 'EUR', status: 'paid',
    created_at: '2026-09-16T08:00:00.000Z', submitted_at: '2026-09-16T08:05:00.000Z',
    reviewed_by: 'carol', reviewed_at: '2026-09-17T10:30:00.000Z', review_comment: null,
    items: [
      { date: '2026-09-15', category: 'other', description: 'Conference ticket', amount_cents: 39900 },
    ],
    payments: [{ amount_cents: 39900, paid_at: '2026-09-22T11:00:00.000Z', reference: 'PAY-2026-0922-01' }],
  },
  {
    id: 3, owner_id: 2, title: 'Client visit Munich', purpose: 'Workshop at the client office',
    currency: 'EUR', status: 'submitted',
    created_at: '2026-10-22T07:45:00.000Z', submitted_at: '2026-10-22T07:50:00.000Z',
    reviewed_by: null, reviewed_at: null, review_comment: null,
    items: [
      { date: '2026-10-20', category: 'travel', description: 'Flight Hamburg to Munich', amount_cents: 15420 },
      { date: '2026-10-21', category: 'travel', description: 'Taxi to client office', amount_cents: 3170 },
      { date: '2026-10-21', category: 'meals', description: 'Lunch', amount_cents: 1890 },
    ],
  },
  {
    id: 4, owner_id: 1, title: 'Office chair', purpose: 'Home office setup',
    currency: 'EUR', status: 'draft',
    created_at: '2026-10-31T16:20:00.000Z', submitted_at: null,
    reviewed_by: null, reviewed_at: null, review_comment: null,
    items: [
      { date: '2026-10-30', category: 'equipment', description: 'Ergonomic office chair', amount_cents: 24900 },
    ],
  },
  {
    id: 5, owner_id: 2, title: 'Team lunch', purpose: null,
    currency: 'EUR', status: 'rejected',
    created_at: '2026-10-16T12:00:00.000Z', submitted_at: '2026-10-16T12:02:00.000Z',
    reviewed_by: 'carol', reviewed_at: '2026-10-17T09:15:00.000Z',
    review_comment: 'Team lunches are paid from the events budget, not through expense claims.',
    items: [
      { date: '2026-10-15', category: 'meals', description: 'Team lunch', amount_cents: 5800 },
    ],
  },
  {
    id: 6, owner_id: 3, title: 'London user research trip', purpose: 'Usability sessions for the new onboarding flow',
    currency: 'GBP', status: 'submitted',
    created_at: '2026-10-29T10:10:00.000Z', submitted_at: '2026-10-29T10:15:00.000Z',
    reviewed_by: null, reviewed_at: null, review_comment: null,
    items: [
      { date: '2026-10-27', category: 'travel', description: 'Train to London', amount_cents: 7640 },
      { date: '2026-10-27', category: 'lodging', description: 'Hotel, 1 night', amount_cents: 14500 },
      { date: '2026-10-28', category: 'meals', description: 'Dinner', amount_cents: 2360 },
    ],
  },
  {
    id: 7, owner_id: 3, title: 'USB-C dock', purpose: null,
    currency: 'USD', status: 'draft',
    created_at: '2026-11-02T13:40:00.000Z', submitted_at: null,
    reviewed_by: null, reviewed_at: null, review_comment: null,
    items: [
      { date: '2026-11-02', category: 'equipment', description: 'USB-C docking station', amount_cents: 18999 },
    ],
  },
  {
    id: 8, owner_id: 2, title: 'Books for the team library', purpose: null,
    currency: 'EUR', status: 'approved',
    created_at: '2026-10-19T09:00:00.000Z', submitted_at: '2026-10-19T09:05:00.000Z',
    reviewed_by: 'carol', reviewed_at: '2026-10-20T11:11:00.000Z', review_comment: 'Approved, thanks',
    items: [
      { date: '2026-10-18', category: 'other', description: 'Designing Data-Intensive Applications', amount_cents: 4630 },
      { date: '2026-10-18', category: 'other', description: 'Release It!', amount_cents: 3870 },
    ],
  },
  {
    id: 9, owner_id: 1, title: 'Taxi to airport', purpose: null,
    currency: 'EUR', status: 'submitted',
    created_at: '2026-11-04T07:30:00.000Z', submitted_at: '2026-11-04T07:31:00.000Z',
    reviewed_by: null, reviewed_at: null, review_comment: null,
    items: [
      { date: '2026-11-03', category: 'travel', description: 'Taxi to Hamburg airport', amount_cents: 3780 },
    ],
  },
  {
    id: 10, owner_id: 3, title: 'Mobile DevSummit ticket', purpose: null,
    currency: 'USD', status: 'paid',
    created_at: '2026-10-02T08:00:00.000Z', submitted_at: '2026-10-02T08:10:00.000Z',
    reviewed_by: 'frank', reviewed_at: '2026-10-03T09:00:00.000Z', review_comment: null,
    items: [
      { date: '2026-10-01', category: 'other', description: 'Conference ticket', amount_cents: 29900 },
    ],
    payments: [{ amount_cents: 29900, paid_at: '2026-10-06T10:00:00.000Z', reference: 'PAY-2026-1006-02' }],
  },
];

function createSeed() {
  const users = USERS.map((user) => ({ ...user }));
  const claims = new Map();
  const items = new Map();
  const payments = new Map();
  let nextItemId = 1;

  for (const seed of CLAIMS) {
    const { items: seedItems, payments: seedPayments, ...fields } = seed;
    let totalCents = 0;
    for (const item of seedItems) {
      items.set(nextItemId, { id: nextItemId, claim_id: seed.id, ...item });
      totalCents += item.amount_cents;
      nextItemId += 1;
    }
    const lastChange = seedPayments
      ? seedPayments[seedPayments.length - 1].paid_at
      : fields.reviewed_at || fields.submitted_at || fields.created_at;
    claims.set(seed.id, { ...fields, total_cents: totalCents, updated_at: lastChange });
    if (seedPayments) payments.set(seed.id, seedPayments.map((p) => ({ ...p })));
  }

  return {
    users,
    claims,
    items,
    payments,
    nextClaimId: CLAIMS.length + 1,
    nextItemId,
  };
}

module.exports = { createSeed };
