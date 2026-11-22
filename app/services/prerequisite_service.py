from collections import defaultdict
from heapq import heapify, heappop, heappush

from sqlalchemy import and_, or_
from sqlalchemy.orm import aliased

from app.api import APIError
from app.extensions import db
from app.models import PathwayTopic, Topic, topic_prerequisite


def lock_topics(*, exclusive=False):
    """Serialize graph writes with pathway creation and completion on MySQL."""
    statement = db.select(Topic.topic_id).order_by(Topic.topic_id)
    return set(db.session.scalars(statement.with_for_update(read=not exclusive)))


def prerequisite_graph(*, current=False):
    """Map each dependent topic to its direct prerequisites."""
    statement = db.select(topic_prerequisite).order_by(
        topic_prerequisite.c.prerequisite_topic_id,
        topic_prerequisite.c.dependent_topic_id,
    )
    if current:
        statement = statement.with_for_update(read=True)
    graph = defaultdict(set)
    for prerequisite_id, dependent_id in db.session.execute(statement):
        graph[dependent_id].add(prerequisite_id)
    return graph


def prerequisite_closure(topic_ids, graph):
    included = set(topic_ids)
    pending = list(included)
    while pending:
        for prerequisite_id in graph.get(pending.pop(), ()):
            if prerequisite_id not in included:
                included.add(prerequisite_id)
                pending.append(prerequisite_id)
    return included


def topological_order(topic_ids, graph):
    included = set(topic_ids)
    waiting = {}
    dependents = defaultdict(list)
    for topic_id in included:
        prerequisites = included.intersection(graph.get(topic_id, ()))
        waiting[topic_id] = len(prerequisites)
        for prerequisite_id in prerequisites:
            dependents[prerequisite_id].append(topic_id)

    ready = [topic_id for topic_id in included if waiting[topic_id] == 0]
    heapify(ready)
    ordered = []
    while ready:
        topic_id = heappop(ready)
        ordered.append(topic_id)
        for dependent_id in dependents[topic_id]:
            waiting[dependent_id] -= 1
            if waiting[dependent_id] == 0:
                heappush(ready, dependent_id)
    if len(ordered) != len(included):
        raise APIError(409, "The selected topics contain a circular prerequisite relationship.")
    return ordered


def add_prerequisite(prerequisite_topic_id, dependent_topic_id):
    if prerequisite_topic_id == dependent_topic_id:
        raise APIError(400, "A topic cannot be its own prerequisite.")
    topic_ids = lock_topics(exclusive=True)
    if not {prerequisite_topic_id, dependent_topic_id}.issubset(topic_ids):
        raise APIError(404, "One or both topics were not found.")

    graph = prerequisite_graph(current=True)
    if prerequisite_topic_id in graph[dependent_topic_id]:
        raise APIError(409, "This prerequisite relationship already exists.")
    if dependent_topic_id in prerequisite_closure([prerequisite_topic_id], graph):
        raise APIError(409, "This prerequisite would create a circular dependency.")

    required = aliased(PathwayTopic)
    conflicts = (
        db.select(PathwayTopic.pathway_id)
        .outerjoin(
            required,
            and_(required.pathway_id == PathwayTopic.pathway_id, required.topic_id == prerequisite_topic_id),
        )
        .where(
            PathwayTopic.topic_id == dependent_topic_id,
            or_(required.pathway_topic_id.is_(None), required.sequence_no >= PathwayTopic.sequence_no),
        )
        .limit(1)
        .with_for_update(read=True)
    )
    if db.session.scalar(conflicts) is not None:
        raise APIError(409, "This prerequisite would invalidate the topic order in an existing pathway.")

    db.session.execute(
        topic_prerequisite.insert().values(
            prerequisite_topic_id=prerequisite_topic_id, dependent_topic_id=dependent_topic_id
        )
    )


def remove_prerequisite(prerequisite_topic_id, dependent_topic_id):
    lock_topics(exclusive=True)
    result = db.session.execute(
        topic_prerequisite.delete().where(
            topic_prerequisite.c.prerequisite_topic_id == prerequisite_topic_id,
            topic_prerequisite.c.dependent_topic_id == dependent_topic_id,
        )
    )
    if result.rowcount != 1:
        raise APIError(404, "This prerequisite relationship was not found.")
