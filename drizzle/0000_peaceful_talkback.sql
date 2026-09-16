CREATE TABLE `access_sessions` (
	`id` text PRIMARY KEY NOT NULL,
	`token_hash` text NOT NULL,
	`expires_at` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE INDEX `idx_access_sessions_token_hash` ON `access_sessions` (`token_hash`);--> statement-breakpoint
CREATE TABLE `team_workspace` (
	`id` integer PRIMARY KEY NOT NULL,
	`payload_json` text NOT NULL,
	`revision` integer DEFAULT 0 NOT NULL,
	`updated_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
