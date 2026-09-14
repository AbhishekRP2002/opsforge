"""Read-only recruitment records with independently timestamped candidates."""

from . import darwinbox_store as store


@store.handler
def listings(db, arguments, step, clock):
    cutoff = store.date(arguments["job_updated_timestamp_from"], store.STAMP)
    matches = []
    for job in store.rows(db, "job"):
        if (
            job["detail"]["job_status"] == "open"
            and store.date(job["listing"]["job_updated_timestamp"], store.STAMP)
            > cutoff
        ):
            matches.append(job["listing"])
    return matches


@store.handler
def detail(db, arguments, step, clock):
    return store.get(db, "job", arguments["job_id"])["detail"]


@store.handler
def candidates(db, arguments, step, clock):
    low, high = store.span(
        arguments["updated_from"], arguments["updated_to"], store.STAMP
    )
    return [
        record["candidate"]
        for record in store.rows(db, "candidate")
        if low <= store.date(record["modified"], store.STAMP) <= high
    ]


HANDLERS = {
    "get_job_listings": listings,
    "get_job_detail": detail,
    "get_bulk_candidates": candidates,
}
