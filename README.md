# Library Recommendation and Study Pathway System

**Folio** is a digital library and study planner for the CD252IA Database Management System Lab at RV College of Engineering, Department of Computer Science and Engineering (Artificial Intelligence and Machine Learning).

**Project team** · Abhinav Vats, Adithya P, Dhruv Kumar

A library needs consistent stock counts during simultaneous checkouts. Students also need a way to discover useful books and work through connected subjects in order. Folio addresses these needs with transactional borrowing, personalized book rankings, prerequisite-aware learning plans, and a verifiable history of topic completions. An administrator can maintain the catalog and inventory, manage the topic graph, and inspect database-backed reports.

## Requirements

- A development laptop with a dual-core processor and approximately 4 GB of RAM.
- Python 3.11 or newer with `pip` and the `venv` module. The commands below use Python 3.13 on Windows.
- MySQL 8.0.16 or newer with InnoDB and an account that can migrate the project schema. Use MySQL 8.4 LTS for a new installation. [MySQL Windows installation guide](https://dev.mysql.com/doc/refman/8.4/en/windows-installation.html)
- A modern browser. Text recommendations run locally on the CPU.

The stack is Flask, HTML5, CSS3, vanilla JavaScript, SQLAlchemy, Flask-SQLAlchemy, Flask-Migrate/Alembic, PyMySQL, scikit-learn, Werkzeug password hashing, Python `hmac` and `hashlib`, python-dotenv, and pytest.

## Windows setup

Open PowerShell in the project directory and install dependencies in a virtual environment.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Start your configured MySQL server. Open a MySQL session with an account authorized to create schemas and users. If the `mysql` command is unavailable on your `PATH`, use the full path to `mysql.exe` in your server's `bin` folder.

```powershell
mysql -h 127.0.0.1 -P 3306 -u root -p
```

For a fresh local installation, create an application database and a separate test database. Replace the user, host, and password as appropriate for your installation. `ALL PRIVILEGES` here applies only to the two named development schemas so the migration and test commands can manage tables and views.

```sql
CREATE DATABASE library_study CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE library_study_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'library_user'@'127.0.0.1' IDENTIFIED BY 'replace_with_your_local_db_password';
GRANT ALL PRIVILEGES ON library_study.* TO 'library_user'@'127.0.0.1';
GRANT ALL PRIVILEGES ON library_study_test.* TO 'library_user'@'127.0.0.1';
```

Edit `.env` and generate two independent random secrets.

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32)); print(secrets.token_hex(32))"
notepad .env
```

| Variable | Value |
|---|---|
| `DATABASE_URL` | `mysql+pymysql://USER:PASSWORD@HOST:PORT/library_study?charset=utf8mb4` with your connection details. Percent-encode URL-reserved characters in the credentials. |
| `TEST_DATABASE_URL` | Same format, pointing to the disposable `library_study_test` schema. Integration tests rebuild its project tables. |
| `SECRET_KEY` | First generated secret, used to sign Flask session cookies. |
| `LEDGER_SECRET` | Second generated secret, used to sign the progress ledger. Preserve it with any database backup you intend to verify. |
| `BORROW_DAYS` | Number of days before new loans are due. Defaults to `14`. |
| `SESSION_COOKIE_SECURE` | Keep `0` for loopback HTTP. Use `1` when serving through HTTPS. |
| `DEMO_PASSWORD`, `DEMO_ADMIN_PASSWORD` | Set development passwords of 8–128 characters before running the optional seed script. |

Apply migrations, seed the development schema, and start the Flask server.

```powershell
.\.venv\Scripts\python.exe -m flask --app run.py db upgrade
.\.venv\Scripts\python.exe -m scripts.seed_data
.\.venv\Scripts\python.exe run.py
```

Open Folio at [http://127.0.0.1:5000](http://127.0.0.1:5000).

The seed script creates 60 sample books with original catalog descriptions, 29 topics, four pathways, reviews, issued and returned loans, and genuine recommendation and ledger records. It can be rerun against the demo schema. Existing records keep their saved progress, credentials, and inventory. Sample catalog titles, authors, imprints, and ISBNs are fictional fixtures.

| Development account | Email | Password configured in `.env` |
|---|---|---|
| Maya Rao | `maya@example.test` | `DEMO_PASSWORD` |
| Adil Menon | `adil@example.test` | `DEMO_PASSWORD` |
| Leena Shah | `leena@example.test` | `DEMO_PASSWORD` |
| Library administrator | `admin@example.test` | `DEMO_ADMIN_PASSWORD` |

## Database architecture

Models and foreign keys live in `app/models.py`, with migrations in `migrations/`. The schema preserves the original ten entities and adds `recommendation.book_id` to reference the actual recommended book and `progress_ledger` to capture signed completions. `sql/schema.sql` is the inspectable MySQL DDL for the current schema. Flask installations use Alembic to create and version the schema.

```mermaid
erDiagram
    users ||--o{ borrow : checks_out
    books ||--o{ borrow : records
    users ||--o{ review : writes
    books ||--o{ review : receives
    users ||--o{ recommendation : receives
    books ||--o{ recommendation : appears_in
    topics |o--o{ recommendation : contextualizes
    users ||--o{ study_pathway : owns
    study_pathway ||--|{ pathway_topic : orders
    topics ||--o{ pathway_topic : appears_in
    books ||--o{ book_topic : covers
    topics ||--o{ book_topic : maps_to
    topics ||--o{ topic_prerequisite : is_required
    topics ||--o{ topic_prerequisite : depends
    users ||--o{ progress_ledger : completes
    study_pathway ||--o{ progress_ledger : records
    pathway_topic ||--o| progress_ledger : signs
```

### Relational mapping

| Table | Primary key | Foreign keys and unique constraints | Other attributes |
|---|---|---|---|
| `users` | `user_id` | Unique `email` | `name`, `password_hash`, `role`, `date_of_joining`, `interests` |
| `books` | `book_id` | Unique `isbn` when present | `title`, `author`, `publisher`, `category`, `description`, `total_copies`, `available_copies`, `cover_url` |
| `borrow` | `borrow_id` | `user_id` → `users`, `book_id` → `books` | `issue_date`, `due_date`, `return_date`, `status` |
| `review` | `review_id` | `user_id` → `users`, `book_id` → `books`, unique `(user_id, book_id)` | `review_text`, `rating`, `timestamp` |
| `topics` | `topic_id` | Unique `(name, subject)` | `name`, `subject`, `description`, `difficulty_level` |
| `book_topic` | `(book_id, topic_id)` | `book_id` → `books`, `topic_id` → `topics` | — |
| `topic_prerequisite` | `(prerequisite_topic_id, dependent_topic_id)` | Both topic IDs → `topics` | — |
| `recommendation` | `rec_id` | `user_id` → `users`, `book_id` → `books`, nullable `topic_id` → `topics` | `score`, `model_type`, `generated_at`, `reason` |
| `study_pathway` | `pathway_id` | `user_id` → `users`, unique `(pathway_id, user_id)` for ledger ownership | `name`, `description`, `target_goal`, `created_at`, `status` |
| `pathway_topic` | `pathway_topic_id` | `pathway_id` → `study_pathway`, `topic_id` → `topics`, unique `(pathway_id, topic_id)`, `(pathway_id, sequence_no)`, `(pathway_id, pathway_topic_id)` | `sequence_no`, `is_completed`, `completed_at` |
| `progress_ledger` | `ledger_id` | `user_id` → `users`, `(pathway_id, user_id)` → `study_pathway`, `(pathway_id, pathway_topic_id)` → `pathway_topic`, unique `pathway_topic_id` | `event_type`, `event_time`, `previous_hash`, `entry_hash`, `hash_version` |

Independent entities and junction tables keep most data in third normal form. Interests are a JSON list of user-selected keywords. `available_copies` is controlled derived data equal to `total_copies` minus currently issued copies. Issue and return operations lock the book row before changing a loan and stock together. The issue operation permits one active checkout per student and book to prevent duplicate submissions. Inventory edits use the same book lock and reject totals below current issues. InnoDB commits both changes or rolls both back. `overdue` is computed from an active loan's due date. All database timestamps represent UTC.

Check constraints enforce stock bounds, valid ratings, issue/return state, valid difficulty levels, and completion timestamps. Restrictive foreign keys preserve borrowing and progress history. Composite ledger foreign keys also enforce owner and step consistency. Catalog search uses a MySQL FULLTEXT index plus parameterized matching for substrings and topic names. Composite indexes support history, active loans by due date, topic lookups, and ordered ledger retrieval.

### SQL lab reports

From the project directory, connect to `library_study` with the configured account and run the query file inside MySQL. Adjust the host, port, and schema as needed.

```powershell
mysql -h 127.0.0.1 -P 3306 -u library_user -p library_study
```

```sql
SOURCE sql/queries.sql;
SELECT * FROM v_current_borrowing;
SELECT * FROM v_pathway_progress;
```

The 12 reports include loan history, overdue items, books never borrowed, review aggregates, topic coverage, ranked books, and pathway completion. An inventory reconciliation should return zero rows. The two `EXPLAIN` examples let you compare candidate and selected indexes, row estimates, and sorting. MySQL may prefer a scan for the small seed dataset. [MySQL EXPLAIN guide](https://dev.mysql.com/doc/refman/8.4/en/using-explain.html)

## Ranking, learning, and verification

### Content-based recommendations

`tfidf_cosine_v1` rebuilds its sparse vocabulary when recommendations are generated. It fits TF-IDF on each title, description, mapped topic names, and category using word unigrams and bigrams. Book vectors can also include a 5% contribution from up to two review excerpts in the existing catalog vocabulary. The profile uses interests, topics in active pathways, and positively reviewed books where enough history exists. A selected focus topic supplies its own independent profile.

The saved score is `0.80 × cosine similarity + 0.20 × topic relevance`. Topic relevance is the strongest mapped-topic match. A preferred topic ID has a relevance of 1. Otherwise, relevance is the fraction of the topic name's analyzed terms also found in the student's interests. A 6% sorting penalty for unavailable books leaves the saved similarity unchanged. Each reason names matching topics or terms from the catalog. If there is no profile or positive match, the app explicitly shows deterministic catalog suggestions with zero scores. MySQL stores the most recent ranking per student and topic context, including a general context.

### Prerequisite-aware pathways

Prerequisite edges point from required topic to dependent topic. Adding an edge checks for cycles and protects existing pathway order. During creation the service finds all transitive prerequisites. A missing-topic response lets students explicitly include them on retry. Topological sorting produces a stable sequence. The completion endpoint checks student ownership, direct prerequisites in the same pathway, and every earlier step before writing progress.

### Hash-linked progress

Each `COMPLETE` event and its pathway step update commit together. The first event's previous hash is 64 zeroes. Later events link to the preceding entry in that pathway. `hmac-sha256-v1` signs compact JSON with sorted keys containing `user_id`, `pathway_id`, `pathway_topic_id`, `event_type`, `event_time`, `previous_hash`, and `hash_version`. The UTC timestamp has six fractional digits and a `Z` suffix. The secret lives outside MySQL.

Verification reads events in ledger ID order, recomputes each HMAC, checks links, and requires a contiguous prefix of completed steps with matching timestamps and overall pathway status. Ledger IDs may skip values when events from multiple pathways are interleaved. A verification error identifies the first invalid entry or missing step when applicable.

The trust model is a centralized, append-only audit history through the application. The ledger provides tamper evidence as long as the signing secret remains private and the verifier is trusted. An actor controlling the database, application, and signing secret can rewrite history. Detecting a coherent rollback of a valid chain tail requires an independent record of the latest trusted hash.

## API

`GET /api/session` returns a CSRF token and the current user, if present. Keep the returned Flask session cookie and send `X-CSRF-Token` with each mutation, including registration and sign-in. When the session changes, use the token returned by the new session. API errors carry an `error` message and may include `details` for required prerequisites or other recoverable issues.

| Area | Routes |
|---|---|
| Account | `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET/PATCH /api/me` |
| Dashboard | `GET /api/dashboard` |
| Catalog | `GET /api/books`, `GET /api/books/{book_id}` |
| Reviews | `GET/POST /api/books/{book_id}/reviews`, `PUT /api/books/{book_id}/reviews/me` |
| Borrowing | `POST /api/borrows`, `GET /api/borrows/me`, `POST /api/borrows/{borrow_id}/return` |
| Topics | `GET /api/topics`, `GET /api/topics/{topic_id}`, `GET /api/topics/{topic_id}/prerequisites` |
| Book recommendations | `POST /api/recommendations/generate`, `GET /api/recommendations/me` |
| Pathways | `POST /api/pathways`, `GET /api/pathways/me`, `GET /api/pathways/{pathway_id}`, `GET /api/pathways/{pathway_id}/topics` |
| Completion and verification | `POST /api/pathway-topics/{pathway_topic_id}/complete`, `GET /api/pathways/{pathway_id}/ledger`, `GET /api/pathways/{pathway_id}/ledger/verify` |
| Admin catalog | `POST /api/admin/books`, `PUT /api/admin/books/{book_id}`, `PUT /api/admin/books/{book_id}/inventory`, `PUT /api/admin/books/{book_id}/topics` |
| Admin topics | `POST /api/admin/topics`, `PUT /api/admin/topics/{topic_id}`, `POST /api/admin/prerequisites`, `DELETE /api/admin/prerequisites/{prerequisite_id}/{dependent_id}` |
| Admin reports | `GET /api/admin/stats`, `GET /api/admin/borrows` |

Get the exact HTTP method and path for each route from Flask.

```powershell
.\.venv\Scripts\python.exe -m flask --app run.py routes
```

## Automated tests

Ensure `TEST_DATABASE_URL` points to the separate disposable MySQL schema created above and run pytest from the project root. Tests exercise real MySQL row locking, rollback, foreign keys, and persistence. The suite includes controlled progress-record tampering and service failure cases.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Classroom demonstration

1. Register a new student, sign out, and sign in again. Open the profile and add Python and Machine Learning interests.
2. Search the catalog for **Python Patterns for First Programs**. Issue a copy, check the change in availability, and open **My Borrowings** to confirm the due date. Return it and verify that history retains the returned record.
3. Generate recommendations, inspect the model scores and explanation, and compare them after changing interests or choosing a new focus topic.
4. Create a pathway with **Supervised Learning**. First request only that topic to see the list of missing prerequisites, then allow Folio to include them. Inspect the order and why later steps are locked.
5. Complete the first eligible step and open **Verify Progress**. Inspect its completion timestamp, previous hash, and verified status. Complete the next step to see the new link.
6. Sign in as Maya to inspect the seeded overdue loan and partially completed **Machine Learning Foundations** pathway. Adil's **SQL Reporting Essentials** is a completed example.
7. Sign in as the administrator to inspect stock, borrowing records, and progress. Edit a book, link a topic, and add a valid prerequisite relationship. Try an administrator route while signed in as a student to verify backend authorization.
8. Restart Flask and sign in again to verify persistent loans and pathways. Run pytest on the separate schema to observe that a changed ledger field or broken link fails verification.

## Feature verification checklist

- [x] Flask starts and seeded demo records load from MySQL 8.4.8.
- [x] Migrations create the eleven InnoDB project tables, 17 foreign keys, 13 check constraints, and two report views. All 12 SQL reports and both `EXPLAIN` queries execute. Inventory reconciliation returns zero discrepancies.
- [x] Registration, login, profile editing, and role checks work.
- [x] Catalog search, filters, details, and review summaries reflect stored records.
- [x] Checkout and return adjust availability atomically and preserve history, including concurrent checkout of the last copy and rollback after a failed write.
- [x] Recommendations persist ranked book references with grounded explanations.
- [x] Pathways include prerequisite order and reject locked or unauthorized completions.
- [x] Completion and ledger events commit together. Verification detects altered event data, broken links, and missing events.
- [x] Chrome smoke checks reached all student and administrator screens, including mobile navigation and ledger verification after a Flask restart.
- [x] All 22 automated tests passed against a separate MySQL 8.4.8 schema.
