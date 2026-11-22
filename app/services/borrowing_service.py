from datetime import timedelta

from flask import current_app

from app.api import APIError
from app.extensions import db
from app.models import Book, Borrow, utcnow


def lock_book(book_id):
    book = db.session.scalar(
        db.select(Book).where(Book.book_id == book_id).with_for_update().execution_options(populate_existing=True)
    )
    if book is None:
        raise APIError(404, "This book could not be found.")
    return book


def issue_book(user_id, book_id):
    book = lock_book(book_id)
    active_id = db.session.scalar(
        db.select(Borrow.borrow_id).where(
            Borrow.book_id == book_id, Borrow.user_id == user_id, Borrow.status == "issued",
        ).limit(1).with_for_update()
    )
    if active_id is not None:
        raise APIError(409, "You already have an active loan for this book.")
    if book.available_copies == 0:
        raise APIError(409, "No copies of this book are available.")
    now = utcnow()
    loan = Borrow(
        user_id=user_id, book=book, issue_date=now,
        due_date=now + timedelta(days=current_app.config["BORROW_DAYS"]), status="issued",
    )
    db.session.add(loan)
    book.available_copies -= 1
    db.session.flush()
    return loan


def return_book(borrow_id, user_id, is_admin=False):
    snapshot = db.session.execute(
        db.select(Borrow.book_id, Borrow.user_id).where(Borrow.borrow_id == borrow_id)
    ).first()
    if snapshot is None:
        raise APIError(404, "This borrowing record could not be found.")
    if snapshot.user_id != user_id and not is_admin:
        raise APIError(403, "You can return only books you borrowed.")

    # Acquire the inventory lock first, as in issuance and inventory editing.
    book = lock_book(snapshot.book_id)
    loan = db.session.scalar(
        db.select(Borrow).where(Borrow.borrow_id == borrow_id).with_for_update().execution_options(populate_existing=True)
    )
    if loan.status != "issued":
        raise APIError(409, "This book has already been returned.")
    if book.available_copies >= book.total_copies:
        raise APIError(409, "Inventory needs to be reconciled before this return can be recorded.")
    loan.return_date = utcnow()
    loan.status = "returned"
    book.available_copies += 1
    db.session.flush()
    return loan


def set_inventory(book, total_copies):
    active_loans = db.select(Borrow.borrow_id).where(
        Borrow.book_id == book.book_id, Borrow.status == "issued",
    ).with_for_update()
    issued = len(list(db.session.scalars(active_loans)))
    if total_copies < issued:
        raise APIError(409, f"At least {issued} copies are required to cover current loans.")
    book.total_copies = total_copies
    book.available_copies = total_copies - issued
