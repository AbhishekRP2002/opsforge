CREATE TABLE darwinbox_records (
    kind TEXT NOT NULL,
    id TEXT NOT NULL,
    data TEXT NOT NULL CHECK(json_valid(data)),
    PRIMARY KEY (kind, id)
);
CREATE TABLE darwinbox_ids (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL
);
