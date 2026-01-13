# Gmail MCP Server

An MCP (Model Context Protocol) server that allows AI assistants to read unread emails from Gmail and create draft replies.

## Overview

This server provides tools for AI assistants to manage Gmail:

### Core Tools

| Tool | Description |
|------|-------------|
| `get_unread_emails` | Fetch unread emails with sender, subject, body/snippet, and thread IDs |
| `create_draft_reply` | Create a properly threaded draft reply to an email |
| `get_style_guide` | Get email writing style guide for better replies |

### Writing Style Tools (RAG-based)

| Tool | Description |
|------|-------------|
| `sync_sent_emails` | Download and index sent emails for style matching |
| `get_writing_examples` | Find similar emails from your sent folder as style examples |

## Project Structure

```
gmail-mcp/
├── src/
│   └── gmail_mcp/
│       ├── __init__.py       # Package init
│       ├── server.py         # MCP server with tool definitions
│       ├── gmail_client.py   # Gmail API wrapper
│       ├── auth.py           # OAuth 2.0 authentication
│       └── corpus.py         # RAG email corpus with embeddings
├── examples/
│   └── style_guide.md        # Example style guide template
├── pyproject.toml            # Project config and dependencies
├── README.md                 # This file
├── .env.example              # Environment variables template
└── .gitignore
```

## Prerequisites

- Python 3.10+
- A Google Cloud project with Gmail API enabled
- OAuth 2.0 credentials (Desktop application type)

## Setup

### 1. Google Cloud Configuration

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Gmail API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API" and enable it
4. Configure OAuth consent screen:
   - Go to "APIs & Services" > "OAuth consent screen"
   - Choose "External" user type
   - Fill in app name, support email, and developer contact
   - Add scopes: `gmail.readonly`, `gmail.compose`
5. Create OAuth credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Application type: "Desktop app"
   - Download the JSON file

### 2. Install the Server

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/gmail-mcp.git
cd gmail-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .
```

### 3. Configure Credentials

```bash
# Create credentials directory
mkdir -p ~/.gmail-mcp

# Move your downloaded OAuth credentials
mv ~/Downloads/client_secret_*.json ~/.gmail-mcp/credentials.json
```

### 4. First Run (Authentication)

```bash
# Run the server once to complete OAuth flow
gmail-mcp
```

This will open a browser for you to authorize Gmail access. The token is saved to `~/.gmail-mcp/token.json`.

## Claude Desktop Configuration

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gmail": {
      "command": "gmail-mcp"
    }
  }
}
```

**Config file locations:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

## Example Usage

Once configured, you can ask Claude:

> "Check my unread emails and summarize them"

> "Draft a reply to the email from John about the project deadline"

> "Read my latest unread email and help me write a professional response"

> "Sync my sent emails so you can learn my writing style"

> "Find examples of how I usually write to colleagues, then draft a reply matching my style"

## Gmail API Scopes

This server requests the following OAuth scopes:

| Scope | Purpose |
|-------|---------|
| `gmail.readonly` | Read emails and metadata |
| `gmail.compose` | Create draft emails |

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## Security Notes

- OAuth credentials (`credentials.json`) and tokens (`token.json`) are stored in `~/.gmail-mcp/`
- Never commit credentials to git (they're in `.gitignore`)
- The server only creates **drafts**, never sends emails automatically
- Tokens can be revoked at [Google Account Permissions](https://myaccount.google.com/permissions)

## Style Guide

The `get_style_guide` tool reads from `~/.gmail-mcp/style_guide.md`. Copy the example to get started:

```bash
cp examples/style_guide.md ~/.gmail-mcp/style_guide.md
```

Edit the file to customize your email tone, templates, and preferences.

## Writing Style Matching (RAG)

The server includes a RAG (Retrieval Augmented Generation) system that learns from your sent emails:

### Setup

```bash
# In Claude Desktop, ask:
"Sync my sent emails for style matching"
```

This downloads and indexes your sent emails locally using:
- **ChromaDB** - Local vector database (`~/.gmail-mcp/corpus/`)
- **sentence-transformers** - Local embeddings (no API key needed)

### Usage

When drafting replies, Claude can find similar emails you've written:

> "Find examples of how I write to clients about project updates"

> "Show me emails similar to this topic so I can match my usual style"

The retrieved examples help Claude match your tone, vocabulary, and formatting.

## Roadmap

- [x] Project scaffold and documentation
- [x] OAuth 2.0 authentication flow
- [x] `get_unread_emails` tool
- [x] `create_draft_reply` tool
- [x] `get_style_guide` tool
- [x] RAG-based writing style matching
- [ ] Auto-generate style guide from corpus
- [ ] Claude Desktop integration demo

## License

MIT
