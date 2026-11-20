CREATE TABLE `article_topics` (
	`page_id` integer NOT NULL,
	`topic` text NOT NULL,
	`group_id` text NOT NULL,
	`path` text NOT NULL,
	`distance` integer NOT NULL,
	PRIMARY KEY(`page_id`, `topic`)
);
--> statement-breakpoint
CREATE INDEX `topic_article` ON `article_topics` (`topic`,`page_id`);--> statement-breakpoint
CREATE INDEX `group_article` ON `article_topics` (`group_id`,`page_id`);--> statement-breakpoint
CREATE TABLE `category_nodes` (
	`name` text PRIMARY KEY NOT NULL,
	`parents` text NOT NULL,
	`updated` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `topic_members` (
	`source` text NOT NULL,
	`page_id` integer NOT NULL,
	`title` text NOT NULL,
	`path` text NOT NULL,
	PRIMARY KEY(`source`, `page_id`)
);
--> statement-breakpoint
CREATE TABLE `topic_queue` (
	`source` text NOT NULL,
	`category` text NOT NULL,
	`path` text NOT NULL,
	`cursor` text,
	`done` integer DEFAULT 0 NOT NULL,
	`updated` integer DEFAULT 0 NOT NULL,
	PRIMARY KEY(`source`, `category`)
);
--> statement-breakpoint
CREATE INDEX `topic_pending` ON `topic_queue` (`source`,`done`,`updated`);
--> statement-breakpoint
UPDATE articles SET category='待归类',data=json_set(data,'$.category','待归类') WHERE category IN ('科学与自然','历史与文明','思想与社会','文化与生活');
--> statement-breakpoint
UPDATE games SET snapshot=json_set(snapshot,'$.category','待归类') WHERE json_extract(snapshot,'$.category') IN ('科学与自然','历史与文明','思想与社会','文化与生活');
