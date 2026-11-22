from urllib.parse import urlsplit

from flask import Blueprint, request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.api import APIError, integer, payload, require_user, string
from app.extensions import db
from app.models import Book, Borrow, PathwayTopic, ProgressLedger, Review, StudyPathway, Topic, User, utcnow
from app.routes.books import rated_books
from app.routes.borrowing import borrowing_query
from app.serializers import borrow_data, topic_data
from app.services.borrowing_service import lock_book, set_inventory


admin = Blueprint("admin", __name__, url_prefix="/api/admin")


def commit_edit(duplicate_message):
    try:
        db.session.commit()
    except IntegrityError as error:
        if getattr(error.orig, "args", (None,))[0] == 1062:
            raise APIError(409, duplicate_message) from error
        raise


def topic_selection(values):
    if not isinstance(values, list) or len(values) > 100:
        raise APIError(400, "Select up to 100 topics.")
    ids = {integer(value, "Topic ID") for value in values}
    topics = list(db.session.scalars(db.select(Topic).where(Topic.topic_id.in_(ids)).order_by(Topic.name))) if ids else []
    if len(topics) != len(ids):
        raise APIError(404, "One or more selected topics could not be found.")
    return topics


def edit_book_details(book, data):
    book.title = string(data.get("title"), "Title", 255)
    book.author = string(data.get("author"), "Author", 255)
    book.publisher = string(data.get("publisher"), "Publisher", 255, required=False) or None
    book.isbn = string(data.get("isbn"), "ISBN", 20, required=False) or None
    book.category = string(data.get("category"), "Category", 100, required=False) or None
    book.description = string(data.get("description"), "Description", 10000)
    if "cover_url" in data:
        cover = string(data["cover_url"], "Cover URL", 1000, required=False)
        if cover:
            try:
                parsed = urlsplit(cover)
            except ValueError as error:
                raise APIError(400, "Enter a valid HTTPS cover URL.") from error
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or any(c.isspace() for c in cover):
                raise APIError(400, "Enter a valid HTTPS cover URL.")
        book.cover_url = cover or None
    if "topic_ids" in data:
        book.topics = topic_selection(data["topic_ids"])


@admin.post("/books")
@require_user("admin")
def add_book():
    data = payload()
    total = integer(data.get("total_copies"), "Total copies", minimum=0)
    book = Book(total_copies=total, available_copies=total)
    edit_book_details(book, data)
    db.session.add(book)
    commit_edit("A book already uses this ISBN.")
    return rated_books([book])[0], 201


@admin.put("/books/<int:book_id>")
@require_user("admin")
def edit_book(book_id):
    book = lock_book(integer(book_id, "Book ID"))
    data = payload()
    edit_book_details(book, data)
    if "total_copies" in data:
        set_inventory(book, integer(data["total_copies"], "Total copies", minimum=0))
    commit_edit("A book already uses this ISBN.")
    return rated_books([book])[0]


@admin.put("/books/<int:book_id>/inventory")
@require_user("admin")
def edit_inventory(book_id):
    total = integer(payload().get("total_copies"), "Total copies", minimum=0)
    book = lock_book(integer(book_id, "Book ID"))
    set_inventory(book, total)
    db.session.commit()
    return rated_books([book])[0]


@admin.put("/books/<int:book_id>/topics")
@require_user("admin")
def edit_book_topics(book_id):
    book = lock_book(integer(book_id, "Book ID"))
    book.topics = topic_selection(payload().get("topic_ids"))
    db.session.commit()
    return rated_books([book])[0]


def set_topic_fields(topic):
    data = payload()
    topic.name = string(data.get("name"), "Topic name", 150)
    topic.description = string(data.get("description"), "Description", 10000)
    topic.subject = string(data.get("subject"), "Subject", 100)
    topic.difficulty_level = string(data.get("difficulty_level"), "Difficulty", 30)
    if topic.difficulty_level not in {"Beginner", "Intermediate", "Advanced"}:
        raise APIError(400, "Choose Beginner, Intermediate, or Advanced.")


@admin.post("/topics")
@require_user("admin")
def add_topic():
    topic = Topic()
    set_topic_fields(topic)
    db.session.add(topic)
    commit_edit("That topic name already exists in this subject.")
    return topic_data(topic), 201


@admin.put("/topics/<int:topic_id>")
@require_user("admin")
def edit_topic(topic_id):
    topic = db.session.get(Topic, integer(topic_id, "Topic ID"))
    if topic is None:
        raise APIError(404, "This topic could not be found.")
    set_topic_fields(topic)
    commit_edit("That topic name already exists in this subject.")
    return topic_data(topic)


@admin.get("/borrows")
@require_user("admin")
def all_borrows():
    page = integer(request.args.get("page", 1), "Page", maximum=10000)
    per_page = integer(request.args.get("per_page", 20), "Page size", maximum=100)
    statement = borrowing_query().options(joinedload(Borrow.user))
    status = request.args.get("status", "all")
    if status in {"issued", "overdue", "returned"}:
        statement = statement.where(Borrow.status == ("issued" if status == "overdue" else status))
    elif status != "all":
        raise APIError(400, "Choose a valid borrowing status.")
    if status == "overdue":
        statement = statement.where(Borrow.due_date < utcnow())
    paged = db.paginate(statement, page=page, per_page=per_page, error_out=False)
    return {
        "items": [borrow_data(loan, include_student=True) for loan in paged.items],
        "page": paged.page, "pages": paged.pages, "total": paged.total,
    }


def count_rows(model, *conditions):
    return db.session.scalar(db.select(db.func.count()).select_from(model).where(*conditions))


@admin.get("/stats")
@require_user("admin")
def stats():
    totals = db.session.execute(db.select(
        db.func.coalesce(db.func.sum(Book.total_copies), 0),
        db.func.coalesce(db.func.sum(Book.available_copies), 0),
    )).one()
    path_stats = db.select(
        StudyPathway.pathway_id, StudyPathway.name, User.name.label("student"), StudyPathway.status,
        db.func.count(db.case((PathwayTopic.is_completed.is_(True), 1))).label("completed_steps"),
        db.func.count(PathwayTopic.pathway_topic_id).label("total_steps"),
    ).join(User, User.user_id == StudyPathway.user_id).outerjoin(
        PathwayTopic, PathwayTopic.pathway_id == StudyPathway.pathway_id,
    ).group_by(StudyPathway.pathway_id, StudyPathway.name, User.name, StudyPathway.status).order_by(
        StudyPathway.pathway_id.desc(),
    )
    return {
        "students": count_rows(User, User.role == "student"), "books": count_rows(Book),
        "topics": count_rows(Topic), "total_copies": int(totals[0]), "available_copies": int(totals[1]),
        "issued": count_rows(Borrow, Borrow.status == "issued"),
        "overdue": count_rows(Borrow, Borrow.status == "issued", Borrow.due_date < utcnow()),
        "reviews": count_rows(Review), "pathways": count_rows(StudyPathway),
        "completed_pathways": count_rows(StudyPathway, StudyPathway.status == "completed"),
        "ledger_entries": count_rows(ProgressLedger),
        "pathway_rows": [dict(row) for row in db.session.execute(path_stats).mappings()],
    }
