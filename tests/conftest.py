import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from flask_migrate import upgrade
from sqlalchemy.engine import make_url

from app import create_app
from app.extensions import db
from app.models import Book, Topic, User, topic_prerequisite
from app.passwords import hash_password


ROOT = Path(__file__).resolve().parents[1]
TEST_PASSWORD = "Folio-test-password!"


@pytest.fixture(scope="session")
def migrated_mysql():
    load_dotenv(ROOT / ".env")
    configured = os.getenv("TEST_DATABASE_URL")
    if not configured:
        pytest.skip("Set TEST_DATABASE_URL to a disposable MySQL database ending in _test.")
    test_url = make_url(configured)
    app_url = os.getenv("DATABASE_URL")
    if (
        test_url.drivername != "mysql+pymysql"
        or not test_url.database
        or not test_url.database.endswith("_test")
        or (app_url and test_url.database == make_url(app_url).database)
    ):
        pytest.fail("Use a separate mysql+pymysql test database ending in _test.")
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-only-session-secret-0123456789abcdef",
        "LEDGER_SECRET": "test-only-ledger-secret-fedcba9876543210",
        "SQLALCHEMY_DATABASE_URI": configured,
        "SESSION_COOKIE_SECURE": False,
    })
    with app.app_context():
        version = db.session.scalar(db.text("SELECT VERSION()"))
        assert "mariadb" not in version.lower() and int(version.split(".")[0]) >= 8
        db.session.remove()
        upgrade(directory=str(ROOT / "migrations"))
    return app


@pytest.fixture
def app(migrated_mysql):
    def clear_records():
        with migrated_mysql.app_context():
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(table.delete())
            db.session.commit()

    clear_records()
    yield migrated_mysql
    clear_records()


@pytest.fixture(scope="session")
def demo_password_hash():
    return hash_password(TEST_PASSWORD)


@pytest.fixture
def demo(app, demo_password_hash):
    with app.app_context():
        accounts = {
            key: User(
                name=key.title(), email=f"{key}@example.test",
                password_hash=demo_password_hash,
                role="admin" if key == "admin" else "student",
                interests=["Python programming"] if key == "student" else [],
            )
            for key in ("student", "other", "admin")
        }
        topics = {
            "basics": Topic(name="Python Programming", subject="Programming",
                            description="Python functions, lists and control flow.", difficulty_level="Beginner"),
            "stats": Topic(name="Statistics", subject="Mathematics",
                           description="Probability and estimation.", difficulty_level="Beginner"),
            "model": Topic(name="Machine Learning", subject="Artificial Intelligence",
                           description="Predictive models and evaluation.", difficulty_level="Intermediate"),
        }
        specs = {
            "python": ("Python Fundamentals", "Programming", "Python programming functions loops and modules.", ["basics"], 1),
            "ml": ("Machine Learning Models", "AI", "Classification and predictive machine learning models.", ["model"], 3),
            "db": ("Relational Databases", "Databases", "SQL joins, normalization and transactions.", [], 2),
            "os": ("Operating Systems", "Systems", "Operating systems memory paging and process scheduling.", [], 0),
        }
        books = {
            key: Book(title=title, author="Test Author", category=category, description=description,
                      total_copies=copies, available_copies=copies, topics=[topics[name] for name in references])
            for key, (title, category, description, references, copies) in specs.items()
        }
        db.session.add_all([*accounts.values(), *topics.values(), *books.values()])
        db.session.flush()
        db.session.execute(topic_prerequisite.insert(), [
            {"prerequisite_topic_id": topics[key].topic_id, "dependent_topic_id": topics["model"].topic_id}
            for key in ("basics", "stats")
        ])
        ids = {key: account.user_id for key, account in accounts.items()}
        ids.update({key: topic.topic_id for key, topic in topics.items()})
        ids.update({key: book.book_id for key, book in books.items()})
        db.session.commit()
    return ids


@pytest.fixture
def change():
    def send(client, method, path, data=None):
        token = client.get("/api/session").get_json()["csrf_token"]
        return client.open(path, method=method, json=data if data is not None else {},
                           headers={"X-CSRF-Token": token})

    return send


@pytest.fixture
def sign_in(app, demo, change):
    def login(role="student"):
        client = app.test_client()
        response = change(client, "POST", "/api/auth/login", {"email": f"{role}@example.test",
                                                              "password": TEST_PASSWORD})
        assert response.status_code == 200, response.get_json()
        return client

    return login
