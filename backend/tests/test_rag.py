"""Unit tests that do not require a running LM Studio server."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest

from app.rag.ingest import LoadedDocument, chunk_document, split_text


class SplitTextTests(unittest.TestCase):
    def test_chunks_cover_text_with_overlap(self) -> None:
        chunks = split_text("alpha beta gamma delta epsilon zeta eta theta", 20, 6)
        self.assertGreater(len(chunks), 1)
        self.assertIn("alpha", chunks[0])
        self.assertIn("theta", chunks[-1])

    def test_rejects_bad_overlap(self) -> None:
        with self.assertRaises(ValueError):
            split_text("text", 10, 10)

    def test_empty_text_yields_no_chunks(self) -> None:
        self.assertEqual(split_text("   ", 100, 10), [])


class ChunkDocumentTests(unittest.TestCase):
    def test_preserves_page_metadata(self) -> None:
        doc = LoadedDocument(
            title="doc.pdf",
            kind="pdf",
            sections=[(1, "first page text here"), (2, "second page text here")],
        )
        chunks = chunk_document(doc, chunk_size=40, chunk_overlap=5)
        pages = {c.page for c in chunks}
        self.assertEqual(pages, {1, 2})
        self.assertEqual([c.chunk_index for c in chunks], list(range(len(chunks))))


if __name__ == "__main__":
    unittest.main()
