from collections import defaultdict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import selectinload

from app.api import APIError
from app.extensions import db
from app.models import Book, PathwayTopic, Recommendation, Review, StudyPathway, Topic, User, utcnow

MODEL_TYPE = "tfidf_cosine_v1"


def _recent_reviews():
    ranked = db.select(
        Review.book_id,
        db.func.left(Review.review_text, 300).label("text"),
        db.func.row_number()
        .over(
            partition_by=Review.book_id,
            order_by=(Review.rating.desc(), Review.timestamp.desc(), Review.review_id.desc()),
        )
        .label("position"),
    ).where(Review.rating >= 3, Review.review_text.is_not(None)).subquery()
    by_book = defaultdict(list)
    for book_id, review in db.session.execute(
        db.select(ranked.c.book_id, ranked.c.text).where(ranked.c.position <= 2).order_by(
            ranked.c.book_id, ranked.c.position
        )
    ):
        by_book[book_id].append(review)
    return by_book


def _preference_profile(user, focus_topic, books_by_id):
    if focus_topic is not None:
        return [focus_topic.name, focus_topic.description or "", focus_topic.subject or ""], [], {focus_topic.topic_id}

    selected_interests = user.interests if isinstance(user.interests, list) else []
    interests = [interest for interest in selected_interests if isinstance(interest, str) and interest.strip()]
    pathway_topic_ids = (
        db.select(PathwayTopic.topic_id)
        .join(StudyPathway, StudyPathway.pathway_id == PathwayTopic.pathway_id)
        .where(StudyPathway.user_id == user.user_id, StudyPathway.status == "active")
        .distinct()
        .order_by(PathwayTopic.topic_id)
        .limit(12)
        .subquery()
    )
    pathway_topics = list(db.session.scalars(
        db.select(Topic).join(pathway_topic_ids, pathway_topic_ids.c.topic_id == Topic.topic_id).order_by(Topic.topic_id)
    ))

    favorite_ids = list(db.session.scalars(
        db.select(Review.book_id)
        .where(Review.user_id == user.user_id, Review.rating >= 4)
        .order_by(Review.timestamp.desc(), Review.review_id.desc())
        .limit(5)
    ))
    favorites = [books_by_id[book_id] for book_id in favorite_ids if book_id in books_by_id]
    if len(favorites) < 2:
        favorites = []

    preferred_ids = {topic.topic_id for topic in pathway_topics}
    profile = [*interests, *interests, *(topic.name for topic in pathway_topics)]
    for book in favorites:
        profile.append(book.title)
        profile.extend(topic.name for topic in book.topics)
        preferred_ids.update(topic.topic_id for topic in book.topics)
    return profile, interests, preferred_ids


def _book_text(book):
    topic_names = " ".join(topic.name for topic in book.topics)
    return " ".join([book.title, book.description or "", topic_names, topic_names])


def _topic_score(book, analyze, interest_terms, preferred_ids):
    score = 0.0
    matched_names = []
    for topic in book.topics:
        terms = set(analyze(topic.name))
        match = 1.0 if topic.topic_id in preferred_ids else len(terms & interest_terms) / max(len(terms), 1)
        if match:
            score = max(score, match)
            matched_names.append(topic.name)
    return score, matched_names


def _reason(matched_topics, matched_features):
    if matched_topics:
        return f"Covers {', '.join(matched_topics[:3])}, matching topics in your learning profile."
    terms = ", ".join(f"“{term}”" for term in matched_features)
    return f"Its catalog content shares {terms} with your learning profile."


def _rank_books(books, profile, interests, preferred_ids, reviews, *, include_fallback):
    vectorizer = TfidfVectorizer(
        stop_words="english", strip_accents="unicode", ngram_range=(1, 2), max_features=12000
    )
    analyze = vectorizer.build_analyzer()
    interest_terms = set(analyze(" ".join(interests)))
    query_text = " ".join(profile)
    primary_texts = [_book_text(book) for book in books]
    content = [f"{text} {book.category or ''}" for book, text in zip(books, primary_texts)]
    has_query = bool(analyze(query_text))
    base_vectors = None
    if has_query and any(analyze(text) for text in content):
        base_vectors = vectorizer.fit_transform(content)
        primary_vectors = vectorizer.transform(primary_texts)
        review_vectors = vectorizer.transform([" ".join(reviews.get(book.book_id, ())) for book in books])
        query = vectorizer.transform([query_text])
        similarities = cosine_similarity(query, base_vectors + 0.05 * review_vectors)[0]
        features = vectorizer.get_feature_names_out()

    ranked = []
    for index, book in enumerate(books):
        relevance, matched_topics = _topic_score(book, analyze, interest_terms, preferred_ids)
        similarity = float(similarities[index]) if base_vectors is not None else 0.0
        matched_features = []
        if base_vectors is not None and not matched_topics:
            overlap = query.multiply(primary_vectors[index]).tocoo()
            strongest = sorted(zip(overlap.data, overlap.col), reverse=True)
            matched_features = [features[column] for _, column in strongest[:3]]
        if not matched_topics and not matched_features:
            continue

        score = round(min(1.0, max(0.0, 0.8 * similarity + 0.2 * relevance)), 6)
        if score <= 0:
            continue
        ranked.append((book, score, _reason(matched_topics, matched_features)))

    if ranked:
        return sorted(ranked, key=lambda result: (
            -result[1] * (1.0 if result[0].available_copies > 0 else 0.94),
            result[0].available_copies <= 0,
            result[0].title.casefold(),
            result[0].book_id,
        ))
    if not include_fallback:
        return []

    reason = (
        "Catalog suggestion. No books matched the current learning profile."
        if has_query else "Catalog suggestion to explore while your learning profile is empty."
    )
    ordered = sorted(books, key=lambda book: (book.available_copies <= 0, book.title.casefold(), book.book_id))
    return [(book, 0.0, reason) for book in ordered]


def rank_topic_books(books, topic_id, name, description):
    return [book for book, _, _ in _rank_books(
        books, [name, description], [name], {topic_id}, {}, include_fallback=False,
    )]


def generate_recommendations(user, topic_id=None, limit=8):
    # Keep a single, complete ranking per student and recommendation context.
    user = db.session.scalar(
        db.select(User).where(User.user_id == user.user_id).with_for_update().execution_options(populate_existing=True)
    )
    focus_topic = db.session.get(Topic, topic_id) if topic_id is not None else None
    if topic_id is not None and focus_topic is None:
        raise APIError(404, "This recommendation topic was not found.")

    books = list(db.session.scalars(db.select(Book).where(Book.is_archived.is_(False))
                                   .options(selectinload(Book.topics)).order_by(Book.book_id)))
    books_by_id = {book.book_id: book for book in books}
    profile, interests, preferred_ids = _preference_profile(user, focus_topic, books_by_id)
    ranked = _rank_books(books, profile, interests, preferred_ids, _recent_reviews(), include_fallback=focus_topic is None)
    db.session.execute(
        db.delete(Recommendation).where(Recommendation.user_id == user.user_id, Recommendation.topic_id == topic_id)
    )

    generated_at = utcnow()
    recommendations = [
        Recommendation(
            user_id=user.user_id,
            book_id=book.book_id,
            topic_id=topic_id,
            score=score,
            model_type=MODEL_TYPE,
            generated_at=generated_at,
            reason=reason,
        )
        for book, score, reason in ranked[:limit]
    ]
    db.session.add_all(recommendations)
    db.session.flush()
    return recommendations
