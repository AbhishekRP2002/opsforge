CREATE TABLE erpnext_documents (
    doctype TEXT NOT NULL,
    name TEXT NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (doctype, name)
);
CREATE TABLE erpnext_ids (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    doctype TEXT NOT NULL,
    name TEXT UNIQUE
);
CREATE TABLE erpnext_notifications (
    todo TEXT PRIMARY KEY,
    recipient TEXT NOT NULL,
    doctype TEXT NOT NULL,
    name TEXT NOT NULL
);
CREATE TABLE erpnext_shares (
    doctype TEXT NOT NULL,
    name TEXT NOT NULL,
    user TEXT NOT NULL,
    PRIMARY KEY (doctype, name, user)
);
