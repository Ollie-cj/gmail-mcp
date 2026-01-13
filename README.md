# Gmail MCP Server

An MCP (Model Context Protocol) server that allows AI assistants to read unread emails from Gmail and create draft replies.

## Overview

This server provides two core tools for AI assistants:

| Tool | Description |
|------|-------------|
| `get_unread_emails` | Fetch unread emails with sender, subject, body/snippet, and thread IDs |
| `create_draft_reply` | Create a properly threaded draft reply to an email |

**Stretch Goal:** A `get_style_guide` tool that pulls external context (style guides, templates) to help the AI write better replies.

## Project Structure

```
gmail-mcp/
├── src/
│   └── gmail_mcp/
│       ├── __init__.py       # Package init
│       ├── server.py         # MCP server with tool definitions
│       ├── gmail_client.py   # Gmail API wrapper
│       └── auth.py           # OAuth 2.0 authentication
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

## Roadmap

- [x] Project scaffold and documentation
- [ ] OAuth 2.0 authentication flow
- [ ] `get_unread_emails` tool
- [ ] `create_draft_reply` tool
- [ ] `get_style_guide` tool (stretch goal)
- [ ] Claude Desktop integration demo
- [ ] Screenshots and example prompts

## License

MIT
