from collections import defaultdict

from flask import Blueprint, g, request
from sqlalchemy.orm import selectinload

from app.api import APIError, integer, iso, payload, require_user, string
from app.extensions import db
from app.models import Book, Recommendation, StudyPathway, Topic, book_topic
from app.routes.books import ratings_for
from app.serializers import book_data, topic_data
from app.services.ledger_service import read_entries, verify_chain
from app.services.pathway_service import assert_pathway_owner, complete_step, create_pathway, missing_steps
from app.services.prerequisite_service import add_prerequisite, prerequisite_graph, remove_prerequisite
from app.services.recommendation_service import generate_recommendations, rank_topic_books

learning = Blueprint("learning", __name__, url_prefix="/api")


def books_by_topic(topic_ids, *, verified=False):
    statement = (
        db.select(book_topic.c.topic_id, Book, book_topic.c.is_featured)
        .join(Book, Book.book_id == book_topic.c.book_id)
        .where(book_topic.c.topic_id.in_(topic_ids), Book.is_archived.is_(False))
        .order_by(book_topic.c.topic_id, Book.title, Book.book_id)
    )
    if verified:
        statement = statement.where(Book.source_url.is_not(None), Book.isbn.is_not(None))
    rows = list(db.session.execute(statement))
    ratings = ratings_for({book.book_id for _, book, _ in rows})
    candidates = defaultdict(list)
    featured = set()
    for topic_id, book, is_featured in rows:
        candidates[topic_id].append(book)
        if is_featured:
            featured.add((topic_id, book.book_id))
    if verified:
        topics = db.session.scalars(db.select(Topic).where(Topic.topic_id.in_(candidates.keys())))
        for topic in topics:
            candidates[topic.topic_id] = rank_topic_books(
                candidates[topic.topic_id], topic.topic_id, topic.name, topic.description,
            )
            candidates[topic.topic_id].sort(key=lambda book: (topic.topic_id, book.book_id) not in featured)
    grouped = defaultdict(list)
    for topic_id, books in candidates.items():
        grouped[topic_id] = [book_data(book, *ratings.get(book.book_id, (None, 0))) for book in books]
    return grouped


def topic_references(topic_ids, topic_names):
    return [{"topic_id": topic_id, "name": topic_names[topic_id]} for topic_id in topic_ids]


def topic_names(topic_ids):
    statement = db.select(Topic.topic_id, Topic.name).where(Topic.topic_id.in_(topic_ids))
    return dict(db.session.execute(statement).all())


def pathway_summary(pathway):
    total = len(pathway.steps)
    completed = sum(step.is_completed for step in pathway.steps)
    return {
        "pathway_id": pathway.pathway_id, "name": pathway.name, "description": pathway.description,
        "target_goal": pathway.target_goal, "created_at": iso(pathway.created_at), "status": pathway.status,
        "total_steps": total, "completed_steps": completed,
        "course_id": pathway.course_id,
        "estimated_hours": sum(step.estimated_hours or 0 for step in pathway.steps),
        "progress_percent": round(100 * completed / total) if total else 0,
    }


def pathway_detail(pathway):
    graph = prerequisite_graph()
    step_topic_ids = {step.topic_id for step in pathway.steps}
    reference_ids = step_topic_ids.union(*(graph.get(topic_id, ()) for topic_id in step_topic_ids))
    names = topic_names(reference_ids)
    book_map = books_by_topic(step_topic_ids, verified=pathway.course_id is not None)
    steps = []
    for step in pathway.steps:
        blocked_by = [] if step.is_completed else missing_steps(step, pathway.steps, graph)
        state = "completed" if step.is_completed else "locked" if blocked_by else "available"
        steps.append({
            **topic_data(step.topic),
            "pathway_topic_id": step.pathway_topic_id, "sequence_no": step.sequence_no,
            "module": step.module, "estimated_hours": step.estimated_hours,
            "is_completed": step.is_completed, "completed_at": iso(step.completed_at), "state": state,
            "prerequisites": topic_references(sorted(graph.get(step.topic_id, ())), names),
            "blocked_by": topic_references(blocked_by, names),
            "books": book_map[step.topic_id][:5] if pathway.course_id else book_map[step.topic_id],
        })
    return {**pathway_summary(pathway), "steps": steps}


def owned_pathway(pathway_id, *, admin_allowed=False):
    pathway = db.session.get(StudyPathway, integer(pathway_id, "Pathway ID"))
    return assert_pathway_owner(pathway, g.user.user_id, administrator=admin_allowed and g.user.role == "admin")


def existing_topic(topic_id):
    topic = db.session.get(Topic, integer(topic_id, "Topic ID"))
    if topic is None:
        raise APIError(404, "This topic was not found.")
    return topic


@learning.get("/topics")
@require_user()
def topics():
    rows = list(db.session.scalars(db.select(Topic).order_by(Topic.subject, Topic.name, Topic.topic_id)))
    graph = prerequisite_graph()
    names = {topic.topic_id: topic.name for topic in rows}
    book_map = books_by_topic(names.keys())
    return {"topics": [{
        **topic_data(topic),
        "prerequisites": topic_references(sorted(graph.get(topic.topic_id, ())), names),
        "books": book_map[topic.topic_id],
    } for topic in rows]}


@learning.get("/topics/<int:topic_id>")
@require_user()
def topic_details(topic_id):
    topic = existing_topic(topic_id)
    required = sorted(prerequisite_graph().get(topic_id, ()))
    return {"topic": {
        **topic_data(topic), "prerequisites": topic_references(required, topic_names(required)),
        "books": books_by_topic([topic_id])[topic_id],
    }}


@learning.get("/topics/<int:topic_id>/prerequisites")
@require_user()
def topic_prerequisites(topic_id):
    existing_topic(topic_id)
    required = sorted(prerequisite_graph().get(topic_id, ()))
    return {"prerequisites": topic_references(required, topic_names(required))}


@learning.post("/admin/prerequisites")
@require_user("admin")
def prerequisite_add():
    data = payload()
    prerequisite_id = integer(data.get("prerequisite_topic_id"), "Prerequisite topic ID")
    dependent_id = integer(data.get("dependent_topic_id"), "Dependent topic ID")
    add_prerequisite(prerequisite_id, dependent_id)
    db.session.commit()
    return {"prerequisite_topic_id": prerequisite_id, "dependent_topic_id": dependent_id}, 201


@learning.delete("/admin/prerequisites/<int:prerequisite_id>/<int:dependent_id>")
@require_user("admin")
def prerequisite_remove(prerequisite_id, dependent_id):
    remove_prerequisite(integer(prerequisite_id, "Prerequisite topic ID"), integer(dependent_id, "Dependent topic ID"))
    db.session.commit()
    return {"message": "Prerequisite removed."}


@learning.post("/pathways")
@require_user("student")
def pathway_create():
    data = payload()
    name = string(data.get("name"), "Pathway name", 200)
    description = string(data.get("description"), "Description", 6000, required=False)
    target_goal = string(data.get("target_goal"), "Learning goal", 255)
    ids = data.get("topic_ids")
    if not isinstance(ids, list):
        raise APIError(400, "Select at least one topic for your pathway.")
    topic_ids = [integer(topic_id, "Topic ID") for topic_id in ids]
    include = data.get("include_prerequisites", False)
    if not isinstance(include, bool):
        raise APIError(400, "Choose whether to include missing prerequisites.")
    pathway = create_pathway(g.user.user_id, name, description, target_goal, topic_ids, include)
    db.session.commit()
    return {"pathway": pathway_detail(pathway)}, 201


@learning.get("/pathways/me")
@require_user("student")
def my_pathways():
    rows = db.session.scalars(
        db.select(StudyPathway).where(StudyPathway.user_id == g.user.user_id).order_by(StudyPathway.pathway_id.desc())
    )
    return {"pathways": [pathway_summary(pathway) for pathway in rows]}


@learning.get("/pathways/<int:pathway_id>")
@require_user()
def pathway_get(pathway_id):
    return {"pathway": pathway_detail(owned_pathway(pathway_id))}


@learning.get("/pathways/<int:pathway_id>/topics")
@require_user()
def pathway_topics(pathway_id):
    return {"steps": pathway_detail(owned_pathway(pathway_id))["steps"]}


@learning.post("/pathway-topics/<int:step_id>/complete")
@require_user("student")
def pathway_step_complete(step_id):
    pathway = complete_step(g.user.user_id, integer(step_id, "Pathway step ID"))
    db.session.commit()
    return {"pathway": pathway_detail(pathway)}


@learning.get("/pathways/<int:pathway_id>/ledger")
@require_user()
def pathway_ledger(pathway_id):
    pathway = owned_pathway(pathway_id, admin_allowed=True)
    by_id = {step.pathway_topic_id: step for step in pathway.steps}
    recorded_entries = read_entries(pathway_id)
    entries = []
    for entry in recorded_entries:
        step = by_id.get(entry.pathway_topic_id)
        entries.append({
            "ledger_id": entry.ledger_id, "pathway_topic_id": entry.pathway_topic_id,
            "topic_name": step.topic.name if step else None, "sequence_no": step.sequence_no if step else None,
            "event_type": entry.event_type, "event_time": iso(entry.event_time), "previous_hash": entry.previous_hash,
            "entry_hash": entry.entry_hash, "hash_version": entry.hash_version,
        })
    return {
        "pathway": pathway_summary(pathway), "entries": entries,
        "verification": verify_chain(pathway, pathway.steps, recorded_entries),
    }


@learning.get("/pathways/<int:pathway_id>/ledger/verify")
@require_user()
def pathway_verify(pathway_id):
    pathway = owned_pathway(pathway_id, admin_allowed=True)
    return verify_chain(pathway, pathway.steps, read_entries(pathway_id))


def recommendation_data(rows):
    ratings = ratings_for({row.book_id for row in rows})
    return [{
        "rec_id": row.rec_id, "book_id": row.book_id, "topic_id": row.topic_id,
        "book": book_data(row.book, *ratings.get(row.book_id, (None, 0))),
        "topic": topic_data(row.topic) if row.topic else None,
        "score": float(row.score), "model_type": row.model_type,
        "generated_at": iso(row.generated_at), "reason": row.reason,
    } for row in rows]


@learning.post("/recommendations/generate")
@require_user("student")
def recommendation_generate():
    data = payload()
    topic_id = integer(data["topic_id"], "Topic ID") if data.get("topic_id") is not None else None
    limit = integer(data.get("limit", 8), "Recommendation limit", maximum=30)
    rows = generate_recommendations(g.user, topic_id, limit)
    db.session.commit()
    return {"recommendations": recommendation_data(rows)}


@learning.get("/recommendations/me")
@require_user("student")
def recommendations_get():
    raw_topic = request.args.get("topic_id")
    topic_id = integer(raw_topic, "Topic ID") if raw_topic is not None else None
    statement = (
        db.select(Recommendation)
        .join(Recommendation.book)
        .where(Recommendation.user_id == g.user.user_id, Recommendation.topic_id == topic_id)
        .where(Book.is_archived.is_(False))
        .options(selectinload(Recommendation.book), selectinload(Recommendation.topic))
        .order_by(Recommendation.rec_id)
    )
    return {"recommendations": recommendation_data(list(db.session.scalars(statement)))}
