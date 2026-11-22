from datetime import datetime, timezone

from sqlalchemy.dialects.mysql import CHAR, DATETIME

from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


INNODB = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}


def foreign_key(target):
    return db.ForeignKey(target, ondelete="RESTRICT", onupdate="RESTRICT")


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (db.CheckConstraint("role IN ('student', 'admin')", name="role"), INNODB)

    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student", server_default="student")
    date_of_joining = db.Column(DATETIME(fsp=6), nullable=False, default=utcnow)
    interests = db.Column(db.JSON(none_as_null=True))


book_topic = db.Table(
    "book_topic",
    db.Column("book_id", db.Integer, foreign_key("books.book_id"), primary_key=True),
    db.Column("topic_id", db.Integer, foreign_key("topics.topic_id"), primary_key=True),
    db.Index("ix_book_topic_topic", "topic_id", "book_id"),
    **INNODB,
)

topic_prerequisite = db.Table(
    "topic_prerequisite",
    db.Column("prerequisite_topic_id", db.Integer, foreign_key("topics.topic_id"), primary_key=True),
    db.Column("dependent_topic_id", db.Integer, foreign_key("topics.topic_id"), primary_key=True),
    db.CheckConstraint("prerequisite_topic_id <> dependent_topic_id", name="distinct_topics"),
    db.Index("ix_topic_prerequisite_dependent", "dependent_topic_id", "prerequisite_topic_id"),
    **INNODB,
)


class Book(db.Model):
    __tablename__ = "books"
    __table_args__ = (
        db.CheckConstraint("total_copies >= 0", name="total_nonnegative"),
        db.CheckConstraint("available_copies BETWEEN 0 AND total_copies", name="available_range"),
        db.Index("ix_books_catalog_category", "category", "title", "book_id"),
        db.Index("ix_books_available", "available_copies"),
        db.Index("ft_books_text", "title", "author", "category", "description", mysql_prefix="FULLTEXT"),
        INNODB,
    )

    book_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    publisher = db.Column(db.String(255))
    isbn = db.Column(db.String(20), unique=True)
    category = db.Column(db.String(100))
    description = db.Column(db.Text, nullable=False)
    total_copies = db.Column(db.Integer, nullable=False)
    available_copies = db.Column(db.Integer, nullable=False)
    cover_url = db.Column(db.String(1000))
    topics = db.relationship("Topic", secondary=book_topic, lazy="selectin", order_by="Topic.name")


class Borrow(db.Model):
    __tablename__ = "borrow"
    __table_args__ = (
        db.CheckConstraint("due_date > issue_date", name="due_after_issue"),
        db.CheckConstraint(
            "(status = 'issued' AND return_date IS NULL) OR "
            "(status = 'returned' AND return_date IS NOT NULL AND return_date >= issue_date)",
            name="status_return_date",
        ),
        db.Index("ix_borrow_user_history", "user_id", "issue_date", "borrow_id"),
        db.Index("ix_borrow_book_status", "book_id", "status", "user_id"),
        db.Index("ix_borrow_status_due", "status", "due_date"),
        INNODB,
    )

    borrow_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, foreign_key("users.user_id"), nullable=False)
    book_id = db.Column(db.Integer, foreign_key("books.book_id"), nullable=False)
    issue_date = db.Column(DATETIME(fsp=6), nullable=False, default=utcnow)
    due_date = db.Column(DATETIME(fsp=6), nullable=False)
    return_date = db.Column(DATETIME(fsp=6))
    status = db.Column(db.String(20), nullable=False, default="issued", server_default="issued")
    user = db.relationship(User)
    book = db.relationship(Book)


class Review(db.Model):
    __tablename__ = "review"
    __table_args__ = (
        db.UniqueConstraint("user_id", "book_id", name="uq_review_user_book"),
        db.CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
        db.Index("ix_review_book_timestamp", "book_id", "timestamp"),
        INNODB,
    )

    review_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, foreign_key("users.user_id"), nullable=False)
    book_id = db.Column(db.Integer, foreign_key("books.book_id"), nullable=False)
    review_text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(DATETIME(fsp=6), nullable=False, default=utcnow, onupdate=utcnow)
    user = db.relationship(User)
    book = db.relationship(Book)


class Topic(db.Model):
    __tablename__ = "topics"
    __table_args__ = (
        db.UniqueConstraint("name", "subject", name="uq_topics_name_subject"),
        db.CheckConstraint("difficulty_level IN ('Beginner', 'Intermediate', 'Advanced')", name="difficulty"),
        db.Index("ix_topics_subject", "subject"),
        INNODB,
    )

    topic_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    difficulty_level = db.Column(db.String(30), nullable=False)
    books = db.relationship(Book, secondary=book_topic, viewonly=True, order_by=Book.title)


class Recommendation(db.Model):
    __tablename__ = "recommendation"
    __table_args__ = (
        db.CheckConstraint("score BETWEEN 0 AND 1", name="score_range"),
        db.Index("ix_recommendation_user_topic_batch", "user_id", "topic_id", "generated_at"),
        INNODB,
    )

    rec_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, foreign_key("users.user_id"), nullable=False)
    topic_id = db.Column(db.Integer, foreign_key("topics.topic_id"))
    book_id = db.Column(db.Integer, foreign_key("books.book_id"), nullable=False)
    score = db.Column(db.Numeric(8, 7), nullable=False)
    model_type = db.Column(db.String(100), nullable=False)
    generated_at = db.Column(DATETIME(fsp=6), nullable=False, default=utcnow)
    reason = db.Column(db.Text, nullable=False)
    book = db.relationship(Book)
    topic = db.relationship(Topic)


class StudyPathway(db.Model):
    __tablename__ = "study_pathway"
    __table_args__ = (
        db.UniqueConstraint("pathway_id", "user_id", name="uq_study_pathway_id_user"),
        db.CheckConstraint("status IN ('active', 'completed')", name="status"),
        db.Index("ix_study_pathway_user_status", "user_id", "status"),
        INNODB,
    )

    pathway_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, foreign_key("users.user_id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    target_goal = db.Column(db.String(255), nullable=False)
    created_at = db.Column(DATETIME(fsp=6), nullable=False, default=utcnow)
    status = db.Column(db.String(30), nullable=False, default="active", server_default="active")
    steps = db.relationship("PathwayTopic", lazy="selectin", order_by="PathwayTopic.sequence_no")
    user = db.relationship(User)


class PathwayTopic(db.Model):
    __tablename__ = "pathway_topic"
    __table_args__ = (
        db.UniqueConstraint("pathway_id", "topic_id", name="uq_pathway_topic_topic"),
        db.UniqueConstraint("pathway_id", "sequence_no", name="uq_pathway_topic_sequence"),
        db.UniqueConstraint("pathway_id", "pathway_topic_id", name="uq_pathway_topic_id"),
        db.CheckConstraint("sequence_no >= 1", name="positive_sequence"),
        db.CheckConstraint(
            "(is_completed = 0 AND completed_at IS NULL) OR "
            "(is_completed = 1 AND completed_at IS NOT NULL)",
            name="completion_date",
        ),
        INNODB,
    )

    pathway_topic_id = db.Column(db.Integer, primary_key=True)
    pathway_id = db.Column(db.Integer, foreign_key("study_pathway.pathway_id"), nullable=False)
    topic_id = db.Column(db.Integer, foreign_key("topics.topic_id"), nullable=False)
    sequence_no = db.Column(db.Integer, nullable=False)
    is_completed = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("0"))
    completed_at = db.Column(DATETIME(fsp=6))
    topic = db.relationship(Topic)


class ProgressLedger(db.Model):
    __tablename__ = "progress_ledger"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ("pathway_id", "user_id"), ("study_pathway.pathway_id", "study_pathway.user_id"),
            name="fk_progress_ledger_pathway_owner", ondelete="RESTRICT", onupdate="RESTRICT",
        ),
        db.ForeignKeyConstraint(
            ("pathway_id", "pathway_topic_id"), ("pathway_topic.pathway_id", "pathway_topic.pathway_topic_id"),
            name="fk_progress_ledger_pathway_step", ondelete="RESTRICT", onupdate="RESTRICT",
        ),
        db.CheckConstraint("event_type = 'COMPLETE'", name="event_type"),
        db.Index("ix_progress_ledger_pathway_order", "pathway_id", "ledger_id"),
        INNODB,
    )

    ledger_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, foreign_key("users.user_id"), nullable=False)
    pathway_id = db.Column(db.Integer, nullable=False)
    pathway_topic_id = db.Column(db.Integer, nullable=False, unique=True)
    event_type = db.Column(db.String(30), nullable=False, default="COMPLETE", server_default="COMPLETE")
    event_time = db.Column(DATETIME(fsp=6), nullable=False)
    previous_hash = db.Column(CHAR(64, charset="ascii", collation="ascii_bin"), nullable=False)
    entry_hash = db.Column(CHAR(64, charset="ascii", collation="ascii_bin"), nullable=False)
    hash_version = db.Column(db.String(20), nullable=False)
