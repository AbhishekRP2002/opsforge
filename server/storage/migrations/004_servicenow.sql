CREATE TABLE servicenow_records (
    table_name TEXT NOT NULL,
    sys_id TEXT NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (table_name, sys_id)
);
CREATE TABLE servicenow_sequences (name TEXT PRIMARY KEY, value INTEGER NOT NULL);
CREATE TABLE servicenow_allocated_ids (table_name TEXT NOT NULL, sys_id TEXT NOT NULL, PRIMARY KEY (table_name, sys_id));
CREATE TABLE servicenow_profiles (table_name TEXT NOT NULL, sys_id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY (table_name, sys_id));
