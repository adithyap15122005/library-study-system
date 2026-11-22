from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Book, PathwayTopic, ProgressLedger, Recommendation, StudyPathway, utcnow
from app.services import ledger_service


def create_learning_path(client, change, demo, *, include=True):
    return change(client, "POST", "/api/pathways", {
        "name": "Machine Learning Foundations",
        "description": "Build a first prediction model.",
        "target_goal": "Compare and evaluate a classifier",
        "topic_ids": [demo["model"]],
        "include_prerequisites": include,
    })


def finish_step(client, change, step):
    return change(client, "POST", f"/api/pathway-topics/{step['pathway_topic_id']}/complete")


def ledger_url(pathway):
    return f"/api/pathways/{pathway['pathway_id']}/ledger"


def test_recommendations_rank_content_and_persist_book_references(app, demo, sign_in, change):
    client = sign_in()
    generated = change(client, "POST", "/api/recommendations/generate")
    assert generated.status_code == 200, generated.get_json()
    batch = generated.get_json()["recommendations"]
    assert batch[0]["book_id"] == demo["python"]
    assert "Python Programming" in batch[0]["reason"]
    assert batch[0]["score"] > max((row["score"] for row in batch if row["book_id"] == demo["os"]), default=0)
    assert all(0 <= row["score"] <= 1 and row["model_type"] == "tfidf_cosine_v1" for row in batch)
    assert len({row["book_id"] for row in batch}) == len(batch)

    with app.app_context():
        saved = db.session.execute(
            db.select(Recommendation.rec_id, Book.book_id)
            .join(Book, Book.book_id == Recommendation.book_id)
            .where(Recommendation.user_id == demo["student"])
            .order_by(Recommendation.rec_id)
        ).all()
        assert saved == [(row["rec_id"], row["book_id"]) for row in batch]
    assert sign_in().get("/api/recommendations/me").get_json()["recommendations"] == batch


def test_preferences_change_ranking_and_topic_context_is_independent(demo, sign_in, change):
    client = sign_in()
    result = change(client, "POST", "/api/recommendations/generate").get_json()["recommendations"]
    assert result[0]["book_id"] == demo["python"]

    profile = change(client, "PATCH", "/api/me", {"interests": ["SQL joins", "relational databases"]})
    assert profile.status_code == 200
    updated = change(client, "POST", "/api/recommendations/generate").get_json()["recommendations"]
    assert updated[0]["book_id"] == demo["db"]
    assert set(row["rec_id"] for row in result).isdisjoint(row["rec_id"] for row in updated)

    focus = change(client, "POST", "/api/recommendations/generate", {"topic_id": demo["model"]})
    assert focus.status_code == 200, focus.get_json()
    focused = focus.get_json()["recommendations"]
    assert focused[0]["book_id"] == demo["ml"]
    assert all(row["topic_id"] == demo["model"] for row in focused)
    assert client.get(f"/api/recommendations/me?topic_id={demo['model']}").get_json()["recommendations"] == focused
    assert client.get("/api/recommendations/me").get_json()["recommendations"] == updated

    unmatched = change(client, "POST", "/api/recommendations/generate", {"topic_id": demo["stats"]})
    assert unmatched.status_code == 200 and unmatched.get_json()["recommendations"] == []


def test_empty_profile_has_deterministic_catalog_fallback(demo, sign_in, change):
    client = sign_in("other")
    batch = change(client, "POST", "/api/recommendations/generate").get_json()["recommendations"]
    assert [row["book_id"] for row in batch] == [demo["ml"], demo["python"], demo["db"], demo["os"]]
    assert all(row["score"] == 0 and "empty" in row["reason"] for row in batch)
    assert batch[0]["book"]["available_copies"] > 0
    assert batch[-1]["book"]["available_copies"] == 0


def test_missing_prerequisites_and_topological_sequence(app, demo, sign_in, change):
    client = sign_in()
    rejected = create_learning_path(client, change, demo, include=False)
    assert rejected.status_code == 409
    missing = rejected.get_json()["details"]["missing_prerequisites"]
    assert {row["topic_id"] for row in missing} == {demo["basics"], demo["stats"]}
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(StudyPathway)) == 0

    response = create_learning_path(client, change, demo)
    assert response.status_code == 201, response.get_json()
    pathway = response.get_json()["pathway"]
    assert [row["sequence_no"] for row in pathway["steps"]] == [1, 2, 3]
    assert {row["topic_id"] for row in pathway["steps"][:2]} == {demo["basics"], demo["stats"]}
    assert pathway["steps"][2]["topic_id"] == demo["model"]
    assert [row["state"] for row in pathway["steps"]] == ["available", "locked", "locked"]


def test_cycle_and_edits_that_invalidate_existing_pathways_are_rejected(demo, sign_in, change):
    student = sign_in()
    admin = sign_in("admin")
    edge = {"prerequisite_topic_id": demo["model"], "dependent_topic_id": demo["basics"]}
    assert change(student, "POST", "/api/admin/prerequisites", edge).status_code == 403
    circular = change(admin, "POST", "/api/admin/prerequisites", edge)
    assert circular.status_code == 409
    assert "circular" in circular.get_json()["error"]

    pathway = create_learning_path(student, change, demo).get_json()["pathway"]
    first, second = pathway["steps"][:2]
    incompatible = change(admin, "POST", "/api/admin/prerequisites", {
        "prerequisite_topic_id": second["topic_id"], "dependent_topic_id": first["topic_id"],
    })
    assert incompatible.status_code == 409
    assert "existing pathway" in incompatible.get_json()["error"]
    assert student.get(f"/api/topics/{first['topic_id']}/prerequisites").get_json()["prerequisites"] == []


def test_locked_completion_and_ownership_have_no_side_effects(app, demo, sign_in, change):
    owner = sign_in()
    other = sign_in("other")
    pathway = create_learning_path(owner, change, demo).get_json()["pathway"]
    first, _, last = pathway["steps"]
    blocked = finish_step(owner, change, last)
    assert blocked.status_code == 409
    assert {row["topic_id"] for row in blocked.get_json()["details"]["blocked_by"]} == {demo["basics"], demo["stats"]}
    assert finish_step(other, change, first).status_code == 403
    assert other.get(f"/api/pathways/{pathway['pathway_id']}").status_code == 403
    assert other.get(ledger_url(pathway)).status_code == 403
    assert other.get(f"{ledger_url(pathway)}/verify").status_code == 403
    with app.app_context():
        assert not db.session.get(PathwayTopic, last["pathway_topic_id"]).is_completed
        assert db.session.scalar(db.select(db.func.count()).select_from(ProgressLedger)) == 0


def test_completion_appends_chain_and_survives_new_login(demo, sign_in, change):
    client = sign_in()
    pathway = create_learning_path(client, change, demo).get_json()["pathway"]
    for count, step in enumerate(pathway["steps"], start=1):
        response = finish_step(client, change, step)
        assert response.status_code == 200, response.get_json()
        progress = response.get_json()["pathway"]
        assert progress["completed_steps"] == count
        assert progress["steps"][count - 1]["completed_at"]
    assert progress["status"] == "completed" and progress["progress_percent"] == 100

    later = sign_in()
    entries = later.get(ledger_url(pathway)).get_json()["entries"]
    assert [entry["sequence_no"] for entry in entries] == [1, 2, 3]
    assert entries[0]["previous_hash"] == ledger_service.GENESIS_HASH
    assert [entry["previous_hash"] for entry in entries[1:]] == [entry["entry_hash"] for entry in entries[:-1]]
    result = later.get(f"{ledger_url(pathway)}/verify").get_json()
    assert result["valid"] is True and result["entry_count"] == 3
    assert sign_in("admin").get(f"{ledger_url(pathway)}/verify").get_json()["valid"] is True


@pytest.mark.parametrize("alteration", ["event_time", "previous_hash", "completion_state"])
def test_verification_detects_tampering(app, demo, sign_in, change, alteration):
    client = sign_in()
    pathway = create_learning_path(client, change, demo).get_json()["pathway"]
    first, second, _ = pathway["steps"]
    assert finish_step(client, change, first).status_code == 200
    assert finish_step(client, change, second).status_code == 200
    with app.app_context():
        entry = db.session.scalar(db.select(ProgressLedger).where(ProgressLedger.pathway_topic_id == second["pathway_topic_id"]))
        entry_id = entry.ledger_id
        if alteration == "event_time":
            entry.event_time += timedelta(seconds=1)
        elif alteration == "previous_hash":
            entry.previous_hash = "f" * 64
        else:
            step = db.session.get(PathwayTopic, second["pathway_topic_id"])
            step.is_completed = False
            step.completed_at = None
        db.session.commit()
    result = client.get(f"{ledger_url(pathway)}/verify").get_json()
    assert result["valid"] is False and result["first_invalid_entry"] == entry_id
    assert result["first_invalid_step"] == second["pathway_topic_id"]


def test_verification_detects_completed_step_without_entry(app, demo, sign_in, change):
    client = sign_in()
    pathway = create_learning_path(client, change, demo).get_json()["pathway"]
    step_id = pathway["steps"][0]["pathway_topic_id"]
    with app.app_context():
        step = db.session.get(PathwayTopic, step_id)
        step.is_completed = True
        step.completed_at = utcnow()
        db.session.commit()
    result = client.get(f"{ledger_url(pathway)}/verify").get_json()
    assert result["valid"] is False
    assert result["first_invalid_entry"] is None and result["first_invalid_step"] == step_id


def test_concurrent_duplicate_completion_has_one_event(app, demo, sign_in, change):
    clients = [sign_in(), sign_in()]
    pathway = create_learning_path(clients[0], change, demo).get_json()["pathway"]
    first = pathway["steps"][0]
    ready = Barrier(2, timeout=8)

    def complete(client):
        ready.wait()
        return finish_step(client, change, first).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(complete, clients)) == [200, 409]
    with app.app_context():
        entries = list(db.session.scalars(db.select(ProgressLedger)))
        assert len(entries) == 1 and entries[0].pathway_topic_id == first["pathway_topic_id"]
        assert db.session.get(PathwayTopic, first["pathway_topic_id"]).is_completed


def test_ledger_failure_rolls_back_flushed_step_and_entry(app, demo, sign_in, change, monkeypatch):
    client = sign_in()
    pathway = create_learning_path(client, change, demo).get_json()["pathway"]
    first = pathway["steps"][0]
    append_completion = ledger_service.append_completion

    def fail_after_flush(*args):
        append_completion(*args)
        db.session.flush()
        raise SQLAlchemyError("test failure after ledger flush")

    monkeypatch.setattr(ledger_service, "append_completion", fail_after_flush)
    failed = finish_step(client, change, first)
    assert failed.status_code == 500
    assert "test failure" not in failed.get_json()["error"]
    with app.app_context():
        step = db.session.get(PathwayTopic, first["pathway_topic_id"])
        assert not step.is_completed and step.completed_at is None
        assert db.session.scalar(db.select(db.func.count()).select_from(ProgressLedger)) == 0
    assert client.get(f"{ledger_url(pathway)}/verify").get_json()["valid"] is True
