import test from 'node:test';
import assert from 'node:assert/strict';
import {compatibility} from '../lib/server/postgres.ts';

test('SQLite positional args become PostgreSQL binds', () => {
  const q=compatibility("SELECT * FROM users WHERE username=? AND nickname LIKE '?' AND id=?");
  assert.equal(q.sql,"SELECT * FROM users WHERE username=$1 AND nickname LIKE '?' AND id=$2");
  assert.equal(q.count,2);
});

test('insert ignore and SQLite aggregations are converted', () => {
  assert.match(compatibility('INSERT OR IGNORE INTO pool VALUES(?,?)').sql,/ON CONFLICT DO NOTHING$/);
  assert.match(compatibility("SELECT SUM(state='won'),GROUP_CONCAT(topic) FROM games").sql,/SUM\(CASE WHEN state='won' THEN 1 ELSE 0 END\)/);
  assert.match(compatibility('SELECT GROUP_CONCAT(DISTINCT source) FROM pool').sql,/STRING_AGG\(DISTINCT source::text/);
  assert.match(compatibility("SELECT json_extract(data,'$.classifiedAt') FROM articles").sql,/data::jsonb/);
});
