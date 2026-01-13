"""Gmail MCP Server - Main entry point."""

import asyncio
import json
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .gmail_client import get_gmail_client
from .corpus import get_corpus

server = Server("gmail-mcp")

# Default path for style guide
DEFAULT_STYLE_GUIDE_PATH = Path.home() / ".gmail-mcp" / "style_guide.md"


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available Gmail tools."""
    return [
        Tool(
            name="get_unread_emails",
            description=(
                "Fetch unread emails from Gmail inbox. "
                "Returns sender, subject, body snippet, and IDs needed to reply."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of emails to return (default 10, max 50)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="create_draft_reply",
            description=(
                "Create a draft reply to an email. "
                "The draft will be properly threaded with the original conversation. "
                "Use the thread_id and id from get_unread_emails."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_id": {
                        "type": "string",
                        "description": "Thread ID of the email to reply to",
                    },
                    "message_id": {
                        "type": "string",
                        "description": "Message ID (the 'id' field) of the email to reply to",
                    },
                    "reply_body": {
                        "type": "string",
                        "description": "The text content of the reply",
                    },
                },
                "required": ["thread_id", "message_id", "reply_body"],
            },
        ),
        Tool(
            name="get_style_guide",
            description=(
                "Get the email writing style guide. "
                "Use this to understand preferred tone, templates, and formatting "
                "before drafting replies. Returns markdown content."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="find_unsubscribe_links",
            description=(
                "Find unsubscribe links from recent emails to help clean up inbox. "
                "Scans emails for List-Unsubscribe headers and returns unique "
                "sender/unsubscribe link pairs. Use this to help users unsubscribe "
                "from newsletters and mailing lists."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of emails to scan (default 200)",
                        "default": 200,
                        "minimum": 1,
                        "maximum": 500,
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="sync_sent_emails",
            description=(
                "Download and index sent emails for style matching. "
                "Run this once to build a corpus of your writing style, "
                "then use get_writing_examples to retrieve relevant examples. "
                "This may take a few minutes on first run."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "max_emails": {
                        "type": "integer",
                        "description": "Maximum number of sent emails to sync (default 500)",
                        "default": 500,
                        "minimum": 10,
                        "maximum": 2000,
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="get_writing_examples",
            description=(
                "Find similar emails from your sent folder to use as style examples. "
                "Use this before drafting replies to match your writing style. "
                "Provide context like recipient or topic to find relevant examples."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Context to search for (e.g., topic, recipient name, or situation)",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of examples to return (default 3)",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 10,
                    },
                    "recipient_filter": {
                        "type": "string",
                        "description": "Optional: filter by recipient email or name",
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    if name == "get_unread_emails":
        max_results = arguments.get("max_results", 10)
        max_results = max(1, min(50, max_results))

        client = get_gmail_client()
        emails = client.get_unread_emails(max_results=max_results)

        if not emails:
            return [TextContent(type="text", text="No unread emails found.")]

        return [TextContent(type="text", text=json.dumps(emails, indent=2))]

    elif name == "create_draft_reply":
        thread_id = arguments.get("thread_id")
        message_id = arguments.get("message_id")
        reply_body = arguments.get("reply_body")

        if not all([thread_id, message_id, reply_body]):
            return [
                TextContent(
                    type="text",
                    text="Error: thread_id, message_id, and reply_body are required.",
                )
            ]

        client = get_gmail_client()
        result = client.create_draft_reply(
            thread_id=thread_id,
            message_id=message_id,
            reply_body=reply_body,
        )

        return [
            TextContent(
                type="text",
                text=f"Draft created successfully!\n{json.dumps(result, indent=2)}",
            )
        ]

    elif name == "get_style_guide":
        if not DEFAULT_STYLE_GUIDE_PATH.exists():
            return [
                TextContent(
                    type="text",
                    text=(
                        f"No style guide found at {DEFAULT_STYLE_GUIDE_PATH}\n\n"
                        "Create a markdown file with your email writing preferences, "
                        "including tone, templates, and sign-off preferences."
                    ),
                )
            ]

        content = DEFAULT_STYLE_GUIDE_PATH.read_text()
        return [TextContent(type="text", text=content)]

    elif name == "find_unsubscribe_links":
        max_results = arguments.get("max_results", 200)
        max_results = max(1, min(500, max_results))

        client = get_gmail_client()
        results = client.find_unsubscribe_links(max_results=max_results)

        if not results:
            return [
                TextContent(
                    type="text",
                    text="No unsubscribe links found in recent emails.",
                )
            ]

        # Format as "Sender - unsubscribe link"
        lines = [f"{r['sender']} - {r['unsubscribe_link']}" for r in results]
        output = f"Found {len(results)} subscriptions:\n\n" + "\n".join(lines)

        return [TextContent(type="text", text=output)]

    elif name == "sync_sent_emails":
        max_emails = arguments.get("max_emails", 500)
        max_emails = max(10, min(2000, max_emails))

        corpus = get_corpus()
        stats = corpus.sync_sent_emails(max_emails=max_emails)

        return [
            TextContent(
                type="text",
                text=(
                    f"Sync complete!\n"
                    f"- Downloaded: {stats['downloaded']} emails\n"
                    f"- Embedded: {stats['embedded']} emails\n"
                    f"- Skipped (already indexed or empty): {stats['skipped']}"
                ),
            )
        ]

    elif name == "get_writing_examples":
        query = arguments.get("query", "")
        n_results = arguments.get("n_results", 3)
        recipient_filter = arguments.get("recipient_filter")

        if not query:
            return [
                TextContent(
                    type="text",
                    text="Error: query is required to find similar emails.",
                )
            ]

        corpus = get_corpus()

        # Check if corpus has data
        stats = corpus.get_corpus_stats()
        if stats["total_emails"] == 0:
            return [
                TextContent(
                    type="text",
                    text=(
                        "No emails in corpus yet. "
                        "Run sync_sent_emails first to index your sent emails."
                    ),
                )
            ]

        examples = corpus.find_similar_emails(
            query=query,
            n_results=n_results,
            recipient_filter=recipient_filter,
        )

        if not examples:
            return [
                TextContent(
                    type="text",
                    text="No similar emails found for the given query.",
                )
            ]

        # Format examples for context
        output_parts = [f"Found {len(examples)} similar emails from your sent folder:\n"]

        for i, ex in enumerate(examples, 1):
            similarity = f" (similarity: {ex['similarity']:.2f})" if ex['similarity'] else ""
            output_parts.append(f"--- Example {i}{similarity} ---")
            output_parts.append(f"To: {ex['to']}")
            output_parts.append(f"Subject: {ex['subject']}")
            output_parts.append(f"Date: {ex['date']}")
            output_parts.append(f"\n{ex['content']}\n")

        return [TextContent(type="text", text="\n".join(output_parts))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


def main():
    """Run the MCP server."""

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(run())


if __name__ == "__main__":
    main()
