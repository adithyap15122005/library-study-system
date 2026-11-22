"""Install the Folio curricula, shared topics and verified catalogue."""

from app import create_app
from app.extensions import db
from app.models import Course, CourseTopic, Topic, User, topic_prerequisite
from app.passwords import hash_password
from app.services.prerequisite_service import add_prerequisite
from scripts.curricula import CURRICULA, TOPIC_OBJECTIVES
from scripts.demo_catalog import PREREQUISITES, TOPICS
from scripts.import_catalog import import_editions, load_editions


def seed_accounts(student_password, admin_password):
    accounts = (
        ("Maya Rao", "maya", ["Python", "Machine Learning"]),
        ("Adil Menon", "adil", ["SQL", "Databases"]),
        ("Leena Shah", "leena", ["Deep Learning", "Data Science"]),
        ("Library Administrator", "admin", []),
    )
    for name, key, interests in accounts:
        email = f"{key}@example.test"
        role = "admin" if key == "admin" else "student"
        password = admin_password if role == "admin" else student_password
        if not db.session.scalar(db.select(User).where(User.email == email)):
            if not isinstance(password, str) or not 8 <= len(password) <= 128:
                raise ValueError("Configure development demo passwords of 8–128 characters in .env.")
            db.session.add(User(name=name, email=email, role=role, interests=interests,
                                password_hash=hash_password(password)))


def seed_courses():
    topics = {(item.name, item.subject): item for item in db.session.scalars(db.select(Topic))}
    existing = {item.name for item in db.session.scalars(db.select(Course))}
    edges = set(tuple(row) for row in db.session.execute(db.select(topic_prerequisite)))
    shared = {}
    pending_edges = []
    for key, name, subject, level, objective in TOPICS:
        if (name, subject) not in topics:
            topics[name, subject] = Topic(name=name, subject=subject, difficulty_level=level, description=objective)
            db.session.add(topics[name, subject])
        shared[key] = topics[name, subject]
    pending_edges.extend((shared[prerequisite], shared[dependent]) for prerequisite, dependent in PREREQUISITES)
    for name, level, objectives, modules in CURRICULA:
        if name in existing:
            continue
        course = Course(name=name, subject=name, difficulty_level=level, objectives=list(objectives),
                        description=" ".join(objectives))
        previous = None
        for module, names in modules:
            for item in names.split("; "):
                topic = shared.get(item)
                if topic is None:
                    if (item, name) not in topics:
                        topic = topics[item, name] = Topic(
                            name=item, subject=name, difficulty_level=level,
                            description=TOPIC_OBJECTIVES.get(item, f"Apply {item.lower()} in a worked example and explain your choices."),
                        )
                        if previous is not None:
                            pending_edges.append((previous, topic))
                    topic = topics[item, name]
                hours = 6 if item.endswith(("Project", "Capstone")) else 3 if level == "Advanced" else 2
                course.syllabus.append(CourseTopic(topic=topic, module=module,
                                                  sequence_no=len(course.syllabus) + 1, estimated_hours=hours))
                previous = topic
        db.session.add(course)
    db.session.flush()
    for required, dependent in pending_edges:
        edge = (required.topic_id, dependent.topic_id)
        if edge not in edges:
            add_prerequisite(*edge)
            edges.add(edge)


def main():
    app = create_app()
    with app.app_context():
        seed_accounts(app.config["DEMO_PASSWORD"], app.config["DEMO_ADMIN_PASSWORD"])
        seed_courses()
        count = import_editions(load_editions())
        db.session.commit()
        print(f"Seeded {count} verified editions and {len(CURRICULA)} default courses.")


if __name__ == "__main__":
    main()
