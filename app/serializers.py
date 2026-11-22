from .api import iso
from .models import utcnow


def user_data(user):
    return {
        "user_id": user.user_id, "name": user.name, "email": user.email,
        "role": user.role, "date_of_joining": iso(user.date_of_joining), "interests": user.interests or [],
    }


def topic_data(topic):
    return {
        "topic_id": topic.topic_id, "name": topic.name, "subject": topic.subject,
        "difficulty_level": topic.difficulty_level, "description": topic.description,
    }


def book_data(book, average_rating=None, review_count=0):
    return {
        "book_id": book.book_id, "title": book.title, "author": book.author, "publisher": book.publisher,
        "isbn": book.isbn, "category": book.category, "description": book.description,
        "total_copies": book.total_copies, "available_copies": book.available_copies, "cover_url": book.cover_url,
        "edition": book.edition, "source_url": book.source_url, "is_archived": book.is_archived,
        "average_rating": round(float(average_rating), 2) if average_rating is not None else None,
        "review_count": int(review_count or 0), "topics": [topic_data(topic) for topic in book.topics],
    }


def borrow_data(loan, include_student=False):
    status = "overdue" if loan.status == "issued" and loan.due_date < utcnow() else loan.status
    data = {
        "borrow_id": loan.borrow_id, "user_id": loan.user_id, "book_id": loan.book_id,
        "title": loan.book.title, "author": loan.book.author,
        "issue_date": iso(loan.issue_date), "due_date": iso(loan.due_date),
        "return_date": iso(loan.return_date), "status": status,
    }
    if include_student:
        data["student"] = loan.user.name
    return data


def review_data(review):
    return {
        "review_id": review.review_id, "user_id": review.user_id,
        "author": review.user.name, "review_text": review.review_text,
        "rating": review.rating, "timestamp": iso(review.timestamp),
    }
