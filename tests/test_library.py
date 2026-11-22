from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from werkzeug.security import check_password_hash

from app import create_app
from app.extensions import db
from app.models import Book, Borrow, User, utcnow


def test_registration_hash_and_duplicate_email(app, change):
    client = app.test_client()
    data = {"name": "New Student", "email": "New@example.test", "password": "student-passphrase"}
    assert client.post("/api/auth/register", json=data).status_code == 403
    assert change(client, "POST", "/api/auth/register", data | {"role": "admin"}).status_code == 400
    response = change(client, "POST", "/api/auth/register", data)
    assert response.status_code == 201
    account = response.get_json()["user"]
    assert account["role"] == "student" and account["email"] == "new@example.test"
    with app.app_context():
        stored = db.session.get(User, account["user_id"])
        assert stored.password_hash != data["password"]
        assert check_password_hash(stored.password_hash, data["password"])
    assert change(client, "POST", "/api/auth/register", data).status_code == 409
    assert change(client, "POST", "/api/auth/logout").status_code == 200
    assert client.get("/api/me").status_code == 401
    wrong = change(client, "POST", "/api/auth/login", data | {"password": "wrong-password"})
    assert wrong.status_code == 401
    assert change(client, "POST", "/api/auth/login", data).get_json()["user"]["user_id"] == account["user_id"]


def test_catalog_search_filters_and_pagination(app, demo, sign_in):
    anonymous = app.test_client()
    assert anonymous.get("/api/books").status_code == 401
    student = sign_in()
    results = student.get("/api/books", query_string={"q": "Python", "availability": "available"}).get_json()
    assert [book["book_id"] for book in results["items"]] == [demo["python"]]
    results = student.get("/api/books", query_string={"q": "SQL", "category": "Databases"}).get_json()
    assert [book["book_id"] for book in results["items"]] == [demo["db"]]
    results = student.get("/api/books", query_string={"subject": "Artificial Intelligence"}).get_json()
    assert [book["book_id"] for book in results["items"]] == [demo["ml"]]
    paged = student.get("/api/books", query_string={"per_page": 2, "page": 2, "sort": "author"}).get_json()
    assert (paged["total"], paged["page"], paged["pages"], len(paged["items"])) == (4, 2, 2, 2)


def test_borrow_return_inventory_and_permissions(app, demo, sign_in, change):
    student, other = sign_in(), sign_in("other")
    assert change(student, "POST", "/api/borrows", {"book_id": demo["os"]}).status_code == 409
    assert change(student, "POST", "/api/borrows", {"book_id": 2147483647}).status_code == 404
    assert change(student, "PUT", f"/api/admin/books/{demo['python']}/inventory",
                  {"total_copies": 3}).status_code == 403
    issued = change(student, "POST", "/api/borrows", {"book_id": demo["python"]})
    assert issued.status_code == 201, issued.get_json()
    loan_id = issued.get_json()["borrow_id"]
    url = f"/api/borrows/{loan_id}/return"
    with app.app_context():
        book = db.session.get(Book, demo["python"])
        loan = db.session.get(Borrow, loan_id)
        assert book.available_copies == 0 and loan.status == "issued"
        assert loan.due_date - loan.issue_date == timedelta(days=app.config["BORROW_DAYS"])
        loan.issue_date = utcnow() - timedelta(days=4)
        loan.due_date = utcnow() - timedelta(days=1)
        db.session.commit()
    assert student.get("/api/dashboard").get_json()["overdue"] == 1
    assert change(other, "POST", url).status_code == 403
    librarian = sign_in("admin")
    assert change(librarian, "PUT", f"/api/admin/books/{demo['python']}/inventory",
                  {"total_copies": 0}).status_code == 409
    assert change(student, "POST", url).get_json()["status"] == "returned"
    assert change(student, "POST", url).status_code == 409
    with app.app_context():
        assert db.session.get(Book, demo["python"]).available_copies == 1
        loan = db.session.get(Borrow, loan_id)
        assert loan.return_date is not None and loan.status == "returned"
    assert student.get("/api/borrows/me").get_json()["items"][0]["borrow_id"] == loan_id
    assert librarian.get("/api/admin/stats").get_json()["issued"] == 0


def test_concurrent_checkout_of_last_copy(app, demo, sign_in):
    clients = [sign_in("student"), sign_in("other")]
    tokens = [client.get("/api/session").get_json()["csrf_token"] for client in clients]
    barrier = Barrier(2)

    def issue(index):
        barrier.wait(timeout=5)
        return clients[index].post("/api/borrows", json={"book_id": demo["python"]},
                                   headers={"X-CSRF-Token": tokens[index]}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(issue, range(2))) == [201, 409]
    with app.app_context():
        assert db.session.get(Book, demo["python"]).available_copies == 0
        assert db.session.scalar(db.select(db.func.count()).select_from(Borrow).where(
            Borrow.book_id == demo["python"], Borrow.status == "issued",
        )) == 1


def test_issue_and_return_rollback(app, demo, sign_in, change, monkeypatch):
    client = sign_in()

    def fail_commit():
        raise SQLAlchemyError("simulated commit failure after flush")

    with monkeypatch.context() as overrides:
        overrides.setattr(db.session, "commit", fail_commit)
        assert change(client, "POST", "/api/borrows", {"book_id": demo["python"]}).status_code == 500
    with app.app_context():
        assert db.session.get(Book, demo["python"]).available_copies == 1
        assert db.session.scalar(db.select(db.func.count()).select_from(Borrow)) == 0

    issued = change(client, "POST", "/api/borrows", {"book_id": demo["python"]}).get_json()
    with monkeypatch.context() as overrides:
        overrides.setattr(db.session, "commit", fail_commit)
        assert change(client, "POST", f"/api/borrows/{issued['borrow_id']}/return").status_code == 500
    with app.app_context():
        assert db.session.get(Book, demo["python"]).available_copies == 0
        assert db.session.get(Borrow, issued["borrow_id"]).status == "issued"


def test_real_reviews_and_rating_aggregate(demo, sign_in, change):
    student, other = sign_in(), sign_in("other")
    book_url = f"/api/books/{demo['python']}"
    reviews_url = book_url + "/reviews"
    assert change(student, "POST", reviews_url, {"rating": 6, "review_text": "Invalid"}).status_code == 400
    assert change(student, "POST", reviews_url, {"rating": 5, "review_text": "Clear examples."}).status_code == 201
    assert change(student, "POST", reviews_url, {"rating": 4}).status_code == 409
    assert change(other, "POST", reviews_url, {"rating": 3, "review_text": "Useful exercises."}).status_code == 201
    assert student.get(book_url).get_json()["average_rating"] == 4
    assert change(student, "PUT", reviews_url + "/me", {"rating": 4, "review_text": "Updated review."}).status_code == 200
    detail = student.get(book_url).get_json()
    assert (detail["average_rating"], detail["review_count"]) == (3.5, 2)
    records = student.get(reviews_url).get_json()["items"]
    assert {(record["author"], record["review_text"]) for record in records} == {
        ("Student", "Updated review."), ("Other", "Useful exercises."),
    }


def test_state_survives_new_app_instance(app, demo, sign_in, change):
    original = sign_in()
    stored = change(original, "POST", "/api/borrows", {"book_id": demo["python"]}).get_json()
    created = change(original, "POST", "/api/pathways", {
        "name": "Programming lab", "description": "Practice Python functions.",
        "target_goal": "Write a function", "topic_ids": [demo["basics"]],
    })
    assert created.status_code == 201
    pathway = created.get_json()["pathway"]
    steps = original.get(f"/api/pathways/{pathway['pathway_id']}/topics").get_json()["steps"]
    step_id = steps[0]["pathway_topic_id"]
    assert change(original, "POST", f"/api/pathway-topics/{step_id}/complete").status_code == 200
    assert change(original, "POST", "/api/auth/logout").status_code == 200
    fresh_app = create_app({key: app.config[key] for key in (
        "TESTING", "SECRET_KEY", "LEDGER_SECRET", "SQLALCHEMY_DATABASE_URI", "SESSION_COOKIE_SECURE",
    )})
    fresh = fresh_app.test_client()
    response = change(fresh, "POST", "/api/auth/login", {"email": "student@example.test",
                                                        "password": "Folio-test-password!"})
    assert response.status_code == 200
    assert fresh.get("/api/borrows/me").get_json()["items"][0]["borrow_id"] == stored["borrow_id"]
    proof = fresh.get(f"/api/pathways/{pathway['pathway_id']}/ledger/verify").get_json()
    assert proof["valid"] and proof["entry_count"] == 1


def test_admin_catalog_topic_and_inventory_management(app, demo, sign_in, change):
    admin = sign_in("admin")
    topic_result = change(admin, "POST", "/api/admin/topics", {
        "name": "Transactions", "subject": "Databases", "description": "Practice atomicity and isolation.",
        "difficulty_level": "Intermediate",
    })
    assert topic_result.status_code == 201, topic_result.get_json()
    topic_id = topic_result.get_json()["topic_id"]
    topic_edit = change(admin, "PUT", f"/api/admin/topics/{topic_id}", {
        "name": "Database Transactions", "subject": "Databases", "description": "Practice locks and isolation.",
        "difficulty_level": "Advanced",
    })
    assert topic_edit.get_json()["name"] == "Database Transactions"
    new_book = change(admin, "POST", "/api/admin/books", {
        "title": "Transaction Lab", "author": "Test Author", "description": "Practical row-level locking exercises.",
        "category": "Databases", "total_copies": 3, "topic_ids": [topic_id],
    })
    assert new_book.status_code == 201, new_book.get_json()
    new_book_id = new_book.get_json()["book_id"]
    loan = change(sign_in(), "POST", "/api/borrows", {"book_id": new_book_id})
    assert loan.status_code == 201
    inventory = change(admin, "PUT", f"/api/admin/books/{new_book_id}/inventory", {"total_copies": 2})
    assert inventory.get_json()["available_copies"] == 1
    associated = change(admin, "PUT", f"/api/admin/books/{new_book_id}/topics", {"topic_ids": [topic_id, demo["model"]]})
    assert {topic["topic_id"] for topic in associated.get_json()["topics"]} == {topic_id, demo["model"]}
    assert change(admin, "POST", f"/api/borrows/{loan.get_json()['borrow_id']}/return").status_code == 200
    with app.app_context():
        assert db.session.get(Book, new_book_id).available_copies == 2


def test_database_rejects_invalid_inventory_and_foreign_keys(app, demo):
    with app.app_context():
        book = db.session.get(Book, demo["python"])
        book.available_copies = 2
        with pytest.raises(DBAPIError) as invalid_stock:
            db.session.flush()
        assert invalid_stock.value.orig.args[0] == 3819
        db.session.rollback()
        now = utcnow()
        db.session.add(Borrow(user_id=demo["student"], book_id=2147483647,
                              issue_date=now, due_date=now + timedelta(days=1)))
        with pytest.raises(DBAPIError) as missing_book:
            db.session.flush()
        assert missing_book.value.orig.args[0] == 1452
        db.session.rollback()
