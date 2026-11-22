import hashlib
import hmac
import json
from datetime import UTC

from flask import current_app

from app.extensions import db
from app.models import ProgressLedger

GENESIS_HASH = "0" * 64
HASH_VERSION = "hmac-sha256-v1"
COMPLETION_EVENT = "COMPLETE"


def _event_digest(entry):
    event_time = entry.event_time
    if event_time.tzinfo is not None:
        event_time = event_time.astimezone(UTC).replace(tzinfo=None)
    fields = {
        "event_time": event_time.isoformat(timespec="microseconds") + "Z",
        "event_type": entry.event_type,
        "hash_version": entry.hash_version,
        "pathway_id": entry.pathway_id,
        "pathway_topic_id": entry.pathway_topic_id,
        "previous_hash": entry.previous_hash,
        "user_id": entry.user_id,
    }
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("ascii")
    secret = current_app.config["LEDGER_SECRET"].encode("utf-8")
    return hmac.new(secret, canonical, hashlib.sha256).hexdigest()


def read_entries(pathway_id, *, current=False):
    statement = (
        db.select(ProgressLedger)
        .where(ProgressLedger.pathway_id == pathway_id)
        .order_by(ProgressLedger.ledger_id)
    )
    if current:
        statement = statement.with_for_update(read=True).execution_options(populate_existing=True)
    return list(db.session.scalars(statement))


def append_completion(pathway, step, event_time, previous_hash=GENESIS_HASH):
    entry = ProgressLedger(
        user_id=pathway.user_id,
        pathway_id=pathway.pathway_id,
        pathway_topic_id=step.pathway_topic_id,
        event_type=COMPLETION_EVENT,
        event_time=event_time,
        previous_hash=previous_hash,
        hash_version=HASH_VERSION,
    )
    entry.entry_hash = _event_digest(entry)
    db.session.add(entry)
    return entry


def verify_chain(pathway, steps, entries):
    def result(valid, message, entry=None, step=None):
        return {
            "valid": valid,
            "message": message,
            "entry_count": len(entries),
            "first_invalid_entry": entry.ledger_id if entry is not None else None,
            "first_invalid_step": step.pathway_topic_id if step is not None else None,
        }

    previous_hash = GENESIS_HASH
    previous_id = 0
    previous_time = None
    for index, entry in enumerate(entries):
        step = steps[index] if index < len(steps) else None
        if (
            step is None
            or entry.pathway_id != pathway.pathway_id
            or entry.user_id != pathway.user_id
            or entry.pathway_topic_id != step.pathway_topic_id
            or step.sequence_no != index + 1
            or entry.ledger_id <= previous_id
            or (previous_time is not None and entry.event_time < previous_time)
        ):
            return result(False, "A progress entry is out of order or refers to the wrong pathway step.", entry, step)
        if entry.previous_hash != previous_hash:
            return result(False, "A progress entry has an invalid previous-hash link.", entry, step)
        if entry.event_type != COMPLETION_EVENT or entry.hash_version != HASH_VERSION:
            return result(False, "A progress entry uses an unsupported event or hash version.", entry, step)
        if not hmac.compare_digest(_event_digest(entry).encode("ascii"), entry.entry_hash.encode("utf-8")):
            return result(False, "A progress entry does not match its cryptographic digest.", entry, step)
        if not step.is_completed or step.completed_at != entry.event_time:
            return result(False, "The progress entry disagrees with the pathway step's completion state.", entry, step)
        previous_hash = entry.entry_hash
        previous_id = entry.ledger_id
        previous_time = entry.event_time

    for index, step in enumerate(steps[len(entries):], start=len(entries) + 1):
        if step.is_completed or step.completed_at is not None or step.sequence_no != index:
            return result(False, "The pathway has a missing progress entry or an invalid step sequence.", step=step)

    expected_status = "completed" if steps and len(entries) == len(steps) else "active"
    if not steps or pathway.status != expected_status:
        return result(False, "The pathway status does not agree with its progress history.")
    return result(True, "Progress history verified. Recorded entries and pathway completion state are consistent.")
