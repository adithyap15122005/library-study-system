from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.extensions import db
from app.models import Book, Borrow, ProgressLedger, StudyPathway, topic_prerequisite
from scripts.import_catalog import import_editions, load_editions, valid_isbn
from scripts.seed_data import seed_courses


def test_bundled_editions_are_unique_and_have_source_records():
    editions = load_editions()
    assert len(editions) >= 150
    assert len(Counter(item["category"] for item in editions)) == 14
    assert len({item["source_url"] for item in editions}) == len(editions)
    assert valid_isbn("9781108470049") and not valid_isbn("9781108470048")


def test_import_idempotence_preserves_book_ids_stock_and_loans(app, sign_in, change):
    records = load_editions()[:3]
    with app.app_context():
        import_editions(records)
        book = db.session.scalar(db.select(Book).where(Book.isbn == records[0]["isbn"]))
        assert book.total_copies == book.available_copies == 0
        book_id = book.book_id
        book.total_copies = book.available_copies = 2
        db.session.commit()
    loan = change(sign_in(), "POST", "/api/borrows", {"book_id": book_id}).get_json()
    with app.app_context():
        import_editions(records)
        db.session.commit()
        book = db.session.get(Book, book_id)
        assert (book.total_copies, book.available_copies) == (2, 1)
        assert db.session.get(Borrow, loan["borrow_id"]).book_id == book_id
        assert db.session.scalar(db.select(db.func.count()).select_from(Book).where(
            Book.isbn.in_([record["isbn"] for record in records]),
        )) == len(records)


@pytest.fixture
def machine_learning(app, demo):
    from app.models import Course

    with app.app_context():
        seed_courses()
        import_editions(load_editions())
        db.session.commit()
        return db.session.scalar(db.select(Course.course_id).where(Course.name == "Machine Learning"))


def test_full_machine_learning_preview_and_generation(app, machine_learning, sign_in, change):
    client = sign_in()
    courses = client.get("/api/courses").get_json()["courses"]
    assert len(courses) == 14
    preview = client.get(f"/api/courses/{machine_learning}/preview").get_json()
    assert preview["course"]["name"] == "Machine Learning"
    steps = preview["steps"]
    assert len(steps) == 24 == len({step["topic_id"] for step in steps})
    indices = {step["topic_id"]: step["sequence_no"] for step in steps}
    assert all(indices[required["topic_id"]] < step["sequence_no"]
               for step in steps for required in step["prerequisites"])
    assert sum(step["estimated_hours"] for step in steps) == preview["course"]["estimated_hours"]
    for topic, isbn in [("Linear Algebra", "9781108470049"), ("Linear Regression", "9781098122478"),
                        ("Production Systems", "9781098107963")]:
        step = next(step for step in steps if step["name"] == topic)
        assert any(book["isbn"] == isbn and book["source_url"] for book in step["books"])
    body = {"course_id": machine_learning}
    response = change(client, "POST", "/api/pathways/from-course", body)
    assert response.status_code == 201, response.get_json()
    pathway = response.get_json()["pathway"]
    path_id = pathway["pathway_id"]
    assert pathway["progress_percent"] == 0
    assert [step["topic_id"] for step in pathway["steps"]] == list(indices)
    assert all(not step["is_completed"] and step["completed_at"] is None for step in pathway["steps"])
    base = f"/api/pathways/{path_id}"
    assert client.get(f"{base}/ledger").get_json()["entries"] == []
    assert sign_in("other").get(base).status_code == 403
    assert change(sign_in("admin"), "POST", "/api/pathways/from-course", body).status_code == 403
    response = change(client, "POST", f"/api/pathway-topics/{pathway['steps'][-1]['pathway_topic_id']}/complete")
    assert response.status_code == 409
    assert change(client, "POST", f"/api/pathway-topics/{pathway['steps'][0]['pathway_topic_id']}/complete").status_code == 200
    proof = client.get(f"{base}/ledger").get_json()
    assert proof["verification"]["valid"] and len(proof["entries"]) == 1
    repeated = change(client, "POST", "/api/pathways/from-course", body)
    assert repeated.status_code == 200 and repeated.get_json()["pathway"]["pathway_id"] == path_id
    assert repeated.get_json()["pathway"]["completed_steps"] == 1
    assert change(sign_in("other"), "POST", "/api/pathways/from-course", body).status_code == 201
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(StudyPathway)) == 2
        assert db.session.scalar(db.select(db.func.count()).select_from(ProgressLedger)) == 1


def test_transitive_prerequisites_admin_curation_and_cycles(app, demo, sign_in, change):
    admin, student = sign_in("admin"), sign_in()
    data = {"name": "Classifier Lab", "subject": "AI", "description": "Compare trained classifiers.",
            "difficulty_level": "Intermediate", "objectives": ["Train a classifier"],
            "syllabus": [{"topic_id": demo["model"], "module": "Training", "estimated_hours": 3}]}
    assert change(student, "POST", "/api/admin/courses", data).status_code == 403
    with app.app_context():
        db.session.execute(topic_prerequisite.insert().values(prerequisite_topic_id=demo["basics"],
                                                              dependent_topic_id=demo["stats"]))
        db.session.commit()
    created = change(admin, "POST", "/api/admin/courses", data)
    assert created.status_code == 201, created.get_json()
    course_id = created.get_json()["course_id"]
    preview = student.get(f"/api/courses/{course_id}/preview").get_json()
    assert [step["topic_id"] for step in preview["steps"]] == [demo["basics"], demo["stats"], demo["model"]]
    assert preview["course"]["estimated_hours"] == 7
    data["syllabus"][0]["estimated_hours"] = 5
    assert change(admin, "PUT", f"/api/admin/courses/{course_id}", data).status_code == 200
    with app.app_context():
        db.session.execute(topic_prerequisite.insert().values(prerequisite_topic_id=demo["model"],
                                                              dependent_topic_id=demo["basics"]))
        db.session.commit()
    assert change(student, "POST", "/api/pathways/from-course", {"course_id": course_id}).status_code == 409


def test_concurrent_course_requests_reuse_one_pathway(app, machine_learning, sign_in, change):
    clients = [sign_in(), sign_in()]
    start = Barrier(2)

    def submit(client):
        start.wait(timeout=10)
        return change(client, "POST", "/api/pathways/from-course", {"course_id": machine_learning})

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, clients))
    assert sorted(response.status_code for response in results) == [200, 201]
    assert len({response.get_json()["pathway"]["pathway_id"] for response in results}) == 1
