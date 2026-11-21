import re
from contextlib import closing
from typing import Any

from app.db.database import get_connection, get_writable_connection


def ingest_document(source_name: str, document_type: str, content: str) -> int:
    if not isinstance(source_name, str) or not source_name.strip():
        raise ValueError("Source name is required")
    if not isinstance(document_type, str) or not document_type.strip():
        raise ValueError("Document type is required")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Document content is required")

    words = re.split(r"\n{2,}", content.strip())
    chunks: list[str] = []
    for paragraph in words:
        paragraph = " ".join(paragraph.split())
        if not paragraph:
            continue
        while len(paragraph) > 1200:
            chunks.append(paragraph[:1200])
            paragraph = paragraph[1200:]
        if paragraph:
            chunks.append(paragraph)

    with closing(get_writable_connection()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO rag_documents (source_name, document_type, content)
            VALUES (?, ?, ?)
            ON CONFLICT(source_name)
            DO UPDATE SET document_type=excluded.document_type,
                          content=excluded.content,
                          updated_at=CURRENT_TIMESTAMP
            """,
            (source_name.strip(), document_type.strip(), content.strip()),
        )
        document_id = int(
            connection.execute(
                "SELECT id FROM rag_documents WHERE source_name=?",
                (source_name.strip(),),
            ).fetchone()["id"]
        )
        connection.execute(
            "DELETE FROM rag_chunks WHERE document_id=?",
            (document_id,),
        )
        connection.executemany(
            """
            INSERT INTO rag_chunks (document_id, chunk_index, chunk_text)
            VALUES (?, ?, ?)
            """,
            [(document_id, index, chunk) for index, chunk in enumerate(chunks)],
        )
        connection.commit()
    return document_id


def retrieve_chunks(query: str, limit: int = 5) -> list[dict[str, Any]]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query is required")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("Limit must be a positive integer")
    terms = [term.casefold() for term in re.findall(r"[a-z0-9]+", query) if len(term) >= 3]
    if not terms:
        return []
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT d.source_name,d.document_type,c.chunk_text
            FROM rag_chunks c
            JOIN rag_documents d ON d.id=c.document_id
            """
        ).fetchall()
    ranked = []
    for row in rows:
        haystack = row["chunk_text"].casefold()
        score = sum(haystack.count(term) for term in set(terms))
        if score:
            ranked.append(
                {
                    "source_name": row["source_name"],
                    "document_type": row["document_type"],
                    "chunk_text": row["chunk_text"],
                    "score": score,
                }
            )
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:limit]
