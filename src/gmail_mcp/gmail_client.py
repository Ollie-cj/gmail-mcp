"""Gmail API client wrapper."""

import base64
from email.mime.text import MIMEText
from typing import Any

from googleapiclient.discovery import build, Resource

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
        Fetch unread emails from inbox.

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
        emails = []

        for msg in messages:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=msg["id"], format="full")
                .execute()
            )

            headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}
            body = self._extract_body(message["payload"])

            emails.append(
                {
                    "id": message["id"],
                    "thread_id": message["threadId"],
                    "sender": headers.get("From", "Unknown"),
                    "subject": headers.get("Subject", "(No subject)"),
                    "snippet": message.get("snippet", ""),
                    "body": body,
                    "date": headers.get("Date", ""),
                }
            )

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


_client: GmailClient | None = None


def get_gmail_client() -> GmailClient:
    """Get or create Gmail client singleton."""
    global _client
    if _client is None:
        _client = GmailClient()
    return _client
