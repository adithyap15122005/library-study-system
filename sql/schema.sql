-- Folio reference schema for a fresh MySQL 8.0.16+ database.

-- Select the target database before running this script.

-- For application upgrades, use the Alembic migrations instead.

SET NAMES utf8mb4;

CREATE TABLE books (
	book_id INTEGER NOT NULL AUTO_INCREMENT,
	title VARCHAR(255) NOT NULL,
	author VARCHAR(255) NOT NULL,
	publisher VARCHAR(255),
	isbn VARCHAR(20),
	category VARCHAR(100),
	description TEXT NOT NULL,
	total_copies INTEGER NOT NULL,
	available_copies INTEGER NOT NULL,
	cover_url VARCHAR(1000),
	CONSTRAINT pk_books PRIMARY KEY (book_id),
	CONSTRAINT ck_books_total_nonnegative CHECK (total_copies >= 0),
	CONSTRAINT ck_books_available_range CHECK (available_copies BETWEEN 0 AND total_copies),
	CONSTRAINT uq_books_isbn UNIQUE (isbn)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE FULLTEXT INDEX ft_books_text ON books (title, author, category, description);

CREATE INDEX ix_books_available ON books (available_copies);

CREATE INDEX ix_books_catalog_category ON books (category, title, book_id);

CREATE TABLE topics (
	topic_id INTEGER NOT NULL AUTO_INCREMENT,
	name VARCHAR(150) NOT NULL,
	description TEXT NOT NULL,
	subject VARCHAR(100) NOT NULL,
	difficulty_level VARCHAR(30) NOT NULL,
	CONSTRAINT pk_topics PRIMARY KEY (topic_id),
	CONSTRAINT uq_topics_name_subject UNIQUE (name, subject),
	CONSTRAINT ck_topics_difficulty CHECK (difficulty_level IN ('Beginner', 'Intermediate', 'Advanced'))
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX ix_topics_subject ON topics (subject);

CREATE TABLE users (
	user_id INTEGER NOT NULL AUTO_INCREMENT,
	name VARCHAR(120) NOT NULL,
	email VARCHAR(255) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	`role` VARCHAR(20) NOT NULL DEFAULT 'student',
	date_of_joining DATETIME(6) NOT NULL,
	interests JSON,
	CONSTRAINT pk_users PRIMARY KEY (user_id),
	CONSTRAINT ck_users_role CHECK (role IN ('student', 'admin')),
	CONSTRAINT uq_users_email UNIQUE (email)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE book_topic (
	book_id INTEGER NOT NULL,
	topic_id INTEGER NOT NULL,
	CONSTRAINT pk_book_topic PRIMARY KEY (book_id, topic_id),
	CONSTRAINT fk_book_topic_book_id_books FOREIGN KEY(book_id) REFERENCES books (book_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
	CONSTRAINT fk_book_topic_topic_id_topics FOREIGN KEY(topic_id) REFERENCES topics (topic_id) ON DELETE RESTRICT ON UPDATE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX ix_book_topic_topic ON book_topic (topic_id, book_id);

CREATE TABLE borrow (
	borrow_id INTEGER NOT NULL AUTO_INCREMENT,
	user_id INTEGER NOT NULL,
	book_id INTEGER NOT NULL,
	issue_date DATETIME(6) NOT NULL,
	due_date DATETIME(6) NOT NULL,
	return_date DATETIME(6),
	status VARCHAR(20) NOT NULL DEFAULT 'issued',
	CONSTRAINT pk_borrow PRIMARY KEY (borrow_id),
	CONSTRAINT ck_borrow_due_after_issue CHECK (due_date > issue_date),
	CONSTRAINT ck_borrow_status_return_date CHECK ((status = 'issued' AND return_date IS NULL) OR (status = 'returned' AND return_date IS NOT NULL AND return_date >= issue_date)),
	CONSTRAINT fk_borrow_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
	CONSTRAINT fk_borrow_book_id_books FOREIGN KEY(book_id) REFERENCES books (book_id) ON DELETE RESTRICT ON UPDATE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX ix_borrow_book_status ON borrow (book_id, status, user_id);

CREATE INDEX ix_borrow_status_due ON borrow (status, due_date);

CREATE INDEX ix_borrow_user_history ON borrow (user_id, issue_date, borrow_id);

CREATE TABLE recommendation (
	rec_id INTEGER NOT NULL AUTO_INCREMENT,
	user_id INTEGER NOT NULL,
	topic_id INTEGER,
	book_id INTEGER NOT NULL,
	score NUMERIC(8, 7) NOT NULL,
	model_type VARCHAR(100) NOT NULL,
	generated_at DATETIME(6) NOT NULL,
	reason TEXT NOT NULL,
	CONSTRAINT pk_recommendation PRIMARY KEY (rec_id),
	CONSTRAINT ck_recommendation_score_range CHECK (score BETWEEN 0 AND 1),
	CONSTRAINT fk_recommendation_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
	CONSTRAINT fk_recommendation_topic_id_topics FOREIGN KEY(topic_id) REFERENCES topics (topic_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
	CONSTRAINT fk_recommendation_book_id_books FOREIGN KEY(book_id) REFERENCES books (book_id) ON DELETE RESTRICT ON UPDATE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX ix_recommendation_user_topic_batch ON recommendation (user_id, topic_id, generated_at);

CREATE TABLE review (
	review_id INTEGER NOT NULL AUTO_INCREMENT,
	user_id INTEGER NOT NULL,
	book_id INTEGER NOT NULL,
	review_text TEXT NOT NULL,
	rating INTEGER NOT NULL,
	timestamp DATETIME(6) NOT NULL,
	CONSTRAINT pk_review PRIMARY KEY (review_id),
	CONSTRAINT uq_review_user_book UNIQUE (user_id, book_id),
	CONSTRAINT ck_review_rating_range CHECK (rating BETWEEN 1 AND 5),
	CONSTRAINT fk_review_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
	CONSTRAINT fk_review_book_id_books FOREIGN KEY(book_id) REFERENCES books (book_id) ON DELETE RESTRICT ON UPDATE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX ix_review_book_timestamp ON review (book_id, timestamp);

CREATE TABLE study_pathway (
	pathway_id INTEGER NOT NULL AUTO_INCREMENT,
	user_id INTEGER NOT NULL,
	name VARCHAR(200) NOT NULL,
	description TEXT NOT NULL,
	target_goal VARCHAR(255) NOT NULL,
	created_at DATETIME(6) NOT NULL,
	status VARCHAR(30) NOT NULL DEFAULT 'active',
	CONSTRAINT pk_study_pathway PRIMARY KEY (pathway_id),
	CONSTRAINT uq_study_pathway_id_user UNIQUE (pathway_id, user_id),
	CONSTRAINT ck_study_pathway_status CHECK (status IN ('active', 'completed')),
	CONSTRAINT fk_study_pathway_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX ix_study_pathway_user_status ON study_pathway (user_id, status);

CREATE TABLE topic_prerequisite (
	prerequisite_topic_id INTEGER NOT NULL,
	dependent_topic_id INTEGER NOT NULL,
	CONSTRAINT pk_topic_prerequisite PRIMARY KEY (prerequisite_topic_id, dependent_topic_id),
	CONSTRAINT ck_topic_prerequisite_distinct_topics CHECK (prerequisite_topic_id <> dependent_topic_id),
	CONSTRAINT fk_topic_prerequisite_prerequisite_topic_id_topics FOREIGN KEY(prerequisite_topic_id) REFERENCES topics (topic_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
	CONSTRAINT fk_topic_prerequisite_dependent_topic_id_topics FOREIGN KEY(dependent_topic_id) REFERENCES topics (topic_id) ON DELETE RESTRICT ON UPDATE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX ix_topic_prerequisite_dependent ON topic_prerequisite (dependent_topic_id, prerequisite_topic_id);

CREATE TABLE pathway_topic (
	pathway_topic_id INTEGER NOT NULL AUTO_INCREMENT,
	pathway_id INTEGER NOT NULL,
	topic_id INTEGER NOT NULL,
	sequence_no INTEGER NOT NULL,
	is_completed BOOL NOT NULL DEFAULT 0,
	completed_at DATETIME(6),
	CONSTRAINT pk_pathway_topic PRIMARY KEY (pathway_topic_id),
	CONSTRAINT uq_pathway_topic_topic UNIQUE (pathway_id, topic_id),
	CONSTRAINT uq_pathway_topic_sequence UNIQUE (pathway_id, sequence_no),
	CONSTRAINT uq_pathway_topic_id UNIQUE (pathway_id, pathway_topic_id),
	CONSTRAINT ck_pathway_topic_positive_sequence CHECK (sequence_no >= 1),
	CONSTRAINT ck_pathway_topic_completion_date CHECK ((is_completed = 0 AND completed_at IS NULL) OR (is_completed = 1 AND completed_at IS NOT NULL)),
	CONSTRAINT fk_pathway_topic_pathway_id_study_pathway FOREIGN KEY(pathway_id) REFERENCES study_pathway (pathway_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
	CONSTRAINT fk_pathway_topic_topic_id_topics FOREIGN KEY(topic_id) REFERENCES topics (topic_id) ON DELETE RESTRICT ON UPDATE RESTRICT
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE progress_ledger (
	ledger_id BIGINT NOT NULL AUTO_INCREMENT,
	user_id INTEGER NOT NULL,
	pathway_id INTEGER NOT NULL,
	pathway_topic_id INTEGER NOT NULL,
	event_type VARCHAR(30) NOT NULL DEFAULT 'COMPLETE',
	event_time DATETIME(6) NOT NULL,
	previous_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
	entry_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
	hash_version VARCHAR(20) NOT NULL,
	CONSTRAINT pk_progress_ledger PRIMARY KEY (ledger_id),
	CONSTRAINT fk_progress_ledger_pathway_owner FOREIGN KEY(pathway_id, user_id) REFERENCES study_pathway (pathway_id, user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
	CONSTRAINT fk_progress_ledger_pathway_step FOREIGN KEY(pathway_id, pathway_topic_id) REFERENCES pathway_topic (pathway_id, pathway_topic_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
	CONSTRAINT ck_progress_ledger_event_type CHECK (event_type = 'COMPLETE'),
	CONSTRAINT fk_progress_ledger_user_id_users FOREIGN KEY(user_id) REFERENCES users (user_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
	CONSTRAINT uq_progress_ledger_pathway_topic_id UNIQUE (pathway_topic_id)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE INDEX ix_progress_ledger_pathway_order ON progress_ledger (pathway_id, ledger_id);

CREATE SQL SECURITY INVOKER VIEW v_current_borrowing AS
SELECT br.borrow_id, br.user_id, br.book_id, bk.title, br.issue_date, br.due_date,
       CASE WHEN br.due_date < UTC_TIMESTAMP(6) THEN 'overdue' ELSE 'issued' END AS current_status
FROM borrow AS br
JOIN books AS bk ON bk.book_id = br.book_id
WHERE br.status = 'issued';

CREATE SQL SECURITY INVOKER VIEW v_pathway_progress AS
SELECT sp.pathway_id, sp.user_id, sp.name, sp.status,
       COUNT(pt.pathway_topic_id) AS total_steps,
       COUNT(CASE WHEN pt.is_completed = 1 THEN 1 END) AS completed_steps,
       COALESCE(ROUND(100 * COUNT(CASE WHEN pt.is_completed = 1 THEN 1 END)
                          / NULLIF(COUNT(pt.pathway_topic_id), 0), 1), 0) AS progress_percent
FROM study_pathway AS sp
LEFT JOIN pathway_topic AS pt ON pt.pathway_id = sp.pathway_id
GROUP BY sp.pathway_id, sp.user_id, sp.name, sp.status;

-- Running upgrade 0001_folio -> 0002_courses

ALTER TABLE books ADD COLUMN edition VARCHAR(255);

ALTER TABLE books ADD COLUMN source_url VARCHAR(1000);

ALTER TABLE books ADD COLUMN is_archived BOOL NOT NULL DEFAULT 0;

UPDATE books SET is_archived = 1
        WHERE isbn REGEXP '^9780000000[0-9]{3}$'
          AND publisher IN ('Meridian Academic', 'Northbridge Technical Press', 'Lab Manual Collective');

CREATE TABLE courses (
    course_id INTEGER NOT NULL AUTO_INCREMENT,
    name VARCHAR(150) NOT NULL,
    subject VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    difficulty_level VARCHAR(30) NOT NULL,
    objectives JSON NOT NULL,
    CONSTRAINT pk_courses PRIMARY KEY (course_id),
    CONSTRAINT uq_courses_name UNIQUE (name),
    CONSTRAINT ck_courses_ck_courses_difficulty CHECK (difficulty_level IN ('Beginner', 'Intermediate', 'Advanced'))
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE course_topic (
    course_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    module VARCHAR(100) NOT NULL,
    sequence_no INTEGER NOT NULL,
    estimated_hours INTEGER NOT NULL,
    CONSTRAINT pk_course_topic PRIMARY KEY (course_id, topic_id),
    CONSTRAINT fk_course_topic_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (course_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_course_topic_topic_id_topics FOREIGN KEY(topic_id) REFERENCES topics (topic_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT uq_course_topic_sequence UNIQUE (course_id, sequence_no),
    CONSTRAINT ck_course_topic_ck_course_topic_positive_values CHECK (sequence_no > 0 AND estimated_hours > 0)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_0900_ai_ci;

ALTER TABLE study_pathway ADD COLUMN course_id INTEGER;

ALTER TABLE study_pathway ADD CONSTRAINT fk_study_pathway_course_id_courses FOREIGN KEY(course_id) REFERENCES courses (course_id) ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE study_pathway ADD CONSTRAINT uq_study_pathway_user_course UNIQUE (user_id, course_id);

ALTER TABLE pathway_topic ADD COLUMN module VARCHAR(100);

ALTER TABLE pathway_topic ADD COLUMN estimated_hours INTEGER;

ALTER TABLE book_topic ADD COLUMN is_featured BOOL NOT NULL DEFAULT 0;
