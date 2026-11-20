CREATE TABLE `selection_skips` (
	`title` text PRIMARY KEY NOT NULL,
	`reason` text NOT NULL,
	`retry_after` integer NOT NULL
);
