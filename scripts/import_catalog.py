"""Import a frozen snapshot of edition records and preserve local stock."""

import json
import re
from pathlib import Path

from sqlalchemy.dialects.mysql import insert

from app import create_app
from app.extensions import db
from app.models import Book, Topic, book_topic


CATALOG = Path(__file__).with_name("verified_editions.json")
PROVENANCE = re.compile(r"https://openlibrary\.org/books/OL[0-9]+M")


def valid_isbn(isbn):
    return isinstance(isbn, str) and bool(re.fullmatch(r"97[89][0-9]{10}", isbn)) and (
        sum(int(digit) * (1, 3)[index % 2] for index, digit in enumerate(isbn)) % 10 == 0
    )


def load_editions(path=CATALOG):
    records = json.loads(path.read_text(encoding="utf-8"))
    seen = set()
    limits = {"title": 255, "author": 255, "publisher": 255, "edition": 255, "source_url": 1000, "category": 100}
    for record in records:
        isbn = record.get("isbn")
        if not valid_isbn(isbn) or isbn in seen:
            raise ValueError(f"Invalid or duplicate ISBN: {isbn}")
        for key, limit in limits.items():
            value = record.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError(f"Missing or invalid {key} for ISBN {isbn}")
        if not PROVENANCE.fullmatch(record["source_url"]):
            raise ValueError(f"Invalid edition source for ISBN {isbn}")
        cover = record.get("cover_url")
        if cover and not re.fullmatch(r"https://covers\.openlibrary\.org/b/id/[0-9]+-M\.jpg\?default=false", cover):
            raise ValueError(f"Invalid cover source for ISBN {isbn}")
        seen.add(isbn)
    return records


def words(value):
    return set(re.findall(r"[a-z0-9]+", value.lower())) - {
        "and", "for", "the", "an", "to", "in", "with", "using", "fundamentals", "introduction", "project",
    }


def import_editions(records):
    metadata = ("title", "author", "publisher", "edition", "source_url", "category", "cover_url")
    rows = []
    for record in records:
        tags = record.get("keywords", [])
        details = f" Open Library subjects include {', '.join(tags[:8])}." if tags else ""
        rows.append({
            "isbn": record["isbn"], **{key: record.get(key) for key in metadata},
            "description": f"A published resource in {record['category']}.{details}",
            "is_archived": False, "total_copies": 0, "available_copies": 0,
        })
    upsert = insert(Book.__table__).values(rows)
    db.session.execute(upsert.on_duplicate_key_update(
        **{key: upsert.inserted[key] for key in (*metadata, "description")},
    ))
    ids = dict(db.session.execute(db.select(Book.isbn, Book.book_id).where(
        Book.isbn.in_([record["isbn"] for record in records]),
    )).all())
    topics = list(db.session.scalars(db.select(Topic)))
    links = []
    for record in records:
        tags = words(" ".join([record["title"], *record.get("keywords", [])]))
        explicit = set(record.get("topics", []))
        for topic in topics:
            terms = words(topic.name)
            if topic.name in explicit or (terms and terms <= tags):
                links.append({"book_id": ids[record["isbn"]], "topic_id": topic.topic_id,
                              "is_featured": topic.name in explicit})
    if links:
        mapping = insert(book_topic).values(links)
        db.session.execute(mapping.on_duplicate_key_update(
            is_featured=db.func.greatest(book_topic.c.is_featured, mapping.inserted.is_featured),
        ))
    return len(rows)


def main():
    with create_app().app_context():
        count = import_editions(load_editions())
        db.session.commit()
        print(f"Imported {count} verified editions. Existing stock was preserved.")


if __name__ == "__main__":
    main()
