"""Copy-paste template for a custom Hermes memory provider plugin.

Drop this in $HERMES_HOME/plugins/<name>/__init__.py (keep plugin.yaml
alongside). Replace <backend> with your backend's name. This is the
generalized shape of the proven gbrain provider at
/root/.hermes/plugins/gbrain/ — a subprocess-shelling provider with
per-turn recall, memory-write mirroring, an on-demand tool, config
schema for `hermes memory setup`, and backup coverage.

Imports resolve against hermes-agent's own runtime — no pip installs.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)


class <Backend>Provider(MemoryProvider):
    """Memory provider that shells out to the <backend> CLI."""

    def __init__(self):
        # defaults; overridable via env or saved config
        self._bin: str = os.environ.get(
            "<BACKEND>_BIN", str(Path.home() / "<backend>"))
        self._dir: str = os.environ.get(
            "<BACKEND>_DIR", str(Path.home() / "<backend>"))
        self._limit: int = 5
        self._writable: bool = True  # flipped False in initialize() for non-primary contexts

    # ---------- MemoryProvider ABC ----------
    @property
    def name(self) -> str:
        return "<backend>"

    def is_available(self) -> bool:
        # Must be fast and side-effect-free: no network, no subprocess.
        return Path(self._bin).exists()

    def initialize(self, session_id: str, **kwargs) -> None:
        # Writability gate: only primary/flush contexts should write.
        agent_context = kwargs.get("agent_context", "primary")
        self._writable = agent_context in ("primary", "flush")
        # kwargs also carries hermes_home, platform, agent_identity, user_id...

    def system_prompt_block(self) -> str:
        return (
            f"You have access to the user's <backend> knowledge base. "
            "Before answering questions about the user or their projects, "
            "check <backend> FIRST via the automatic recall block or the "
            "<backend> tool. Store durable facts with the memory tool "
            "(writes are mirrored into <backend>)."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        q = (query or "").strip()
        if len(q) < 3:
            return ""
        out = self._run(["query", q, "--limit", str(self._limit)])
        if out is None:
            out = self._run(["search", q, "--limit", str(self._limit)])
        return self._format(out, q)

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        pass  # v1: synchronous prefetch is fine

    def sync_turn(self, user_content: str, assistant_content: str, *,
                  session_id: str = "",
                  messages: Optional[List[Dict[str, Any]]] = None) -> None:
        pass  # writes handled via on_memory_write

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [{
            "name": self.name,
            "description": f"Query or capture in the user's <backend> knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["query", "search", "salience", "capture"],
                        "description": "What to do",
                    },
                    "query": {"type": "string", "description": "Search text (query/search)"},
                    "content": {"type": "string", "description": "Note text (capture)"},
                    "limit": {"type": "integer", "description": "Max results"},
                },
                "required": ["action"],
            },
        }]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name != self.name:
            raise NotImplementedError(f"Provider {self.name} does not handle tool {tool_name}")
        action = args.get("action")
        if action in ("query", "search"):
            out = self._run([action, args.get("query", ""), "--limit", str(args.get("limit", self._limit))])
            if out is None:
                return '{"error": "<backend> command failed"}'
            return self._format_json(out)  # must be a JSON string
        elif action == "capture":
            out = self._run(["capture", args.get("content", ""), "--quiet", "--json"], timeout=30)
            if out is None:
                return '{"error": "<backend> capture failed"}'
            return out  # already JSON
        else:
            return f'{{"error": "unsupported action {action}"}}'

    def shutdown(self) -> None:
        pass

    def on_memory_write(self, action: str, target: str, content: str,
                        metadata: Optional[Dict[str, Any]] = None) -> None:
        # Mirror built-in memory tool writes into the backend.
        if not getattr(self, "_writable", True) or action in ("remove",):
            return
        self._run(["capture", f"[hermes:{target}] {content}", "--quiet", "--json"], timeout=30)

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        pass

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {"key": "<backend>_bin", "type": "text",
             "description": "Path to the <backend> binary", "default": self._bin},
            {"key": "recall_limit", "type": "integer",
             "description": "How many recall items to inject per turn",
             "default": self._limit, "minimum": 1, "maximum": 20},
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        # Non-secret config only; secrets belong in .env (env_var fields).
        cfg_dir = Path(hermes_home) / "plugins" / self.name
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.json").write_text(json.dumps(values, indent=2))

    def backup_paths(self) -> List[str]:
        # External state dirs that `hermes backup` must capture.
        return [self._dir]

    # ---------- helpers ----------
    def _run(self, args: list, stdin: str | None = None,
             timeout: float = 25.0) -> str | None:
        env = dict(os.environ)
        env["PATH"] = f"{Path(self._bin).parent}:" + env.get("PATH", "")
        try:
            p = subprocess.run([self._bin, *args], input=stdin,
                               capture_output=True, text=True,
                               timeout=timeout, env=env, cwd=self._dir)
        except Exception as e:
            logger.warning("<backend> %s error: %s", args[0], e)
            return None
        if p.returncode != 0:
            logger.warning("<backend> %s rc=%s: %s", args[0],
                           p.returncode, p.stderr.strip()[:300])
            return None
        return p.stdout

    def _format(self, raw: Optional[str], query: str) -> str:
        if not raw:
            return ""
        # Filter CLI noise (UPGRADE_AVAILABLE banners etc.) before parsing.
        lines = [ln.rstrip() for ln in raw.splitlines()
                 if ln.strip() and not ln.startswith("UPGRADE_AVAILABLE")]
        hits: list[tuple[float, str, str]] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("[") and "]" in line and "--" in line:
                try:
                    score_part, rest = line.split("]", 1)
                    score = float(score_part[1:])
                    if " -- " in rest:
                        slug_title, excerpt = rest.split(" -- ", 1)
                        i += 1
                        while i < len(lines) and lines[i] and not lines[i].startswith("["):
                            excerpt += " " + lines[i].strip()
                            i += 1
                        hits.append((score, slug_title.strip(), excerpt.strip()))
                        continue
                except ValueError:
                    pass
            i += 1
        if not hits:
            return ""
        hits.sort(key=lambda x: x[0], reverse=True)
        out_lines = [f"<BACKEND> RECALL (query: {query}):"]
        for _, slug, title in hits[: self._limit]:
            out_lines.append(f"- {slug}: {title[:600]}")
        return "\n".join(out_lines)

    def _format_json(self, raw: Optional[str]) -> str:
        if not raw:
            return '{"results": []}'
        return raw.strip()  # pass through if CLI already emits JSON


def register(ctx):
    """Plugin entry-point (preferred over a bare subclass)."""
    try:
        provider = <Backend>Provider()
        if provider.is_available():
            ctx.register_memory_provider(provider)
            logger.info("<backend> memory provider registered")
        else:
            logger.warning("<backend> memory provider not available (bin=%s)", provider._bin)
    except Exception as e:
        logger.exception("Failed to register <backend> provider: %s", e)