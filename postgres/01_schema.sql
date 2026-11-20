-- PostgreSQL schema for Weiwu Mystery. All timestamps are Unix milliseconds.
-- This preserves the original D1 table and column names for game compatibility.
BEGIN;
CREATE TABLE IF NOT EXISTS users(id text PRIMARY KEY,username text NOT NULL UNIQUE,password_hash text NOT NULL,salt text NOT NULL,nickname text NOT NULL,avatar text NOT NULL DEFAULT '🌫️',role text NOT NULL DEFAULT 'user',nickname_blocked bigint NOT NULL DEFAULT 0,avatar_blocked bigint NOT NULL DEFAULT 0,blocked_nickname text,blocked_avatar text,moderation_reason text,created_at bigint NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token text PRIMARY KEY,user_id text,guest_id text NOT NULL,expires bigint NOT NULL);
CREATE INDEX IF NOT EXISTS session_expiry ON sessions(expires);
CREATE TABLE IF NOT EXISTS captchas(id text PRIMARY KEY,hash text NOT NULL,expires bigint NOT NULL);
CREATE TABLE IF NOT EXISTS rate_limits(key text PRIMARY KEY,count bigint NOT NULL,expires bigint NOT NULL);
CREATE TABLE IF NOT EXISTS articles(id bigint PRIMARY KEY,title text NOT NULL,canonical text NOT NULL,data text NOT NULL,category text NOT NULL,chars bigint NOT NULL,views double precision,fetched bigint NOT NULL,filter_version bigint NOT NULL DEFAULT 1,status text NOT NULL DEFAULT 'active',featured bigint NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS articles_status_random ON articles(status,id);
CREATE INDEX IF NOT EXISTS articles_title ON articles(title);
CREATE TABLE IF NOT EXISTS exclusions(page_id bigint PRIMARY KEY,title text NOT NULL,reason text NOT NULL,kind text NOT NULL,created_at bigint NOT NULL,actor text);
CREATE TABLE IF NOT EXISTS pool(source text NOT NULL,title text NOT NULL,PRIMARY KEY(source,title));
CREATE TABLE IF NOT EXISTS source_jobs(source text NOT NULL,page text NOT NULL,cursor text,done bigint NOT NULL DEFAULT 0,updated bigint NOT NULL DEFAULT 0,PRIMARY KEY(source,page));
CREATE TABLE IF NOT EXISTS daily(date text PRIMARY KEY,page_id bigint NOT NULL,manual bigint NOT NULL DEFAULT 0,updated bigint NOT NULL);
CREATE TABLE IF NOT EXISTS games(id text PRIMARY KEY,owner text NOT NULL,user_id text,page_id bigint NOT NULL,mode text NOT NULL,date text,state text NOT NULL DEFAULT 'playing',started bigint NOT NULL,finished bigint,guess_count bigint NOT NULL DEFAULT 0,competitive bigint NOT NULL DEFAULT 1,snapshot text NOT NULL,source text);
CREATE INDEX IF NOT EXISTS game_owner ON games(owner,started);
CREATE INDEX IF NOT EXISTS game_page ON games(page_id);
CREATE UNIQUE INDEX IF NOT EXISTS daily_once ON games(owner,mode,date);
CREATE TABLE IF NOT EXISTS guesses(id text PRIMARY KEY,game_id text NOT NULL,text text NOT NULL,normalized text NOT NULL,correct bigint NOT NULL,created bigint NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS guess_once ON guesses(game_id,normalized);
CREATE TABLE IF NOT EXISTS votes(user_id text NOT NULL,page_id bigint NOT NULL,value bigint NOT NULL,created bigint NOT NULL,PRIMARY KEY(user_id,page_id));
CREATE TABLE IF NOT EXISTS aliases(page_id bigint NOT NULL,answer text NOT NULL,normalized text NOT NULL,PRIMARY KEY(page_id,normalized));
CREATE TABLE IF NOT EXISTS alias_proposals(id text PRIMARY KEY,user_id text NOT NULL,page_id bigint NOT NULL,answer text NOT NULL,status text NOT NULL DEFAULT 'pending',created bigint NOT NULL,reviewer text);
CREATE TABLE IF NOT EXISTS comments(id text PRIMARY KEY,user_id text NOT NULL,page_id bigint NOT NULL,body text NOT NULL,created bigint NOT NULL,hidden bigint NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS comment_page ON comments(page_id,created);
CREATE TABLE IF NOT EXISTS settings(key text PRIMARY KEY,value text NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id text PRIMARY KEY,actor text NOT NULL,action text NOT NULL,detail text NOT NULL,created bigint NOT NULL);
CREATE TABLE IF NOT EXISTS selection_skips(title text PRIMARY KEY,reason text NOT NULL,retry_after bigint NOT NULL);
CREATE TABLE IF NOT EXISTS category_nodes(name text PRIMARY KEY,parents text NOT NULL,updated bigint NOT NULL);
CREATE TABLE IF NOT EXISTS article_topics(page_id bigint NOT NULL,topic text NOT NULL,group_id text NOT NULL,path text NOT NULL,distance bigint NOT NULL,PRIMARY KEY(page_id,topic));
CREATE INDEX IF NOT EXISTS topic_article ON article_topics(topic,page_id);
CREATE INDEX IF NOT EXISTS group_article ON article_topics(group_id,page_id);
CREATE TABLE IF NOT EXISTS topic_queue(source text NOT NULL,category text NOT NULL,path text NOT NULL,cursor text,done bigint NOT NULL DEFAULT 0,updated bigint NOT NULL DEFAULT 0,PRIMARY KEY(source,category));
CREATE INDEX IF NOT EXISTS topic_pending ON topic_queue(source,done,updated);
CREATE TABLE IF NOT EXISTS topic_members(source text NOT NULL,page_id bigint NOT NULL,title text NOT NULL,path text NOT NULL,PRIMARY KEY(source,page_id));
-- Snapshot metadata is separate from player/operational data.
CREATE TABLE IF NOT EXISTS wiki_snapshots(id text PRIMARY KEY,source_date text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),article_count bigint NOT NULL DEFAULT 0,state text NOT NULL DEFAULT 'staging');
COMMIT;
