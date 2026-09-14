"""Bounded storage primitives shared by explicit Okta domain handlers."""

import json

from .okta_identity import _error, _next_id, _page, _scope, _valid


def error(message, listed=False):
    return _error(message, listed=listed)


def guard(db, scope, arguments, ids=(), listed=False, id_listed=None):
    denied = _scope(db, scope, listed=listed)
    if denied:
        return denied
    for key in ids:
        invalid = _valid(arguments[key], key)
        if invalid:
            value = invalid[0]
            assert isinstance(value, list)
            return error(value[0]["error"], listed if id_listed is None else id_listed)
    return None


def get(db, table, identifier):
    row = db.connection.execute(
        f"SELECT data_json FROM {table} WHERE id=?", (identifier,)
    ).fetchone()
    return json.loads(row[0]) if row else None


def rows(db, table):
    return [
        json.loads(row[0])
        for row in db.connection.execute(f"SELECT data_json FROM {table} ORDER BY id")
    ]


def save(db, table, value):
    changed = db.connection.execute(
        f"UPDATE {table} SET data_json=? WHERE id=?", (json.dumps(value), value["id"])
    )
    if not changed.rowcount:
        db.connection.execute(
            f"INSERT INTO {table} (id,data_json) VALUES (?,?)",
            (value["id"], json.dumps(value)),
        )
    return value, False


def create(db, table, prefix, data):
    return save(db, table, data | {"id": _next_id(db, table, prefix)})


def remove(db, table, identifier):
    db.connection.execute(f"DELETE FROM {table} WHERE id=?", (identifier,))


def page(items, arguments, kind, minimum=20, maximum=100):
    result, failure = _page(
        items,
        kind=kind,
        query=tuple(
            (key, arguments[key])
            for key in sorted(arguments)
            if key not in {"after", "fetch_all", "limit"}
        ),
        after=arguments.get("after"),
        limit=arguments.get("limit"),
        fetch_all=arguments.get("fetch_all", False),
        minimum=minimum,
        maximum=maximum,
        max_pages=500,
        fetch_all_size=maximum,
    )
    return error(failure) if failure else (result, False)
