"""Populate a migrated development database with repeatable demonstration data."""

from datetime import timedelta

from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models import Book, Borrow, Recommendation, Review, StudyPathway, Topic, User, topic_prerequisite, utcnow
from app.passwords import hash_password
from app.services.pathway_service import complete_step, create_pathway
from app.services.prerequisite_service import add_prerequisite
from app.services.recommendation_service import generate_recommendations
from scripts.demo_catalog import BOOKS, PREREQUISITES, TOPICS


ACCOUNTS = (
    ("Maya Rao", "maya@example.test", "student", ["Python Programming", "Machine Learning", "Neural Networks"]),
    ("Adil Menon", "adil@example.test", "student", ["Relational Databases", "SQL", "Database Transactions"]),
    ("Leena Shah", "leena@example.test", "student", ["Computer Vision", "Linear Algebra", "Digital Image Processing"]),
    ("Library Administrator", "admin@example.test", "admin", []),
)

LOANS = (
    ("maya", "Python Patterns for First Programs", 3, None),
    ("maya", "SQL by Query", 18, None),
    ("maya", "Probability for Computing", 24, 9),
    ("adil", "Transactions Under Load", 12, None),
    ("leena", "Operating Systems Lab Notebook", 21, 11),
    ("leena", "Images as Arrays", 5, None),
)

REVIEWS = (
    ("maya", "Python Patterns for First Programs", 5, "I used the course planner exercise to practice dictionaries. The traceback examples made debugging much easier."),
    ("maya", "Probability for Computing", 4, "The Bayes' rule tables are clear. I would have liked another worked example on continuous distributions."),
    ("maya", "Machine Learning from First Principles", 5, "The decision tree exercise explains validation separately from training, which helped with my lab report."),
    ("adil", "SQL by Query", 5, "The section on LEFT JOIN was useful for finding students who had never registered for a course."),
    ("adil", "Transactions Under Load", 4, "Running the two-session examples helped me see how a row lock changes borrowing outcomes."),
    ("adil", "Relational Design Studio", 4, "The library case study has a good step-by-step explanation of junction tables."),
    ("leena", "Images as Arrays", 5, "The resizing examples show the differences between interpolation methods on the same tiny image."),
    ("leena", "Linear Algebra for Data", 4, "The projection diagrams helped me understand least squares before writing the matrix operations myself."),
    ("leena", "Operating Systems Lab Notebook", 4, "The file permission exercise is easy to reproduce. The process cleanup questions were the hardest part."),
    ("leena", "Python Patterns for First Programs", 4, "I liked the debugging walkthrough. More examples of reading text files would make it even better."),
)

PATHWAYS = (
    ("maya", "Machine Learning Foundations", "Build the mathematical and Python foundations for training supervised models.", "Train and evaluate a first classifier", ("supervised", "evaluation"), 2),
    ("maya", "Text Retrieval in Python", "Study language features and supervised models before implementing a document retriever.", "Build a short-document search system", ("nlp",), 0),
    ("adil", "SQL Reporting Essentials", "Move from relational tables to reports that combine and summarize data.", "Write a grouped report with a join", ("sql_joins",), 3),
    ("leena", "Digital Images with Python", "Practice array operations and apply them to pixels, filters, and resizing.", "Build a small image filtering program", ("images",), 1),
)


def demo_isbn(index):
    """Give fixtures a stable ISBN-13-shaped identifier for repeatable lookups."""
    digits = f"9780000000{index:02d}"
    weighted_sum = sum(int(digit) * (1 if offset % 2 == 0 else 3) for offset, digit in enumerate(digits))
    return f"{digits}{-weighted_sum % 10}"


def seed_users(student_password, admin_password):
    users = {}
    for name, email, role, interests in ACCOUNTS:
        user = db.session.scalar(select(User).where(User.email == email))
        if user is None:
            password = admin_password if role == "admin" else student_password
            user = User(name=name, email=email, password_hash=hash_password(password), role=role, interests=interests)
            db.session.add(user)
        elif user.role != role:
            raise ValueError(f"Existing account {email} has a different role. Use an empty demo database.")
        users[email.split("@", 1)[0]] = user
    return users


def seed_topics():
    topics = {}
    for key, name, subject, difficulty, description in TOPICS:
        topic = db.session.scalar(select(Topic).where(Topic.name == name, Topic.subject == subject))
        if topic is None:
            topic = Topic(name=name, subject=subject, difficulty_level=difficulty, description=description)
            db.session.add(topic)
        topics[key] = topic
    db.session.flush()

    existing_edges = {(required, dependent) for required, dependent in db.session.execute(select(topic_prerequisite))}
    for prerequisite, dependent in PREREQUISITES:
        edge = (topics[prerequisite].topic_id, topics[dependent].topic_id)
        if edge not in existing_edges:
            add_prerequisite(*edge)
    return topics


def seed_books(topics):
    books = {}
    publishers = ("Meridian Academic", "Northbridge Technical Press", "Lab Manual Collective")
    for index, (title, author, category, topic_keys, description) in enumerate(BOOKS, start=1):
        isbn = demo_isbn(index)
        book = db.session.scalar(select(Book).where(Book.isbn == isbn))
        if book is None:
            copies = 0 if index in {8, 24, 44, 59} else 2 + (index % 5)
            book = Book(
                title=title,
                author=author,
                publisher=publishers[(index - 1) % len(publishers)],
                isbn=isbn,
                category=category,
                description=description,
                total_copies=copies,
                available_copies=copies,
                topics=[topics[key] for key in topic_keys.split()],
            )
            db.session.add(book)
        books[title] = book
    db.session.flush()
    return books


def seed_loans(users, books):
    now = utcnow()
    for username, title, age, loan_length in LOANS:
        user_id, book_id = users[username].user_id, books[title].book_id
        book = db.session.scalar(
            select(Book).where(Book.book_id == book_id).with_for_update().execution_options(populate_existing=True)
        )
        if db.session.scalar(select(Borrow.borrow_id).where(Borrow.user_id == user_id, Borrow.book_id == book_id).limit(1)):
            continue
        issued = now - timedelta(days=age)
        returned = None if loan_length is None else issued + timedelta(days=loan_length)
        if returned is None:
            if book.available_copies < 1:
                raise ValueError(f"Cannot seed an active loan for {title} because no copy is available.")
            book.available_copies -= 1
        db.session.add(Borrow(
            user_id=user_id,
            book_id=book_id,
            issue_date=issued,
            due_date=issued + timedelta(days=14),
            return_date=returned,
            status="issued" if returned is None else "returned",
        ))


def seed_reviews(users, books):
    for username, title, rating, text in REVIEWS:
        user_id, book_id = users[username].user_id, books[title].book_id
        existing = db.session.scalar(select(Review.review_id).where(Review.user_id == user_id, Review.book_id == book_id))
        if existing is None:
            db.session.add(Review(user_id=user_id, book_id=book_id, rating=rating, review_text=text))


def seed_pathways(users, topics):
    for username, name, description, goal, targets, completed_count in PATHWAYS:
        user_id = users[username].user_id
        existing = db.session.scalar(
            select(StudyPathway.pathway_id).where(StudyPathway.user_id == user_id, StudyPathway.name == name).limit(1)
        )
        if existing is not None:
            continue
        pathway = create_pathway(user_id, name, description, goal, [topics[key].topic_id for key in targets], True)
        db.session.flush()
        steps = sorted(pathway.steps, key=lambda step: step.sequence_no)
        for step in steps[:completed_count]:
            complete_step(user_id, step.pathway_topic_id)


def seed_database(student_password, admin_password):
    users = seed_users(student_password, admin_password)
    topics = seed_topics()
    books = seed_books(topics)
    seed_loans(users, books)
    seed_reviews(users, books)
    seed_pathways(users, topics)
    for user in users.values():
        if user.role == "student" and db.session.scalar(
            select(Recommendation.rec_id).where(Recommendation.user_id == user.user_id).limit(1)
        ) is None:
            generate_recommendations(user)
    db.session.commit()


def main():
    app = create_app()
    student_password = app.config["DEMO_PASSWORD"] or ""
    admin_password = app.config["DEMO_ADMIN_PASSWORD"] or ""
    if any(not 8 <= len(password) <= 128 or "\x00" in password for password in (student_password, admin_password)):
        raise SystemExit("Set DEMO_PASSWORD and DEMO_ADMIN_PASSWORD to development passwords of 8–128 characters.")
    with app.app_context():
        try:
            seed_database(student_password, admin_password)
        except Exception:
            db.session.rollback()
            raise
    print(f"Demo data ready: {len(BOOKS)} books, {len(TOPICS)} topics, {len(ACCOUNTS)} accounts, and {len(PATHWAYS)} pathways.")


if __name__ == "__main__":
    main()
