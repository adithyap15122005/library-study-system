from flask import Blueprint, g
from sqlalchemy.exc import IntegrityError

from app.api import APIError, integer, payload, require_user, string
from app.extensions import db
from app.models import Course, CourseTopic, Topic
from app.routes.learning import books_by_topic, pathway_detail, topic_references
from app.serializers import topic_data
from app.services.course_service import course_plan, generate_course_pathway, get_course, replace_syllabus
from app.services.prerequisite_service import prerequisite_graph


courses = Blueprint("courses", __name__, url_prefix="/api")


def description(course, plan):
    return {
        "course_id": course.course_id, "name": course.name, "subject": course.subject,
        "description": course.description, "difficulty_level": course.difficulty_level,
        "objectives": course.objectives, "total_steps": len(plan),
        "estimated_hours": sum(hours for _, _, hours in plan),
    }


@courses.get("/courses")
@require_user()
def course_list():
    graph = prerequisite_graph()
    rows = db.session.scalars(db.select(Course).order_by(Course.name))
    return {"courses": [description(course, course_plan(course.syllabus, graph)) for course in rows]}


@courses.get("/courses/<int:course_id>")
@courses.get("/courses/<int:course_id>/preview")
@require_user()
def course_preview(course_id):
    course = get_course(integer(course_id, "Course ID"))
    graph = prerequisite_graph()
    plan = course_plan(course.syllabus, graph)
    ids = [topic_id for topic_id, _, _ in plan]
    topics = {topic.topic_id: topic for topic in db.session.scalars(db.select(Topic).where(Topic.topic_id.in_(ids)))}
    names = {topic_id: topic.name for topic_id, topic in topics.items()}
    books = books_by_topic(ids, verified=True)
    steps = [
        {
            **topic_data(topics[topic_id]), "sequence_no": index, "module": module, "estimated_hours": hours,
            "prerequisites": topic_references(sorted(graph.get(topic_id, ())), names), "books": books[topic_id][:5],
        }
        for index, (topic_id, module, hours) in enumerate(plan, 1)
    ]
    syllabus = [{"topic_id": entry.topic_id, "module": entry.module, "estimated_hours": entry.estimated_hours}
                for entry in course.syllabus]
    return {"course": description(course, plan), "steps": steps, "syllabus": syllabus}


@courses.post("/pathways/from-course")
@require_user("student")
def create_from_course():
    course_id = integer(payload().get("course_id"), "Course ID")
    pathway, created = generate_course_pathway(g.user.user_id, course_id)
    db.session.commit()
    return {"pathway": pathway_detail(pathway), "created": created}, 201 if created else 200


@courses.post("/admin/courses")
@courses.put("/admin/courses/<int:course_id>")
@require_user("admin")
def save_course(course_id=None):
    course = get_course(integer(course_id, "Course ID"), lock="exclusive") if course_id else Course()
    data = payload()
    course.name = string(data.get("name"), "Course name", 150)
    course.subject = string(data.get("subject"), "Subject", 100)
    course.description = string(data.get("description"), "Description", 6000)
    course.difficulty_level = string(data.get("difficulty_level"), "Difficulty", 30)
    if course.difficulty_level not in {"Beginner", "Intermediate", "Advanced"}:
        raise APIError(400, "Choose a supported course difficulty.")
    objectives = data.get("objectives")
    if not isinstance(objectives, list) or not 1 <= len(objectives) <= 12:
        raise APIError(400, "Provide between 1 and 12 learning objectives.")
    course.objectives = [string(value, "Objective", 255) for value in objectives]
    syllabus = data.get("syllabus")
    if not isinstance(syllabus, list) or not 1 <= len(syllabus) <= 100 or any(not isinstance(item, dict) for item in syllabus):
        raise APIError(400, "Provide between 1 and 100 syllabus entries.")
    entries = [
        CourseTopic(
            topic_id=integer(item.get("topic_id"), "Topic ID"), sequence_no=index,
            module=string(item.get("module"), "Module", 100),
            estimated_hours=integer(item.get("estimated_hours"), "Study hours", maximum=100),
        )
        for index, item in enumerate(syllabus, 1)
    ]
    if len({entry.topic_id for entry in entries}) != len(entries):
        raise APIError(400, "Each topic may appear in a course once.")
    try:
        db.session.add(course)
        db.session.flush()
        for entry in entries:
            entry.course_id = course.course_id
        replace_syllabus(course, entries)
        db.session.commit()
    except IntegrityError as error:
        if error.orig.args[0] == 1062:
            raise APIError(409, "A course with that name already exists.") from error
        raise
    return {"course_id": course.course_id}, 200 if course_id else 201
