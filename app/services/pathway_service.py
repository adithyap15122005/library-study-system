from sqlalchemy.orm import lazyload

from app.api import APIError
from app.extensions import db
from app.models import PathwayTopic, StudyPathway, Topic, utcnow
from app.services import ledger_service
from app.services.prerequisite_service import (
    lock_topics,
    prerequisite_closure,
    prerequisite_graph,
    topological_order,
)


def create_pathway(user_id, name, description, target_goal, topic_ids, include_prerequisites=False):
    selected = set(topic_ids)
    if not selected:
        raise APIError(400, "Select at least one topic for your pathway.")
    if not selected.issubset(lock_topics()):
        raise APIError(404, "One or more selected topics were not found.")

    graph = prerequisite_graph(current=True)
    included = prerequisite_closure(selected, graph)
    missing = included - selected
    if missing and not include_prerequisites:
        statement = (
            db.select(Topic.topic_id, Topic.name)
            .where(Topic.topic_id.in_(missing))
            .order_by(Topic.name, Topic.topic_id)
            .with_for_update(read=True)
        )
        raise APIError(
            409,
            "This pathway needs additional prerequisite topics.",
            {"missing_prerequisites": [dict(row._mapping) for row in db.session.execute(statement)]},
        )

    ordered = topological_order(included, graph)
    pathway = StudyPathway(user_id=user_id, name=name, description=description, target_goal=target_goal, status="active")
    pathway.steps = [
        PathwayTopic(topic_id=topic_id, sequence_no=index, is_completed=False)
        for index, topic_id in enumerate(ordered, start=1)
    ]
    db.session.add(pathway)
    db.session.flush()
    return pathway


def assert_pathway_owner(pathway, user_id, *, administrator=False):
    if pathway is None:
        raise APIError(404, "This study pathway was not found.")
    if pathway.user_id != user_id and not administrator:
        raise APIError(403, "You do not have permission to view this pathway.")
    return pathway


def missing_steps(step, steps, graph):
    completed = {candidate.topic_id for candidate in steps if candidate.is_completed}
    earlier = [
        candidate.topic_id for candidate in steps if candidate.sequence_no < step.sequence_no and not candidate.is_completed
    ]
    prerequisites = sorted(set(graph.get(step.topic_id, ())) - completed)
    return list(dict.fromkeys(earlier + prerequisites))


def complete_step(user_id, pathway_topic_id):
    lock_topics()
    pathway_id = db.session.scalar(
        db.select(PathwayTopic.pathway_id).where(PathwayTopic.pathway_topic_id == pathway_topic_id)
    )
    if pathway_id is None:
        raise APIError(404, "This pathway step was not found.")

    pathway = db.session.scalar(
        db.select(StudyPathway)
        .where(StudyPathway.pathway_id == pathway_id)
        .options(lazyload(StudyPathway.steps))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert_pathway_owner(pathway, user_id)
    statement = (
        db.select(PathwayTopic)
        .where(PathwayTopic.pathway_id == pathway_id)
        .order_by(PathwayTopic.sequence_no)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    steps = list(db.session.scalars(statement))
    step = next(candidate for candidate in steps if candidate.pathway_topic_id == pathway_topic_id)
    if step.is_completed:
        raise APIError(409, "This pathway step is already complete.")

    blocked_by = missing_steps(step, steps, prerequisite_graph(current=True))
    if blocked_by:
        names = {
            topic_id: name
            for topic_id, name in db.session.execute(
                db.select(Topic.topic_id, Topic.name).where(Topic.topic_id.in_(blocked_by))
            )
        }
        blocked = [{"topic_id": topic_id, "name": names.get(topic_id, f"Topic {topic_id}")} for topic_id in blocked_by]
        labels = ", ".join(topic["name"] for topic in blocked)
        raise APIError(409, f"Complete {labels} first.", {"blocked_by": blocked})

    entries = ledger_service.read_entries(pathway_id, current=True)
    verification = ledger_service.verify_chain(pathway, steps, entries)
    if not verification["valid"]:
        raise APIError(409, "Progress verification failed. Resolve the ledger error before continuing.", verification)

    event_time = utcnow()
    previous_hash = ledger_service.GENESIS_HASH
    if entries:
        event_time = max(event_time, entries[-1].event_time)
        previous_hash = entries[-1].entry_hash
    step.is_completed = True
    step.completed_at = event_time
    if all(candidate.is_completed for candidate in steps):
        pathway.status = "completed"
    ledger_service.append_completion(pathway, step, event_time, previous_hash)
    db.session.flush()
    return pathway
