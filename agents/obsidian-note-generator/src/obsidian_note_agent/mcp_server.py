"""Cross-client MCP server wrapping the Google ADK obsidian_note_agent.

Exposes 3 thin MCP tools over stdio (default) or Streamable HTTP:
- generate_note_from_url: delegates YouTube/article/docs URLs to the ADK agent
- generate_note_from_text: delegates pasted/paywalled text to the ADK agent
- list_recent_notes: fast read-only SQLite ledger lookup (zero LLM tokens)
"""

from __future__ import annotations

import argparse
import logging
import sys
import warnings
from pathlib import Path
from typing import Any

# Guard stdout for stdio JSON-RPC BEFORE importing urllib3/httpx/trafilatura/google-adk.
warnings.filterwarnings("ignore", message=".*SOCKS support in urllib3.*")
logging.basicConfig(
    stream=sys.stderr,
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from mcp.server.fastmcp import FastMCP  # noqa: E402

from obsidian_note_agent.config import has_gemini_auth, load_config, project_root  # noqa: E402
from obsidian_note_agent.runner import run_pasted_text_async, run_urls_async  # noqa: E402
from obsidian_note_agent.tools.ingest_tools import list_recent_notes_impl  # noqa: E402
from obsidian_note_agent.tools.vault_tools import ToolRuntimeContext  # noqa: E402

logger = logging.getLogger("obsidian_note_agent.mcp")


def _auth_missing_response() -> dict[str, Any]:
    env_hint = project_root() / ".env"
    return {
        "status": "error",
        "error": (
            "Gemini authentication is not configured. Set GOOGLE_API_KEY (or "
            "GOOGLE_GENAI_USE_VERTEXAI=TRUE + GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION) "
            f"in {env_hint} or the MCP server environment."
        ),
    }


def create_mcp_server(
    *,
    config_path: Path | None = None,
    env_file: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> FastMCP:
    """Create a FastMCP server exposing the 3 thin ADK delegation & history tools."""
    mcp = FastMCP(
        name="obsidian-note-generator",
        instructions=(
            "Delegates YouTube, technical article, and product documentation URLs (or pasted text) "
            "to the local Google ADK obsidian_note_agent, staging validated Mastery Framework notes "
            "or Update Drafts under obsidian-notes/staging/<Category>/."
        ),
        host=host,
        port=port,
    )

    @mcp.tool()
    async def generate_note_from_url(
        urls: list[str],
        force: bool = False,
        dry_run: bool = False,
        output_dir: str = "",
        model: str = "",
    ) -> dict[str, Any]:
        """Generate staged Obsidian note(s) or Update Draft(s) from one or more URLs via the ADK agent.

        Handles YouTube links, engineering blog/article URLs, and official technical/product
        documentation URLs. Automatically deduplicates via SQLite, checks existing production
        and staged notes for overlap (writing an Update Draft when overlapping), validates with
        validate_note.py, and writes strictly inside obsidian-notes/staging/<Category>/.

        Args:
            urls: One or more public HTTP/HTTPS URLs (YouTube, article, or documentation).
            force: Bypass SQLite deduplication and regenerate even if already processed.
            dry_run: Write to preview directory without updating SQLite history.
            output_dir: Optional override output directory (e.g., /tmp/obsidian-preview for dry runs).
            model: Optional Gemini model override (defaults to config.yaml agent.model).
        """
        load_config(config_path, env_file=env_file)
        if not has_gemini_auth():
            return _auth_missing_response()

        cleaned_urls = [u.strip() for u in urls if u and u.strip()]
        if not cleaned_urls:
            return {"status": "error", "error": "Provide at least one non-empty URL."}

        resolved_out = Path(output_dir).expanduser().resolve() if output_dir.strip() else None
        try:
            summary = await run_urls_async(
                cleaned_urls,
                config_path=config_path,
                env_file=env_file,
                dry_run=dry_run,
                output_dir=resolved_out,
                force=force,
                model=model.strip() or None,
                user_id="mcp-user",
            )
            return {
                "status": "ok",
                "urls": cleaned_urls,
                "dry_run": dry_run,
                "summary": summary,
            }
        except Exception as exc:
            logger.exception("generate_note_from_url failed")
            return {"status": "error", "urls": cleaned_urls, "error": str(exc)}

    @mcp.tool()
    async def generate_note_from_text(
        text: str,
        title: str,
        source_type: str = "article",
        url: str = "",
        force: bool = False,
        dry_run: bool = False,
        output_dir: str = "",
        model: str = "",
    ) -> dict[str, Any]:
        """Generate a staged Obsidian note or Update Draft from pasted text via the ADK agent.

        Use this for paywalled articles, local transcripts, or internal documentation that
        cannot be fetched over public HTTP.

        Args:
            text: Raw source text (transcript, article body, or documentation excerpt).
            title: Clean source title.
            source_type: One of 'youtube', 'article', or 'documentation'.
            url: Optional canonical source URL for frontmatter provenance.
            force: Bypass SQLite content-hash deduplication.
            dry_run: Write without updating SQLite history.
            output_dir: Optional override output directory.
            model: Optional Gemini model override.
        """
        load_config(config_path, env_file=env_file)
        if not has_gemini_auth():
            return _auth_missing_response()

        if not text.strip():
            return {"status": "error", "error": "Source text cannot be empty."}

        resolved_out = Path(output_dir).expanduser().resolve() if output_dir.strip() else None
        try:
            summary = await run_pasted_text_async(
                text=text,
                title=title,
                source_type=source_type,
                url=url,
                config_path=config_path,
                env_file=env_file,
                dry_run=dry_run,
                output_dir=resolved_out,
                force=force,
                model=model.strip() or None,
                user_id="mcp-user",
            )
            return {
                "status": "ok",
                "title": title,
                "source_type": source_type,
                "dry_run": dry_run,
                "summary": summary,
            }
        except Exception as exc:
            logger.exception("generate_note_from_text failed")
            return {"status": "error", "title": title, "error": str(exc)}

    @mcp.tool()
    def list_recent_notes(limit: int = 15) -> dict[str, Any]:
        """List recent staged Obsidian notes and Update Drafts from the SQLite ledger (zero LLM cost).

        Args:
            limit: Maximum number of recent runs to return (1-100).
        """
        config, _ = load_config(config_path, env_file=env_file)
        ctx = ToolRuntimeContext(config=config)
        return list_recent_notes_impl(ctx, limit=limit)

    return mcp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="obsidian-note-mcp",
        description="Cross-client MCP server wrapping the Google ADK obsidian_note_agent.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
        help="MCP transport mode (default: stdio for agy, Claude, Cursor, Codex).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host for streamable-http transport (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Bind port for streamable-http transport (default: 8765).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional explicit path to config.yaml.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional explicit path to .env file with Gemini/Vertex credentials.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    server = create_mcp_server(
        config_path=args.config,
        env_file=args.env_file,
        host=args.host,
        port=args.port,
    )
    server.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    sys.exit(main())
