/** A narrow Cloudflare D1-compatible adapter over PostgreSQL.
 * This keeps the existing game logic portable without changing its API.
 * Supported rewrites are limited to the SQL actually used by this project.
 */
import pg from 'pg';

pg.types.setTypeParser(20, (x: string) => Number(x)); // int8: epoch milliseconds / counts
pg.types.setTypeParser(1700, (x: string) => Number(x)); // NUMERIC: AVG and ratios

let pool: pg.Pool | null = null;
function getPool() {
  if (!pool) {
    if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL must be set');
    pool = new pg.Pool({
      connectionString: process.env.DATABASE_URL,
      max: Number(process.env.PG_POOL_SIZE || 12),
      connectionTimeoutMillis: 10_000,
      idleTimeoutMillis: 30_000,
      statement_timeout: 30_000,
    });
  }
  return pool;
}

export function compatibility(sql: string) {
  let s = sql.trim();
  if (/^INSERT OR IGNORE\s+INTO\b/i.test(s)) {
    s = s.replace(/^INSERT OR IGNORE\s+INTO\b/i, 'INSERT INTO');
    s += ' ON CONFLICT DO NOTHING';
  }
  s = s.replace(/\bGROUP_CONCAT\(DISTINCT\s+([\w.]+)\)/gi, "STRING_AGG(DISTINCT $1::text, ',')");
  s = s.replace(/\bGROUP_CONCAT\(([\w.]+)\)/gi, "STRING_AGG($1::text, ',')");
  s = s.replace(/\bSUM\(([\w.]+)\s*=\s*('[^']*'|-?\d+)\)/gi,
    'SUM(CASE WHEN $1=$2 THEN 1 ELSE 0 END)');
  s = s.replace(/\bjson_extract\(data\s*,\s*'\$\.classifiedAt'\)/gi,
    "NULLIF(data::jsonb->>'classifiedAt', '')::bigint");
  // Convert only genuine SQLite bind markers, not question marks in string values.
  let quoted: string | null = null;
  let count = 0;
  let out = '';
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (quoted) {
      out += c;
      if (c === quoted) {
        if (s[i + 1] === quoted) out += s[++i];
        else quoted = null;
      }
    } else if (c === "'" || c === '"') {
      quoted = c;
      out += c;
    } else if (c === '?') {
      out += `$${++count}`;
    } else {
      out += c;
    }
  }
  return {sql: out, count};
}

type SqlQuery = {sql: string; args: unknown[]};

class Statement {
  private args: unknown[] = [];
  private translated;
  constructor(sql: string) { this.translated = compatibility(sql); }
  bind(...values: unknown[]) {this.args = values; return this;}
  query(): SqlQuery {
    if (this.args.length !== this.translated.count) {
      throw new Error(`SQL bind mismatch: ${this.translated.count} expected, ${this.args.length} received`);
    }
    return {...this.translated, args: this.args};
  }
  async first() {const rows = await execute(this.query()); return rows[0] ?? null;}
  async all() {return {results: await execute(this.query())};}
  async run() {const rows = await execute(this.query()); return {results: rows};}
}

async function execute(q: SqlQuery, client?: pg.PoolClient | pg.Pool) {
  return (await (client || getPool()).query(q.sql, q.args)).rows;
}

export const database = {
  prepare(sql: string) {return new Statement(sql);},
  async batch(statements: Statement[]) {
    const client = await getPool().connect();
    try {
      await client.query('BEGIN');
      const results = [];
      for (const statement of statements) results.push(await execute(statement.query(), client));
      await client.query('COMMIT');
      return results;
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {client.release();}
  },
};
