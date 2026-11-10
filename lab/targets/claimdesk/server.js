'use strict';

const http = require('node:http');
const crypto = require('node:crypto');
const { createSeed } = require('./seed');

const PORT = Number(process.env.PORT) || 3001;

const STATUSES = ['draft', 'submitted', 'approved', 'rejected', 'paid'];
const EDITABLE_STATUSES = ['draft', 'rejected'];
const CURRENCIES = ['EUR', 'USD', 'GBP'];
const CATEGORIES = ['travel', 'meals', 'lodging', 'equipment', 'other'];
const REVIEW_DECISIONS = ['approve', 'reject'];
const READ_ONLY_FIELDS = ['id', 'owner', 'owner_id', 'team', 'items', 'total', 'created_at', 'updated_at'];

const MAX_TITLE_LENGTH = 120;
const MAX_PURPOSE_LENGTH = 500;
const MAX_DESCRIPTION_LENGTH = 200;
const MAX_COMMENT_LENGTH = 500;
const MAX_REFERENCE_LENGTH = 64;
const MAX_ITEM_AMOUNT = 10000;
const MEAL_LIMIT_CENTS = 6000;
const MAX_ITEM_AGE_DAYS = 90;
const DAY_MS = 24 * 60 * 60 * 1000;
const DEFAULT_PER_PAGE = 10;
const MAX_PER_PAGE = 50;
const MAX_BODY_BYTES = 1024 * 1024;

const db = createSeed();
const sessions = new Map();

class HttpError extends Error {
  constructor(status, code, message, field) {
    super(message);
    this.status = status;
    this.code = code;
    this.field = field;
  }
}

const badRequest = (field, message) => new HttpError(400, 'validation_failed', message, field);
const forbidden = (message) => new HttpError(403, 'forbidden', message);
const notFound = (message = 'claim not found') => new HttpError(404, 'not_found', message);
const conflict = (message) => new HttpError(409, 'invalid_state', message);

// ---------------------------------------------------------------------------
// HTTP helpers

function send(res, status, body, headers = {}) {
  if (body === undefined) {
    res.writeHead(status, headers);
    res.end();
    return;
  }
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(payload),
    ...headers,
  });
  res.end(payload);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    let tooLarge = false;
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        tooLarge = true;
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => {
      if (tooLarge) {
        reject(new HttpError(413, 'payload_too_large', 'request body must not exceed 1 MB'));
        return;
      }
      resolve(Buffer.concat(chunks).toString('utf8'));
    });
    req.on('error', reject);
  });
}

function parseJson(raw) {
  if (raw.trim() === '') return undefined;
  try {
    return JSON.parse(raw);
  } catch {
    throw new HttpError(400, 'invalid_json', 'request body is not valid JSON');
  }
}

function requireObject(body) {
  if (body === null || typeof body !== 'object' || Array.isArray(body)) {
    throw new HttpError(400, 'invalid_body', 'request body must be a JSON object');
  }
  return body;
}

function optionalObject(body) {
  if (body === undefined) return {};
  return requireObject(body);
}

// ---------------------------------------------------------------------------
// Users, sessions and permissions

function userById(id) {
  return db.users.find((user) => user.id === id);
}

function userByUsername(username) {
  return db.users.find((user) => user.username === username);
}

function publicUser(user) {
  return { id: user.id, username: user.username, name: user.name, role: user.role, team: user.team };
}

function authenticate(req) {
  const header = req.headers.authorization || '';
  const match = /^bearer\s+(\S+)\s*$/i.exec(header);
  const userId = match ? sessions.get(match[1]) : undefined;
  if (!userId) {
    throw new HttpError(401, 'unauthorized', 'a valid bearer token is required');
  }
  return userById(userId);
}

function canView(user, claim) {
  if (claim.owner_id === user.id) return true;
  if (claim.status === 'draft') return false;
  if (user.role === 'finance') return true;
  if (user.role === 'manager') return userById(claim.owner_id).team === user.team;
  return false;
}

function canReview(user, claim) {
  return user.role === 'manager' && claim.owner_id !== user.id;
}

function deny(user, claim, message) {
  return canView(user, claim) ? forbidden(message) : notFound();
}

function parseId(value) {
  return /^[1-9]\d{0,14}$/.test(value) ? Number(value) : null;
}

function findClaim(rawId) {
  const id = parseId(rawId);
  const claim = id === null ? undefined : db.claims.get(id);
  if (!claim) throw notFound();
  return claim;
}

function loadVisibleClaim(user, rawId) {
  const claim = findClaim(rawId);
  if (!canView(user, claim)) throw notFound();
  return claim;
}

function loadOwnClaim(user, rawId) {
  const claim = findClaim(rawId);
  if (claim.owner_id !== user.id) throw deny(user, claim, 'only the owner of a claim can change it');
  return claim;
}

function assertEditable(claim) {
  if (!EDITABLE_STATUSES.includes(claim.status)) {
    throw conflict(`claim is ${claim.status}; only draft or rejected claims can be changed`);
  }
}

// ---------------------------------------------------------------------------
// Validation

function validateText(value, field, maxLength, { required }) {
  if (value === undefined || value === null) {
    if (required) throw badRequest(field, `${field} is required`);
    return null;
  }
  if (typeof value !== 'string') throw badRequest(field, `${field} must be a string`);
  const text = value.trim();
  if (text.length === 0) {
    if (required) throw badRequest(field, `${field} must not be empty`);
    return null;
  }
  if (text.length > maxLength) throw badRequest(field, `${field} must be at most ${maxLength} characters`);
  return text;
}

function validateCurrency(value) {
  if (!CURRENCIES.includes(value)) {
    throw badRequest('currency', `currency must be one of ${CURRENCIES.join(', ')}`);
  }
  return value;
}

function parseCalendarDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [year, month, day] = value.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    return null;
  }
  return date;
}

function toCents(amount) {
  return Math.floor(amount * 100);
}

function fromCents(cents) {
  return cents / 100;
}

function validateItem(input, prefix) {
  const field = (name) => (prefix ? `${prefix}.${name}` : name);
  if (input === null || typeof input !== 'object' || Array.isArray(input)) {
    throw badRequest(prefix || 'item', 'item must be a JSON object');
  }

  const date = parseCalendarDate(input.date);
  if (!date) throw badRequest(field('date'), 'date must be a valid calendar date in YYYY-MM-DD format');
  const now = new Date();
  if (date > now) throw badRequest(field('date'), 'date must not be in the future');
  const earliest = new Date(now.getTime() - MAX_ITEM_AGE_DAYS * DAY_MS);
  if (date < earliest) {
    throw badRequest(field('date'), `date must not be more than ${MAX_ITEM_AGE_DAYS} days in the past`);
  }

  if (!CATEGORIES.includes(input.category)) {
    throw badRequest(field('category'), `category must be one of ${CATEGORIES.join(', ')}`);
  }

  const description = validateText(input.description, field('description'), MAX_DESCRIPTION_LENGTH, { required: true });

  const { amount } = input;
  if (typeof amount !== 'number' || !Number.isFinite(amount)) {
    throw badRequest(field('amount'), 'amount must be a number');
  }
  if (amount < 0) throw badRequest(field('amount'), 'amount must be greater than 0');
  if (amount > MAX_ITEM_AMOUNT) throw badRequest(field('amount'), 'amount must not exceed 10000.00');
  if (!/^\d+(\.\d{1,2})?$/.test(String(amount))) {
    throw badRequest(field('amount'), 'amount must have at most two decimal places');
  }

  const amountCents = toCents(amount);
  if (input.category === 'meals' && amountCents > MEAL_LIMIT_CENTS) {
    throw badRequest(field('amount'), 'meals are limited to 60.00 per day');
  }

  return { date: input.date, category: input.category, description, amount_cents: amountCents };
}

function parsePositiveInt(value, fallback, field) {
  if (value === null || value === '') return fallback;
  if (!/^\d+$/.test(value) || Number(value) < 1) {
    throw badRequest(field, `${field} must be a positive integer`);
  }
  return Number(value);
}

// ---------------------------------------------------------------------------
// Representations

function itemsOf(claimId) {
  return [...db.items.values()].filter((item) => item.claim_id === claimId);
}

function itemView(item) {
  return {
    id: item.id,
    claim_id: item.claim_id,
    date: item.date,
    category: item.category,
    description: item.description,
    amount: fromCents(item.amount_cents),
  };
}

function claimSummary(claim) {
  const owner = userById(claim.owner_id);
  return {
    id: claim.id,
    title: claim.title,
    owner: owner.username,
    team: owner.team,
    currency: claim.currency,
    status: claim.status,
    total: fromCents(claim.total_cents),
    created_at: claim.created_at,
    submitted_at: claim.submitted_at,
  };
}

function claimDetail(claim) {
  const owner = userById(claim.owner_id);
  const items = itemsOf(claim.id);
  const payments = db.payments.get(claim.id) || [];
  const lastPayment = payments[payments.length - 1];
  return {
    id: claim.id,
    title: claim.title,
    purpose: claim.purpose,
    owner: owner.username,
    team: owner.team,
    currency: claim.currency,
    status: claim.status,
    items: items.map(itemView),
    total: fromCents(items.reduce((sum, item) => sum + item.amount_cents, 0)),
    created_at: claim.created_at,
    updated_at: claim.updated_at,
    submitted_at: claim.submitted_at,
    reviewed_by: claim.reviewed_by,
    reviewed_at: claim.reviewed_at,
    review_comment: claim.review_comment,
    paid_at: lastPayment ? lastPayment.paid_at : null,
    amount_paid: payments.length ? fromCents(payments.reduce((sum, p) => sum + p.amount_cents, 0)) : null,
    payment_reference: lastPayment ? lastPayment.reference : null,
  };
}

// ---------------------------------------------------------------------------
// Handlers

function ping() {
  return { status: 200, body: { status: 'ok' } };
}

function login({ body }) {
  const { username, password } = requireObject(body);
  if (typeof username !== 'string' || typeof password !== 'string') {
    throw badRequest('username', 'username and password must be strings');
  }
  const user = userByUsername(username);
  if (!user || user.password !== password) {
    throw new HttpError(401, 'invalid_credentials', 'username or password is incorrect');
  }
  const token = crypto.randomBytes(24).toString('hex');
  sessions.set(token, user.id);
  return { status: 200, body: { token, user: publicUser(user) } };
}

function claimsInScope(user, ownerFilter) {
  if (ownerFilter) {
    const owner = userByUsername(ownerFilter);
    return owner ? [...db.claims.values()].filter((claim) => claim.owner_id === owner.id) : [];
  }
  return [...db.claims.values()].filter((claim) => canView(user, claim));
}

const SORTS = {
  created_at: (a, b) => a.created_at.localeCompare(b.created_at),
  total: (a, b) => a.total_cents - b.total_cents,
};

function listClaims({ user, query }) {
  const status = query.get('status');
  if (status && !STATUSES.includes(status)) {
    throw badRequest('status', `status must be one of ${STATUSES.join(', ')}`);
  }
  const page = parsePositiveInt(query.get('page'), 1, 'page');
  const perPage = parsePositiveInt(query.get('per_page'), DEFAULT_PER_PAGE, 'per_page');
  if (perPage > MAX_PER_PAGE) throw badRequest('per_page', `per_page must be at most ${MAX_PER_PAGE}`);
  const search = (query.get('q') || '').trim().toLowerCase();
  const sort = query.get('sort') || '-created_at';

  let rows = claimsInScope(user, query.get('owner'));
  if (status) rows = rows.filter((claim) => claim.status === status);
  if (search) rows = rows.filter((claim) => claim.title.toLowerCase().includes(search));

  const descending = sort.startsWith('-');
  const compare = SORTS[descending ? sort.slice(1) : sort];
  rows.sort((a, b) => (descending ? -compare(a, b) : compare(a, b)) || a.id - b.id);

  const start = (page - 1) * perPage;
  const data = rows.slice(start, start + perPage).map(claimSummary);
  return {
    status: 200,
    body: {
      data,
      meta: {
        page,
        per_page: perPage,
        total_count: rows.length,
        next_page: start + perPage <= rows.length ? page + 1 : null,
      },
    },
  };
}

function insertItem(claim, item) {
  const id = db.nextItemId;
  db.nextItemId += 1;
  const stored = { id, claim_id: claim.id, ...item };
  db.items.set(id, stored);
  claim.total_cents += item.amount_cents;
  return stored;
}

function createClaim({ user, body }) {
  if (user.role !== 'employee') throw forbidden('only employees can create claims');
  const input = requireObject(body);
  const title = validateText(input.title, 'title', MAX_TITLE_LENGTH, { required: true });
  const purpose = validateText(input.purpose, 'purpose', MAX_PURPOSE_LENGTH, { required: false });
  if (input.currency === undefined) throw badRequest('currency', 'currency is required');
  const currency = validateCurrency(input.currency);

  let items = [];
  if (input.items !== undefined) {
    if (!Array.isArray(input.items)) throw badRequest('items', 'items must be an array');
    items = input.items.map((item, index) => validateItem(item, `items[${index}]`));
  }

  const now = new Date().toISOString();
  const claim = {
    id: db.nextClaimId,
    owner_id: user.id,
    title,
    purpose,
    currency,
    status: 'draft',
    total_cents: 0,
    created_at: now,
    updated_at: now,
    submitted_at: null,
    reviewed_by: null,
    reviewed_at: null,
    review_comment: null,
  };
  db.nextClaimId += 1;
  db.claims.set(claim.id, claim);
  for (const item of items) insertItem(claim, item);

  return { status: 201, body: claimDetail(claim), headers: { Location: `/claims/${claim.id}` } };
}

function getClaim({ user, params }) {
  return { status: 200, body: claimDetail(loadVisibleClaim(user, params.id)) };
}

function updateClaim({ user, params, body }) {
  const claim = loadOwnClaim(user, params.id);
  assertEditable(claim);
  const input = requireObject(body);

  const changes = {};
  for (const [key, value] of Object.entries(input)) {
    if (!READ_ONLY_FIELDS.includes(key)) changes[key] = value;
  }
  if ('title' in changes) {
    changes.title = validateText(changes.title, 'title', MAX_TITLE_LENGTH, { required: true });
  }
  if ('purpose' in changes) {
    changes.purpose = validateText(changes.purpose, 'purpose', MAX_PURPOSE_LENGTH, { required: false });
  }
  if ('currency' in changes) changes.currency = validateCurrency(changes.currency);

  Object.assign(claim, changes);
  claim.updated_at = new Date().toISOString();
  return { status: 200, body: claimDetail(claim) };
}

function deleteClaim({ user, params }) {
  const claim = loadOwnClaim(user, params.id);
  if (claim.status !== 'draft') throw conflict(`claim is ${claim.status}; only draft claims can be deleted`);
  for (const item of itemsOf(claim.id)) db.items.delete(item.id);
  db.claims.delete(claim.id);
  return { status: 204 };
}

function addItem({ user, params, body }) {
  const claim = loadOwnClaim(user, params.id);
  assertEditable(claim);
  const item = insertItem(claim, validateItem(requireObject(body), ''));
  claim.updated_at = new Date().toISOString();
  return { status: 201, body: itemView(item) };
}

function removeItem({ user, params }) {
  const claim = loadOwnClaim(user, params.id);
  assertEditable(claim);
  const itemId = parseId(params.itemId);
  if (itemId === null || !db.items.has(itemId)) throw notFound('item not found');
  db.items.delete(itemId);
  claim.updated_at = new Date().toISOString();
  return { status: 204 };
}

function submitClaim({ user, params }) {
  const claim = loadOwnClaim(user, params.id);
  if (claim.status !== 'draft') {
    throw conflict(`claim is ${claim.status}; only draft claims can be submitted`);
  }
  if (itemsOf(claim.id).length === 0) {
    throw badRequest('items', 'a claim needs at least one item before it can be submitted');
  }
  const now = new Date().toISOString();
  claim.status = 'submitted';
  claim.submitted_at = now;
  claim.updated_at = now;
  return { status: 200, body: claimDetail(claim) };
}

function reviewClaim({ user, params, body }) {
  const claim = findClaim(params.id);
  if (!canReview(user, claim)) {
    throw deny(user, claim, "only a manager of the claimant's team can review this claim");
  }
  if (claim.status !== 'submitted') {
    throw conflict(`claim is ${claim.status}; only submitted claims can be reviewed`);
  }
  const input = requireObject(body);
  if (!REVIEW_DECISIONS.includes(input.decision)) {
    throw badRequest('decision', 'decision must be "approve" or "reject"');
  }
  const comment = validateText(input.comment, 'comment', MAX_COMMENT_LENGTH, { required: false });
  if (input.decision === 'reject' && !comment) {
    throw badRequest('comment', 'a comment is required when rejecting a claim');
  }

  const now = new Date().toISOString();
  claim.status = input.decision === 'approve' ? 'approved' : 'rejected';
  claim.reviewed_by = user.username;
  claim.reviewed_at = now;
  claim.review_comment = comment;
  claim.updated_at = now;
  return { status: 200, body: claimDetail(claim) };
}

function payClaim({ user, params, body }) {
  const claim = loadVisibleClaim(user, params.id);
  if (user.role !== 'finance') throw forbidden('only finance can pay claims');
  if (claim.status !== 'approved' && claim.status !== 'paid') {
    throw conflict(`claim is ${claim.status}; only approved claims can be paid`);
  }
  const input = optionalObject(body);
  const reference = validateText(input.reference, 'reference', MAX_REFERENCE_LENGTH, { required: false });

  const now = new Date().toISOString();
  const payments = db.payments.get(claim.id) || [];
  payments.push({ amount_cents: claim.total_cents, paid_at: now, reference });
  db.payments.set(claim.id, payments);
  claim.status = 'paid';
  claim.updated_at = now;
  return { status: 200, body: claimDetail(claim) };
}

// ---------------------------------------------------------------------------
// Routing

const ROUTES = [
  { pattern: /^\/ping$/, methods: { GET: { handler: ping, auth: false } } },
  { pattern: /^\/auth\/login$/, methods: { POST: { handler: login, auth: false } } },
  { pattern: /^\/claims$/, methods: { GET: { handler: listClaims }, POST: { handler: createClaim } } },
  {
    pattern: /^\/claims\/(?<id>[^/]+)$/,
    methods: { GET: { handler: getClaim }, PATCH: { handler: updateClaim }, DELETE: { handler: deleteClaim } },
  },
  { pattern: /^\/claims\/(?<id>[^/]+)\/items$/, methods: { POST: { handler: addItem } } },
  { pattern: /^\/claims\/(?<id>[^/]+)\/items\/(?<itemId>[^/]+)$/, methods: { DELETE: { handler: removeItem } } },
  { pattern: /^\/claims\/(?<id>[^/]+)\/submit$/, methods: { POST: { handler: submitClaim } } },
  { pattern: /^\/claims\/(?<id>[^/]+)\/review$/, methods: { POST: { handler: reviewClaim } } },
  { pattern: /^\/claims\/(?<id>[^/]+)\/pay$/, methods: { POST: { handler: payClaim } } },
];

function matchRoute(method, pathname) {
  for (const route of ROUTES) {
    const match = route.pattern.exec(pathname);
    if (!match) continue;
    const endpoint = route.methods[method];
    if (!endpoint) {
      const allow = Object.keys(route.methods).join(', ');
      throw Object.assign(
        new HttpError(405, 'method_not_allowed', `${method} is not allowed on ${pathname}`),
        { headers: { Allow: allow } },
      );
    }
    return { endpoint, params: { ...match.groups } };
  }
  throw new HttpError(404, 'not_found', `no route for ${method} ${pathname}`);
}

function parseUrl(rawUrl) {
  try {
    return new URL(rawUrl, 'http://localhost');
  } catch {
    throw new HttpError(400, 'invalid_url', 'request URL could not be parsed');
  }
}

async function handle(req, res) {
  const url = parseUrl(req.url);
  let pathname = url.pathname;
  if (pathname.length > 1 && pathname.endsWith('/')) pathname = pathname.slice(0, -1);

  const { endpoint, params } = matchRoute(req.method, pathname);
  const raw = await readBody(req);
  const user = endpoint.auth === false ? null : authenticate(req);
  const body = req.method === 'POST' || req.method === 'PATCH' ? parseJson(raw) : undefined;
  const result = endpoint.handler({ user, params, query: url.searchParams, body });
  send(res, result.status, result.body, result.headers);
}

const server = http.createServer((req, res) => {
  handle(req, res).catch((err) => {
    if (err instanceof HttpError) {
      const body = { error: err.code, message: err.message };
      if (err.field) body.field = err.field;
      send(res, err.status, body, err.headers);
      return;
    }
    console.error(err);
    send(res, 500, { error: 'internal_error', message: 'unexpected server error' });
  });
});

server.listen(PORT, () => {
  console.log(`Claimdesk API listening on http://localhost:${PORT}`);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => process.exit(0));
}
