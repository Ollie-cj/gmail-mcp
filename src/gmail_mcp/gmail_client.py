"""Gmail API client wrapper."""

import base64
import re
from email.mime.text import MIMEText
from typing import Any

from googleapiclient.discovery import build, Resource
from googleapiclient.http import BatchHttpRequest

from .auth import get_credentials


class GmailClient:
    """Wrapper for Gmail API operations."""

    def __init__(self):
        self._service: Resource | None = None

    @property
    def service(self) -> Resource:
        """Lazy-load Gmail API service."""
        if self._service is None:
            creds = get_credentials()
            self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def get_unread_emails(self, max_results: int = 10) -> list[dict[str, Any]]:
        """
        Fetch unread emails from inbox using batch requests for speed.

        Args:
            max_results: Maximum number of emails to return

        Returns:
            List of email dicts with id, thread_id, sender, subject, snippet, body, date
        """
        results = (
            self.service.users()
            .messages()
            .list(userId="me", q="is:unread", maxResults=max_results)
            .execute()
        )

        messages = results.get("messages", [])
        if not messages:
            return []

        # Use batch request to fetch all messages in one round-trip
        emails: list[dict[str, Any]] = []

        def handle_message(request_id: str, response: dict, exception: Exception | None):
            if exception is not None:
                return
            headers = {h["name"]: h["value"] for h in response["payload"]["headers"]}
            body = self._extract_body(response["payload"])
            emails.append(
                {
                    "id": response["id"],
                    "thread_id": response["threadId"],
                    "sender": headers.get("From", "Unknown"),
                    "subject": headers.get("Subject", "(No subject)"),
                    "snippet": response.get("snippet", ""),
                    "body": body,
                    "date": headers.get("Date", ""),
                }
            )

        batch: BatchHttpRequest = self.service.new_batch_http_request(callback=handle_message)
        for msg in messages:
            batch.add(
                self.service.users().messages().get(userId="me", id=msg["id"], format="full")
            )
        batch.execute()

        return emails

    def _extract_body(self, payload: dict) -> str:
        """Extract plain text body from email payload."""
        if "body" in payload and payload["body"].get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")

        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain" and part["body"].get("data"):
                    return base64.urlsafe_b64decode(part["body"]["data"]).decode(
                        "utf-8"
                    )
                if "parts" in part:
                    body = self._extract_body(part)
                    if body:
                        return body

        return ""

    def create_draft_reply(
        self,
        thread_id: str,
        message_id: str,
        reply_body: str,
    ) -> dict[str, Any]:
        """
        Create a draft reply to an email.

        Args:
            thread_id: Thread ID for proper threading
            message_id: Original message ID to reply to
            reply_body: The reply text content

        Returns:
            Draft metadata including draft_id, thread_id, to, subject
        """
        original = (
            self.service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["Subject", "From", "To", "Message-ID"],
            )
            .execute()
        )

        headers = {h["name"]: h["value"] for h in original["payload"]["headers"]}

        subject = headers.get("Subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        message = MIMEText(reply_body)
        message["To"] = headers.get("From", "")
        message["Subject"] = subject
        message["In-Reply-To"] = headers.get("Message-ID", "")
        message["References"] = headers.get("Message-ID", "")

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        draft = (
            self.service.users()
            .drafts()
            .create(
                userId="me",
                body={"message": {"raw": raw, "threadId": thread_id}},
            )
            .execute()
        )

        return {
            "draft_id": draft["id"],
            "thread_id": thread_id,
            "to": headers.get("From", ""),
            "subject": subject,
        }

    def find_unsubscribe_links(self, max_results: int = 200) -> list[dict[str, str]]:
        """
        Find unsubscribe links from recent emails.

        Looks for the List-Unsubscribe header in emails, which is the
        standard way newsletters provide unsubscribe links.

        Args:
            max_results: Maximum number of emails to scan (default 200)

        Returns:
            List of dicts with sender and unsubscribe_link, deduplicated by sender
        """
        results = (
            self.service.users()
            .messages()
            .list(userId="me", maxResults=max_results)
            .execute()
        )

        messages = results.get("messages", [])
        if not messages:
            return []

        # Use batch to fetch headers only (faster than full format)
        unsubscribe_data: dict[str, str] = {}  # sender -> link (deduped)

        def handle_message(request_id: str, response: dict, exception: Exception | None):
            if exception is not None:
                return
            headers = {h["name"]: h["value"] for h in response["payload"]["headers"]}

            list_unsubscribe = headers.get("List-Unsubscribe", "")
            if not list_unsubscribe:
                return

            # Extract HTTP URL from List-Unsubscribe header
            # Format: <https://...>, <mailto:...> or both
            http_match = re.search(r"<(https?://[^>]+)>", list_unsubscribe)
            if http_match:
                link = http_match.group(1)
                sender = headers.get("From", "Unknown")
                # Deduplicate by sender domain/name
                if sender not in unsubscribe_data:
                    unsubscribe_data[sender] = link

        # Gmail batch API has a limit of 100 requests per batch
        batch_size = 100
        for i in range(0, len(messages), batch_size):
            chunk = messages[i : i + batch_size]
            batch: BatchHttpRequest = self.service.new_batch_http_request(
                callback=handle_message
            )
            for msg in chunk:
                batch.add(
                    self.service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=msg["id"],
                        format="metadata",
                        metadataHeaders=["From", "List-Unsubscribe"],
                    )
                )
            batch.execute()

        # Convert to list format
        return [
            {"sender": sender, "unsubscribe_link": link}
            for sender, link in sorted(unsubscribe_data.items())
        ]


_client: GmailClient | None = None


def get_gmail_client() -> GmailClient:
    """Get or create Gmail client singleton."""
    global _client
    if _client is None:
        _client = GmailClient()
    return _client
