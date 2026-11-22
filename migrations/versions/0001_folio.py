"""Create the eleven Folio tables and two reporting views.

Revision ID: 0001_folio
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0001_folio"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'books',
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=False),
        sa.Column('publisher', sa.String(length=255), nullable=True),
        sa.Column('isbn', sa.String(length=20), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('total_copies', sa.Integer(), nullable=False),
        sa.Column('available_copies', sa.Integer(), nullable=False),
        sa.Column('cover_url', sa.String(length=1000), nullable=True),
        sa.CheckConstraint('available_copies BETWEEN 0 AND total_copies', name=op.f('ck_books_available_range')),
        sa.CheckConstraint('total_copies >= 0', name=op.f('ck_books_total_nonnegative')),
        sa.PrimaryKeyConstraint('book_id', name=op.f('pk_books')),
        sa.UniqueConstraint('isbn', name=op.f('uq_books_isbn')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_engine='InnoDB'
    )
    op.create_index('ft_books_text', 'books', ['title', 'author', 'category', 'description'], unique=False, mysql_prefix='FULLTEXT')
    op.create_index('ix_books_available', 'books', ['available_copies'], unique=False)
    op.create_index('ix_books_catalog_category', 'books', ['category', 'title', 'book_id'], unique=False)
    op.create_table(
        'topics',
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('subject', sa.String(length=100), nullable=False),
        sa.Column('difficulty_level', sa.String(length=30), nullable=False),
        sa.CheckConstraint("difficulty_level IN ('Beginner', 'Intermediate', 'Advanced')", name=op.f('ck_topics_difficulty')),
        sa.PrimaryKeyConstraint('topic_id', name=op.f('pk_topics')),
        sa.UniqueConstraint('name', 'subject', name='uq_topics_name_subject'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_engine='InnoDB'
    )
    op.create_index('ix_topics_subject', 'topics', ['subject'], unique=False)
    op.create_table(
        'users',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), server_default='student', nullable=False),
        sa.Column('date_of_joining', mysql.DATETIME(fsp=6), nullable=False),
        sa.Column('interests', sa.JSON(none_as_null=True), nullable=True),
        sa.CheckConstraint("role IN ('student', 'admin')", name=op.f('ck_users_role')),
        sa.PrimaryKeyConstraint('user_id', name=op.f('pk_users')),
        sa.UniqueConstraint('email', name=op.f('uq_users_email')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_engine='InnoDB'
    )
    op.create_table(
        'book_topic',
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['book_id'], ['books.book_id'], name=op.f('fk_book_topic_book_id_books'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.topic_id'], name=op.f('fk_book_topic_topic_id_topics'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('book_id', 'topic_id', name=op.f('pk_book_topic')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_engine='InnoDB'
    )
    op.create_index('ix_book_topic_topic', 'book_topic', ['topic_id', 'book_id'], unique=False)
    op.create_table(
        'borrow',
        sa.Column('borrow_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('issue_date', mysql.DATETIME(fsp=6), nullable=False),
        sa.Column('due_date', mysql.DATETIME(fsp=6), nullable=False),
        sa.Column('return_date', mysql.DATETIME(fsp=6), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='issued', nullable=False),
        sa.CheckConstraint("(status = 'issued' AND return_date IS NULL) OR (status = 'returned' AND return_date IS NOT NULL AND return_date >= issue_date)", name=op.f('ck_borrow_status_return_date')),
        sa.CheckConstraint('due_date > issue_date', name=op.f('ck_borrow_due_after_issue')),
        sa.ForeignKeyConstraint(['book_id'], ['books.book_id'], name=op.f('fk_borrow_book_id_books'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], name=op.f('fk_borrow_user_id_users'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('borrow_id', name=op.f('pk_borrow')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_engine='InnoDB'
    )
    op.create_index('ix_borrow_book_status', 'borrow', ['book_id', 'status', 'user_id'], unique=False)
    op.create_index('ix_borrow_status_due', 'borrow', ['status', 'due_date'], unique=False)
    op.create_index('ix_borrow_user_history', 'borrow', ['user_id', 'issue_date', 'borrow_id'], unique=False)
    op.create_table(
        'recommendation',
        sa.Column('rec_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=True),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Numeric(precision=8, scale=7), nullable=False),
        sa.Column('model_type', sa.String(length=100), nullable=False),
        sa.Column('generated_at', mysql.DATETIME(fsp=6), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.CheckConstraint('score BETWEEN 0 AND 1', name=op.f('ck_recommendation_score_range')),
        sa.ForeignKeyConstraint(['book_id'], ['books.book_id'], name=op.f('fk_recommendation_book_id_books'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.topic_id'], name=op.f('fk_recommendation_topic_id_topics'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], name=op.f('fk_recommendation_user_id_users'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('rec_id', name=op.f('pk_recommendation')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_engine='InnoDB'
    )
    op.create_index('ix_recommendation_user_topic_batch', 'recommendation', ['user_id', 'topic_id', 'generated_at'], unique=False)
    op.create_table(
        'review',
        sa.Column('review_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('review_text', sa.Text(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('timestamp', mysql.DATETIME(fsp=6), nullable=False),
        sa.CheckConstraint('rating BETWEEN 1 AND 5', name=op.f('ck_review_rating_range')),
        sa.ForeignKeyConstraint(['book_id'], ['books.book_id'], name=op.f('fk_review_book_id_books'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], name=op.f('fk_review_user_id_users'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('review_id', name=op.f('pk_review')),
        sa.UniqueConstraint('user_id', 'book_id', name='uq_review_user_book'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_engine='InnoDB'
    )
    op.create_index('ix_review_book_timestamp', 'review', ['book_id', 'timestamp'], unique=False)
    op.create_table(
        'study_pathway',
        sa.Column('pathway_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('target_goal', sa.String(length=255), nullable=False),
        sa.Column('created_at', mysql.DATETIME(fsp=6), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='active', nullable=False),
        sa.CheckConstraint("status IN ('active', 'completed')", name=op.f('ck_study_pathway_status')),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], name=op.f('fk_study_pathway_user_id_users'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('pathway_id', name=op.f('pk_study_pathway')),
        sa.UniqueConstraint('pathway_id', 'user_id', name='uq_study_pathway_id_user'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_engine='InnoDB'
    )
    op.create_index('ix_study_pathway_user_status', 'study_pathway', ['user_id', 'status'], unique=False)
    op.create_table(
        'topic_prerequisite',
        sa.Column('prerequisite_topic_id', sa.Integer(), nullable=False),
        sa.Column('dependent_topic_id', sa.Integer(), nullable=False),
        sa.CheckConstraint('prerequisite_topic_id <> dependent_topic_id', name=op.f('ck_topic_prerequisite_distinct_topics')),
        sa.ForeignKeyConstraint(['dependent_topic_id'], ['topics.topic_id'], name=op.f('fk_topic_prerequisite_dependent_topic_id_topics'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['prerequisite_topic_id'], ['topics.topic_id'], name=op.f('fk_topic_prerequisite_prerequisite_topic_id_topics'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('prerequisite_topic_id', 'dependent_topic_id', name=op.f('pk_topic_prerequisite')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_engine='InnoDB'
    )
    op.create_index('ix_topic_prerequisite_dependent', 'topic_prerequisite', ['dependent_topic_id', 'prerequisite_topic_id'], unique=False)
    op.create_table(
        'pathway_topic',
        sa.Column('pathway_topic_id', sa.Integer(), nullable=False),
        sa.Column('pathway_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('sequence_no', sa.Integer(), nullable=False),
        sa.Column('is_completed', sa.Boolean(), server_default=sa.text('0'), nullable=False),
        sa.Column('completed_at', mysql.DATETIME(fsp=6), nullable=True),
        sa.CheckConstraint('(is_completed = 0 AND completed_at IS NULL) OR (is_completed = 1 AND completed_at IS NOT NULL)', name=op.f('ck_pathway_topic_completion_date')),
        sa.CheckConstraint('sequence_no >= 1', name=op.f('ck_pathway_topic_positive_sequence')),
        sa.ForeignKeyConstraint(['pathway_id'], ['study_pathway.pathway_id'], name=op.f('fk_pathway_topic_pathway_id_study_pathway'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.topic_id'], name=op.f('fk_pathway_topic_topic_id_topics'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('pathway_topic_id', name=op.f('pk_pathway_topic')),
        sa.UniqueConstraint('pathway_id', 'pathway_topic_id', name='uq_pathway_topic_id'),
        sa.UniqueConstraint('pathway_id', 'sequence_no', name='uq_pathway_topic_sequence'),
        sa.UniqueConstraint('pathway_id', 'topic_id', name='uq_pathway_topic_topic'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_engine='InnoDB'
    )
    op.create_table(
        'progress_ledger',
        sa.Column('ledger_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('pathway_id', sa.Integer(), nullable=False),
        sa.Column('pathway_topic_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=30), server_default='COMPLETE', nullable=False),
        sa.Column('event_time', mysql.DATETIME(fsp=6), nullable=False),
        sa.Column('previous_hash', mysql.CHAR(charset='ascii', collation='ascii_bin', length=64), nullable=False),
        sa.Column('entry_hash', mysql.CHAR(charset='ascii', collation='ascii_bin', length=64), nullable=False),
        sa.Column('hash_version', sa.String(length=20), nullable=False),
        sa.CheckConstraint("event_type = 'COMPLETE'", name=op.f('ck_progress_ledger_event_type')),
        sa.ForeignKeyConstraint(['pathway_id', 'pathway_topic_id'], ['pathway_topic.pathway_id', 'pathway_topic.pathway_topic_id'], name='fk_progress_ledger_pathway_step', onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['pathway_id', 'user_id'], ['study_pathway.pathway_id', 'study_pathway.user_id'], name='fk_progress_ledger_pathway_owner', onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], name=op.f('fk_progress_ledger_user_id_users'), onupdate='RESTRICT', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('ledger_id', name=op.f('pk_progress_ledger')),
        sa.UniqueConstraint('pathway_topic_id', name=op.f('uq_progress_ledger_pathway_topic_id')),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_engine='InnoDB'
    )
    op.create_index('ix_progress_ledger_pathway_order', 'progress_ledger', ['pathway_id', 'ledger_id'], unique=False)
    op.execute("""
        CREATE SQL SECURITY INVOKER VIEW v_current_borrowing AS
        SELECT br.borrow_id, br.user_id, br.book_id, bk.title, br.issue_date, br.due_date,
               CASE WHEN br.due_date < UTC_TIMESTAMP(6) THEN 'overdue' ELSE 'issued' END AS current_status
        FROM borrow AS br
        JOIN books AS bk ON bk.book_id = br.book_id
        WHERE br.status = 'issued'
    """)
    op.execute("""
        CREATE SQL SECURITY INVOKER VIEW v_pathway_progress AS
        SELECT sp.pathway_id, sp.user_id, sp.name, sp.status,
               COUNT(pt.pathway_topic_id) AS total_steps,
               COUNT(CASE WHEN pt.is_completed = 1 THEN 1 END) AS completed_steps,
               COALESCE(ROUND(100 * COUNT(CASE WHEN pt.is_completed = 1 THEN 1 END)
                                  / NULLIF(COUNT(pt.pathway_topic_id), 0), 1), 0) AS progress_percent
        FROM study_pathway AS sp
        LEFT JOIN pathway_topic AS pt ON pt.pathway_id = sp.pathway_id
        GROUP BY sp.pathway_id, sp.user_id, sp.name, sp.status
    """)

def downgrade():
    op.execute('DROP VIEW v_pathway_progress')
    op.execute('DROP VIEW v_current_borrowing')
    op.drop_table('progress_ledger')
    op.drop_table('pathway_topic')
    op.drop_table('topic_prerequisite')
    op.drop_table('study_pathway')
    op.drop_table('review')
    op.drop_table('recommendation')
    op.drop_table('borrow')
    op.drop_table('book_topic')
    op.drop_table('users')
    op.drop_table('topics')
    op.drop_table('books')
