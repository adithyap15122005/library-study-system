-- MySQL 8 classroom reports. Select the migrated database before running these queries.
-- Change the values below to inspect a different student, topic, or pathway.
SET @student_email = 'maya@example.test';
SET @topic_name = 'Machine Learning Fundamentals';
SET @pathway_name = 'Machine Learning Foundations';
SET @student_id = (SELECT user_id FROM users WHERE email = @student_email);
SET @topic_id = (SELECT topic_id FROM topics WHERE name = @topic_name ORDER BY topic_id LIMIT 1);
SET @pathway_id = (
    SELECT pathway_id FROM study_pathway
    WHERE user_id = @student_id AND name = @pathway_name ORDER BY pathway_id LIMIT 1
);

-- 1. Borrowing history. Derive overdue only for an active loan and keep every return.
SELECT loan.borrow_id, book.title, loan.issue_date, loan.due_date, loan.return_date,
       CASE WHEN loan.status = 'issued' AND loan.due_date < UTC_TIMESTAMP()
            THEN 'overdue' ELSE loan.status END AS current_status
FROM borrow AS loan
JOIN books AS book ON book.book_id = loan.book_id
WHERE loan.user_id = @student_id
ORDER BY loan.issue_date DESC, loan.borrow_id DESC;

-- 2. Books with inventory immediately available for issue.
SELECT book_id, title, author, category, available_copies, total_copies
FROM books
WHERE available_copies > 0
ORDER BY title, book_id;

-- 3. Active loans that have passed their due date, including the borrower and title.
SELECT loan.borrow_id, borrower.name AS borrower, book.title, loan.issue_date, loan.due_date
FROM borrow AS loan
JOIN users AS borrower ON borrower.user_id = loan.user_id
JOIN books AS book ON book.book_id = loan.book_id
WHERE loan.status = 'issued' AND loan.due_date < UTC_TIMESTAMP()
ORDER BY loan.due_date, loan.borrow_id;

-- 4. A correlated anti-join finds books without any historical borrowing row.
SELECT book.book_id, book.title, book.author
FROM books AS book
WHERE NOT EXISTS (SELECT 1 FROM borrow AS loan WHERE loan.book_id = book.book_id)
ORDER BY book.title, book.book_id;

-- 5. Rank books by lifetime checkout count. HAVING excludes books with no history.
SELECT book.book_id, book.title, COUNT(loan.borrow_id) AS checkout_count
FROM books AS book
LEFT JOIN borrow AS loan ON loan.book_id = book.book_id
GROUP BY book.book_id, book.title
HAVING COUNT(loan.borrow_id) > 0
ORDER BY checkout_count DESC, book.title, book.book_id
LIMIT 10;

-- 6. LEFT JOIN retains books with no reviews, whose average remains NULL.
SELECT book.book_id, book.title, COUNT(review.review_id) AS review_count,
       ROUND(AVG(review.rating), 2) AS average_rating
FROM books AS book
LEFT JOIN review ON review.book_id = book.book_id
GROUP BY book.book_id, book.title
ORDER BY book.title, book.book_id;

-- 7. Traverse the book-topic junction to retrieve actual titles for a topic.
SELECT topic.name AS topic, book.book_id, book.title, book.author, book.available_copies
FROM book_topic AS coverage
JOIN topics AS topic ON topic.topic_id = coverage.topic_id
JOIN books AS book ON book.book_id = coverage.book_id
WHERE coverage.topic_id = @topic_id
ORDER BY book.title, book.book_id;

-- 8. A recommendation always identifies a book. Topic context is optional.
SELECT rec.rec_id, book.title, book.author, topic.name AS context_topic, rec.score,
       rec.model_type, rec.generated_at, rec.reason, book.available_copies
FROM recommendation AS rec
JOIN books AS book ON book.book_id = rec.book_id
LEFT JOIN topics AS topic ON topic.topic_id = rec.topic_id
WHERE rec.user_id = @student_id
ORDER BY rec.generated_at DESC, rec.score DESC, rec.rec_id;

-- 9. Remaining steps of one owned pathway, using the stored learning order.
SELECT step.sequence_no, topic.name, topic.difficulty_level
FROM study_pathway AS pathway
JOIN pathway_topic AS step ON step.pathway_id = pathway.pathway_id
JOIN topics AS topic ON topic.topic_id = step.topic_id
WHERE pathway.pathway_id = @pathway_id AND pathway.user_id = @student_id
  AND step.is_completed = FALSE
ORDER BY step.sequence_no;

-- 10. Find immediate prerequisites by joining the topic catalog to both ends of an edge.
SELECT dependent.name AS dependent_topic, required.name AS prerequisite_topic
FROM topic_prerequisite AS edge
JOIN topics AS dependent ON dependent.topic_id = edge.dependent_topic_id
JOIN topics AS required ON required.topic_id = edge.prerequisite_topic_id
WHERE edge.dependent_topic_id = @topic_id
ORDER BY required.name, required.topic_id;

-- 11. Compute progress from actual step rows. An empty pathway has zero percent.
SELECT pathway.pathway_id, pathway.name, pathway.status,
       COUNT(step.pathway_topic_id) AS total_steps,
       COUNT(CASE WHEN step.is_completed THEN 1 END) AS completed_steps,
       COALESCE(ROUND(100.0 * COUNT(CASE WHEN step.is_completed THEN 1 END)
                      / NULLIF(COUNT(step.pathway_topic_id), 0), 1), 0) AS percent_complete
FROM study_pathway AS pathway
LEFT JOIN pathway_topic AS step ON step.pathway_id = pathway.pathway_id
WHERE pathway.user_id = @student_id
GROUP BY pathway.pathway_id, pathway.name, pathway.status
ORDER BY pathway.pathway_id;

-- 12. Retrieve signed events in permanent order and show their corresponding step state.
-- Flask performs digest verification using the application secret outside MySQL.
SELECT ledger.ledger_id, ledger.user_id, ledger.pathway_id, ledger.pathway_topic_id,
       step.sequence_no, topic.name, step.is_completed, step.completed_at,
       ledger.event_type, ledger.event_time, ledger.previous_hash, ledger.entry_hash, ledger.hash_version
FROM progress_ledger AS ledger
JOIN pathway_topic AS step ON step.pathway_topic_id = ledger.pathway_topic_id
JOIN topics AS topic ON topic.topic_id = step.topic_id
WHERE ledger.pathway_id = @pathway_id
ORDER BY ledger.ledger_id;

-- Inventory reconciliation. The expected result is zero rows.
SELECT book.book_id, book.title, book.available_copies, book.total_copies,
       COUNT(loan.borrow_id) AS issued_copies
FROM books AS book
LEFT JOIN borrow AS loan ON loan.book_id = book.book_id AND loan.status = 'issued'
GROUP BY book.book_id, book.title, book.available_copies, book.total_copies
HAVING book.available_copies + COUNT(loan.borrow_id) <> book.total_copies;

-- Inspect the candidate and selected indexes, estimated rows, and any extra sorting.
-- MySQL may choose a table scan on the small demo dataset. Compare plans as data grows.
EXPLAIN
SELECT borrow_id, book_id, due_date FROM borrow
WHERE status = 'issued' AND due_date < UTC_TIMESTAMP()
ORDER BY due_date;

EXPLAIN
SELECT ledger_id, entry_hash FROM progress_ledger
WHERE pathway_id = @pathway_id ORDER BY ledger_id;
