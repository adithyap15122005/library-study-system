from sqlalchemy.orm import lazyload

from app.api import APIError
from app.extensions import db
from app.models import Course, CourseTopic, PathwayTopic, StudyPathway, User
from app.services.prerequisite_service import lock_topics, prerequisite_closure, prerequisite_graph, topological_order


def get_course(course_id, *, lock=None):
    statement = db.select(Course).where(Course.course_id == course_id)
    if lock:
        statement = statement.options(lazyload(Course.syllabus)).with_for_update(read=lock == "shared")
    course = db.session.scalar(statement)
    if course is None:
        raise APIError(404, "This course was not found.")
    return course


def course_plan(syllabus, graph):
    """Insert transitive prerequisites before their earliest dependent."""
    if not syllabus:
        raise APIError(409, "This course does not have a syllabus yet.")
    entries = {entry.topic_id: entry for entry in syllabus}
    priority = {}
    modules = {}
    for entry in syllabus:
        for topic_id in prerequisite_closure([entry.topic_id], graph):
            priority.setdefault(topic_id, entry.sequence_no)
            modules.setdefault(topic_id, entry.module)
    ordered = topological_order(priority, graph, priority)
    return [
        (topic_id, modules[topic_id], entries[topic_id].estimated_hours if topic_id in entries else 2)
        for topic_id in ordered
    ]


def get_syllabus(course_id, *, current=False):
    statement = db.select(CourseTopic).where(CourseTopic.course_id == course_id).order_by(CourseTopic.sequence_no)
    if current:
        statement = statement.with_for_update(read=True)
    return list(db.session.scalars(statement))


def generate_course_pathway(user_id, course_id):
    # Serialize repeated submissions by one student. The unique key also protects the invariant.
    db.session.scalar(db.select(User.user_id).where(User.user_id == user_id).with_for_update())
    course = get_course(course_id, lock="shared")
    existing = db.session.scalar(
        db.select(StudyPathway).where(StudyPathway.user_id == user_id, StudyPathway.course_id == course_id)
        .options(lazyload(StudyPathway.steps)).with_for_update()
    )
    if existing is not None:
        return existing, False
    lock_topics()
    plan = course_plan(get_syllabus(course_id, current=True), prerequisite_graph(current=True))
    pathway = StudyPathway(
        user_id=user_id, course_id=course_id, name=course.name, description=course.description,
        target_goal=f"Complete the {course.name} curriculum",
    )
    pathway.steps = [
        PathwayTopic(topic_id=topic_id, module=module, estimated_hours=hours, sequence_no=index)
        for index, (topic_id, module, hours) in enumerate(plan, 1)
    ]
    db.session.add(pathway)
    db.session.flush()
    return pathway, True


def replace_syllabus(course, entries):
    valid_ids = lock_topics()
    if any(entry.topic_id not in valid_ids for entry in entries):
        raise APIError(404, "One or more syllabus topics could not be found.")
    course_plan(entries, prerequisite_graph(current=True))
    db.session.execute(db.delete(CourseTopic).where(CourseTopic.course_id == course.course_id))
    db.session.add_all(entries)
