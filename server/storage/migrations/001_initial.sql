CREATE TABLE okta_users (id TEXT PRIMARY KEY, login TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, first_name TEXT NOT NULL, last_name TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE servicenow_users (sys_id TEXT PRIMARY KEY, user_name TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, active INTEGER NOT NULL);
CREATE TABLE servicenow_groups (sys_id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, available INTEGER NOT NULL);
CREATE TABLE servicenow_memberships (sys_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES servicenow_users(sys_id), group_id TEXT NOT NULL REFERENCES servicenow_groups(sys_id));
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE events (sequence INTEGER PRIMARY KEY, at INTEGER NOT NULL, kind TEXT NOT NULL, group_id TEXT NOT NULL REFERENCES servicenow_groups(sys_id), applied INTEGER NOT NULL DEFAULT 0);
CREATE TABLE journal (sequence INTEGER PRIMARY KEY AUTOINCREMENT, step INTEGER NOT NULL, clock INTEGER NOT NULL, kind TEXT NOT NULL, provider TEXT NOT NULL, record_id TEXT, group_id TEXT);
CREATE TABLE delivery (invocation_id TEXT PRIMARY KEY, payload TEXT NOT NULL, response TEXT NOT NULL);
CREATE TABLE result (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), artifact TEXT NOT NULL);
