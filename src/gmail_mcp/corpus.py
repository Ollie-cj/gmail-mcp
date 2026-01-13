"""Email corpus management with embeddings and vector storage."""

import re
from collections import Counter
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

    def analyze_writing_style(self, sample_size: int = 50) -> dict[str, Any]:
        """
        Analyze writing patterns from the corpus to generate a style guide.

        Args:
            sample_size: Number of emails to analyze

        Returns:
            Dict containing style analysis and representative samples
        """
        if self.collection.count() == 0:
            return {"error": "No emails in corpus. Run sync_sent_emails first."}

        # Get a sample of emails from the corpus
        results = self.collection.get(
            limit=min(sample_size, self.collection.count()),
            include=["documents", "metadatas"],
        )

        documents = results.get("documents", [])
        if not documents:
            return {"error": "No documents found in corpus."}

        # Extract just the body text (after the headers)
        bodies = []
        for doc in documents:
            # Split off headers (To:, Subject:) to get body
            parts = doc.split("\n\n", 1)
            if len(parts) > 1:
                bodies.append(parts[1])
            else:
                bodies.append(doc)

        # Analyze greetings (first line patterns)
        greetings = []
        for body in bodies:
            first_line = body.strip().split("\n")[0] if body.strip() else ""
            # Common greeting patterns
            if any(
                first_line.lower().startswith(g)
                for g in ["hi ", "hey ", "hello ", "dear ", "good ", "morning", "afternoon", "evening"]
            ):
                greetings.append(first_line.split(",")[0] if "," in first_line else first_line)

        # Analyze sign-offs (last few lines)
        sign_offs = []
        sign_off_patterns = [
            "best", "thanks", "thank you", "regards", "cheers",
            "kind regards", "best regards", "many thanks", "sincerely",
            "yours", "warm regards", "take care"
        ]
        for body in bodies:
            lines = [l.strip() for l in body.strip().split("\n") if l.strip()]
            for line in lines[-5:]:  # Check last 5 lines
                line_lower = line.lower().rstrip(",.")
                if any(line_lower.startswith(p) or line_lower == p for p in sign_off_patterns):
                    sign_offs.append(line.rstrip(",."))
                    break

        # Calculate sentence statistics
        all_sentences = []
        for body in bodies:
            sentences = re.split(r'[.!?]+', body)
            all_sentences.extend([s.strip() for s in sentences if s.strip() and len(s.strip()) > 10])

        avg_sentence_length = (
            sum(len(s.split()) for s in all_sentences) / len(all_sentences)
            if all_sentences else 0
        )

        # Find common phrases (2-4 word patterns)
        all_text = " ".join(bodies).lower()
        words = re.findall(r'\b[a-z]+\b', all_text)

        # Bigrams and trigrams
        bigrams = [" ".join(words[i:i+2]) for i in range(len(words)-1)]
        trigrams = [" ".join(words[i:i+3]) for i in range(len(words)-2)]

        # Filter out very common/boring phrases
        boring = {"i am", "it is", "this is", "that is", "we are", "you are", "i have", "to the", "in the", "of the", "and the", "for the"}
        common_bigrams = [p for p, c in Counter(bigrams).most_common(30) if p not in boring and c > 2][:10]
        common_trigrams = [p for p, c in Counter(trigrams).most_common(30) if c > 2][:10]

        # Get diverse sample emails for context
        sample_emails = []
        # Sample different types: short, medium, long
        sorted_by_length = sorted(enumerate(bodies), key=lambda x: len(x[1]))
        indices = [
            sorted_by_length[0][0],  # Shortest
            sorted_by_length[len(sorted_by_length)//2][0],  # Medium
            sorted_by_length[-1][0],  # Longest
        ]
        # Add a couple more random ones
        import random
        remaining = [i for i in range(len(bodies)) if i not in indices]
        if remaining:
            indices.extend(random.sample(remaining, min(2, len(remaining))))

        for idx in indices[:5]:
            meta = results["metadatas"][idx] if results.get("metadatas") else {}
            sample_emails.append({
                "to": meta.get("to", "Unknown")[:100],
                "subject": meta.get("subject", "")[:100],
                "body": bodies[idx][:1000],  # Truncate long bodies
            })

        return {
            "emails_analyzed": len(documents),
            "greetings": Counter(greetings).most_common(10),
            "sign_offs": Counter(sign_offs).most_common(10),
            "avg_sentence_length_words": round(avg_sentence_length, 1),
            "total_sentences_analyzed": len(all_sentences),
            "common_phrases": {
                "two_word": common_bigrams,
                "three_word": common_trigrams,
            },
            "sample_emails": sample_emails,
        }


# Singleton instance
_corpus: EmailCorpus | None = None


def get_corpus() -> EmailCorpus:
    """Get or create corpus singleton."""
    global _corpus
    if _corpus is None:
        _corpus = EmailCorpus()
    return _corpus
