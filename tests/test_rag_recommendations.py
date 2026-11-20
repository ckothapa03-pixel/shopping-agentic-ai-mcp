import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.db.database as database
from app.rag.retrieval import ingest_document, retrieve_chunks
from app.shopping.recommendations import recommend_products


class RAGRecommendationTests(unittest.TestCase):
    def setUp(self) -> None:
        original_db_path = database.DB_PATH
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.addCleanup(setattr, database, "DB_PATH", original_db_path)
        self.db = Path(temporary_directory.name) / "shopping.db"
        connection = sqlite3.connect(self.db)
        connection.executescript(
            """
            CREATE TABLE rag_documents (
                id INTEGER PRIMARY KEY,
                source_name TEXT NOT NULL UNIQUE,
                document_type TEXT NOT NULL,
                content TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE rag_chunks (
                id INTEGER PRIMARY KEY,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                UNIQUE(document_id, chunk_index)
            );
            CREATE TABLE categories (id INTEGER PRIMARY KEY,name TEXT NOT NULL,slug TEXT NOT NULL);
            CREATE TABLE brands (id INTEGER PRIMARY KEY,name TEXT NOT NULL);
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,sku TEXT NOT NULL,name TEXT NOT NULL,
                description TEXT,category_id INTEGER NOT NULL,brand_id INTEGER NOT NULL,
                price REAL NOT NULL,mrp REAL NOT NULL,stock INTEGER NOT NULL,
                rating_avg REAL NOT NULL,rating_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            INSERT INTO categories VALUES (1,'Test','test');
            INSERT INTO brands VALUES (1,'Test Brand');
            INSERT INTO products VALUES
                (1,'S1','Test Product','Description',1,1,100,120,5,4.5,20,'2026-01-01');
            """
        )
        connection.commit()
        connection.close()
        database.DB_PATH = self.db
        self.patcher = patch("app.db.database.DB_PATH", self.db)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_rag_ingestion_retrieval_and_recommendation_are_grounded(self) -> None:
        ingest_document(
            "Return Policy",
            "policy",
            "Products may be returned within 30 days in original condition.",
        )
        chunks = retrieve_chunks("return policy 30 days")
        self.assertTrue(chunks)
        self.assertEqual(chunks[0]["source_name"], "Return Policy")
        recommendations = recommend_products(limit=1)
        self.assertEqual(recommendations[0]["id"], 1)

    def test_empty_or_invalid_queries_are_rejected_safely(self) -> None:
        with self.assertRaises(ValueError):
            retrieve_chunks("")
        with self.assertRaises(ValueError):
            ingest_document("", "policy", "content")


if __name__ == "__main__":
    unittest.main()
