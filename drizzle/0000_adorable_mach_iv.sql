CREATE TABLE `aliases` (
	`page_id` integer NOT NULL,
	`answer` text NOT NULL,
	`normalized` text NOT NULL,
	PRIMARY KEY(`page_id`, `normalized`)
);
--> statement-breakpoint
CREATE TABLE `articles` (
	`id` integer PRIMARY KEY NOT NULL,
	`title` text NOT NULL,
	`canonical` text NOT NULL,
	`data` text NOT NULL,
	`category` text NOT NULL,
	`chars` integer NOT NULL,
	`views` real,
	`fetched` integer NOT NULL,
	`filter_version` integer DEFAULT 1 NOT NULL,
	`status` text DEFAULT 'active' NOT NULL,
	`featured` integer DEFAULT 0 NOT NULL
);
--> statement-breakpoint
CREATE TABLE `audit` (
	`id` text PRIMARY KEY NOT NULL,
	`actor` text NOT NULL,
	`action` text NOT NULL,
	`detail` text NOT NULL,
	`created` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `captchas` (
	`id` text PRIMARY KEY NOT NULL,
	`hash` text NOT NULL,
	`expires` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `comments` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`page_id` integer NOT NULL,
	`body` text NOT NULL,
	`created` integer NOT NULL,
	`hidden` integer DEFAULT 0 NOT NULL
);
--> statement-breakpoint
CREATE INDEX `comment_page` ON `comments` (`page_id`,`created`);--> statement-breakpoint
CREATE TABLE `daily` (
	`date` text PRIMARY KEY NOT NULL,
	`page_id` integer NOT NULL,
	`manual` integer DEFAULT 0 NOT NULL,
	`updated` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `exclusions` (
	`page_id` integer PRIMARY KEY NOT NULL,
	`title` text NOT NULL,
	`reason` text NOT NULL,
	`kind` text NOT NULL,
	`created_at` integer NOT NULL,
	`actor` text
);
--> statement-breakpoint
CREATE TABLE `games` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`user_id` text,
	`page_id` integer NOT NULL,
	`mode` text NOT NULL,
	`date` text,
	`state` text DEFAULT 'playing' NOT NULL,
	`started` integer NOT NULL,
	`finished` integer,
	`guess_count` integer DEFAULT 0 NOT NULL,
	`competitive` integer DEFAULT 1 NOT NULL,
	`snapshot` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `game_owner` ON `games` (`owner`,`started`);--> statement-breakpoint
CREATE INDEX `game_page` ON `games` (`page_id`);--> statement-breakpoint
CREATE UNIQUE INDEX `daily_once` ON `games` (`owner`,`mode`,`date`);--> statement-breakpoint
CREATE TABLE `guesses` (
	`id` text PRIMARY KEY NOT NULL,
	`game_id` text NOT NULL,
	`text` text NOT NULL,
	`normalized` text NOT NULL,
	`correct` integer NOT NULL,
	`created` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `guess_once` ON `guesses` (`game_id`,`normalized`);--> statement-breakpoint
CREATE TABLE `rate_limits` (
	`key` text PRIMARY KEY NOT NULL,
	`count` integer NOT NULL,
	`expires` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `pool` (
	`source` text NOT NULL,
	`title` text NOT NULL,
	PRIMARY KEY(`source`, `title`)
);
--> statement-breakpoint
CREATE TABLE `alias_proposals` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text NOT NULL,
	`page_id` integer NOT NULL,
	`answer` text NOT NULL,
	`status` text DEFAULT 'pending' NOT NULL,
	`created` integer NOT NULL,
	`reviewer` text
);
--> statement-breakpoint
CREATE TABLE `sessions` (
	`token` text PRIMARY KEY NOT NULL,
	`user_id` text,
	`guest_id` text NOT NULL,
	`expires` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `session_expiry` ON `sessions` (`expires`);--> statement-breakpoint
CREATE TABLE `settings` (
	`key` text PRIMARY KEY NOT NULL,
	`value` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `source_jobs` (
	`source` text NOT NULL,
	`page` text NOT NULL,
	`cursor` text,
	`done` integer DEFAULT 0 NOT NULL,
	`updated` integer DEFAULT 0 NOT NULL,
	PRIMARY KEY(`source`, `page`)
);
--> statement-breakpoint
CREATE TABLE `users` (
	`id` text PRIMARY KEY NOT NULL,
	`username` text NOT NULL,
	`password_hash` text NOT NULL,
	`salt` text NOT NULL,
	`nickname` text NOT NULL,
	`avatar` text DEFAULT '🌫️' NOT NULL,
	`role` text DEFAULT 'user' NOT NULL,
	`nickname_blocked` integer DEFAULT 0 NOT NULL,
	`avatar_blocked` integer DEFAULT 0 NOT NULL,
	`blocked_nickname` text,
	`blocked_avatar` text,
	`moderation_reason` text,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `users_username_unique` ON `users` (`username`);--> statement-breakpoint
CREATE TABLE `votes` (
	`user_id` text NOT NULL,
	`page_id` integer NOT NULL,
	`value` integer NOT NULL,
	`created` integer NOT NULL,
	PRIMARY KEY(`user_id`, `page_id`)
);
