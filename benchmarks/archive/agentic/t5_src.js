const path = require('path');
const fs = require('fs');
const assert = require('assert');

function load() {
  const p = path.join(__dirname, 'db.js');
  delete require.cache[require.resolve(p)];
  return require(p);
}
const fresh = () => load().createDB();

const reqs = [
  { id: 'R1', spec: 'db.js must export createDB(). db.collection(name) returns a collection, creating it on first use and returning the same object thereafter. coll.insert(doc) stores a shallow copy, assigns a unique string _id (do not mutate the caller\'s object), and returns the stored doc. coll.get(id) returns the stored doc or undefined. coll.count() returns the number of live docs.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      const input = { name: 'a' };
      const d = c.insert(input);
      assert.ok(typeof d._id === 'string' && d._id.length, '_id must be a non-empty string');
      assert.strictEqual(input._id, undefined, 'insert must not mutate the caller doc');
      assert.strictEqual(c.get(d._id).name, 'a');
      assert.strictEqual(c.get('nope'), undefined);
      assert.strictEqual(db.collection('u'), c, 'collection() must be idempotent');
      assert.strictEqual(c.count(), 1);
      const e = c.insert({ name: 'b' });
      assert.notStrictEqual(e._id, d._id, '_ids must be unique');
      assert.strictEqual(c.count(), 2);
    } },
  { id: 'R2', spec: 'coll.delete(id) removes a doc and returns true, or false if it was already absent. coll.update(id, patch) shallow-merges patch into the doc and returns the updated doc, or undefined if absent. Neither may renumber or reuse _ids. coll.all() returns every live doc in insertion order.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      const a = c.insert({ n: 1 }), b = c.insert({ n: 2 }), z = c.insert({ n: 3 });
      assert.strictEqual(c.delete(b._id), true);
      assert.strictEqual(c.delete(b._id), false);
      assert.strictEqual(c.count(), 2);
      assert.deepStrictEqual(c.all().map((d) => d.n), [1, 3]);
      assert.strictEqual(c.update(a._id, { n: 9, extra: true }).n, 9);
      assert.strictEqual(c.get(a._id).extra, true);
      assert.strictEqual(c.update('gone', { n: 1 }), undefined);
      assert.strictEqual(c.insert({ n: 4 })._id !== z._id, true);
    } },
  { id: 'R3', spec: 'coll.find(query) returns docs matching an equality query: every key in query must equal the doc field (strict equality). An empty query matches everything. Results keep insertion order.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      c.insert({ n: 1, t: 'x' }); c.insert({ n: 2, t: 'x' }); c.insert({ n: 3, t: 'y' });
      assert.deepStrictEqual(c.find({ t: 'x' }).map((d) => d.n), [1, 2]);
      assert.deepStrictEqual(c.find({ t: 'x', n: 2 }).map((d) => d.n), [2]);
      assert.strictEqual(c.find({}).length, 3);
      assert.strictEqual(c.find({ t: 'zz' }).length, 0);
      assert.strictEqual(c.find({ n: '1' }).length, 0, 'equality must be strict');
    } },
  { id: 'R4', spec: 'find() supports operator objects as values: $eq $ne $gt $gte $lt $lte $in $nin $exists. A value that is a plain object with at least one $-prefixed key is an operator object; any other value is an equality test.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      c.insert({ n: 1 }); c.insert({ n: 5 }); c.insert({ n: 9, tag: 'k' });
      assert.deepStrictEqual(c.find({ n: { $gt: 4 } }).map((d) => d.n), [5, 9]);
      assert.deepStrictEqual(c.find({ n: { $gte: 5, $lt: 9 } }).map((d) => d.n), [5]);
      assert.deepStrictEqual(c.find({ n: { $in: [1, 9] } }).map((d) => d.n), [1, 9]);
      assert.deepStrictEqual(c.find({ n: { $nin: [1, 9] } }).map((d) => d.n), [5]);
      assert.deepStrictEqual(c.find({ n: { $ne: 5 } }).map((d) => d.n), [1, 9]);
      assert.deepStrictEqual(c.find({ tag: { $exists: true } }).map((d) => d.n), [9]);
      assert.deepStrictEqual(c.find({ tag: { $exists: false } }).map((d) => d.n), [1, 5]);
    } },
  { id: 'R5', spec: 'find() supports the logical combinators $and, $or and $not at the top level of a query. $and and $or take arrays of sub-queries; $not takes a single sub-query. They nest arbitrarily and combine with field conditions in the same query object (all top-level keys are ANDed together).',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      c.insert({ n: 1, t: 'x' }); c.insert({ n: 5, t: 'y' }); c.insert({ n: 9, t: 'x' });
      assert.deepStrictEqual(c.find({ $or: [{ n: 1 }, { n: 9 }] }).map((d) => d.n), [1, 9]);
      assert.deepStrictEqual(c.find({ $and: [{ t: 'x' }, { n: { $gt: 2 } }] }).map((d) => d.n), [9]);
      assert.deepStrictEqual(c.find({ $not: { t: 'x' } }).map((d) => d.n), [5]);
      assert.deepStrictEqual(c.find({ t: 'x', $or: [{ n: 1 }, { n: 5 }] }).map((d) => d.n), [1]);
      assert.deepStrictEqual(c.find({ $or: [{ $and: [{ n: 1 }] }, { $not: { n: { $lt: 9 } } }] }).map((d) => d.n), [1, 9]);
    } },
  { id: 'R6', spec: 'find(query, opts) supports opts.sort as an array of [field, dir] pairs (dir 1 ascending, -1 descending, applied as a stable multi-key sort), opts.offset and opts.limit (offset applied before limit), and opts.project as an array of field names (returned docs contain only those fields plus _id).',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      c.insert({ n: 2, g: 'a', z: 1 }); c.insert({ n: 1, g: 'b', z: 2 }); c.insert({ n: 2, g: 'b', z: 3 }); c.insert({ n: 1, g: 'a', z: 4 });
      assert.deepStrictEqual(c.find({}, { sort: [['n', 1]] }).map((d) => d.z), [2, 4, 1, 3], 'sort must be stable');
      assert.deepStrictEqual(c.find({}, { sort: [['n', 1], ['g', -1]] }).map((d) => d.z), [2, 4, 3, 1]);
      assert.deepStrictEqual(c.find({}, { sort: [['n', 1]], offset: 1, limit: 2 }).map((d) => d.z), [4, 1]);
      const p = c.find({ z: 1 }, { project: ['n'] })[0];
      assert.deepStrictEqual(Object.keys(p).sort(), ['_id', 'n']);
    } },
  { id: 'R7', spec: 'Dotted field paths work everywhere a field name is accepted (queries, sort, project): "a.b.c" reads nested objects and yields undefined if any level is missing.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      c.insert({ k: 1, meta: { size: 10, deep: { x: 'p' } } });
      c.insert({ k: 2, meta: { size: 3 } });
      c.insert({ k: 3 });
      assert.deepStrictEqual(c.find({ 'meta.size': { $gt: 5 } }).map((d) => d.k), [1]);
      assert.deepStrictEqual(c.find({ 'meta.deep.x': 'p' }).map((d) => d.k), [1]);
      assert.deepStrictEqual(c.find({ 'meta.deep.x': { $exists: false } }).map((d) => d.k), [2, 3]);
      assert.deepStrictEqual(c.find({}, { sort: [['meta.size', -1]] }).map((d) => d.k), [1, 2, 3]);
    } },
  { id: 'R8', spec: 'coll.createIndex(field) builds an index used by equality and $in lookups. coll.stats() returns {scanned, indexHits} counting docs examined by find() and index lookups performed; an indexed equality find must not scan the whole collection. Indexes stay correct across insert, update and delete.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      for (let i = 0; i < 100; i++) c.insert({ n: i % 10, i });
      c.createIndex('n');
      const before = c.stats();
      const got = c.find({ n: 3 });
      const after = c.stats();
      assert.strictEqual(got.length, 10);
      assert.ok(after.indexHits > before.indexHits, 'indexHits must increase');
      assert.ok(after.scanned - before.scanned < 100, 'indexed find must not scan everything, scanned delta=' + (after.scanned - before.scanned));
      const d = c.find({ n: 3 })[0];
      c.update(d._id, { n: 99 });
      assert.strictEqual(c.find({ n: 99 }).length, 1);
      assert.strictEqual(c.find({ n: 3 }).length, 9);
      c.delete(c.find({ n: 99 })[0]._id);
      assert.strictEqual(c.find({ n: 99 }).length, 0);
    } },
  { id: 'R9', spec: 'coll.createIndex(field, {unique: true}) rejects duplicate values: insert and update throw an Error with code "DUPLICATE_KEY". Creating a unique index over existing duplicate data throws the same. Deleting a doc frees its key.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      c.createIndex('email', { unique: true });
      const a = c.insert({ email: 'x@y' });
      assert.throws(() => c.insert({ email: 'x@y' }), (e) => e.code === 'DUPLICATE_KEY');
      const b = c.insert({ email: 'z@y' });
      assert.throws(() => c.update(b._id, { email: 'x@y' }), (e) => e.code === 'DUPLICATE_KEY');
      c.delete(a._id);
      assert.ok(c.insert({ email: 'x@y' })._id);
      const d2 = fresh().collection('v');
      d2.insert({ e: 1 }); d2.insert({ e: 1 });
      assert.throws(() => d2.createIndex('e', { unique: true }), (e) => e.code === 'DUPLICATE_KEY');
    } },
  { id: 'R10', spec: 'coll.aggregate({groupBy, count, sum, avg, min, max}) groups docs by the groupBy field (dotted paths allowed) and returns an array of {key, count, sum, avg, min, max} — only the requested statistics plus key and count. Omitting groupBy aggregates the whole collection into a single row with key null. Groups appear in first-seen order. avg of zero numeric values is null, not NaN.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      c.insert({ g: 'b', v: 2 }); c.insert({ g: 'a', v: 4 }); c.insert({ g: 'b', v: 6 }); c.insert({ g: 'a' });
      const r = c.aggregate({ groupBy: 'g', count: true, sum: 'v', avg: 'v' });
      assert.deepStrictEqual(r.map((x) => x.key), ['b', 'a']);
      assert.strictEqual(r[0].count, 2); assert.strictEqual(r[0].sum, 8); assert.strictEqual(r[0].avg, 4);
      assert.strictEqual(r[1].count, 2); assert.strictEqual(r[1].sum, 4); assert.strictEqual(r[1].avg, 4, 'non-numeric values are excluded from avg');
      assert.strictEqual(r[0].min, undefined, 'unrequested stats must be absent');
      const t = c.aggregate({ count: true, max: 'v', min: 'v' });
      assert.strictEqual(t.length, 1); assert.strictEqual(t[0].key, null);
      assert.strictEqual(t[0].max, 6); assert.strictEqual(t[0].min, 2);
      const e = fresh().collection('e');
      e.insert({ g: 'a' });
      assert.strictEqual(e.aggregate({ groupBy: 'g', avg: 'v' })[0].avg, null);
    } },
  { id: 'R11', spec: 'db.toJSON() returns a plain JSON-serialisable snapshot of every collection, its docs and its index definitions. createDB({from: snapshot}) restores it exactly: docs, _ids, insertion order, indexes and unique constraints all survive a round trip through JSON.stringify/parse.',
    test: () => {
      const { createDB } = load();
      const db = createDB(); const c = db.collection('u');
      c.createIndex('e', { unique: true });
      const a = c.insert({ e: 1, n: 'x' }); c.insert({ e: 2, n: 'y' });
      const snap = JSON.parse(JSON.stringify(db.toJSON()));
      const db2 = createDB({ from: snap });
      const c2 = db2.collection('u');
      assert.strictEqual(c2.count(), 2);
      assert.strictEqual(c2.get(a._id).n, 'x');
      assert.deepStrictEqual(c2.all().map((d) => d.e), [1, 2]);
      assert.throws(() => c2.insert({ e: 1 }), (e) => e.code === 'DUPLICATE_KEY', 'unique index must survive restore');
    } },
  { id: 'R12', spec: 'db.begin() starts a transaction. Writes made through it are visible to reads inside it but not outside until tx.commit(). tx.rollback() discards them, including index changes. Committing or rolling back twice throws code "TX_CLOSED". Reads outside an open transaction never see uncommitted data.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      c.insert({ n: 1 });
      const tx = db.begin();
      const tc = tx.collection('u');
      tc.insert({ n: 2 });
      assert.strictEqual(tc.count(), 2, 'transaction sees its own writes');
      assert.strictEqual(c.count(), 1, 'outside must not see uncommitted writes');
      tx.rollback();
      assert.strictEqual(c.count(), 1);
      assert.throws(() => tx.rollback(), (e) => e.code === 'TX_CLOSED');
      const tx2 = db.begin();
      tx2.collection('u').insert({ n: 3 });
      tx2.commit();
      assert.strictEqual(c.count(), 2);
      assert.deepStrictEqual(c.find({ n: 3 }).length, 1);
      assert.throws(() => tx2.commit(), (e) => e.code === 'TX_CLOSED');
    } },
  { id: 'R13', spec: 'coll.setSchema(schema) validates on insert and update. A schema maps field names to {type, required, min, max, enum} where type is one of "string" "number" "boolean" "object" "array". Violations throw an Error with code "VALIDATION" and a .field property naming the first offending field, checked in schema key order. Fields not in the schema are allowed.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      c.setSchema({ name: { type: 'string', required: true }, age: { type: 'number', min: 0, max: 150 }, role: { enum: ['a', 'b'] } });
      assert.ok(c.insert({ name: 'x', age: 3, role: 'a', extra: 1 })._id);
      assert.throws(() => c.insert({ age: 3 }), (e) => e.code === 'VALIDATION' && e.field === 'name');
      assert.throws(() => c.insert({ name: 5 }), (e) => e.code === 'VALIDATION' && e.field === 'name');
      assert.throws(() => c.insert({ name: 'x', age: -1 }), (e) => e.code === 'VALIDATION' && e.field === 'age');
      assert.throws(() => c.insert({ name: 'x', age: 200 }), (e) => e.code === 'VALIDATION' && e.field === 'age');
      assert.throws(() => c.insert({ name: 'x', role: 'c' }), (e) => e.code === 'VALIDATION' && e.field === 'role');
      const d = c.insert({ name: 'ok' });
      assert.throws(() => c.update(d._id, { age: 999 }), (e) => e.code === 'VALIDATION');
      assert.strictEqual(c.get(d._id).age, undefined, 'a rejected update must not partially apply');
    } },
  { id: 'R14', spec: 'coll.insert(doc, {ttlMs}) marks a doc to expire. db.tick(ms) advances an internal logical clock; expired docs disappear from get, find, all, count and aggregates, and their index entries are released. Time never moves on its own — only db.tick advances it.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      c.createIndex('n', { unique: true });
      const a = c.insert({ n: 1 }, { ttlMs: 100 });
      c.insert({ n: 2 });
      db.tick(50);
      assert.strictEqual(c.count(), 2);
      db.tick(60);
      assert.strictEqual(c.get(a._id), undefined, 'expired doc must vanish');
      assert.strictEqual(c.count(), 1);
      assert.strictEqual(c.find({ n: 1 }).length, 0);
      assert.ok(c.insert({ n: 1 })._id, 'expiry must release the unique key');
    } },
  { id: 'R15', spec: 'db.join(leftName, rightName, {on, as, type}) returns left docs with matching right docs attached under the `as` key. `on` is [leftField, rightField]. type is "inner" (drop unmatched left docs) or "left" (keep them with an empty array). Results must not mutate the stored documents.',
    test: () => {
      const db = fresh();
      const u = db.collection('u'), o = db.collection('o');
      const a = u.insert({ name: 'a' }), b = u.insert({ name: 'b' });
      o.insert({ uid: a._id, v: 1 }); o.insert({ uid: a._id, v: 2 });
      const inner = db.join('u', 'o', { on: ['_id', 'uid'], as: 'orders', type: 'inner' });
      assert.strictEqual(inner.length, 1);
      assert.deepStrictEqual(inner[0].orders.map((x) => x.v), [1, 2]);
      const left = db.join('u', 'o', { on: ['_id', 'uid'], as: 'orders', type: 'left' });
      assert.strictEqual(left.length, 2);
      assert.deepStrictEqual(left[1].orders, []);
      assert.strictEqual(u.get(b._id).orders, undefined, 'join must not mutate stored docs');
    } },
  { id: 'R16', spec: 'coll.page(query, {sort, limit}) returns {docs, cursor}. Passing that cursor back as {cursor, limit} continues exactly where the previous page stopped, with no duplicates and no gaps, even if unrelated docs are inserted or deleted between calls. cursor is null when the last page is reached, and must be an opaque string.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      for (let i = 0; i < 7; i++) c.insert({ i });
      const seen = [];
      let r = c.page({}, { sort: [['i', 1]], limit: 3 });
      assert.strictEqual(typeof r.cursor, 'string');
      seen.push(...r.docs.map((d) => d.i));
      c.insert({ i: 99 });
      r = c.page({}, { cursor: r.cursor, limit: 3 });
      seen.push(...r.docs.map((d) => d.i));
      r = c.page({}, { cursor: r.cursor, limit: 3 });
      seen.push(...r.docs.map((d) => d.i));
      assert.deepStrictEqual(seen, [0, 1, 2, 3, 4, 5, 6, 99]);
      assert.strictEqual(r.cursor, null, 'final page must report a null cursor');
    } },
  { id: 'R17', spec: 'Every doc carries a numeric _version starting at 1 and incremented on each successful update. coll.update(id, patch, {ifVersion}) throws code "CONFLICT" when ifVersion does not match the current version, leaving the doc untouched.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      const d = c.insert({ n: 1 });
      assert.strictEqual(d._version, 1);
      const u1 = c.update(d._id, { n: 2 });
      assert.strictEqual(u1._version, 2);
      assert.throws(() => c.update(d._id, { n: 3 }, { ifVersion: 1 }), (e) => e.code === 'CONFLICT');
      assert.strictEqual(c.get(d._id).n, 2, 'a conflicted update must not apply');
      assert.strictEqual(c.update(d._id, { n: 4 }, { ifVersion: 2 }).n, 4);
      assert.strictEqual(c.get(d._id)._version, 3);
    } },
  { id: 'R18', spec: 'coll.createIndex(field, {range: true}) builds an ordered index that also serves $gt/$gte/$lt/$lte and sorted scans. A range query over a range index must examine far fewer docs than the collection size, as visible in stats().scanned.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      for (let i = 0; i < 500; i++) c.insert({ n: i });
      c.createIndex('n', { range: true });
      const before = c.stats().scanned;
      const got = c.find({ n: { $gte: 490 } });
      const delta = c.stats().scanned - before;
      assert.deepStrictEqual(got.map((d) => d.n).sort((a, b) => a - b), [490, 491, 492, 493, 494, 495, 496, 497, 498, 499]);
      assert.ok(delta < 100, 'range index must avoid a full scan, scanned delta=' + delta);
      c.insert({ n: 495 });
      assert.strictEqual(c.find({ n: { $gte: 490 } }).length, 11, 'range index must stay live on insert');
    } },
  { id: 'R19', spec: 'coll.explain(query, opts) returns {plan, index, estimatedDocs} without running the query: plan is "index" | "range" | "scan", index names the chosen field, and the planner must prefer a unique index, then an equality index, then a range index, then a full scan. Ties break toward the field appearing first in the query object.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      for (let i = 0; i < 50; i++) c.insert({ a: i, b: i % 5, e: 'k' + i });
      c.createIndex('b'); c.createIndex('a', { range: true }); c.createIndex('e', { unique: true });
      assert.strictEqual(c.explain({ b: 2 }).plan, 'index');
      assert.strictEqual(c.explain({ b: 2 }).index, 'b');
      assert.strictEqual(c.explain({ a: { $gt: 40 } }).plan, 'range');
      assert.strictEqual(c.explain({ zzz: 1 }).plan, 'scan');
      const both = c.explain({ e: 'k1', b: 2 });
      assert.strictEqual(both.index, 'e', 'unique index must win over a plain equality index');
      const scannedBefore = c.stats().scanned;
      c.explain({ b: 2 });
      assert.strictEqual(c.stats().scanned, scannedBefore, 'explain must not execute the query');
    } },
  { id: 'R20', spec: 'db.compact() permanently drops expired and deleted docs, rebuilds all indexes, and returns {reclaimed} counting the docs removed. After compaction every earlier behaviour still holds: ids, versions, order, indexes, unique constraints and schemas are unchanged for surviving docs.',
    test: () => {
      const db = fresh(); const c = db.collection('u');
      c.createIndex('n', { unique: true });
      const keep = c.insert({ n: 1 });
      const del = c.insert({ n: 2 });
      c.insert({ n: 3 }, { ttlMs: 10 });
      c.update(keep._id, { extra: 1 });
      c.delete(del._id);
      db.tick(50);
      const r = db.compact();
      assert.strictEqual(r.reclaimed, 2, 'must reclaim the deleted doc and the expired doc');
      assert.strictEqual(c.count(), 1);
      assert.strictEqual(c.get(keep._id)._version, 2, 'versions must survive compaction');
      assert.strictEqual(c.get(keep._id).extra, 1);
      assert.strictEqual(c.find({ n: 1 }).length, 1, 'indexes must be rebuilt');
      assert.ok(c.insert({ n: 2 })._id, 'compaction must release keys of removed docs');
      assert.throws(() => c.insert({ n: 1 }), (e) => e.code === 'DUPLICATE_KEY');
    } },
  { id: 'R21', spec: 'Write your own regression suite at tests/suite.js. Running `node tests/suite.js` must exit 0 and print a final line "assertions: <n>" where n is at least 80. It must require ../db.js, exercise every requirement R1-R20, and use node\'s assert module. It must be a real suite: deleting any feature from db.js should make it fail.',
    test: () => {
      const p = path.join(__dirname, 'tests', 'suite.js');
      assert.ok(fs.existsSync(p), 'tests/suite.js does not exist');
      const src = fs.readFileSync(p, 'utf8');
      assert.ok(/require\(.*db(\.js)?.*\)/.test(src), 'suite must require ../db.js');
      const calls = (src.match(/assert\s*[.(]/g) || []).length;
      assert.ok(calls >= 80, 'suite must contain at least 80 assert calls, found ' + calls);
      const { execFileSync } = require('child_process');
      let out;
      try {
        out = execFileSync(process.execPath, [p], { encoding: 'utf8', timeout: 30000, cwd: __dirname });
      } catch (e) {
        throw new Error('node tests/suite.js exited non-zero:\n' + ((e.stdout || '') + (e.stderr || '')).slice(-1500));
      }
      const m = out.trim().split('\n').pop().match(/^assertions:\s*(\d+)$/);
      assert.ok(m, 'last line must be "assertions: <n>", got: ' + JSON.stringify(out.trim().split('\n').pop()));
      assert.ok(Number(m[1]) >= 80, 'suite must report at least 80 assertions, reported ' + m[1]);
    } },
];

let done = 0;
for (const r of reqs) {
  let failure = null;
  try { r.test(); } catch (e) { failure = e; }
  if (failure) {
    console.log('=== ' + r.id + ' of ' + reqs.length + ' — NOT MET ===');
    console.log(r.spec);
    console.log('');
    console.log('failing check:');
    console.log('  ' + String(failure.message || failure).split('\n').join('\n  '));
    console.log('');
    console.log('requirements met so far: ' + done + '/' + reqs.length);
    console.log('(the next requirement is revealed only once this one passes)');
    process.exit(1);
  }
  done++;
}
console.log('COMPLETE: all ' + reqs.length + ' requirements met');
