ALTER TABLE okta_users ADD COLUMN profile_json TEXT NOT NULL DEFAULT '{}';
CREATE TABLE okta_groups (
    id TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL
);
CREATE TABLE okta_group_memberships (
    group_id TEXT NOT NULL REFERENCES okta_groups(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES okta_users(id) ON DELETE CASCADE,
    PRIMARY KEY (group_id, user_id)
);
CREATE TABLE okta_group_apps (
    group_id TEXT NOT NULL REFERENCES okta_groups(id) ON DELETE CASCADE,
    app_id TEXT NOT NULL,
    app_json TEXT NOT NULL,
    PRIMARY KEY (group_id, app_id)
);
CREATE TABLE okta_scopes (scope TEXT PRIMARY KEY);
CREATE TABLE simulated_sequences (name TEXT PRIMARY KEY, value INTEGER NOT NULL);
CREATE TABLE episode_artifacts (
    path TEXT PRIMARY KEY,
    content BLOB NOT NULL CHECK(length(content) <= 1048576),
    media_type TEXT NOT NULL,
    created_step INTEGER NOT NULL,
    created_clock INTEGER NOT NULL
);
