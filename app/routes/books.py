import re

from flask import Blueprint, g, request
from sqlalchemy import case, or_
from sqlalchemy.dialects.mysql import match
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.api import APIError, integer, payload, require_user, string
from app.extensions import db
from app.models import Book, Review, Topic, book_topic
from app.serializers import book_data, review_data


books = Blueprint("books", __name__, url_prefix="/api")
SEARCH_FIELDS = (Book.title, Book.author, Book.category, Book.description)


def get_book(book_id):
    book = db.session.get(Book, integer(book_id, "Book ID"))
    if book is None:
        raise APIError(404, "This book could not be found.")
    return book


def ratings_for(book_ids):
    if not book_ids:
        return {}
    statement = (
        db.select(Review.book_id, db.func.avg(Review.rating), db.func.count(Review.review_id))
        .where(Review.book_id.in_(book_ids)).group_by(Review.book_id)
    )
    return {book_id: (average, count) for book_id, average, count in db.session.execute(statement)}


def rated_books(records):
    rating = ratings_for([book.book_id for book in records])
    return [book_data(book, *rating.get(book.book_id, (None, 0))) for book in records]


def term_match(term):
    return or_(
        *(field.contains(term, autoescape=True) for field in SEARCH_FIELDS),
        Book.topics.any(or_(Topic.name.contains(term, autoescape=True), Topic.subject.contains(term, autoescape=True))),
    )


@books.get("/books")
@require_user()
def catalog():
    query = string(request.args.get("q"), "Search query", 150, required=False)
    category = string(request.args.get("category"), "Category", 100, required=False)
    subject = string(request.args.get("subject"), "Subject", 100, required=False)
    sort = request.args.get("sort", "relevance" if query else "title")
    availability = request.args.get("availability", "")
    page = integer(request.args.get("page", 1), "Page", maximum=10000)
    per_page = integer(request.args.get("per_page", 12), "Page size", maximum=50)

    include_archived = g.user.role == "admin" and request.args.get("archived") == "1"
    statement = db.select(Book)
    if not include_archived:
        statement = statement.where(Book.is_archived.is_(False))
    relevance = None
    if query:
        terms = re.findall(r"[\w+#.-]+", query)
        lexical = db.and_(*(term_match(term) for term in terms)) if terms else term_match(query)
        relevance = match(*SEARCH_FIELDS, against=query).in_natural_language_mode()
        statement = statement.where(or_(relevance > 0, lexical))
    if category:
        statement = statement.where(Book.category == category)
    if subject:
        statement = statement.where(Book.topics.any(Topic.subject == subject))
    if availability == "available":
        statement = statement.where(Book.available_copies > 0)
    elif availability == "unavailable":
        statement = statement.where(Book.available_copies == 0)
    elif availability not in {"", "all"}:
        raise APIError(400, "Choose a valid availability filter.")

    if sort == "rating":
        ratings = db.select(
            Review.book_id, db.func.avg(Review.rating).label("average"), db.func.count().label("count"),
        ).group_by(Review.book_id).subquery()
        statement = statement.outerjoin(ratings, ratings.c.book_id == Book.book_id)
        statement = statement.order_by(ratings.c.average.desc(), ratings.c.count.desc())
    elif sort == "relevance" and relevance is not None:
        statement = statement.order_by(case((Book.title.contains(query, autoescape=True), 1), else_=0).desc(),
                                       relevance.desc())
    elif sort == "author":
        statement = statement.order_by(Book.author)
    elif sort == "available":
        statement = statement.order_by(Book.available_copies.desc())
    elif sort not in {"title", "relevance"}:
        raise APIError(400, "Choose a valid sort order.")

    paged = db.paginate(statement.order_by(Book.title, Book.book_id), page=page, per_page=per_page, error_out=False)
    category_options = db.select(Book.category).where(Book.category.is_not(None))
    if not include_archived:
        category_options = category_options.where(Book.is_archived.is_(False))
    categories = db.session.scalars(category_options.distinct().order_by(Book.category)).all()
    subjects = db.session.scalars(db.select(Topic.subject).distinct().order_by(Topic.subject)).all()
    return {
        "items": rated_books(paged.items), "page": paged.page, "pages": paged.pages, "total": paged.total,
        "per_page": paged.per_page, "categories": list(categories), "subjects": list(subjects),
    }


@books.get("/books/<int:book_id>")
@require_user()
def book_detail(book_id):
    book = get_book(book_id)
    topic_ids = [topic.topic_id for topic in book.topics]
    if topic_ids:
        shared = db.select(book_topic.c.book_id, db.func.count().label("matches")).where(
            book_topic.c.topic_id.in_(topic_ids)
        ).group_by(book_topic.c.book_id).subquery()
        related = db.select(Book).join(shared, shared.c.book_id == Book.book_id).order_by(shared.c.matches.desc())
    elif book.category:
        related = db.select(Book).where(Book.category == book.category)
    else:
        related = db.select(Book).where(db.false())
    related = related.where(Book.book_id != book_id, Book.is_archived.is_(False)).order_by(
        Book.available_copies.desc(), Book.title, Book.book_id,
    )
    result = rated_books([book])[0]
    result["related_books"] = rated_books(db.session.scalars(related.limit(4)).all())
    return result


@books.get("/books/<int:book_id>/reviews")
@require_user()
def reviews(book_id):
    get_book(book_id)
    statement = (
        db.select(Review).where(Review.book_id == book_id).options(joinedload(Review.user))
        .order_by(Review.timestamp.desc(), Review.review_id.desc())
    )
    return {"items": [review_data(review) for review in db.session.scalars(statement)]}


def save_review(book_id, edit):
    get_book(book_id)
    data = payload()
    rating = integer(data.get("rating"), "Rating", minimum=1, maximum=5)
    description = string(data.get("review_text"), "Review", 3500, required=False)
    existing = db.session.scalar(db.select(Review).where(
        Review.book_id == book_id, Review.user_id == g.user.user_id,
    ))
    if edit and existing is None:
        raise APIError(404, "You have not reviewed this book yet.")
    if not edit and existing is not None:
        raise APIError(409, "You already reviewed this book. Edit your existing review instead.")
    review = existing or Review(book_id=book_id, user_id=g.user.user_id)
    review.rating = rating
    review.review_text = description
    db.session.add(review)
    try:
        db.session.commit()
    except IntegrityError as error:
        if getattr(error.orig, "args", (None,))[0] == 1062:
            raise APIError(409, "You already reviewed this book. Edit your existing review instead.") from error
        raise
    return review_data(review), 200 if edit else 201


@books.post("/books/<int:book_id>/reviews")
@require_user("student")
def create_review(book_id):
    return save_review(book_id, edit=False)


@books.put("/books/<int:book_id>/reviews/me")
@require_user("student")
def edit_review(book_id):
    return save_review(book_id, edit=True)
