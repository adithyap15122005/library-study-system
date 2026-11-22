"""Add verified editions and normalized course curricula."""

from alembic import op
import sqlalchemy as sa

revision = "0002_courses"
down_revision = "0001_folio"
branch_labels = None
depends_on = None

MYSQL = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_0900_ai_ci"}


def upgrade():
    op.add_column("books", sa.Column("edition", sa.String(255)))
    op.add_column("books", sa.Column("source_url", sa.String(1000)))
    op.add_column("books", sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.execute("""
        UPDATE books SET is_archived = 1
        WHERE isbn REGEXP '^9780000000[0-9]{3}$'
          AND publisher IN ('Meridian Academic', 'Northbridge Technical Press', 'Lab Manual Collective')
    """)
    op.create_table(
        "courses",
        sa.Column("course_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("difficulty_level", sa.String(30), nullable=False),
        sa.Column("objectives", sa.JSON(), nullable=False),
        sa.UniqueConstraint("name", name="uq_courses_name"),
        sa.CheckConstraint("difficulty_level IN ('Beginner', 'Intermediate', 'Advanced')", name="ck_courses_difficulty"),
        **MYSQL,
    )
    op.create_table(
        "course_topic",
        sa.Column("course_id", sa.Integer(), primary_key=True),
        sa.Column("topic_id", sa.Integer(), primary_key=True),
        sa.Column("module", sa.String(100), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("estimated_hours", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.course_id"], name="fk_course_topic_course_id_courses",
                                ondelete="RESTRICT", onupdate="RESTRICT"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.topic_id"], name="fk_course_topic_topic_id_topics",
                                ondelete="RESTRICT", onupdate="RESTRICT"),
        sa.UniqueConstraint("course_id", "sequence_no", name="uq_course_topic_sequence"),
        sa.CheckConstraint("sequence_no > 0 AND estimated_hours > 0", name="ck_course_topic_positive_values"),
        **MYSQL,
    )
    op.add_column("study_pathway", sa.Column("course_id", sa.Integer()))
    op.create_foreign_key("fk_study_pathway_course_id_courses", "study_pathway", "courses", ["course_id"],
                          ["course_id"], ondelete="RESTRICT", onupdate="RESTRICT")
    op.create_unique_constraint("uq_study_pathway_user_course", "study_pathway", ["user_id", "course_id"])
    op.add_column("pathway_topic", sa.Column("module", sa.String(100)))
    op.add_column("pathway_topic", sa.Column("estimated_hours", sa.Integer()))


def downgrade():
    op.drop_column("pathway_topic", "estimated_hours")
    op.drop_column("pathway_topic", "module")
    op.drop_constraint("uq_study_pathway_user_course", "study_pathway", type_="unique")
    op.drop_constraint("fk_study_pathway_course_id_courses", "study_pathway", type_="foreignkey")
    op.drop_column("study_pathway", "course_id")
    op.drop_table("course_topic")
    op.drop_table("courses")
    for column in ("is_archived", "source_url", "edition"):
        op.drop_column("books", column)
