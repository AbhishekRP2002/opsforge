CREATE TABLE jira_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES jira_projects(id),
    name TEXT NOT NULL,
    data TEXT NOT NULL CHECK(json_valid(data)),
    UNIQUE(project_id, name)
);
CREATE TABLE jira_service_desks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL UNIQUE REFERENCES jira_projects(id),
    data TEXT NOT NULL CHECK(json_valid(data))
);
CREATE TABLE jira_queues (
    id TEXT PRIMARY KEY,
    service_desk_id TEXT NOT NULL REFERENCES jira_service_desks(id) ON DELETE CASCADE,
    data TEXT NOT NULL CHECK(json_valid(data))
);
CREATE TABLE jira_request_types (
    id TEXT NOT NULL,
    service_desk_id TEXT NOT NULL REFERENCES jira_service_desks(id) ON DELETE CASCADE,
    data TEXT NOT NULL CHECK(json_valid(data)),
    PRIMARY KEY(id, service_desk_id)
);
CREATE TABLE jira_requests (
    issue_id INTEGER PRIMARY KEY REFERENCES jira_issues(id) ON DELETE CASCADE,
    service_desk_id TEXT NOT NULL,
    request_type_id TEXT NOT NULL,
    reporter_id TEXT NOT NULL REFERENCES jira_users(id),
    participants TEXT NOT NULL CHECK(json_valid(participants))
);
CREATE TABLE jira_forms (
    id TEXT NOT NULL,
    issue_id INTEGER NOT NULL REFERENCES jira_issues(id) ON DELETE CASCADE,
    data TEXT NOT NULL CHECK(json_valid(data)),
    PRIMARY KEY(id, issue_id)
);
CREATE TABLE jira_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INTEGER NOT NULL REFERENCES jira_issues(id) ON DELETE CASCADE,
    path TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    media_type TEXT NOT NULL
);
CREATE TABLE jira_development_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INTEGER NOT NULL REFERENCES jira_issues(id) ON DELETE CASCADE,
    application_type TEXT NOT NULL,
    data_type TEXT NOT NULL,
    data TEXT NOT NULL CHECK(json_valid(data))
);
