from datetime import timedelta

from flask import Blueprint, g
from sqlalchemy.orm import joinedload

from app.api import integer, payload, require_user
from app.extensions import db
from app.models import Book, Borrow, PathwayTopic, StudyPathway, utcnow
from app.serializers import borrow_data
from app.services.borrowing_service import issue_book, return_book


borrowing = Blueprint("borrowing", __name__, url_prefix="/api")


def borrowing_query():
    return db.select(Borrow).options(joinedload(Borrow.book).lazyload(Book.topics)).order_by(
        Borrow.issue_date.desc(), Borrow.borrow_id.desc(),
    )


@borrowing.post("/borrows")
@require_user("student")
def issue():
    book_id = integer(payload().get("book_id"), "Book ID")
    loan = issue_book(g.user.user_id, book_id)
    db.session.commit()
    return borrow_data(loan), 201


@borrowing.get("/borrows/me")
@require_user()
def my_borrows():
    loans = db.session.scalars(borrowing_query().where(Borrow.user_id == g.user.user_id))
    return {"items": [borrow_data(loan) for loan in loans]}


@borrowing.post("/borrows/<int:borrow_id>/return")
@require_user()
def return_loan(borrow_id):
    borrow_id = integer(borrow_id, "Borrowing ID")
    loan = return_book(borrow_id, g.user.user_id, is_admin=g.user.role == "admin")
    db.session.commit()
    return borrow_data(loan)


@borrowing.get("/dashboard")
@require_user("student")
def dashboard():
    user_id = g.user.user_id
    now = utcnow()
    issued = Borrow.status == "issued"

    def matching(condition):
        return db.func.count(db.case((condition, 1)))

    metrics = db.session.execute(
        db.select(db.func.count(), matching(issued), matching(issued & (Borrow.due_date < now)),
                  matching(issued & Borrow.due_date.between(now, now + timedelta(days=3))))
        .select_from(Borrow).where(Borrow.user_id == user_id)
    ).one()
    active_pathways = db.session.scalar(db.select(db.func.count()).select_from(StudyPathway).where(
        StudyPathway.user_id == user_id, StudyPathway.status == "active",
    ))
    completed_steps = db.session.scalar(db.select(db.func.count()).select_from(PathwayTopic).join(StudyPathway).where(
        StudyPathway.user_id == user_id, PathwayTopic.is_completed.is_(True),
    ))
    recent = db.session.scalars(borrowing_query().where(Borrow.user_id == user_id).limit(5))
    return dict(zip(("total_borrowed", "issued", "overdue", "due_soon"), metrics)) | {
        "active_pathways": active_pathways, "completed_steps": completed_steps,
        "recent_borrows": [borrow_data(loan) for loan in recent],
    }
