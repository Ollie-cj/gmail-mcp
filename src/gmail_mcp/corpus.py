"""Email corpus management with embeddings and vector storage."""

from pathlib import Path
from typing import Any, Callable

import chromadb
from sentence_transformers import SentenceTransformer

from .gmail_client import get_gmail_client

# Default paths
CORPUS_DIR = Path.home() / ".gmail-mcp" / "corpus"

# Embedding model - runs locally, no API key needed
# all-MiniLM-L6-v2 is fast and good for semantic similarity
MODEL_NAME = "all-MiniLM-L6-v2"


class EmailCorpus:
    """Manages email embeddings and similarity search."""

    def __init__(self, corpus_dir: Path | None = None):
        self.corpus_dir = corpus_dir or CORPUS_DIR
        self.corpus_dir.mkdir(parents=True, exist_ok=True)

        self._model: SentenceTransformer | None = None
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load embedding model."""
        if self._model is None:
            self._model = SentenceTransformer(MODEL_NAME)
        return self._model

    @property
    def client(self) -> chromadb.ClientAPI:
        """Lazy-load ChromaDB persistent client."""
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=str(self.corpus_dir),
            )
        return self._client

    @property
    def collection(self) -> chromadb.Collection:
        """Get or create the sent emails collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name="sent_emails",
                metadata={"description": "User's sent emails for style matching"},
            )
        return self._collection

    def sync_sent_emails(
        self,
        max_emails: int = 1000,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, int]:
        """
        Download and embed sent emails into the corpus.

        Args:
            max_emails: Maximum number of emails to sync
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            Dict with sync statistics
        """
        gmail = get_gmail_client()

        all_emails: list[dict[str, Any]] = []
        page_token = None

        # Paginate through sent emails
        while len(all_emails) < max_emails:
            remaining = max_emails - len(all_emails)
            emails, page_token = gmail.get_sent_emails(
                max_results=min(remaining, 500),
                page_token=page_token,
            )

            if not emails:
                break

            all_emails.extend(emails)

            if progress_callback:
                progress_callback(len(all_emails), max_emails)

            if not page_token:
                break

        if not all_emails:
            return {"downloaded": 0, "embedded": 0, "skipped": 0}

        # Filter out emails already in corpus
        existing_ids = set(self.collection.get()["ids"])
        new_emails = [e for e in all_emails if e["id"] not in existing_ids]

        if not new_emails:
            return {
                "downloaded": len(all_emails),
                "embedded": 0,
                "skipped": len(all_emails),
            }

        # Prepare documents for embedding
        # Combine subject and body for richer semantic content
        documents = []
        metadatas = []
        ids = []

        for email in new_emails:
            # Skip empty emails
            if not email["body"].strip():
                continue

            doc = f"To: {email['to']}\nSubject: {email['subject']}\n\n{email['body']}"
            documents.append(doc)
            metadatas.append(
                {
                    "to": email["to"][:500],  # Truncate for storage
                    "subject": email["subject"][:500],
                    "date": email["date"],
                    "thread_id": email["thread_id"],
                }
            )
            ids.append(email["id"])

        if not documents:
            return {
                "downloaded": len(all_emails),
                "embedded": 0,
                "skipped": len(all_emails),
            }

        # Generate embeddings
        embeddings = self.model.encode(documents, show_progress_bar=True)

        # Store in ChromaDB
        self.collection.add(
            documents=documents,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
            ids=ids,
        )

        return {
            "downloaded": len(all_emails),
            "embedded": len(documents),
            "skipped": len(all_emails) - len(documents),
        }

    def find_similar_emails(
        self,
        query: str,
        n_results: int = 5,
        recipient_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Find emails similar to the query.

        Args:
            query: Text to find similar emails for (e.g., subject or context)
            n_results: Number of results to return
            recipient_filter: Optional recipient email/name to filter by

        Returns:
            List of similar emails with content and metadata
        """
        if self.collection.count() == 0:
            return []

        # Build query filters if needed
        where_filter = None
        if recipient_filter:
            where_filter = {"to": {"$contains": recipient_filter}}

        # Query the collection
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter,
        )

        # Format results
        emails = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else None

                emails.append(
                    {
                        "content": doc,
                        "to": metadata.get("to", "Unknown"),
                        "subject": metadata.get("subject", ""),
                        "date": metadata.get("date", ""),
                        "similarity": 1 - distance if distance else None,
                    }
                )

        return emails

    def get_corpus_stats(self) -> dict[str, Any]:
        """Get statistics about the corpus."""
        count = self.collection.count()
        return {
            "total_emails": count,
            "corpus_path": str(self.corpus_dir),
            "model": MODEL_NAME,
        }


# Singleton instance
_corpus: EmailCorpus | None = None


def get_corpus() -> EmailCorpus:
    """Get or create corpus singleton."""
    global _corpus
    if _corpus is None:
        _corpus = EmailCorpus()
    return _corpus
